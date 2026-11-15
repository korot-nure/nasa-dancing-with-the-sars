"""M14 source finding (clusters of up-wind origins across dates), M18 bright targets
(platforms/anchored vessels vs transient ships) and date-level event flags."""
import numpy as np
import pandas as pd
from scipy import ndimage, stats
from sklearn.cluster import DBSCAN

from .detect import db


def find_sources(objs, region, min_score=0.4, min_area=2.0, eps_km=5.0, min_samples=3, min_dates=2):
    o = objs[(objs.score >= min_score) & (objs.area_km2 >= min_area) & objs.origin_x.notna()].copy()
    if len(o) < min_samples:
        return pd.DataFrame(), o.assign(cluster=-1)
    o["cluster"] = DBSCAN(eps=eps_km * 1000, min_samples=min_samples).fit_predict(o[["origin_x", "origin_y"]].values)
    rows = []
    for c, g in o[o.cluster >= 0].groupby("cluster"):
        if g.date.nunique() < min_dates:
            continue
        x, y = g.origin_x.median(), g.origin_y.median()
        lon, lat = region.xy_to_lonlat(x, y)
        rows.append(dict(source=int(c), lon=lon, lat=lat, x=x, y=y, n_objects=len(g), n_dates=g.date.nunique(),
                         n_tracks=g.track.nunique(), first=g.date.min(), last=g.date.max(),
                         dates=",".join(sorted(g.date.unique())), median_score=float(g.score.median()),
                         max_area_km2=float(g.area_km2.max()), total_area_km2=float(g.area_km2.sum()),
                         dist_land_km=float(region.dist_land_km[int((region.grid[1][0] - y) / region.res),
                                                                  int((x - region.grid[0][0]) / region.res)])))
    src = pd.DataFrame(rows)
    if len(src):
        src = src.sort_values(["n_dates", "total_area_km2"], ascending=False).reset_index(drop=True)
        src["rank"] = np.arange(1, len(src) + 1)
        if region.known_source:
            kx, ky = region.lonlat_to_xy(*region.known_source)
            src["dist_known_source_km"] = np.hypot(src.x - kx, src.y - ky) / 1000
    return src, o


def bright_targets(region, a, pfa=1e-6, min_snr_db=13.0, win_m=2000, guard_m=300):
    """CFAR on unsmoothed gamma0 of the main channel; returns target table."""
    res = region.res
    img = np.where(a["sea"] | (region.dist_land_km > 0.5), a["g0"], np.nan)
    img = np.where(region.land, np.nan, img)
    m = np.isfinite(img)
    x = np.nan_to_num(img)
    w = 7
    s1, s2, c = (ndimage.uniform_filter(v, w) for v in (x, x ** 2, m.astype(float)))
    ok = c > 0.95
    mean, var = s1[ok] / c[ok], s2[ok] / c[ok] - (s1[ok] / c[ok]) ** 2
    enl = float(np.median(mean ** 2 / np.maximum(var, 1e-30)))
    W, G = int(win_m / res) | 1, max(1, int(guard_m / res) | 1)
    sw, cw = ndimage.uniform_filter(x, W) * W * W, ndimage.uniform_filter(m.astype(float), W) * W * W
    sg, cg = ndimage.uniform_filter(x, G) * G * G, ndimage.uniform_filter(m.astype(float), G) * G * G
    clutter = (sw - sg) / np.maximum(cw - cg, 1)
    thr = stats.gamma.ppf(1 - pfa, a=enl, scale=1 / enl)
    det = np.nan_to_num(img / clutter) > thr
    lab, n = ndimage.label(det)
    XX, YY = region.mesh()
    rows = []
    for i in range(1, n + 1):
        o = lab == i
        k = np.argmax(np.where(o, img, -np.inf))
        r, cc = np.unravel_index(k, img.shape)
        snr = float(db(img[r, cc] / clutter[r, cc]))
        if snr < min_snr_db:
            continue
        lon, lat = region.xy_to_lonlat(XX[r, cc], YY[r, cc])
        rows.append(dict(acq_id=a["meta"]["acq_id"], date=a["meta"]["time"][:10], x=XX[r, cc], y=YY[r, cc], lon=lon, lat=lat,
                         snr_db=snr, peak_db=float(db(img[r, cc])), n_px=int(o.sum()),
                         dist_land_km=float(region.dist_land_km[r, cc])))
    return pd.DataFrame(rows)


def classify_targets(t, match_m=600, coastal_km=2.0):
    if t.empty:
        return t
    t = t.copy()
    t["cls"] = np.where(t.dist_land_km < coastal_km, "coastal", "offshore")
    off = t[t.cls == "offshore"]
    pers = []
    for _, r in off.iterrows():
        o = off[off.date != r.date]
        pers.append(bool((np.hypot(o.x - r.x, o.y - r.y) < match_m).any()))
    t.loc[off.index, "cls"] = np.where(pers, "offshore_persistent", "offshore_transient")
    return t


def attach_targets(src, targets, radius_km=2.0):
    if src.empty or targets.empty:
        return src
    pers = targets[targets.cls == "offshore_persistent"]
    trans = targets[targets.cls == "offshore_transient"]
    src = src.copy()
    for col, t in (("persistent_target_km", pers), ("transient_target_km", trans)):
        src[col] = [float(np.min(np.hypot(t.x - r.x, t.y - r.y)) / 1000) if len(t) else np.nan for r in src.itertuples()]
    return src


def event_flags(objs, acq, cls=("probable",)):
    """Per acquisition: area of probable objects and a robust anomaly flag within its track group."""
    a = objs[objs["class"].isin(cls)].groupby("acq_id").area_km2.sum()
    t = acq.copy()
    t["probable_km2"] = t.acq_id.map(a).fillna(0.0)
    t["probable_per_1000km2"] = t.probable_km2 / t.sea_km2 * 1000
    flags = []
    for _, g in t.groupby("group"):
        med = g.probable_per_1000km2.median()
        mad = 1.4826 * (g.probable_per_1000km2 - med).abs().median()
        flags.append(g.probable_per_1000km2 > med + 3 * max(mad, 0.5))
    t["event_flag"] = pd.concat(flags).reindex(t.index).fillna(False)
    return t
