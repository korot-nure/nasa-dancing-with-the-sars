"""Detection layers per acquisition (methods selected on the Oman battery):
M0 noise margin, M2 local contrast, M3b CFAR ratio, M19 thin dark lines (valley filter),
M8c block anomaly score, M9 cross-pol contrast.

Without a known clean control date, M3b/M19/M8c thresholds are calibrated per track group
(same track, direction, polarisation) from ALL its acquisitions: the median over dates of a
per-date quantile (oil covers a tiny share of the sea, so the median date is close to clean).
"""
import numpy as np
from scipy import ndimage, stats
from skimage.filters import sato
from sklearn.ensemble import IsolationForest

PARAMS = {"HH": dict(k=5, thr=0.8), "VV": dict(k=5, thr=1.0)}
M2_MIN_KM2 = 2.0
CAND_MIN_KM2 = 1.0


def db(a):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(a)


def smooth(lin, k):
    m = np.isfinite(lin)
    s = ndimage.uniform_filter(np.where(m, lin, 0.0), k)
    c = ndimage.uniform_filter(m.astype(float), k)
    r = np.where(c > 0.5, s / np.maximum(c, 1e-12), np.nan)
    r[~m] = np.nan
    return r


def block_background(lin, res, block_m=20000, min_frac=0.15):
    B = max(4, int(block_m / res))
    ny, nx = int(np.ceil(lin.shape[0] / B)), int(np.ceil(lin.shape[1] / B))
    med = np.full((ny, nx), np.nan)
    for i in range(ny):
        for j in range(nx):
            blk = lin[i * B:(i + 1) * B, j * B:(j + 1) * B]
            blk = blk[np.isfinite(blk)]
            if blk.size > min_frac * B * B:
                med[i, j] = np.median(blk)
    if np.isnan(med).all():
        return np.full(lin.shape, np.nan)
    idx = ndimage.distance_transform_edt(np.isnan(med), return_distances=False, return_indices=True)
    bg = ndimage.zoom(np.log(med[tuple(idx)]), (lin.shape[0] / ny, lin.shape[1] / nx), order=1)
    return np.exp(bg[: lin.shape[0], : lin.shape[1]])


def clean_mask(mask, res, min_km2, opening=1):
    m = ndimage.binary_opening(mask, iterations=opening) if opening else mask.copy()
    lab, n = ndimage.label(m)
    if n == 0:
        return m, lab, 0
    sizes = ndimage.sum(m, lab, range(1, n + 1)) * (res / 1000) ** 2
    keep = np.isin(lab, np.nonzero(sizes >= min_km2)[0] + 1)
    lab, n = ndimage.label(keep)
    return keep, lab, n


# ------------------------------------------------------------------ per-acquisition layers
def layers(region, a):
    """Unthresholded layers of one acquisition."""
    pol = a["meta"]["main_pol"]
    p = PARAMS[pol]
    sea = a["sea"]
    res = region.res
    lin = smooth(np.where(sea, a["g0"], np.nan), p["k"])
    bg = block_background(lin, res)
    out = {"delta": (db(lin) - db(bg)).astype(np.float32)}              # M2 contrast, dB
    out["margin"] = db(lin) - db(a["neb"]) if "neb" in a else np.full(sea.shape, np.nan)   # M0
    # M3b clutter ratio (4 km window, 1 km guard). Censored ring: pixels > +6 dB over the 20 km
    # background (platforms, ships, breakwaters; dilated by 2 px) are left out of the ring mean,
    # otherwise one bright target lifts the ring by several dB and the dark tail is dominated by
    # ordinary sea around structures (seen in the UAE run: threshold -14 dB at pixels brighter than the median sea).
    W, G = int(4000 / res) | 1, int(1000 / res) | 1
    bright = ndimage.binary_dilation(np.nan_to_num(lin / bg, nan=0) > 10 ** 0.6, iterations=2)
    keep = np.isfinite(lin) & ~bright
    x, m = np.where(keep, lin, 0.0), keep.astype(float)
    sw, cw = ndimage.uniform_filter(x, W) * W * W, ndimage.uniform_filter(m, W) * W * W
    sg, cg = ndimage.uniform_filter(x, G) * G * G, ndimage.uniform_filter(m, G) * G * G
    out["ratio"] = db(lin / ((sw - sg) / np.maximum(cw - cg, 1))).astype(np.float32)
    # M19 valley response; shoreline zone (3 km) excluded
    s = db(smooth(np.where(sea, a["g0"], np.nan), 2))
    s = np.where(np.isfinite(s), s, np.nanmedian(s))
    v = sato(s, sigmas=(2, 4, 6), black_ridges=True)
    v[~(sea & (region.dist_land_km >= 3))] = 0
    out["valley"] = v.astype(np.float32)
    # M9 cross-pol contrast
    if "g0_hv" in a and np.isfinite(a["g0_hv"]).any():
        hv = smooth(np.where(sea, a["g0_hv"], np.nan), 7)
        out["hv_delta"] = db(hv) - db(block_background(hv, res))
        out["hv_margin"] = db(hv) - db(a["neb_hv"]) if "neb_hv" in a else np.full(sea.shape, np.nan)
        out["depol"] = db(hv) - db(smooth(np.where(sea, a["g0"], np.nan), 7))
    return out


