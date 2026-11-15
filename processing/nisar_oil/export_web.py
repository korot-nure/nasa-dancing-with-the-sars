"""Export a processed region into the web data package of docs/API_CONTRACT.md (version 1.2).

Inputs are the outputs of a pipeline run (runs/<region>/: acquisitions/, maps/, output/) plus a hand-written
location spec (title, description, which acquisitions become timeline snapshots, the 'before' acquisition of
the same track and polarisation for each, manual labels and notes).

Output (out_dir):
  data/locations/<id>/  before_<track>_<pol>.webp, after_<step>.webp, mask_<step>.webp,
                        contour_<step>.geojson, targets_<step>.geojson, sources.geojson, meta.json
  mock/                 locations.json (GET /locations), <id>.json (GET /locations/<id>),
                        <id>/contour_<step>.geojson, <id>/targets_<step>.geojson, <id>/sources.geojson

Rasters: resampled from the region UTM grid onto a grid that is regular in EPSG:3857 inside the EPSG:4326
bbox (what L.imageOverlay expects), same W x H for all rasters of a location; brightness 2-98 % percentiles
per track/polarisation pair; NaN (no data, land) -> alpha 0. Mask: class 'probable' only, #ef4444 / alpha 0.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage

from .detect import db, smooth
from .ingest import load_acquisition

R_EARTH = 6378137.0
MASK_RGBA = (239, 68, 68, 255)
FLAG_MAP = {"near_coast<2km": "near_coast", "low_wind<3m/s": "low_wind", "near_noise<1dB": "near_noise",
            "rain>1mm": "rain", "small<2km2": "small", "static_iou>=0.4": "static"}
TARGET_KIND = {"offshore_transient": "ship", "offshore_persistent": "platform", "coastal": "coastal"}


def _merc(lon, lat):
    return R_EARTH * np.radians(lon), R_EARTH * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def _inv_merc(x, y):
    return np.degrees(x / R_EARTH), np.degrees(2 * np.arctan(np.exp(y / R_EARTH)) - np.pi / 2)


def web_grid(region, max_px=1200):
    """Pixel centres of a grid regular in EPSG:3857 over region.bbox, as fractional (row, col) of the region grid."""
    lon0, lat0, lon1, lat1 = region.bbox
    x0, y0 = _merc(lon0, lat0)
    x1, y1 = _merc(lon1, lat1)
    if (x1 - x0) >= (y1 - y0):
        W = max_px
        H = int(round(max_px * (y1 - y0) / (x1 - x0)))
    else:
        H = max_px
        W = int(round(max_px * (x1 - x0) / (y1 - y0)))
    mx = x0 + (np.arange(W) + 0.5) * (x1 - x0) / W
    my = y1 - (np.arange(H) + 0.5) * (y1 - y0) / H              # row 0 = north
    MX, MY = np.meshgrid(mx, my)
    lon, lat = _inv_merc(MX, MY)
    ux, uy = region.lonlat_to_xy(lon, lat)
    ux, uy = np.asarray(ux), np.asarray(uy)
    xs, ys = region.grid
    col = (ux - xs[0]) / region.res
    row = (ys[0] - uy) / region.res
    px_m = (x1 - x0) / W * math.cos(math.radians((lat0 + lat1) / 2))   # ground size of an output pixel
    return np.stack([row, col]), (H, W), px_m, (ux, uy)


# ------------------------------------------------------------------ reference slicks of a known event
def reference_slicks(scene_id, epsg):
    """Source-linked slicks of a known event from the Oman method battery (oman_case/battery): the battery's
    main M2 detector with its default thresholds (HH 0.8 dB k5, VV 1.0 dB k3, >= 2 km2; the source-linked
    areas of the report table), components touching the 6 km circle around the known source.
    Used to fill dates on which the automatic pipeline misses the event (early chronic leak).
    Score and flags: pipeline formula applied to the battery features of the liberal candidate object
    (oman_case/results/objects.csv) that contains the slick."""
    import sys
    from skimage import measure
    case = Path(__file__).resolve().parents[1] / "oman_case"
    if str(case) not in sys.path:
        sys.path.insert(0, str(case))
    from battery import config as BC, data as BD, detect as BM, objects as BO
    from .scoring import score_objects
    if BC.EPSG != epsg:
        raise ValueError(f"battery grid EPSG {BC.EPSG} != region EPSG {epsg}")
    sc = BD.load_scene(scene_id)
    aoi = sc["meta"]["aoi"]
    lab = BM.m2_contrast(sc)["labels"]
    ids = np.unique(lab[(BD.source_distance(aoi) < BC.SOURCE_RADIUS_M) & (lab > 0)])
    ids = ids[ids > 0]
    xs, ys, res = BD.grid(aoi)
    _, rl = BO.candidates(scene_id)                       # liberal candidates = battery objects (features)
    lab_lib = rl["labels"]
    feats = pd.read_csv(case / "results" / "objects.csv")
    f = feats[feats.scene == scene_id].copy()
    f = f.rename(columns={"era5_wspd": "wind_ms", "margin_noise_db": "margin_db", "precip_mm": "precip_3h"})
    f["n_detectors"] = 1
    f = score_objects(f) if len(f) else f
    slicks = []
    for oid in ids:
        obj = lab == oid
        hit = lab_lib[obj]
        hit = hit[hit > 0]
        row = f[f.obj == np.bincount(hit).argmax()] if hit.size else f.iloc[:0]
        rr, cc = np.nonzero(obj)
        r0, c0 = rr.min(), cc.min()
        crop = np.pad(obj[r0:rr.max() + 1, c0:cc.max() + 1], 1)
        cs = measure.find_contours(crop.astype(float), 0.5)
        if not cs:
            continue
        c = max(cs, key=len)
        c = c[:: max(1, len(c) // 150)]
        lon, lat = BD.TO_LL.transform(xs[0] + (c[:, 1] - 1 + c0) * res, ys[0] - (c[:, 0] - 1 + r0) * res)
        slicks.append(dict(obj=int(oid), area_km2=float(obj.sum() * (res / 1000) ** 2),
                           score=float(row.score.iloc[0]) if len(row) else np.nan,
                           flags=str(row["flags"].iloc[0]) if len(row) else "",
                           ring=list(zip(np.asarray(lon).tolist(), np.asarray(lat).tolist()))))
    return dict(labels=lab, ids=ids, xs=xs, ys=ys, res=res, slicks=slicks)


def _flags(s):
    return [FLAG_MAP[f] for f in s.split(",") if f in FLAG_MAP] if isinstance(s, str) else []


def _sample(a, rc, order=0, cval=np.nan):
    return ndimage.map_coordinates(a, rc, order=order, mode="constant", cval=cval)


def _radar_db(region, acq_id, px_m):
    """Smoothed gamma0 (dB) of the acquisition; NaN outside data and on land (Natural Earth, no buffer)."""
    a = load_acquisition(region, acq_id)
    lin = np.where(np.isfinite(a["g0"]) & (a["g0"] > 0) & ~region.land, a["g0"], np.nan)
    k = max(1, int(round(px_m / region.res)))
    return db(smooth(lin, k) if k > 1 else lin), a["meta"]


def _gray_rgba(dbimg, lo, hi):
    v = np.clip((dbimg - lo) / (hi - lo), 0, 1)
    g = np.nan_to_num(v * 255, nan=0).astype(np.uint8)
    alpha = np.where(np.isfinite(dbimg), 255, 0).astype(np.uint8)
    return np.dstack([g, g, g, alpha])


def _save_webp(rgba, path):
    Image.fromarray(rgba, "RGBA").save(path, "WEBP", lossless=True, exact=True)


def _feature_collection(feats):
    return {"type": "FeatureCollection", "features": feats}


def _close_ring(ring):
    ring = [[round(float(x), 5), round(float(y), 5)] for x, y in ring]
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def export_location(region, spec, out_dir, max_px=1200, objs=None, srcs=None):
    """spec: dict(id, title, description, source_url, known_source (lon, lat) or None, known_source_label,
                  snapshots=[dict(acq_id, before, label, note)])"""
    loc_id = spec["id"]
    out_dir = Path(out_dir)
    data_dir = out_dir / "data" / "locations" / loc_id
    mock_dir = out_dir / "mock"
    (mock_dir / loc_id).mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    run_out = region.out
    objs = pd.read_csv(run_out / "objects.csv") if objs is None else objs      # objs/srcs: alternative scoring
    outlines = {(f["properties"]["acq_id"], int(f["properties"]["obj"])): f["geometry"]["coordinates"][0]
                for f in json.loads((run_out / "objects.geojson").read_text())["features"]}
    targets = pd.read_csv(run_out / "bright_targets.csv") if (run_out / "bright_targets.csv").exists() else pd.DataFrame()
    if srcs is None:
        srcs = pd.read_csv(run_out / "sources.csv") if (run_out / "sources.csv").exists() else pd.DataFrame()
    rc, (H, W), px_m, (ux, uy) = web_grid(region, max_px)

    # radar rasters on the web grid
    radar = {}
    for aid in {s["acq_id"] for s in spec["snapshots"]} | {s["before"] for s in spec["snapshots"]}:
        dbimg, meta = _radar_db(region, aid, px_m)
        radar[aid] = (_sample(dbimg, rc), meta)

    def track_pol(aid):
        m = radar[aid][1]
        return f"{m['track']}{m['direction']}", m["main_pol"]

    # brightness scale per track/polarisation pair: before + all afters of that track
    pairs = {}
    for s in spec["snapshots"]:
        tp = track_pol(s["acq_id"])
        if track_pol(s["before"]) != tp:
            raise ValueError(f"before {s['before']} is not the same track/polarisation as {s['acq_id']}")
        pairs.setdefault(tp, {"before": s["before"], "afters": []})["afters"].append(s["acq_id"])
    scale = {}
    for tp, p in pairs.items():
        vals = np.concatenate([radar[a][0][np.isfinite(radar[a][0])] for a in [p["before"]] + p["afters"]])
        scale[tp] = (float(np.percentile(vals, 2)), float(np.percentile(vals, 98)))
        before_name = f"before_{tp[0]}_{tp[1]}.webp"
        _save_webp(_gray_rgba(radar[p["before"]][0], *scale[tp]), data_dir / before_name)

    snaps = []
    base = f"/data/locations/{loc_id}"
    api = f"/api/v1/locations/{loc_id}"
    for i, s in enumerate(sorted(spec["snapshots"], key=lambda s: radar[s["acq_id"]][1]["time"]), start=1):
        step = f"t{i}"
        aid = s["acq_id"]
        tp = track_pol(aid)
        meta = radar[aid][1]
        _save_webp(_gray_rgba(radar[aid][0], *scale[tp]), data_dir / f"after_{step}.webp")
        # mask: probable objects of this acquisition
        o = objs[objs.acq_id == aid]
        prob_ids = o[o["class"] == "probable"].obj.values
        labels = np.load(region.root / "maps" / f"{aid}.npz")["labels"]
        m = _sample(np.isin(labels, prob_ids).astype(np.float32), rc, cval=0) > 0.5
        ref = reference_slicks(s["reference"], region.epsg) if s.get("reference") else None
        if ref is not None:
            rrc = np.stack([(ref["ys"][0] - uy) / ref["res"], (ux - ref["xs"][0]) / ref["res"]])
            m |= _sample(np.isin(ref["labels"], ref["ids"]).astype(np.float32), rrc, cval=0) > 0.5
        mask = np.zeros((H, W, 4), np.uint8)
        mask[m] = MASK_RGBA
        _save_webp(mask, data_dir / f"mask_{step}.webp")
        # contours: one feature per probable/possible slick
        feats = []
        for r in o[o["class"].isin(["probable", "possible"])].sort_values("score", ascending=False).itertuples():
            ring = outlines.get((aid, int(r.obj)))
            if not ring:
                continue
            feats.append({"type": "Feature",
                          "properties": {"location_id": loc_id, "step_id": step, "slick_id": f"{step}-{int(r.obj):02d}",
                                         "area_km2": round(float(r.area_km2), 1), "class": o.loc[r.Index, "class"],
                                         "score": round(float(r.score), 2), "flags": _flags(r.flags), "origin": "pipeline"},
                          "geometry": {"type": "Polygon", "coordinates": [_close_ring(ring)]}})
        ref_area = 0.0
        for sl in (ref["slicks"] if ref is not None else []):
            ref_area += sl["area_km2"]
            feats.append({"type": "Feature",
                          "properties": {"location_id": loc_id, "step_id": step, "slick_id": f"{step}-r{sl['obj']:02d}",
                                         "area_km2": round(sl["area_km2"], 1), "class": "probable",
                                         "score": round(sl["score"], 2) if np.isfinite(sl["score"]) else None,
                                         "flags": _flags(sl["flags"]), "origin": "reference"},
                          "geometry": {"type": "Polygon", "coordinates": [_close_ring(sl["ring"])]}})
        (data_dir / f"contour_{step}.geojson").write_text(json.dumps(_feature_collection(feats), ensure_ascii=False))
        # bright targets of this acquisition
        tfeats = []
        if len(targets):
            for t in targets[targets.acq_id == aid].itertuples():
                tfeats.append({"type": "Feature",
                               "properties": {"kind": TARGET_KIND.get(t.cls, "ship"), "snr_db": round(float(t.snr_db), 1),
                                              "date": str(t.date)[:10]},
                               "geometry": {"type": "Point", "coordinates": [round(float(t.lon), 5), round(float(t.lat), 5)]}})
        (data_dir / f"targets_{step}.geojson").write_text(json.dumps(_feature_collection(tfeats), ensure_ascii=False))
        area = float(o[o["class"] == "probable"].area_km2.sum()) + ref_area
        bmeta = radar[s["before"]][1]
        snaps.append({
            "step_id": step, "date": meta["time"][:10], "track": tp[0], "polarization": tp[1],
            "before_url": f"{base}/before_{tp[0]}_{tp[1]}.webp", "before_date": bmeta["time"][:10],
            "label": s["label"], "label_source": "manual", "note": s.get("note"),
            "area_km2": round(area, 1),
            "after_url": f"{base}/after_{step}.webp", "mask_url": f"{base}/mask_{step}.webp",
            "contour_geojson_url": f"{api}/snapshots/{step}/contour.geojson",
            "targets_geojson_url": f"{api}/snapshots/{step}/targets.geojson"})

    # sources: detected (M14) + known
    sfeats = []
    for r in srcs.itertuples() if len(srcs) else []:
        d = float(r.dist_known_source_km) if "dist_known_source_km" in srcs and np.isfinite(r.dist_known_source_km) else None
        lbl = f"Знайдене джерело №{int(r.rank)}: {int(r.n_dates)} дат" + (f", {d:.1f} км від відомого джерела".replace(".", ",") if d is not None else "")
        sfeats.append({"type": "Feature",
                       "properties": {"kind": "detected", "rank": int(r.rank), "n_dates": int(r.n_dates),
                                      "first_date": str(r.first)[:10], "last_date": str(r.last)[:10],
                                      "dist_known_km": round(d, 1) if d is not None else None, "label": lbl},
                       "geometry": {"type": "Point", "coordinates": [round(float(r.lon), 5), round(float(r.lat), 5)]}})
    if spec.get("known_source"):
        sfeats.append({"type": "Feature",
                       "properties": {"kind": "known", "rank": None, "n_dates": None, "first_date": None, "last_date": None,
                                      "dist_known_km": None, "label": spec.get("known_source_label", "Відоме джерело")},
                       "geometry": {"type": "Point", "coordinates": list(spec["known_source"])}})
    (data_dir / "sources.geojson").write_text(json.dumps(_feature_collection(sfeats), ensure_ascii=False))

    lon0, lat0, lon1, lat1 = region.bbox
    coords = list(spec["known_source"]) if spec.get("known_source") else [round((lon0 + lon1) / 2, 4), round((lat0 + lat1) / 2, 4)]
    detail = {"id": loc_id, "title": spec["title"], "coords": coords, "bbox": [lon0, lat0, lon1, lat1],
              "baseline_date": snaps[0]["before_date"], "baseline_before_url": snaps[0]["before_url"],
              "description": spec["description"], "source_url": spec.get("source_url"),
              "sources_geojson_url": f"{api}/sources.geojson" if sfeats else None,
              "snapshots": snaps}
    (data_dir / "meta.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2))
    summary = {"id": loc_id, "title": spec["title"], "coords": coords, "baseline_date": detail["baseline_date"],
               "latest_date": snaps[-1]["date"], "area_km2": snaps[-1]["area_km2"]}
    # mocks for the frontend (frontend/public/mock/)
    lst_path = mock_dir / "locations.json"
    lst = json.loads(lst_path.read_text()) if lst_path.exists() else {"total": 0, "locations": []}
    lst["locations"] = [l for l in lst["locations"] if l["id"] != loc_id] + [summary]
    lst["total"] = len(lst["locations"])
    lst_path.write_text(json.dumps(lst, ensure_ascii=False, indent=2))
    (mock_dir / f"{loc_id}.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2))
    for f in data_dir.glob("*.geojson"):
        (mock_dir / loc_id / f.name).write_text(f.read_text())
    return detail, (H, W)


def main():
    import argparse
    from .region import Region
    from .web_specs import SPECS
    ap = argparse.ArgumentParser(description="Export a processed region into the web data package (API contract 1.2)")
    ap.add_argument("spec", choices=sorted(SPECS))
    ap.add_argument("--out", default="frontend_data")
    ap.add_argument("--max-px", type=int, default=1200)
    a = ap.parse_args()
    spec = SPECS[a.spec]
    spec = spec() if callable(spec) else spec      # known-event specs are built from the run outputs
    detail, (H, W) = export_location(Region.load(spec["region"]), spec, a.out, a.max_px)
    print(f"{detail['id']}: {len(detail['snapshots'])} snapshots, rasters {W}x{H} -> {a.out}")


if __name__ == "__main__":
    main()
