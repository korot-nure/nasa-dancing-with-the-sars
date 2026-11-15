"""Context methods: M14 recurrence map and source finding, M15 drift consistency,
M18 bright targets (ships/structures), M19 linear features, M21 coastal backscatter change."""
import numpy as np
import pandas as pd
from scipy import ndimage, stats
from skimage.morphology import skeletonize
from skimage.transform import probabilistic_hough_line
from sklearn.cluster import DBSCAN

from . import config as C
from . import detect as M
from .data import TO_LL, TO_UTM, db, land_raw, load_scene, meshgrid, smooth, source_distance, source_xy


# ------------------------------------------------------------------------- M14
def m14_recurrence(scene_ids, masks):
    """Fraction of scenes in which each pixel is dark (same AOI grid)."""
    stack = np.stack([masks[s].astype(float) for s in scene_ids])
    seas = np.stack([load_scene(s)["sea"] for s in scene_ids])
    with np.errstate(invalid="ignore"):
        freq = stack.sum(0) / np.maximum(seas.sum(0), 1)
    freq[seas.sum(0) == 0] = np.nan
    return freq


def upwind_origins(sid, labels, wind_from_deg, min_km2=5.0):
    """Most-upwind pixel of every object (candidate origin of a drifting slick)."""
    sc = load_scene(sid)
    res = sc["meta"]["res"]
    XX, YY = meshgrid(sc["meta"]["aoi"])
    down = np.deg2rad((wind_from_deg + 180) % 360)          # bearing the wind blows towards
    ux, uy = np.sin(down), np.cos(down)
    rows = []
    for lab_id in range(1, labels.max() + 1):
        obj = labels == lab_id
        area = obj.sum() * (res / 1000) ** 2
        if area < min_km2:
            continue
        proj = XX[obj] * ux + YY[obj] * uy
        k = np.argmin(proj)
        rows.append(dict(scene=sid, x=XX[obj][k], y=YY[obj][k], area_km2=area))
    return pd.DataFrame(rows)


def m14_source_finding(origins, eps_km=5.0, min_samples=3):
    """DBSCAN of upwind origins across dates; clusters = candidate chronic sources."""
    if origins.empty:
        return pd.DataFrame()
    lab = DBSCAN(eps=eps_km * 1000, min_samples=min_samples).fit_predict(origins[["x", "y"]].values)
    origins = origins.assign(cluster=lab)
    sx, sy = source_xy()
    rows = []
    for c in sorted(set(lab) - {-1}):
        g = origins[origins.cluster == c]
        cx, cy = g.x.median(), g.y.median()
        lon, lat = TO_LL.transform(cx, cy)
        rows.append(dict(cluster=c, n_objects=len(g), n_scenes=g.scene.nunique(), scenes=",".join(sorted(g.scene.unique())),
                         lon=lon, lat=lat, dist_to_true_source_km=np.hypot(cx - sx, cy - sy) / 1000,
                         total_area_km2=g.area_km2.sum()))
    return pd.DataFrame(rows).sort_values("n_scenes", ascending=False), origins


# ------------------------------------------------------------------------- M15
def m15_orientation(sid, labels_src, wind_from_deg, current_uv=None, wind_factor=0.03):
    """Bearing from the source to the centroid of the source-linked slick vs expected drift
    (wind_factor * wind + surface current). Returns angles in degrees."""
    sc = load_scene(sid)
    XX, YY = meshgrid(sc["meta"]["aoi"])
    obj = labels_src
    if not obj.any():
        return None
    sx, sy = source_xy()
    cx, cy = XX[obj].mean(), YY[obj].mean()
    slick_bearing = np.degrees(np.arctan2(cx - sx, cy - sy)) % 360
    down = (wind_from_deg + 180) % 360
    out = dict(scene=sid, slick_bearing=slick_bearing, downwind_bearing=down,
               diff_wind=abs((slick_bearing - down + 180) % 360 - 180),
               centroid_dist_km=np.hypot(cx - sx, cy - sy) / 1000)
    if current_uv is not None:
        (wu, wv), (cu, cv) = current_uv
        du, dv = wind_factor * wu + cu, wind_factor * wv + cv
        drift_bearing = np.degrees(np.arctan2(du, dv)) % 360
        out.update(drift_bearing=drift_bearing, drift_speed_ms=float(np.hypot(du, dv)),
                   diff_drift=abs((slick_bearing - drift_bearing + 180) % 360 - 180))
    return out