def block_features(region, lay, sea, block_m=1000):
    B = max(4, int(round(block_m / region.res)))
    ny, nx = sea.shape[0] // B, sea.shape[1] // B
    d, v = lay["delta"], lay["valley"]
    rows, idx = [], []
    for i in range(ny):
        for j in range(nx):
            sl = (slice(i * B, (i + 1) * B), slice(j * B, (j + 1) * B))
            s = sea[sl]
            if s.mean() < 0.9:
                continue
            dd = d[sl][s]
            rows.append([np.nanmean(dd), np.nanpercentile(dd, 10), np.nanstd(dd), np.nanmean(v[sl][s])])
            idx.append((i, j))
    return np.array(rows), idx, B


# ------------------------------------------------------------------ group calibration
def calib_stats(region, lay, sea, q3=1e-3, q19=0.995):
    """Compact per-acquisition statistics needed for the group calibration (first pass)."""
    r = lay["ratio"][sea & np.isfinite(lay["ratio"])]
    return dict(t3=float(np.quantile(r, q3)) if r.size else np.nan,
                t19=float(np.quantile(lay["valley"][sea], q19)) if sea.any() else np.nan,
                feats=block_features(region, lay, sea)[0])


def calibrate_group(stats_list, q8=0.995, seed=0):
    """Thresholds for M3b/M19 and the anomaly model for M8c from all acquisitions of a track group
    (median over dates of per-date quantiles; isolation forest on pooled 1 km blocks)."""
    t3 = [s["t3"] for s in stats_list if np.isfinite(s["t3"])]
    t19 = [s["t19"] for s in stats_list if np.isfinite(s["t19"])]
    feats = [s["feats"] for s in stats_list]
    pool = np.concatenate([f for f in feats if len(f)])
    pool = pool[np.isfinite(pool).all(1)]
    rng = np.random.default_rng(seed)
    sub = pool[rng.choice(len(pool), size=min(len(pool), 40000), replace=False)]
    model = IsolationForest(n_estimators=200, random_state=seed).fit(sub)
    t8 = float(np.quantile(-model.score_samples(sub), q8))
    return dict(thr_ratio_db=float(np.median(t3)), thr_valley=float(np.median(t19)), model=model, thr_anom=t8,
                n_dates=len(stats_list), per_date_ratio_q=[float(x) for x in t3])


def masks(region, a, lay, cal):
    """Thresholded detector masks (bool) + anomaly map for one acquisition."""
    pol = a["meta"]["main_pol"]
    sea, res = a["sea"], region.res
    m2, _, _ = clean_mask((np.nan_to_num(lay["delta"], nan=0) < -PARAMS[pol]["thr"]) & sea, res, M2_MIN_KM2)
    m3, _, _ = clean_mask((np.nan_to_num(lay["ratio"], nan=0) < cal["thr_ratio_db"]) & sea, res, 1.0)
    m19, _, _ = clean_mask((lay["valley"] > cal["thr_valley"]) & sea, res, 0.5, opening=0)
    X, idx, B = block_features(region, lay, sea)
    anom = np.full(sea.shape, np.nan, np.float32)
    if len(X):
        ok = np.isfinite(X).all(1)
        sc = np.full(len(X), np.nan)
        sc[ok] = -cal["model"].score_samples(X[ok])
        for (i, j), s in zip(idx, sc):
            anom[i * B:(i + 1) * B, j * B:(j + 1) * B] = s
    m8 = np.nan_to_num(anom, nan=0) > cal["thr_anom"]
    return {"M2": m2, "M3b": m3, "M19": m19, "M8c": m8 & sea, "anom": anom}
