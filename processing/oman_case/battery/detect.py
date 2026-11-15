"""Pixel-level methods: quality layer (M0), incidence normalisation (M1), local contrast (M2),
CFAR (M3), wind-model damping ratio (M4), SAR wind (M5), cross-pol HV (M9),
temporal reference normalisation (M13).

Every detector returns a dict: {"mask": bool array, "score": float array (dB, lower = darker
unless stated), "params": dict, ...}. Masks are already cleaned (opening + min area).
"""
import numpy as np
from scipy import ndimage, stats

from . import config as C
from .data import block_background, clean_mask, db, grid, load_scene, smooth

# default parameters per AOI (resolution differs: island_hh 60 m, island_vv 80 m, coast 40 m)
DEFAULTS = {
    "island_hh": dict(k=5, thr=0.8, min_km2=2.0),
    "island_vv": dict(k=3, thr=1.0, min_km2=2.0),
    "coast": dict(k=5, thr=0.8, min_km2=1.0),
}


def _p(sc, **kw):
    p = dict(DEFAULTS[sc["meta"]["aoi"]])
    p.update({k: v for k, v in kw.items() if v is not None})
    return p


def res_of(sc):
    return sc["meta"]["res"]


# ------------------------------------------------------------------------------ M0
def m0_quality(sc, k=None, undetermined_db=1.0):
    """Margin of the signal above the instrument noise floor (dB) and 'undetermined' masks.

    GCOV gamma0 is NOT noise-corrected, so margin = 10log10(g0/NEB) (NEB assumed to be in the
    same normalisation as the product; this is an assumption of the analysis).
    """
    p = _p(sc, k=k)
    sea = sc["sea"]
    g = smooth(np.where(sea, sc["g0"], np.nan), p["k"])
    margin = db(g) - db(sc["neb"])
    out = {"margin_db": margin, "undetermined": sea & (margin < undetermined_db), "params": p}
    if "g0_hv" in sc:
        ghv = smooth(np.where(sea, sc["g0_hv"], np.nan), p["k"])
        out["margin_hv_db"] = db(ghv) - db(sc["neb_hv"])
        out["undetermined_hv"] = sea & (out["margin_hv_db"] < undetermined_db)
    return out


# ------------------------------------------------------------------------------ M2
def m2_contrast(sc, k=None, thr=None, min_km2=None, block_m=20000, channel="g0"):
    """Local contrast to a 20 km block-median sea background; dark if delta < -thr dB."""
    p = _p(sc, k=k, thr=thr, min_km2=min_km2)
    p["block_m"] = block_m
    lin = smooth(np.where(sc["sea"], sc[channel], np.nan), p["k"])
    bg = block_background(lin, res_of(sc), block_m)
    delta = db(lin) - db(bg)
    raw = np.nan_to_num(delta, nan=0) < -p["thr"]
    mask, lab, n = clean_mask(raw & sc["sea"], res_of(sc), p["min_km2"])
    return {"mask": mask, "labels": lab, "n": n, "score": delta, "params": p}


# ------------------------------------------------------------------------------ M1
def incidence_profile(sigma_db, inc, sea, exclude=None, bin_deg=0.25):
    """Median sigma0 (dB) per incidence bin over sea; returns callable-like arrays (centres, values)."""
    m = sea & np.isfinite(sigma_db) & np.isfinite(inc)
    if exclude is not None:
        m &= ~exclude
    edges = np.arange(np.nanmin(inc[m]), np.nanmax(inc[m]) + bin_deg, bin_deg)
    idx = np.digitize(inc[m], edges)
    vals = sigma_db[m]
    centres, med = [], []
    for i in range(1, len(edges)):
        sel = idx == i
        if sel.sum() > 200:
            centres.append(0.5 * (edges[i - 1] + edges[i]))
            med.append(np.median(vals[sel]))
    return np.array(centres), np.array(med)


def m1_incidence_normalised(sc, k=None, thr=None, min_km2=None):
    """Remove the sigma0(incidence) trend with a scene profile, then ONE global threshold
    relative to the scene median (no local background). Tests how much of M2's work is
    just geometry."""
    p = _p(sc, k=k, thr=thr, min_km2=min_km2)
    s_db = db(smooth(np.where(sc["sea"], sc["s0"], np.nan), p["k"]))
    c, v = incidence_profile(s_db, sc["inc"], sc["sea"])
    trend = np.interp(sc["inc"], c, v)
    norm = s_db - trend
    norm -= np.nanmedian(norm[sc["sea"]])
    raw = np.nan_to_num(norm, nan=0) < -p["thr"]
    mask, lab, n = clean_mask(raw & sc["sea"], res_of(sc), p["min_km2"])
    span = float(np.nanmax(v) - np.nanmin(v)) if len(v) else np.nan
    return {"mask": mask, "labels": lab, "n": n, "score": norm, "params": p,
            "profile": (c, v), "profile_span_db": span}


