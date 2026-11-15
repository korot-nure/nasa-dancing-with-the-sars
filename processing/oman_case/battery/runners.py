"""Orchestration of the battery for the notebook: every run_* function computes one method
(or group) on all relevant scenes and returns tables; plot_* functions make the figures.
Heavy intermediate tables are written to results/ so the notebook output can be inspected
without rerunning.
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import ndimage

from . import ancillary as A
from . import config as C
from . import context as X
from . import detect as M
from . import evaluate as E
from . import ml as ML
from . import objects as O
from .data import TO_LL, db, grid, land_raw, load_scene, meshgrid, smooth, source_linked

CONTROL = {"island_hh": "HH_0624", "island_vv": "VV_0618", "128A": "CA_0717", "049D": "CD_0723"}
MIN_WIND_SENSITIVITY = 0.2     # GMF coefficient b (dB per dB of wind); below it SAR wind is not invertible
TRACK_GROUPS = {          # scenes sharing geometry (same track, same AOI)
    "HH 150D": [s["id"] for s in C.SCENES if s["aoi"] == "island_hh"],
    "VV 056A": [s["id"] for s in C.SCENES if s["aoi"] == "island_vv"],
    "coast 128A": [s["id"] for s in C.SCENES if s["aoi"] == "coast" and s["track"] == "128A"],
    "coast 049D": [s["id"] for s in C.SCENES if s["aoi"] == "coast" and s["track"] == "049D"],
}


def control_of(sid):
    s = C.scene(sid)
    return CONTROL.get(s["aoi"]) or CONTROL[s["track"]]


def group_of(sid):
    return next(g for g, ids in TRACK_GROUPS.items() if sid in ids)


def save(df, name):
    C.RESULTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(C.RESULTS / f"{name}.csv", index=False)
    return df


# ---------------------------------------------------------------- ancillary on the grid
def era5_on_grid(sid):
    sc = load_scene(sid)
    XX, YY = meshgrid(sc["meta"]["aoi"])
    e = A.era5(sid)
    out = {k: A.to_grid(e["lon"], e["lat"], e[k], XX, YY, fill_nan_nearest=True) for k in ("wspd", "u10", "v10", "precip_mm")}
    return out


def sst_on_grid(sid):
    sc = load_scene(sid)
    XX, YY = meshgrid(sc["meta"]["aoi"])
    s = A.sst(sid)
    return A.to_grid(s["lon"], s["lat"], s["sst_c"], XX, YY)


def chl_on_grid(sid):
    sc = load_scene(sid)
    XX, YY = meshgrid(sc["meta"]["aoi"])
    c = A.chl(sid)
    return A.to_grid(c["lon"], c["lat"], c["chl_mg_m3"], XX, YY)


def wind_at_source(sid):
    e = A.era5(sid)
    lon, lat = C.SOURCE_LONLAT
    i, j = np.argmin(abs(e["lat"] - lat)), np.argmin(abs(e["lon"] - lon))
    return float(e["u10"][i, j]), float(e["v10"][i, j]), float(e["wdir_from_deg"][i, j]), float(e["wspd"][i, j])


# ---------------------------------------------------------------- M4 / M5 (wind model)
def _gmf_training(sid, step=8):
    sc = load_scene(sid)
    _, r = O.candidates(sid)
    excl = ndimage.binary_dilation(r["mask"], iterations=max(1, int(1000 / sc["meta"]["res"])))
    far_coast = ndimage.distance_transform_edt(~land_raw(sc["meta"]["aoi"])) * sc["meta"]["res"] >= 5000
    u = era5_on_grid(sid)["wspd"]
    return M.clean_sea_samples(sc, u, excl | ~far_coast, step=step)


def run_m4_m5(thr_db=1.0):
    """GMF fitted per track leave-one-scene-out, M4 detection on the held-out scene,
    M5 SAR wind vs ERA5."""
    samples = {sid: _gmf_training(sid) for g in TRACK_GROUPS.values() for sid in g}
    rows_eval, fits, wind_rows, masks = [], [], [], {}
    for g, ids in TRACK_GROUPS.items():
        allfit = M.fit_wind_gmf({k: np.concatenate([samples[s][k] for s in ids]) for k in ("inc", "u10", "s0_db")})
        fits.append(dict(group=g, **{f"coef_{n}": v for n, v in zip(["a0", "a1", "a2", "b"], allfit["coef"])},
                         rmse_db=allfit["rmse_db"], r2=allfit["r2"], n=allfit["n"],
                         u_min=allfit["u_range"][0], u_max=allfit["u_range"][1]))
        for sid in ids:
            others = [s for s in ids if s != sid]
            fit = M.fit_wind_gmf({k: np.concatenate([samples[s][k] for s in others]) for k in ("inc", "u10", "s0_db")})
            sc = load_scene(sid)
            u = era5_on_grid(sid)["wspd"]
            r = M.m4_damping(sc, u, fit["coef"], thr=thr_db)
            base = M.m2_contrast(sc)
            masks[sid] = r
            rows_eval.append(E.scene_metrics("M4 damping vs wind model", sid, r, base["mask"]))
            if fit["coef"][3] < MIN_WIND_SENSITIVITY:
                wind_rows.append(dict(scene=sid, group=g, era5_median=float(np.nanmedian(u[sc["sea"]])),
                                      sar_median=np.nan, bias=np.nan, rmse=np.nan, low_wind_km2=np.nan, sar_p05=np.nan,
                                      note=f"GMF not invertible (b={fit['coef'][3]:.2f})"))
                continue
            w = M.m5_sar_wind(sc, fit["coef"])
            ok = sc["sea"] & np.isfinite(w["u_ambient"]) & np.isfinite(u)
            d = (w["u_ambient"] - u)[ok][::25]
            wind_rows.append(dict(scene=sid, group=g, era5_median=float(np.median(u[ok])),
                                  sar_median=float(np.median(w["u_ambient"][ok])), bias=float(np.median(d)),
                                  rmse=float(np.sqrt(np.mean(d ** 2))), low_wind_km2=float(w["low_wind"].sum() * (sc["meta"]["res"] / 1000) ** 2),
                                  sar_p05=float(np.percentile(w["u_ambient"][ok], 5)), note=""))
    return pd.DataFrame(rows_eval), pd.DataFrame(fits), pd.DataFrame(wind_rows), masks


def sar_wind_grid(sid, coef):
    return M.m5_sar_wind(load_scene(sid), coef)["u_ambient"]


# ---------------------------------------------------------------- pixel detectors (M1-M3, M9, M13, M19)
def run_pixel_methods():
    rows = []
    for s in C.SCENES:
        sid = s["id"]
        sc = load_scene(sid)
        base = M.m2_contrast(sc)
        rows.append(E.scene_metrics("M2 local contrast", sid, base, base["mask"]))
        rows.append(E.scene_metrics("M1 incidence norm + global thr", sid, M.m1_incidence_normalised(sc), base["mask"]))
        rows.append(E.scene_metrics("M3 CFAR (gamma model)", sid, M.m3_cfar(sc), base["mask"]))
        rows.append(E.scene_metrics("M3 CFAR (calibrated on control)", sid,
                                    M.m3_cfar_calibrated(sc, load_scene(control_of(sid))), base["mask"]))
        rows.append(E.scene_metrics("M13 temporal reference", sid, M.m13_temporal(sid, TRACK_GROUPS[group_of(sid)]), base["mask"]))
        rows.append(E.scene_metrics("M19 thin dark lines (valley filter)", sid, X.m19_line_mask(sid, control_of(sid)), base["mask"]))
        if "g0_hv" in sc:
            rows.append(E.scene_metrics("M9 HV only", sid, M.m9_crosspol(sc), base["mask"]))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- objects + features (M5-M7, M9, M20)
def run_objects(gmf_fits):
    coefs = {r.group: [r.coef_a0, r.coef_a1, r.coef_a2, r.coef_b] for r in gmf_fits.itertuples()}
    dfs = []
    for s in C.SCENES:
        sid = s["id"]
        e = era5_on_grid(sid)
        _, _, wdir, _ = wind_at_source(sid) if s["aoi"].startswith("island") else (0, 0, float(np.nanmedian(A.era5(sid)["wdir_from_deg"])), 0)
        anc = {"sst": sst_on_grid(sid), "chl": chl_on_grid(sid), "precip": e["precip_mm"]}
        coef = coefs[group_of(sid)]
        sw = sar_wind_grid(sid, coef) if coef[3] >= MIN_WIND_SENSITIVITY else None
        df, _ = O.object_table(sid, wind_from_deg=wdir, u10_grid=e["wspd"], sar_wind=sw, anc=anc)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


# ---------------------------------------------------------------- M14 / M15
def run_m14():
    origins, freq = [], {}
    for g in ("HH 150D", "VV 056A"):
        ids = TRACK_GROUPS[g]
        masks = {}
        for sid in ids:
            r = M.m2_contrast(load_scene(sid))
            masks[sid] = r["mask"]
            _, _, wdir, _ = wind_at_source(sid)
            origins.append(X.upwind_origins(sid, r["labels"], wdir))
        freq[g] = X.m14_recurrence(ids, masks)
    clusters, ori = X.m14_source_finding(pd.concat(origins, ignore_index=True))
    return clusters, ori, freq


def run_m15():
    rows = []
    for s in C.ISLAND_SCENES:
        if s["role"] != "event":
            continue
        sid = s["id"]
        r = M.m2_contrast(load_scene(sid))
        src = source_linked(r["labels"], s["aoi"])
        if src.sum() == 0:
            continue
        u, v, wdir, wspd = wind_at_source(sid)
        cur = A.currents(sid)
        cu = cv = 0.0
        if cur is not None:
            lon, lat = C.SOURCE_LONLAT
            i, j = np.argmin(abs(cur["lat"] - lat)), np.argmin(abs(cur["lon"] - lon))
            win = (slice(max(i - 1, 0), i + 2), slice(max(j - 1, 0), j + 2))
            cu, cv = float(np.nanmean(cur["u"][win])), float(np.nanmean(cur["v"][win]))
        o = X.m15_orientation(sid, src, wdir, current_uv=((u, v), (cu, cv)))
        o.update(wind_ms=wspd, current_ms=float(np.hypot(cu, cv)), slick_km2=float(src.sum() * (load_scene(sid)["meta"]["res"] / 1000) ** 2))
        rows.append(o)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- M18 / M21
def run_m18():
    tabs = {}
    for s in C.SCENES:
        t, _ = X.m18_bright_targets(s["id"], channel="g0")
        tabs[s["id"]] = t
    cl = X.m18_classify(tabs)
    summary = cl.groupby(["scene", "cls"]).size().unstack(fill_value=0)
    return cl, summary


def run_m21():
    pairs = [("CA_0717", "CA_0810"), ("CA_0717", "CA_0822"), ("CA_0717", "CA_0903"),
             ("CD_0723", "CD_0816"), ("CD_0723", "CD_0828")]
    return pd.concat([X.m21_coast_change(a, b) for a, b in pairs], ignore_index=True)


# ---------------------------------------------------------------- plotting
def plot_masks(method_fn, scene_ids, title, ncol=4, vmin_pct=2, vmax_pct=98, path=None):
    n = len(scene_ids)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.4 * ncol, 4.0 * nrow), dpi=90, squeeze=False)
    for ax, sid in zip(axes.flat, scene_ids):
        sc = load_scene(sid)
        xs, ys, res = grid(sc["meta"]["aoi"])
        ext = [xs[0] / 1e3, xs[-1] / 1e3, ys[-1] / 1e3, ys[0] / 1e3]
        g = db(smooth(np.where(sc["sea"], sc["g0"], np.nan), 3))
        ax.imshow(g, extent=ext, cmap="gray", vmin=np.nanpercentile(g, vmin_pct), vmax=np.nanpercentile(g, vmax_pct))
        r = method_fn(sid)
        ov = np.zeros(r["mask"].shape + (4,))
        ov[r["mask"]] = [1, 0.2, 0.1, 0.6]
        if sc["meta"]["aoi"].startswith("island"):
            ov[source_linked(ndimage.label(r["mask"])[0], sc["meta"]["aoi"])] = [1, 0, 0, 0.85]
        ax.imshow(ov, extent=ext)
        ax.contour(*np.meshgrid(xs / 1e3, ys / 1e3), land_raw(sc["meta"]["aoi"]).astype(float), levels=[0.5], colors="cyan", linewidths=0.4)
        km2 = r["mask"].sum() * (res / 1000) ** 2
        ax.set_title(f"{sid} ({sc['meta']['role']}): {km2:.0f} km²", fontsize=9)
        ax.tick_params(labelsize=6)
    for ax in axes.flat[n:]:
        ax.axis("off")
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    if path:
        fig.savefig(path, facecolor="white")
    return fig


def plot_map(arrays, scene_ids, title, cmap="RdBu_r", vmin=None, vmax=None, label="", ncol=4, path=None):
    n = len(scene_ids)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.4 * ncol, 4.0 * nrow), dpi=90, squeeze=False)
    for ax, sid, a in zip(axes.flat, scene_ids, arrays):
        sc = load_scene(sid)
        xs, ys, _ = grid(sc["meta"]["aoi"])
        ext = [xs[0] / 1e3, xs[-1] / 1e3, ys[-1] / 1e3, ys[0] / 1e3]
        im = ax.imshow(a, extent=ext, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(sid, fontsize=9)
        ax.tick_params(labelsize=6)
        plt.colorbar(im, ax=ax, shrink=0.7, label=label)
    for ax in axes.flat[n:]:
        ax.axis("off")
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    if path:
        fig.savefig(path, facecolor="white")
    return fig
