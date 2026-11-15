"""Object level: candidate dark objects, their features (M6 texture/edges, M7 geometry,
M9 cross-pol, M20 ancillary, M5 ambient SAR wind) and weak labels.

Weak labels (no independent ground truth exists for the Oman case):
  POS  - object on an event scene of the island AOIs that touches the 6 km circle around the
         grounded tanker (high-confidence oil);
  NEG  - any object on a control scene (before grounding / before landfall);
  UNL  - everything else (oil fragments far from the source, look-alikes, unknown).
Distance-to-source features are excluded from discrimination tests because they define POS.
"""
import numpy as np
import pandas as pd
from scipy import ndimage
from skimage import measure

from . import config as C
from . import detect as M
from .data import TO_LL, db, grid, land_raw, load_scene, meshgrid, smooth, source_distance

# liberal thresholds to obtain enough candidate objects (incl. look-alikes) for discrimination
LIBERAL = {"island_hh": dict(thr=0.5), "island_vv": dict(thr=0.6), "coast": dict(thr=0.5)}
FEATURES_SHAPE = ["area_km2", "log_area", "compactness", "elongation", "solidity", "orient_vs_wind_deg"]
FEATURES_TEXTURE = ["contrast_med_db", "contrast_p10_db", "cv_inside", "cv_ratio_in_out",
                    "edge_step_db", "edge_grad_db_km"]
FEATURES_POL = ["hv_contrast_db", "depol_diff_db"]
FEATURES_QUALITY = ["margin_noise_db", "inc_mean"]
FEATURES_ANC = ["era5_wspd", "sar_wind_ambient", "sst_anom_c", "sst_rel_c", "chl_ratio", "chl_rel", "precip_mm"]


def candidates(sid, **kw):
    sc = load_scene(sid)
    p = dict(LIBERAL[sc["meta"]["aoi"]])
    p.update(kw)
    r = M.m2_contrast(sc, thr=p["thr"], min_km2=1.0)
    return sc, r


def _ring(mask, width):
    return ndimage.binary_dilation(mask, iterations=width) & ~mask