# ------------------------------------------------------------------------------ M3
def estimate_enl(lin, sea, win=11):
    """Equivalent number of looks of a (smoothed) intensity image over sea: median of mean^2/var."""
    x = np.where(sea, lin, np.nan)
    m = np.isfinite(x)
    s1 = ndimage.uniform_filter(np.nan_to_num(x), win)
    s2 = ndimage.uniform_filter(np.nan_to_num(x) ** 2, win)
    c = ndimage.uniform_filter(m.astype(float), win)
    ok = c > 0.95
    mean = s1[ok] / c[ok]
    var = s2[ok] / c[ok] - mean ** 2
    enl = mean ** 2 / np.maximum(var, 1e-30)
    return float(np.median(enl))


def m3_cfar(sc, k=None, pfa=1e-3, win_m=4000, guard_m=1000, min_km2=None):
    """Dark-target CFAR: ratio of the smoothed intensity to the local clutter mean in a ring
    window (win_m box minus guard_m box), threshold = gamma lower quantile at pfa for the ENL
    measured on the scene (texture included, so ENL is conservative)."""
    p = _p(sc, k=k, min_km2=min_km2)
    p.update(pfa=pfa, win_m=win_m, guard_m=guard_m)
    res = res_of(sc)
    lin = smooth(np.where(sc["sea"], sc["g0"], np.nan), p["k"])
    enl = estimate_enl(lin, sc["sea"])
    W = max(3, int(win_m / res) | 1)
    G = max(1, int(guard_m / res) | 1)
    x = np.nan_to_num(lin)
    m = np.isfinite(lin).astype(float)
    sw, cw = ndimage.uniform_filter(x, W) * W * W, ndimage.uniform_filter(m, W) * W * W
    sg, cg = ndimage.uniform_filter(x, G) * G * G, ndimage.uniform_filter(m, G) * G * G
    clutter = (sw - sg) / np.maximum(cw - cg, 1)
    ratio = lin / clutter
    r_thr = stats.gamma.ppf(pfa, a=enl, scale=1.0 / enl)
    raw = np.nan_to_num(ratio, nan=1) < r_thr
    mask, lab, n = clean_mask(raw & sc["sea"], res, p["min_km2"])
    p.update(enl=enl, ratio_thr=float(r_thr), ratio_thr_db=float(db(r_thr)))
    return {"mask": mask, "labels": lab, "n": n, "score": db(ratio), "params": p}


def m3_cfar_calibrated(sc, control_sc, q=1e-3, k=None, win_m=4000, guard_m=1000, min_km2=None):
    """CFAR with an EMPIRICAL threshold: the q-quantile of the clutter ratio on a control scene of
    the same track (captures real sea texture, which the gamma model ignores)."""
    base = m3_cfar(sc, k=k, win_m=win_m, guard_m=guard_m, min_km2=min_km2)
    ctrl = m3_cfar(control_sc, k=k, win_m=win_m, guard_m=guard_m, min_km2=min_km2)
    r_ctrl = ctrl["score"][control_sc["sea"] & np.isfinite(ctrl["score"])]
    thr_db = float(np.quantile(r_ctrl, q))
    raw = np.nan_to_num(base["score"], nan=0) < thr_db
    mask, lab, n = clean_mask(raw & sc["sea"], res_of(sc), base["params"]["min_km2"])
    p = dict(base["params"])
    p.update(q=q, ratio_thr_db=thr_db, control=control_sc["meta"]["id"])
    return {"mask": mask, "labels": lab, "n": n, "score": base["score"], "params": p}


# ------------------------------------------------------------------------------ M9
def m9_crosspol(sc, k=7, thr=0.8, min_km2=2.0, block_m=20000):
    """HV-only local contrast detection and HV/HH depolarisation ratio. Requires HV."""
    if "g0_hv" not in sc:
        return None
    res = res_of(sc)
    hv = smooth(np.where(sc["sea"], sc["g0_hv"], np.nan), k)
    hh = smooth(np.where(sc["sea"], sc["g0"], np.nan), k)
    bg = block_background(hv, res, block_m)
    delta = db(hv) - db(bg)
    raw = np.nan_to_num(delta, nan=0) < -thr
    mask, lab, n = clean_mask(raw & sc["sea"], res, min_km2)
    depol = db(hv) - db(hh)
    return {"mask": mask, "labels": lab, "n": n, "score": delta, "depol_db": depol,
            "margin_hv_db": db(hv) - db(sc["neb_hv"]),
            "params": dict(k=k, thr=thr, min_km2=min_km2, block_m=block_m)}


