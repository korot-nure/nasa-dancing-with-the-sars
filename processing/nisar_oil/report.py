"""Outputs of a pipeline run: tables, GeoJSON, figures and a Markdown report (Russian)."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CLASS_COLOR = {"probable": "#e31a1c", "possible": "#ff9f1c", "background": "#9ecae1"}


def _geojson_polys(objs):
    feats = []
    # to_dict, not itertuples: itertuples renames the column 'class' (a Python keyword) to '_<n>'
    for r in objs.to_dict("records"):
        if not r["outline"]:
            continue
        props = {k: (None if (isinstance(v, float) and not np.isfinite(v)) else (v.item() if hasattr(v, "item") else v))
                 for k, v in r.items() if k not in ("outline", "x", "y", "origin_x", "origin_y")}
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [r["outline"]]}, "properties": props})
    return {"type": "FeatureCollection", "features": feats}


def _geojson_points(df, keys):
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
              "properties": {k: (r[k].item() if hasattr(r[k], "item") else r[k]) for k in keys if k in r}}
             for _, r in df.iterrows()]
    return {"type": "FeatureCollection", "features": feats}


def write_tables(region, acq_ev, objs, src, targets, calib):
    out = region.out
    out.mkdir(parents=True, exist_ok=True)
    acq_ev.to_csv(out / "acquisitions.csv", index=False)
    objs.drop(columns=["outline"]).to_csv(out / "objects.csv", index=False)
    (out / "objects.geojson").write_text(json.dumps(_geojson_polys(objs[objs["class"] != "background"])))
    if len(src):
        src.to_csv(out / "sources.csv", index=False)
        (out / "sources.geojson").write_text(json.dumps(_geojson_points(src, [c for c in src.columns if c not in ("x", "y")])))
    if len(targets):
        targets.to_csv(out / "bright_targets.csv", index=False)
        pers = targets[targets.cls == "offshore_persistent"].drop_duplicates(subset=["lon", "lat"])
        (out / "persistent_targets.geojson").write_text(json.dumps(_geojson_points(pers, ["date", "snr_db"])))
    (out / "calibration.json").write_text(json.dumps(calib, indent=1, default=str))


def fig_overview(region, acq_ev, objs, src, group, maps_dir, path, ncol=4):
    g = acq_ev[acq_ev.group == group].sort_values("time")
    n = len(g)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.6 * ncol, 4.2 * nrow), dpi=85, squeeze=False)
    ext = region.extent_km()
    for ax, r in zip(axes.flat, g.itertuples()):
        m = np.load(maps_dir / f"{r.acq_id}.npz")
        bg = m["g0_db"].astype(float)
        ax.imshow(bg, extent=ext, cmap="gray", vmin=np.nanpercentile(bg, 2), vmax=np.nanpercentile(bg, 98))
        lab = m["labels"]
        o = objs[objs.acq_id == r.acq_id]
        ov = np.zeros(lab.shape + (4,))
        for cls, col in CLASS_COLOR.items():
            ids = o[o["class"] == cls].obj.values
            if len(ids):
                rgb = matplotlib.colors.to_rgb(col)
                ov[np.isin(lab, ids)] = (*rgb, 0.75 if cls != "background" else 0.35)
        ax.imshow(ov, extent=ext)
        ax.contour(*np.meshgrid(region.grid[0] / 1e3, region.grid[1] / 1e3), region.land.astype(float), levels=[0.5], colors="cyan", linewidths=0.4)
        if len(src):
            ax.plot(src.x / 1e3, src.y / 1e3, "y*", ms=11, mec="k")
        if region.known_source:
            kx, ky = region.lonlat_to_xy(*region.known_source)
            ax.plot(kx / 1e3, ky / 1e3, "c+", ms=12, mew=2)
        flag = "  ⚑ event" if r.event_flag else ""
        ax.set_title(f"{r.acq_id} {r.main_pol}: probable {r.probable_km2:.0f} km²{flag}", fontsize=8)
        ax.tick_params(labelsize=6)
    for ax in axes.flat[n:]:
        ax.axis("off")
    fig.suptitle(f"{region.name}, track {group}: red = probable oil, orange = possible, blue = background; ★ = detected sources"
                 + (", + = known source" if region.known_source else ""), fontsize=10)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def fig_sources(region, acq_ev, objs, src, targets, maps_dir, path):
    freq = np.zeros(region.shape, np.float32)
    cnt = np.zeros(region.shape, np.float32)
    for r in acq_ev.itertuples():
        m = np.load(maps_dir / f"{r.acq_id}.npz")
        ids = objs[(objs.acq_id == r.acq_id) & objs["class"].isin(["probable", "possible"])].obj.values
        freq += np.isin(m["labels"], ids)
        cnt += m["sea"]
    with np.errstate(invalid="ignore"):
        f = np.where(cnt > 0, freq / cnt, np.nan)
    fig, ax = plt.subplots(figsize=(10, 8.5), dpi=100)
    ext = region.extent_km()
    im = ax.imshow(f, extent=ext, cmap="magma", vmin=0, vmax=max(0.15, np.nanpercentile(f, 99.9)))
    plt.colorbar(im, ax=ax, shrink=0.7, label="share of dates with a probable/possible slick")
    ax.contour(*np.meshgrid(region.grid[0] / 1e3, region.grid[1] / 1e3), region.land.astype(float), levels=[0.5], colors="cyan", linewidths=0.6)
    if len(targets):
        p = targets[targets.cls == "offshore_persistent"]
        ax.plot(p.x / 1e3, p.y / 1e3, "s", ms=3, color="#7fff00", alpha=0.6, label="recurring bright targets (structures/anchorages)")
    if len(src):
        ax.plot(src.x / 1e3, src.y / 1e3, "y*", ms=16, mec="k", label="detected sources")
        for r in src.itertuples():
            ax.annotate(f"#{r.rank} ({r.n_dates} dates)", (r.x / 1e3, r.y / 1e3), color="yellow", fontsize=8, xytext=(5, 5), textcoords="offset points")
    if region.known_source:
        kx, ky = region.lonlat_to_xy(*region.known_source)
        ax.plot(kx / 1e3, ky / 1e3, "c+", ms=16, mew=2, label="known source (validation only)")
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title(f"{region.name}: slick recurrence, sources (M14) and bright targets (M18)")
    ax.set_xlabel(f"UTM x, km (EPSG:{region.epsg})")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def fig_timeline(region, acq_ev, path):
    fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
    for g, d in acq_ev.groupby("group"):
        t = pd.to_datetime(d.time)
        ax.plot(t, d.probable_per_1000km2, "o-", label=g)
        fl = d[d.event_flag]
        ax.plot(pd.to_datetime(fl.time), fl.probable_per_1000km2, "o", ms=13, mfc="none", mec="red")
    ax.set_ylabel("probable slicks, km² per 1000 km² of sea")
    ax.set_title(f"{region.name}: time series (red circle = date stands out in its track)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def markdown(region, acq_ev, objs, src, targets, calib, figs):
    L = [f"# nisar_oil pipeline report: {region.name}", "",
         f"- Area: {region.bbox} (lon0, lat0, lon1, lat1), grid {region.res:.0f} m, EPSG:{region.epsg}",
         f"- Period: {region.start} — {region.end}", f"- Note: {region.notes}" if region.notes else "", "",
         "Method: M0 (noise) → M2 + M3b + M19 (detection) + M8c (anomalies) → objects → features M6/M9/M15 → "
         "oil-likeness score (heuristic calibrated on Oman) → M14 (sources) + M18 (bright targets). "
         "Classes: **probable** ≥ 0.6; **possible** 0.4–0.6. This is a ranking for human review, not proof.", "",
         "## Data", "",
         f"Passes: {len(acq_ev)}, tracks: {acq_ev.group.nunique()}.", ""]
    L.append(acq_ev[["acq_id", "group", "time", "n_frames", "sea_km2", "probable_km2", "probable_per_1000km2", "event_flag"]]
             .to_markdown(index=False, floatfmt=".1f"))
    L += ["", "## Calibration per track (no control date)", ""]
    L.append(pd.DataFrame([{k: v for k, v in c.items() if k in ("group", "n_dates", "thr_ratio_db", "thr_valley", "thr_anom")} for c in calib])
             .to_markdown(index=False, floatfmt=".3f"))
    L += ["", "## Detected sources (M14)", ""]
    if len(src):
        cols = [c for c in ["rank", "lon", "lat", "n_dates", "n_tracks", "n_objects", "first", "last", "median_score",
                            "max_area_km2", "dist_land_km", "persistent_target_km", "transient_target_km", "dist_known_source_km"] if c in src]
        L.append(src[cols].to_markdown(index=False, floatfmt=".3f"))
    else:
        L.append("No clusters of slick origins recurring on ≥ 2 dates were found.")
    L += ["", "## Most probable slicks", ""]
    top = objs[objs["class"] == "probable"].sort_values("score", ascending=False).head(20)
    if len(top):
        L.append(top[["acq_id", "lon", "lat", "area_km2", "score", "n_detectors", "contrast_p10_db", "cv_ratio_in_out",
                      "dist_land_km", "oman_similarity_dist", "flags"]].to_markdown(index=False, floatfmt=".2f"))
    else:
        L.append("No objects of class probable.")
    st = objs[objs["flags"].fillna("").str.contains("static")]
    L += ["", "## Static dark areas (M13, score lowered)", "",
          "Dark objects that repeat with almost the same outline on other dates of the track "
          "(median IoU with objects of other dates ≥ 0.4). Usually lagoon mouths, shoals, coastal wind shadows "
          "or land-mask inaccuracy, not drifting oil. Check a chronic leak in the M14 sources table.", ""]
    if len(st):
        L.append(st.sort_values("score_raw", ascending=False).head(15)[["acq_id", "lon", "lat", "area_km2", "score_raw", "persist_iou",
                 "n_cmp_dates", "dist_land_km"]].to_markdown(index=False, floatfmt=".2f"))
    else:
        L.append("None.")
    L += ["", "## Object classes per pass", ""]
    L.append(objs.groupby(["acq_id", "class"]).size().unstack(fill_value=0).to_markdown())
    if len(targets):
        L += ["", "## Bright targets (M18)", "", targets.groupby(["date", "cls"]).size().unstack(fill_value=0).to_markdown()]
    if region.known_source:
        kx, ky = region.lonlat_to_xy(*region.known_source)
        near = objs[np.hypot(objs.x - kx, objs.y - ky) < 10000]
        L += ["", "## Check against the known source (not used by detection)", "",
              f"- Nearest detected source: {src.dist_known_source_km.min():.1f} km" if len(src) else "- No sources detected",
              f"- Objects within 10 km of the source: {len(near)}, of them probable {int((near['class'] == 'probable').sum())}, "
              f"possible {int((near['class'] == 'possible').sum())}"]
    L += ["", "## Figures", ""] + [f"![{p.name}]({p.relative_to(region.out).as_posix()})" for p in figs]
    L += ["", "## Limitations", "",
          "- The score is a heuristic calibrated on one case (Oman, L-band, monsoon wind); thresholds may shift in other conditions.",
          "- M3b/M19/M8c thresholds are calibrated on all dates of a track: if a slick is present on most dates (chronic source), sensitivity drops.",
          "- Look-alikes (calm, wind shadows, natural films, upwelling) are not fully rejected; near the coast (< 2 km) the score is lowered.",
          "- Static dark areas (same outline on other dates of the track, median IoU ≥ 0.4) are lowered ×0.4: this removes lagoon mouths, "
          "shoals and wind shadows, but a slick staying with the same outline at a source for several passes is lowered too.",
          "- NISAR PROVISIONAL/VALIDATED products are mixed across dates; calibration offsets between scenes are possible."]
    return "\n".join(x for x in L if x is not None)