# ------------------------------------------------------------------------- M18
def m18_bright_targets(sid, pfa=1e-6, win_m=2000, guard_m=300, channel="g0"):
    """Bright point targets by CFAR on unsmoothed gamma0 (HV preferred where available:
    the sea is close to the noise floor, so metal structures stand out)."""
    sc = load_scene(sid)
    res = sc["meta"]["res"]
    ch = "g0_hv" if (channel == "auto" and "g0_hv" in sc) else ("g0" if channel == "auto" else channel)
    img = np.where(sc["sea"] | ~sc["land"], sc[ch], np.nan)
    img = np.where(land_raw(sc["meta"]["aoi"]), np.nan, img)
    enl = M.estimate_enl(img, np.isfinite(img), win=7)
    W, G = max(5, int(win_m / res) | 1), max(1, int(guard_m / res) | 1)
    x, m = np.nan_to_num(img), np.isfinite(img).astype(float)
    sw, cw = ndimage.uniform_filter(x, W) * W * W, ndimage.uniform_filter(m, W) * W * W
    sg, cg = ndimage.uniform_filter(x, G) * G * G, ndimage.uniform_filter(m, G) * G * G
    clutter = (sw - sg) / np.maximum(cw - cg, 1)
    thr = stats.gamma.ppf(1 - pfa, a=enl, scale=1.0 / enl)
    det = np.nan_to_num(img / clutter) > thr
    lab, n = ndimage.label(det)
    XX, YY = meshgrid(sc["meta"]["aoi"])
    sx, sy = source_xy()
    dist_land = ndimage.distance_transform_edt(~land_raw(sc["meta"]["aoi"])) * res / 1000
    rows = []
    for i in range(1, n + 1):
        o = lab == i
        k = np.argmax(np.where(o, img, -np.inf))
        r, c = np.unravel_index(k, img.shape)
        lon, lat = TO_LL.transform(XX[r, c], YY[r, c])
        rows.append(dict(scene=sid, x=XX[r, c], y=YY[r, c], lon=lon, lat=lat, peak_db=float(db(img[r, c])),
                         snr_db=float(db(img[r, c] / clutter[r, c])), n_px=int(o.sum()),
                         dist_source_km=float(np.hypot(XX[r, c] - sx, YY[r, c] - sy) / 1000),
                         dist_land_km=float(dist_land[r, c])))
    return pd.DataFrame(rows), dict(channel=ch, enl=enl, ratio_thr_db=float(db(thr)), pfa=pfa)


def m18_classify(tables, min_snr_db=13.0, match_m=600, near_source_km=3.0, coastal_km=3.0):
    """Split bright targets into: source cluster (island/tanker), coastal, persistent offshore
    (same place on >= 2 dates: fixed structures or residual clutter) and transient offshore (ships)."""
    allt = pd.concat([t.assign(scene=s) for s, t in tables.items() if len(t)], ignore_index=True)
    allt = allt[allt.snr_db >= min_snr_db].copy()
    allt["cls"] = "offshore"
    allt.loc[allt.dist_source_km < near_source_km, "cls"] = "source_cluster"
    allt.loc[(allt.cls == "offshore") & (allt.dist_land_km < coastal_km), "cls"] = "coastal"
    off = allt[allt.cls == "offshore"]
    persistent = []
    for idx, row in off.iterrows():
        others = off[(off.scene != row.scene)]
        d = np.hypot(others.x - row.x, others.y - row.y)
        persistent.append(bool((d < match_m).any()))
    allt.loc[off.index, "cls"] = np.where(persistent, "offshore_persistent", "offshore_transient")
    return allt


# ------------------------------------------------------------------------- M19
def valley_response(sc, sigmas=(2, 4, 6), coast_km=3.0, source_km=3.0):
    """Thin dark-line enhancement: Sato tubeness filter on sigma0 dB (black ridges), scales
    ~120-360 m (line widths ~0.3-1 km). Shoreline zone and the island vicinity are excluded:
    the land/sea edge and island wind shadows produce strong false 'valleys'."""
    from skimage.filters import sato
    res = sc["meta"]["res"]
    s = db(smooth(np.where(sc["sea"], sc["g0"], np.nan), 2))
    s = np.where(np.isfinite(s), s, np.nanmedian(s))
    resp = sato(s, sigmas=sigmas, black_ridges=True)
    far = ndimage.distance_transform_edt(~land_raw(sc["meta"]["aoi"])) * res >= coast_km * 1000
    keep = sc["sea"] & far
    if sc["meta"]["aoi"].startswith("island"):
        keep &= source_distance(sc["meta"]["aoi"]) >= source_km * 1000
    resp[~keep] = 0
    return resp


