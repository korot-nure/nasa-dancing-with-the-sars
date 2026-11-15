"""Common evaluation of pixel-level detectors on the Oman case.

Metrics (no independent ground truth exists, so they rely on controls and the known source):
- false alarms on control scenes: km² of detections per 1000 km² of valid sea
  (coast AOI: only sea >= 3 km from the shoreline, to exclude shoreline artefacts);
- plume detection on event scenes of the island AOIs: source-linked area (km²) and the
  share of event scenes where a source-linked object >= 2 km² exists;
- agreement with the baseline M2 on event scenes (IoU).
"""
import numpy as np
import pandas as pd
from scipy import ndimage

from . import config as C
from .data import land_raw, load_scene, source_linked


def eval_region(sc):
    aoi = sc["meta"]["aoi"]
    if aoi == "coast":
        res = sc["meta"]["res"]
        far = ndimage.distance_transform_edt(~land_raw(aoi)) * res >= 3000
        return sc["sea"] & far
    return sc["sea"]


def scene_metrics(method, sid, result, baseline_mask=None):
    sc = load_scene(sid)
    res = sc["meta"]["res"]
    px = (res / 1000) ** 2
    reg = eval_region(sc)
    m = result["mask"] & reg
    row = dict(method=method, scene=sid, role=sc["meta"]["role"], aoi=sc["meta"]["aoi"],
               total_km2=float(m.sum() * px), sea_km2=float(reg.sum() * px),
               per_1000km2=float(m.sum() / max(reg.sum(), 1) * 1000))
    if sc["meta"]["aoi"].startswith("island"):
        from scipy.ndimage import label
        lab, _ = label(result["mask"])
        row["source_km2"] = float(source_linked(lab, sc["meta"]["aoi"]).sum() * px)
    else:
        row["source_km2"] = np.nan
    if baseline_mask is not None:
        a, b = result["mask"] & reg, baseline_mask & reg
        u = (a | b).sum()
        row["iou_vs_M2"] = float((a & b).sum() / u) if u else np.nan
    return row


def summarize(rows):
    df = pd.DataFrame(rows)
    out = []
    for meth, g in df.groupby("method", sort=False):
        ctrl = g[g.role == "control"]
        ev_isl = g[(g.role == "event") & g.aoi.str.startswith("island")]
        out.append(dict(
            method=meth,
            fa_island_hh=float(ctrl[ctrl.aoi == "island_hh"].per_1000km2.mean()) if (ctrl.aoi == "island_hh").any() else np.nan,
            fa_island_vv=float(ctrl[ctrl.aoi == "island_vv"].per_1000km2.mean()) if (ctrl.aoi == "island_vv").any() else np.nan,
            fa_coast=float(ctrl[ctrl.aoi == "coast"].per_1000km2.mean()) if (ctrl.aoi == "coast").any() else np.nan,
            plume_detect_rate=float((ev_isl.source_km2 >= 2).mean()) if len(ev_isl) else np.nan,
            plume_km2_median=float(ev_isl.source_km2.median()) if len(ev_isl) else np.nan,
            iou_vs_M2_median=float(ev_isl.iou_vs_M2.median()) if "iou_vs_M2" in ev_isl and len(ev_isl) else np.nan,
            n_scenes=int(len(g)),
        ))
    return pd.DataFrame(out)
