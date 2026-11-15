"""Candidate objects (union of detectors M2, M3b, M19) and their features (M6, M7, M9, M15, M20)."""
import numpy as np
import pandas as pd
from scipy import ndimage
from skimage import measure

from .detect import CAND_MIN_KM2, clean_mask, db, smooth


def _ring(mask, width):
    return ndimage.binary_dilation(mask, iterations=width) & ~mask


def _outline(region, obj, rp, max_pts=150):
    """Object outline as lon/lat polygon (longest contour of the object crop)."""
    r0, c0, r1, c1 = rp.bbox
    crop = np.pad(obj[r0:r1, c0:c1], 1)
    cs = measure.find_contours(crop.astype(float), 0.5)
    if not cs:
        return None
    c = max(cs, key=len)
    step = max(1, len(c) // max_pts)
    c = c[::step]
    xs, ys = region.grid
    x = xs[0] + (c[:, 1] - 1 + c0) * region.res
    y = ys[0] - (c[:, 0] - 1 + r0) * region.res
    lon, lat = region.xy_to_lonlat(x, y)
    pts = list(zip(np.round(lon, 5).tolist(), np.round(lat, 5).tolist()))
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def object_table(region, a, lay, mk, wind=None, cur=None):
    """One row per candidate object of an acquisition."""
    res = region.res
    sea = a["sea"]
    union = (mk["M2"] | mk["M3b"] | mk["M19"]) & sea
    union, lab, n = clean_mask(union, res, CAND_MIN_KM2, opening=0)
    if n == 0:
        return pd.DataFrame(), lab
    s_lin = np.where(sea, a["g0"], np.nan)
    s_db3 = db(smooth(s_lin, 3))
    gy, gx = np.gradient(np.nan_to_num(s_db3, nan=np.nanmedian(s_db3)))
    grad = np.hypot(gx, gy) / (res / 1000.0)
    XX, YY = region.mesh()
    meta = a["meta"]
    rows = []
    for rp in measure.regionprops(lab):
        obj = lab == rp.label
        inner2 = ndimage.binary_erosion(obj, iterations=2)
        inner_ring = obj & ~inner2
        ring2 = _ring(obj, 2) & sea
        ring6 = _ring(obj, max(3, int(1500 / res))) & sea
        edge = ndimage.binary_dilation(obj, iterations=1) & ~ndimage.binary_erosion(obj, iterations=1)
        vin, vout = s_lin[obj & np.isfinite(s_lin)], s_lin[ring6 & np.isfinite(s_lin)]
        cv_in = float(np.std(vin) / np.mean(vin)) if vin.size > 5 else np.nan
        cv_out = float(np.std(vout) / np.mean(vout)) if vout.size > 5 else np.nan
        area = rp.area * (res / 1000) ** 2
        bearing = (90 - np.degrees(rp.orientation)) % 180                 # major axis, 0..180 from north
        cy, cx = rp.centroid
        x, y = XX[int(cy), int(cx)], YY[int(cy), int(cx)]
        lon, lat = region.xy_to_lonlat(x, y)
        row = dict(acq_id=meta["acq_id"], date=meta["time"][:10], time=meta["time"], track=meta["track"] + meta["direction"],
                   pol=meta["main_pol"], obj=rp.label, lon=lon, lat=lat, x=x, y=y,
                   area_km2=area, log_area=np.log10(area),
                   compactness=4 * np.pi * rp.area / max(rp.perimeter, 1) ** 2,
                   elongation=1 - rp.minor_axis_length / max(rp.major_axis_length, 1e-6),
                   solidity=rp.solidity, bearing_deg=bearing,
                   contrast_med_db=float(np.nanmedian(lay["delta"][obj])),
                   contrast_p10_db=float(np.nanpercentile(lay["delta"][obj], 10)),
                   cv_inside=cv_in, cv_ratio_in_out=cv_in / cv_out if cv_out else np.nan,
                   edge_step_db=float(np.nanmedian(s_db3[ring2]) - np.nanmedian(s_db3[inner_ring])) if ring2.any() and inner_ring.any() else np.nan,
                   edge_grad_db_km=float(np.nanmean(grad[edge])),
                   margin_db=float(np.nanmedian(lay["margin"][obj])),
                   dist_land_km=float(region.dist_land_km[obj].min()),
                   anom=float(np.nanmean(mk["anom"][obj])) if np.isfinite(mk["anom"][obj]).any() else np.nan)
        for det in ("M2", "M3b", "M19", "M8c"):
            row[f"det_{det}"] = bool(mk[det][obj].mean() >= 0.1)
        row["n_detectors"] = sum(row[f"det_{d}"] for d in ("M2", "M3b", "M19", "M8c"))
        if "hv_delta" in lay:
            row["hv_contrast_db"] = float(np.nanmedian(lay["hv_delta"][obj]))
            row["hv_margin_db"] = float(np.nanmedian(lay["hv_margin"][obj]))
            row["depol_diff_db"] = float(np.nanmedian(lay["depol"][obj]) - np.nanmedian(lay["depol"][ring6]))
        # context: wind, rain, drift (M15), upwind origin (for M14)
        if wind is not None:
            u, v = float(wind["u10"][int(cy), int(cx)]), float(wind["v10"][int(cy), int(cx)])
            row.update(wind_ms=float(np.hypot(u, v)), wind_from_deg=float((np.degrees(np.arctan2(-u, -v)) + 360) % 360),
                       precip_3h=float(wind["precip_3h"][int(cy), int(cx)]))
            cu = cv = 0.0
            if cur is not None and np.isfinite(cur["u"][int(cy), int(cx)]):
                cu, cv = float(cur["u"][int(cy), int(cx)]), float(cur["v"][int(cy), int(cx)])
                row["current_ms"] = float(np.hypot(cu, cv))
            du, dv = cu + 0.03 * u, cv + 0.03 * v
            drift = (np.degrees(np.arctan2(du, dv)) + 360) % 360
            row["drift_bearing"] = float(drift)
            d = abs(((drift % 180) - bearing + 90) % 180 - 90)
            row["drift_misalign_deg"] = float(d) if row["elongation"] > 0.4 else np.nan
            down = np.deg2rad((row["wind_from_deg"] + 180) % 360)
            proj = XX[obj] * np.sin(down) + YY[obj] * np.cos(down)
            k = int(np.argmin(proj))
            row["origin_x"], row["origin_y"] = float(XX[obj][k]), float(YY[obj][k])
            row["origin_lon"], row["origin_lat"] = region.xy_to_lonlat(row["origin_x"], row["origin_y"])
        row["outline"] = _outline(region, obj, rp)
        rows.append(row)
    return pd.DataFrame(rows), lab


STATIC_MIN_COVER = 0.5      # other date must observe >= 50 % of the object's pixels to be compared


def persistence(objs, maps_dir, workers=1):
    """M13 per object: does the same dark feature, with the same outline, appear on the OTHER dates of the track?

    For every other date that observes >= 50 % of the object: B = union of that date's candidate objects
    touching the object A; IoU = |A & B| / |A | B| over pixels seen on both dates.
      persist_iou  = median IoU over other dates   (used by the static-feature gate)
      persist_frac = median share of A covered by candidates on other dates (descriptive only)
    Oil drifts and changes shape between 12-day passes -> IoU ~ 0. Lagoon mouths, shoals, coastal wind
    shadows repeat with nearly the same outline (UAE run: IoU 0.45-0.68; all other objects median 0).
    Coverage alone is not enough: a small slick inside an area that was a large calm patch on other
    dates has high coverage but IoU ~ 0.
    Needs maps_dir/<acq_id>.npz with 'labels' and 'sea' for every acquisition of the group."""
    jobs = [(str(maps_dir), d[["acq_id", "obj"]].copy()) for _, d in objs.groupby("group")]
    if workers > 1 and len(jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as ex:
            out = [r for rows in ex.map(_persist_group, jobs) for r in rows]
    else:
        out = [r for j in jobs for r in _persist_group(j)]
    cols = ["n_cmp_dates", "persist_iou", "persist_frac"]
    p = pd.DataFrame(out, columns=["acq_id", "obj"] + cols)
    return objs.drop(columns=[c for c in cols if c in objs]).merge(p, on=["acq_id", "obj"], how="left")


def _persist_group(args):
    """persistence() for one track/polarisation group (independent of the other groups)."""
    from pathlib import Path
    maps_dir, d = args
    maps_dir = Path(maps_dir)
    out = []
    ids = sorted(d.acq_id.unique())
    maps = {a: np.load(maps_dir / f"{a}.npz") for a in ids}
    lab = {a: maps[a]["labels"] for a in ids}
    sea = {a: maps[a]["sea"] for a in ids}
    for aid, g in d.groupby("acq_id"):
        for obj in g.obj:
            A = lab[aid] == obj
            fr, iou = [], []
            for b in ids:
                if b == aid or sea[b][A].mean() < STATIC_MIN_COVER:
                    continue
                lb = lab[b]
                hit = np.unique(lb[A & (lb > 0)])
                B = np.isin(lb, hit) if len(hit) else np.zeros_like(A)
                both = sea[aid] & sea[b]
                uni = ((A | B) & both).sum()
                iou.append((A & B & both).sum() / uni if uni else 0.0)
                fr.append(((lb > 0) & sea[b])[A].sum() / sea[b][A].sum())
            out.append(dict(acq_id=aid, obj=obj, n_cmp_dates=len(iou),
                            persist_iou=float(np.median(iou)) if iou else np.nan,
                            persist_frac=float(np.median(fr)) if fr else np.nan))
    return out