def m19_line_mask(sid, control_sid, q=0.995, min_km2=0.5):
    """Line mask: valley response above the q-quantile of the same-track control scene."""
    from .data import clean_mask
    sc, ct = load_scene(sid), load_scene(control_sid)
    r, rc = valley_response(sc), valley_response(ct)
    thr = float(np.quantile(rc[ct["sea"]], q))
    mask, lab, n = clean_mask((r > thr) & sc["sea"], sc["meta"]["res"], min_km2, opening=0)
    return {"mask": mask, "labels": lab, "n": n, "score": r, "params": dict(q=q, thr=thr, control=control_sid)}


def m19_lines(sid, mask, min_len_km=10.0, gap_km=0.5, bright=None):
    """Long straight dark segments (probabilistic Hough on the skeleton of the dark mask)."""
    sc = load_scene(sid)
    res = sc["meta"]["res"]
    sk = skeletonize(mask)
    segs = probabilistic_hough_line(sk, threshold=10, line_length=int(min_len_km * 1000 / res),
                                    line_gap=int(gap_km * 1000 / res), rng=0)
    XX, YY = meshgrid(sc["meta"]["aoi"])
    sx, sy = source_xy()
    rows = []
    for (c0, r0), (c1, r1) in segs:
        x0, y0, x1, y1 = XX[r0, c0], YY[r0, c0], XX[r1, c1], YY[r1, c1]
        L = np.hypot(x1 - x0, y1 - y0) / 1000
        bearing = np.degrees(np.arctan2(x1 - x0, y1 - y0)) % 180
        d_src = min(np.hypot(x0 - sx, y0 - sy), np.hypot(x1 - sx, y1 - sy)) / 1000
        row = dict(scene=sid, length_km=L, bearing_deg=bearing, end_dist_source_km=d_src)
        if bright is not None and len(bright):
            bx, by = TO_UTM.transform(bright.lon.values, bright.lat.values)
            dmin = min(np.min(np.hypot(bx - x0, by - y0)), np.min(np.hypot(bx - x1, by - y1))) / 1000
            row["end_dist_bright_km"] = dmin
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------- M21
COAST_SEGMENTS = {
    # name: (lat0, lat1, lon0, lon1)
    "Ras Madrakah 18.9-19.2N": (18.85, 19.2, 57.6, 58.2),
    "coast 19.2-19.6N": (19.2, 19.6, 57.6, 58.0),
    "Duqm 19.6-20.0N": (19.6, 20.0, 57.6, 58.0),
    "coast 20.0-20.45N": (20.0, 20.45, 57.6, 58.3),
    "Masirah south": (20.1, 20.35, 58.5, 58.9),
}


def m21_coast_change(pre_sid, post_sid, strip_m=1000):
    """Median gamma0 (HH, HV) in a 0..strip_m inland strip per coastal segment, post minus pre."""
    a, b = load_scene(pre_sid), load_scene(post_sid)
    aoi = a["meta"]["aoi"]
    res = a["meta"]["res"]
    land = land_raw(aoi)
    strip = land & ~ndimage.binary_erosion(land, iterations=max(1, int(strip_m / res)))
    XX, YY = meshgrid(aoi)
    LON, LAT = TO_LL.transform(XX, YY)
    rows = []
    for name, (la0, la1, lo0, lo1) in COAST_SEGMENTS.items():
        seg = strip & (LAT >= la0) & (LAT < la1) & (LON >= lo0) & (LON < lo1)
        both = seg & np.isfinite(a["g0"]) & np.isfinite(b["g0"])
        if both.sum() < 50:
            continue
        row = dict(pre=pre_sid, post=post_sid, segment=name, n_px=int(both.sum()),
                   hh_change_db=float(np.median(db(b["g0"][both])) - np.median(db(a["g0"][both]))))
        if "g0_hv" in a and "g0_hv" in b:
            okh = both & np.isfinite(a["g0_hv"]) & np.isfinite(b["g0_hv"])
            row["hv_change_db"] = float(np.median(db(b["g0_hv"][okh])) - np.median(db(a["g0_hv"][okh])))
        rows.append(row)
    return pd.DataFrame(rows)