def object_table(sid, wind_from_deg=None, u10_grid=None, sar_wind=None, anc=None):
    """Features for every liberal candidate object of a scene."""
    sc, r = candidates(sid)
    aoi, res = sc["meta"]["aoi"], sc["meta"]["res"]
    lab = r["labels"]
    delta = r["score"]
    s_lin = np.where(sc["sea"], sc["g0"], np.nan)
    s_db_sm = db(smooth(s_lin, 3))
    gy, gx = np.gradient(np.nan_to_num(s_db_sm, nan=np.nanmedian(s_db_sm)))
    grad = np.hypot(gx, gy) / (res / 1000.0)                      # dB per km
    dist_src = source_distance(aoi) / 1000.0
    land = land_raw(aoi)
    dist_land = ndimage.distance_transform_edt(~land) * res / 1000.0
    q = M.m0_quality(sc)
    hv = M.m9_crosspol(sc) if "g0_hv" in sc else None
    XX, YY = meshgrid(aoi)
    rows = []
    for rp in measure.regionprops(lab):
        obj = lab == rp.label
        inner = ndimage.binary_erosion(obj, iterations=1)
        ring2 = _ring(obj, 2) & sc["sea"]
        ring6 = _ring(obj, max(3, int(1500 / res))) & sc["sea"]
        edge = ndimage.binary_dilation(obj, iterations=1) & ~inner
        vin = s_lin[obj & np.isfinite(s_lin)]
        vout = s_lin[ring6 & np.isfinite(s_lin)]
        cv_in = float(np.std(vin) / np.mean(vin)) if vin.size > 5 else np.nan
        cv_out = float(np.std(vout) / np.mean(vout)) if vout.size > 5 else np.nan
        inner2 = ndimage.binary_erosion(obj, iterations=2)
        inner_ring = obj & ~inner2
        edge_step = float(np.nanmedian(s_db_sm[ring2]) - np.nanmedian(s_db_sm[inner_ring])) if ring2.any() and inner_ring.any() else np.nan
        orient = np.degrees(rp.orientation)        # skimage: angle between rows axis and major axis
        bearing = (90 - orient) % 180              # approx. bearing of major axis (0-180, from north)
        ow = np.nan
        if wind_from_deg is not None:
            d = abs(((wind_from_deg % 180) - bearing + 90) % 180 - 90)
            ow = float(d)
        cy, cx = rp.centroid
        lon, lat = TO_LL.transform(XX[int(cy), int(cx)], YY[int(cy), int(cx)])
        row = dict(
            scene=sid, role=sc["meta"]["role"], pol=sc["meta"]["pol"], aoi=aoi, obj=rp.label,
            lon=lon, lat=lat,
            area_km2=rp.area * (res / 1000) ** 2, log_area=np.log10(rp.area * (res / 1000) ** 2),
            perimeter_km=rp.perimeter * res / 1000,
            compactness=4 * np.pi * rp.area / max(rp.perimeter, 1) ** 2,
            elongation=1 - rp.minor_axis_length / max(rp.major_axis_length, 1e-6),
            solidity=rp.solidity, bearing_deg=bearing, orient_vs_wind_deg=ow,
            contrast_med_db=float(np.nanmedian(delta[obj])), contrast_p10_db=float(np.nanpercentile(delta[obj], 10)),
            cv_inside=cv_in, cv_ratio_in_out=cv_in / cv_out if cv_out else np.nan,
            edge_step_db=edge_step, edge_grad_db_km=float(np.nanmean(grad[edge])),
            margin_noise_db=float(np.nanmedian(q["margin_db"][obj])),
            inc_mean=float(np.nanmean(sc["inc"][obj])),
            dist_source_km=float(dist_src[obj].min()), touches_source=bool(dist_src[obj].min() < C.SOURCE_RADIUS_M / 1000),
            dist_land_km=float(dist_land[obj].min()),
        )
        if hv is not None:
            hv_in = np.nanmedian(hv["score"][obj])
            row["hv_contrast_db"] = float(hv_in)
            dep_in, dep_out = np.nanmedian(hv["depol_db"][obj]), np.nanmedian(hv["depol_db"][ring6])
            row["depol_diff_db"] = float(dep_in - dep_out)
        else:
            row["hv_contrast_db"] = np.nan
            row["depol_diff_db"] = np.nan
        row["era5_wspd"] = float(np.nanmean(u10_grid[obj])) if u10_grid is not None else np.nan
        # ambient SAR wind is taken in the ring around the object (inside, oil darkens sigma0)
        row["sar_wind_ambient"] = float(np.nanmedian(sar_wind[ring6])) if sar_wind is not None and ring6.any() else np.nan
        for k in ("sst_anom_c", "sst_rel_c", "chl_ratio", "chl_rel", "precip_mm"):
            row[k] = np.nan
        if anc:
            if anc.get("sst") is not None:
                sst = anc["sst"]
                ins, outs = np.nanmedian(sst[obj]), np.nanmedian(sst[ring6])
                row["sst_anom_c"] = float(ins - outs)                                  # local front
                row["sst_rel_c"] = float(ins - np.nanmedian(sst[sc["sea"]]))           # cold-water location
            if anc.get("chl") is not None:
                chl = anc["chl"]
                ins, outs = np.nanmedian(chl[obj]), np.nanmedian(chl[ring6])
                row["chl_ratio"] = float(ins / outs) if outs and np.isfinite(outs) else np.nan
                med = np.nanmedian(chl[sc["sea"]])
                row["chl_rel"] = float(ins / med) if med and np.isfinite(med) else np.nan
            if anc.get("precip") is not None:
                row["precip_mm"] = float(np.nanmean(anc["precip"][obj]))
        role = sc["meta"]["role"]
        if role == "event" and aoi.startswith("island") and row["touches_source"]:
            row["label"] = "POS"
        elif role == "control":
            row["label"] = "NEG"
        else:
            row["label"] = "UNL"
        rows.append(row)
    return pd.DataFrame(rows), lab


def univariate_auc(df, features, pos="POS", neg="NEG"):
    """AUC of each feature for POS vs NEG (0.5 = useless; <0.5 means the feature is lower for oil)."""
    from sklearn.metrics import roc_auc_score
    sub = df[df.label.isin([pos, neg])]
    y = (sub.label == pos).astype(int).values
    out = []
    for f in features:
        x = sub[f].values.astype(float)
        ok = np.isfinite(x)
        if ok.sum() < 6 or len(np.unique(y[ok])) < 2:
            out.append(dict(feature=f, auc=np.nan, n_pos=int(y[ok].sum()), n_neg=int((1 - y[ok]).sum())))
            continue
        auc = roc_auc_score(y[ok], x[ok])
        out.append(dict(feature=f, auc=float(auc), sep=float(abs(auc - 0.5) * 2),
                        pos_median=float(np.median(x[ok][y[ok] == 1])), neg_median=float(np.median(x[ok][y[ok] == 0])),
                        n_pos=int(y[ok].sum()), n_neg=int((1 - y[ok]).sum())))
    return pd.DataFrame(out).sort_values("sep", ascending=False, na_position="last")