# ------------------------------------------------------------------------------ M13
def m13_temporal(sid, peers, k=None, thr=1.0, min_km2=None):
    """Leave-one-out temporal reference of the same track: anomaly = n_t - median(n_others),
    with n = sigma0_dB - scene median (removes the overall wind level of each date).
    Geometry (incidence, antenna) and persistent patterns cancel; transient features remain."""
    sc = load_scene(sid)
    p = _p(sc, k=k, min_km2=min_km2)
    p["thr"] = thr

    def norm(s):
        x = db(smooth(np.where(s["sea"], s["g0"], np.nan), p["k"]))
        return x - np.nanmedian(x[s["sea"]])

    cur = norm(sc)
    others = np.stack([norm(load_scene(o)) for o in peers if o != sid])
    with np.errstate(all="ignore"):
        ref = np.nanmedian(others, axis=0)
    anom = cur - ref
    raw = np.nan_to_num(anom, nan=0) < -thr
    mask, lab, n = clean_mask(raw & sc["sea"] & np.isfinite(ref), res_of(sc), p["min_km2"])
    p["n_reference_dates"] = int(len(peers) - 1)
    return {"mask": mask, "labels": lab, "n": n, "score": anom, "params": p}


# ------------------------------------------------------------------------------ M4 / M5
def fit_wind_gmf(samples):
    """Self-calibrated L-band 'GMF' per track/pol from clean-sea samples:
        sigma0_dB = a0 + a1*(inc-40) + a2*(inc-40)^2 + b*10log10(U10)
    samples: dict with arrays inc, u10, s0_db. Returns coefficients and fit statistics.
    The narrow range of wind directions (SW monsoon) does not allow fitting azimuth terms,
    so the relative-direction dependence is absorbed per track."""
    inc, u, y = samples["inc"], samples["u10"], samples["s0_db"]
    ok = np.isfinite(inc) & np.isfinite(u) & np.isfinite(y) & (u > 0.5)
    X = np.c_[np.ones(ok.sum()), inc[ok] - 40, (inc[ok] - 40) ** 2, 10 * np.log10(u[ok])]
    coef, *_ = np.linalg.lstsq(X, y[ok], rcond=None)
    pred = X @ coef
    resid = y[ok] - pred
    return {"coef": coef.tolist(), "rmse_db": float(np.sqrt(np.mean(resid ** 2))),
            "n": int(ok.sum()), "u_range": [float(np.min(u[ok])), float(np.max(u[ok]))],
            "r2": float(1 - resid.var() / y[ok].var())}


def gmf_predict(coef, inc, u10):
    a0, a1, a2, b = coef
    return a0 + a1 * (inc - 40) + a2 * (inc - 40) ** 2 + b * 10 * np.log10(np.maximum(u10, 0.3))


def gmf_invert(coef, inc, s0_db):
    a0, a1, a2, b = coef
    return 10 ** ((s0_db - a0 - a1 * (inc - 40) - a2 * (inc - 40) ** 2) / (10 * b))


def m4_damping(sc, u10_grid, coef, k=None, thr=1.0, min_km2=None):
    """Damping ratio DR_dB = sigma0_model(ERA5 wind, inc) - sigma0_obs (positive = darker than a
    clean sea at that wind). Dark if DR_dB > thr."""
    p = _p(sc, k=k, min_km2=min_km2)
    p["thr"] = thr
    s_db = db(smooth(np.where(sc["sea"], sc["s0"], np.nan), p["k"]))
    model = gmf_predict(coef, sc["inc"], u10_grid)
    dr = model - s_db
    raw = np.nan_to_num(dr, nan=0) > thr
    mask, lab, n = clean_mask(raw & sc["sea"], res_of(sc), p["min_km2"])
    return {"mask": mask, "labels": lab, "n": n, "score": -dr, "dr_db": dr, "params": p}


def m5_sar_wind(sc, coef, block_m=5000, low_wind=3.0):
    """Wind speed from sigma0 by inverting the self-calibrated GMF, on the smooth background
    (block median, so slicks do not dominate) and per pixel."""
    res = res_of(sc)
    s = np.where(sc["sea"], sc["s0"], np.nan)
    bg = block_background(smooth(s, 5), res, block_m, min_frac=0.3)
    u_bg = gmf_invert(coef, sc["inc"], db(bg))
    u_px = gmf_invert(coef, sc["inc"], db(smooth(s, 5)))
    return {"u_ambient": np.where(sc["sea"], u_bg, np.nan), "u_pixel": np.where(sc["sea"], u_px, np.nan),
            "low_wind": sc["sea"] & (u_bg < low_wind), "params": dict(block_m=block_m, low_wind=low_wind)}


def clean_sea_samples(sc, u10_grid, exclude_mask, step=8):
    """Sub-sampled clean-sea samples (inc, u10, sigma0_dB) for GMF fitting, excluding dark objects."""
    s_db = db(smooth(np.where(sc["sea"], sc["s0"], np.nan), 5))
    ok = sc["sea"] & ~exclude_mask & np.isfinite(s_db) & np.isfinite(u10_grid)
    ok[::step, :] &= True
    sel = np.zeros_like(ok)
    sel[::step, ::step] = ok[::step, ::step]
    return {"inc": sc["inc"][sel], "u10": u10_grid[sel], "s0_db": s_db[sel]}
