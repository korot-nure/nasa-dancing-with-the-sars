"""Uniform weak labels and leave-one-event-out (LOEO) validation of the feature complex on the
known-events set (nisar_oil/events.py, events/candidate_events.csv).

Labels (one rule for every event; the known source is used ONLY here, never by detection):
  POS  point events: object reaches within R km of the known source on an active date
       UAE: object overlaps the Sentinel-1 slick polygon of the same pass (S1 40 min after NISAR)
  NEG  every object of a twin (no oil) and every object on a control date (before the event)
  UNL  everything else (other dark objects in seep/production scenes may be oil, dates outside
       activity windows are unknown, not background)

Features = per-object detector output (radiometry, shape, detector agreement, polarimetry, wind,
drift, persistence) + scene context computed here without labels (same-date bright targets near the
object, recurrence of the object's origin on other dates, object density of the pass).

Models are trained on all events but one and applied to the held-out event:
  lr   logistic regression on standardised features (radiometry standardised within pol/mode)
  gb   shallow gradient boosting (non-linear reference)
  heur current pipeline score (weights calibrated on Oman only; not retrained)
Operating threshold per fold: false-alarm density on the TRAINING negatives = FA_TARGET
detections per 1000 km^2 of sea per pass.

  python -m nisar_oil.evaluate            -> events/results/
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
from scipy import ndimage

from .events import APPROVED, event_regions
from .region import PROJECT
from .sources import find_sources

OUT = PROJECT / "events" / "results"
S1_GEOJSON = PROJECT / "events" / "data" / "cerulean_s1_slicks_near_nisar_dates.geojson"
UAE_PAIRS = {"2026-10-21": [5302861], "2026-11-02": [5326372, 5326376]}   # NISAR 128A date -> Cerulean ids, S1 +40 min
UAE_MIN_OVERLAP = 0.3
RECUR_KM = 3.0
TARGET_CAP_KM = 20.0
FA_TARGETS = (0.1, 0.3, 1.0)
FA_TARGET = 0.3
MIN_AREA = 2.0            # objects smaller than this are not counted as detections (as in source finding)

RADIO = ["contrast_p10_db", "contrast_med_db", "cv_inside", "cv_ratio_in_out", "edge_step_db", "edge_grad_db_km", "margin_db"]
SHAPE = ["log_area", "compactness", "elongation", "solidity"]
CONTEXT = ["n_detectors", "low_wind", "high_wind", "log_dist_land", "drift_misalign_deg", "persist_iou",
           "origin_recur", "log_dist_ship", "log_dist_platform", "scene_obj_density", "is_vv", "bw5"]
FEATS = RADIO + SHAPE + CONTEXT
FEATS_HV = FEATS + ["hv_contrast_db"]
# without features whose weights reflect the composition of the event set rather than physics
# (most oil events are VV and calm, both twins mostly HH with moderate wind): polarisation, mode, wind
SUSPECT = ["is_vv", "bw5", "low_wind", "high_wind"]
FEATS_CLEAN = [f for f in FEATS if f not in SUSPECT]
MODELS = {"lr": ("lr", FEATS), "lr_clean": ("lr", FEATS_CLEAN), "lr_gated": ("lr", FEATS_CLEAN), "lr_hv": ("lr", FEATS_HV),
          "lr_calm": ("lr", FEATS_CLEAN), "gb": ("gb", FEATS), "heur": None}
CALM_AREA_KM2, CALM_WIND_MS = 100.0, 3.5     # lr_calm: a large dark area in near-calm is a calm zone, not a slick


def calm_factor(d):
    w = d["wind_ms"].astype(float).values
    return np.where((d["area_km2"].values > CALM_AREA_KM2) & (w < CALM_WIND_MS), 0.5, 1.0)
# pipeline quality gates (scoring.py rules) applied on top of the learned score in lr_gated
GATES = {"near_coast<2km": 0.6, "low_wind<3m/s": 0.5, "near_noise<1dB": 0.5, "rain>1mm": 0.6, "small<2km2": 0.8,
         "static_iou>=0.4": 0.4}


def gate_factor(flags):
    f = np.ones(len(flags))
    for i, s in enumerate(flags.fillna("").astype(str)):
        for name in s.split(","):
            f[i] *= GATES.get(name, 1.0)
    return f


# ------------------------------------------------------------------ per-event table
def _rasterize(region, geoms):
    xs, ys = region.grid
    img = Image.new("1", (len(xs), len(ys)), 0)
    m = np.zeros((len(ys), len(xs)), bool)
    for g in geoms:
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for k, ring in enumerate(poly):
                r = np.asarray(ring)
                px, py = region.to_utm.transform(r[:, 0], r[:, 1])
                pts = list(zip(((np.asarray(px) - xs[0]) / region.res).tolist(), ((ys[0] - np.asarray(py)) / region.res).tolist()))
                ri = Image.new("1", img.size, 0)
                ImageDraw.Draw(ri).polygon(pts, fill=1)
                m ^= np.array(ri, bool)
    return m


def _date_set(spec):
    """'2026-06-18;2026-06-24' or '2026-06-18..2026-10-05' -> predicate on ISO date strings."""
    if not spec:
        return lambda d: False
    if ".." in spec:
        a, b = spec.split("..")
        return lambda d: a <= d <= b
    s = set(spec.split(";"))
    return lambda d: d in s


def _active(meta):
    a, b = meta["active_start"], meta["active_end"]
    if a in ("continuous", "permanent"):
        return lambda d: True
    if len(a) == 7:                      # YYYY-MM
        a, b = a + "-01", b + "-31"
    return lambda d: a <= d <= b


def event_table(eid, region):
    out = region.out
    objs = pd.read_csv(out / "objects.csv")
    acq = pd.read_csv(out / "acquisitions.csv")
    tg = pd.read_csv(out / "bright_targets.csv") if (out / "bright_targets.csv").exists() else pd.DataFrame()
    maps_dir = region.root / "maps"
    meta = region.extra
    XX, YY = region.mesh()
    dsrc = None
    if region.known_source:
        kx, ky = region.lonlat_to_xy(*region.known_source)
        dsrc = np.hypot(XX - kx, YY - ky) / 1000
    s1 = {}
    if eid == "uae_gem2_2026":
        fc = json.loads(S1_GEOJSON.read_text())["features"]
        for d, ids in UAE_PAIRS.items():
            g = [f["geometry"] for f in fc if f["properties"]["cerulean_id"] in ids]
            s1[d] = ndimage.binary_dilation(_rasterize(region, g), iterations=int(500 / region.res))
    rows = []
    for aid, g in objs.groupby("acq_id"):
        m = np.load(maps_dir / f"{aid}.npz")
        lab = m["labels"]
        idx = g.obj.values
        extra = pd.DataFrame({"acq_id": aid, "obj": idx})
        extra["d_src_km"] = ndimage.minimum(dsrc, lab, idx) if dsrc is not None else np.nan
        t = tg[tg.acq_id == aid] if len(tg) else tg
        for kind, col in (("offshore_transient", "dist_ship_km"), ("offshore_persistent", "dist_platform_km")):
            tt = t[t.cls == kind] if len(t) else t
            if len(tt):
                tm = np.zeros(lab.shape, bool)
                r = np.clip(((region.grid[1][0] - tt.y.values) / region.res).astype(int), 0, lab.shape[0] - 1)
                c = np.clip(((tt.x.values - region.grid[0][0]) / region.res).astype(int), 0, lab.shape[1] - 1)
                tm[r, c] = True
                dist = ndimage.distance_transform_edt(~tm) * region.res / 1000
                extra[col] = np.minimum(ndimage.minimum(dist, lab, idx), TARGET_CAP_KM)
            else:
                extra[col] = TARGET_CAP_KM
        d = g.date.iloc[0]
        if d in s1:
            inside = ndimage.mean(s1[d].astype(float), lab, idx)
            extra["s1_overlap"] = inside
        else:
            extra["s1_overlap"] = np.nan
        rows.append(extra)
    df = objs.merge(pd.concat(rows, ignore_index=True), on=["acq_id", "obj"], how="left")
    # recurrence of the origin on other dates (chronic sources start at the same place; drifting look-alikes do not)
    big = df[(df.area_km2 >= 1) & df.origin_x.notna()]
    n_dates = max(df.date.nunique() - 1, 1)
    rec = np.full(len(df), np.nan)
    ox, oy, od = big.origin_x.values, big.origin_y.values, big.date.values
    for i, r in enumerate(df.itertuples()):
        if not np.isfinite(r.origin_x):
            continue
        near = (np.hypot(ox - r.origin_x, oy - r.origin_y) < RECUR_KM * 1000) & (od != r.date)
        rec[i] = len(np.unique(od[near])) / n_dates
    df["origin_recur"] = rec
    dens = df.groupby("acq_id").size() / (acq.set_index("acq_id").sea_km2 / 1000)
    df["scene_obj_density"] = df.acq_id.map(dens)
    df = df.merge(acq[["acq_id", "bw", "sea_km2"]], on="acq_id", how="left")
    # labels
    act, ctrl = _active(meta), _date_set(meta.get("control_dates", ""))
    R = meta.get("source_radius_km")
    lab = np.full(len(df), "UNL", dtype=object)
    if str(meta["event_type"]).startswith("twin"):
        lab[:] = "NEG"
    else:
        is_ctrl = df.date.map(ctrl).values
        lab[is_ctrl] = "NEG"
        if eid == "uae_gem2_2026":
            pos = (df.s1_overlap >= UAE_MIN_OVERLAP).values
        else:
            pos = (df.d_src_km <= R).values & df.date.map(act).values
        lab[pos & ~is_ctrl] = "POS"
    df["label"] = lab
    df["event"] = eid
    df["event_type"] = meta["event_type"]
    acq = acq.assign(event=eid, is_neg_pass=[str(meta["event_type"]).startswith("twin") or ctrl(d) for d in acq.time.str[:10]])
    return df, acq


def features(df):
    f = df.copy()
    w = f["wind_ms"].astype(float)
    f["low_wind"] = np.clip(3 - w, 0, None)
    f["high_wind"] = np.clip(w - 10, 0, None)
    f["log_dist_land"] = np.log1p(f["dist_land_km"].clip(upper=50))
    f["log_dist_ship"] = np.log1p(f["dist_ship_km"])
    f["log_dist_platform"] = np.log1p(f["dist_platform_km"])
    f["is_vv"] = (f["pol"] == "VV").astype(float)
    f["bw5"] = (f["bw"] == 5).astype(float)
    f["persist_iou"] = f["persist_iou"].fillna(0)
    f["bucket"] = f["pol"] + np.where(f["bw"] == 5, "5", "")
    return f


# ------------------------------------------------------------------ models
def _prep(ref, parts, feats):
    """Impute and standardise `parts` with statistics of the training objects `ref` (all labels: unsupervised).
    Radiometry is first standardised within its pol/mode bucket (HH and VV contrasts differ by ~1 dB)."""
    ref_x = ref[feats].astype(float)
    med = ref_x.median()
    out = [p[feats].astype(float).fillna(med) for p in parts]
    ref_x = ref_x.fillna(med)
    for c in feats:
        if c not in RADIO + ["hv_contrast_db"]:
            continue
        for b in ref.bucket.unique():
            mr = (ref.bucket == b).values
            mu, sd = ref_x.loc[mr, c].mean(), ref_x.loc[mr, c].std() or 1.0
            ref_x.loc[mr, c] = (ref_x.loc[mr, c] - mu) / sd
            for p, x in zip(parts, out):
                m = (p.bucket == b).values
                x.loc[m, c] = (x.loc[m, c] - mu) / sd
        for p, x in zip(parts, out):          # bucket unseen in training: standardise on its own objects
            m = ~p.bucket.isin(ref.bucket.unique()).values
            if m.any():
                mu, sd = x.loc[m, c].mean(), x.loc[m, c].std() or 1.0
                x.loc[m, c] = (x.loc[m, c] - mu) / sd
    mu, sd = ref_x.mean(), ref_x.std().replace(0, 1)
    return [((x - mu) / sd).values for x in out]


def _weights(lbl, ev):
    """Each (event, label) group gets the same total weight: no event or class dominates."""
    k = pd.Series(list(zip(ev, lbl)))
    return (1.0 / k.map(k.value_counts())).values


def fit_predict(train, test, kind, feats):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    trl = train[train.label.isin(["POS", "NEG"])]
    Xtr, Xte = _prep(train, [trl, test], feats)
    y = (trl.label == "POS").astype(int).values
    w = _weights(trl.label.values, trl.event.values)
    if kind == "lr":
        m = LogisticRegression(C=0.3, max_iter=2000).fit(Xtr, y, sample_weight=w)
        return m.predict_proba(Xte)[:, 1], dict(zip(feats, m.coef_[0]))
    m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, l2_regularization=1.0)
    m.fit(Xtr, y, sample_weight=w)
    return m.predict_proba(Xte)[:, 1], None


def threshold_for_fa(p, df, acq, fa):
    """Lowest threshold whose detection density on negative passes is <= fa per 1000 km^2 per pass."""
    neg = df.label.values == "NEG"
    neg_passes = acq[acq.is_neg_pass]
    area = neg_passes.sea_km2.sum() / 1000
    if area == 0:
        return 0.5
    big = df.area_km2.values >= MIN_AREA
    s = np.sort(p[neg & big])[::-1]
    k = int(np.floor(fa * area))              # allowed number of false detections
    return float(s[k]) + 1e-9 if k < len(s) else 0.0


# ------------------------------------------------------------------ evaluation of one held-out event
def _quicklook_dates(row):
    import re
    txt = str(row.get("nisar_quicklook", ""))
    return {f"2026-{m}" for m in re.findall(r"\b(\d\d-\d\d)\b", txt)}


def eval_event(eid, region, test, acq_e, p, thr, ql):
    t = test.assign(p=p)
    det = (t.p >= thr) & (t.area_km2 >= MIN_AREA)
    res = dict(event=eid, thr=thr, n_obj=len(t), n_pos=int((t.label == "POS").sum()), n_neg=int((t.label == "NEG").sum()))
    neg_pass = acq_e[acq_e.is_neg_pass]
    if len(neg_pass):
        a = neg_pass.sea_km2.sum() / 1000
        res["fa_per_1000km2_pass"] = float((det & (t.label == "NEG")).sum() / a)
        res["n_neg_passes"] = len(neg_pass)
    if res["n_pos"]:
        pos = t.label == "POS"
        res["pos_recall"] = float((det & pos).sum() / pos.sum())
        dates_pos = sorted(t[pos].date.unique())
        dates_det = sorted(t[pos & det].date.unique())
        res["pos_dates"] = len(dates_pos)
        res["pos_dates_detected"] = len(dates_det)
        if ql:
            act_dates = set(acq_e.time.str[:10])
            qd = sorted(ql & act_dates)
            res["ql_dates"] = len(qd)
            res["ql_dates_detected"] = len(set(dates_det) & set(qd))
            res["det_dates_not_ql"] = len(set(dates_det) - set(qd))
        far = (t.d_src_km > 10) if t.d_src_km.notna().any() else (t.label == "UNL")
        sub = t[pos | (far & (t.label != "NEG"))]
        if sub.label.nunique() == 2 and (sub.label == "POS").sum() >= 2:
            from sklearn.metrics import roc_auc_score
            res["auc_pos_vs_scene"] = float(roc_auc_score((sub.label == "POS").astype(int), sub.p))
        if t.d_src_km.notna().any():
            area_all = acq_e.sea_km2.sum() / 1000
            res["other_det_per_1000km2_pass"] = float((det & far).sum() / area_all)
    # source finding with the model score
    s, _ = find_sources(t.assign(score=t.p), region, min_score=thr, min_area=MIN_AREA)
    res["n_sources"] = len(s)
    if len(s) and region.known_source:
        kx, ky = region.lonlat_to_xy(*region.known_source)
        d = np.hypot(s.x - kx, s.y - ky) / 1000
        R = region.extra.get("source_radius_km") or 3
        ok = d <= R + 5
        res["src_found"] = bool(ok.any())
        res["src_rank"] = int(s["rank"][ok].min()) if ok.any() else None
        res["src_dist_km"] = float(d[ok].min()) if ok.any() else float(d.min())
    return res


# ------------------------------------------------------------------ main
def _table_job(eid):
    from .events import event_region
    return event_table(eid, event_region(eid))


def build_dataset(ids=None):
    """Per-event tables in parallel (one process per event: maps of every acquisition are read)."""
    from concurrent.futures import ProcessPoolExecutor
    regs = event_regions(ids)
    ready = [e for e, r in regs.items() if (r.out / "objects.csv").exists()]
    for e in set(regs) - set(ready):
        print(f"skip {e}: no pipeline output")
    with ProcessPoolExecutor(max_workers=min(len(ready), 9)) as ex:
        res = list(ex.map(_table_job, ready))
    tabs, acqs = [r[0] for r in res], [r[1] for r in res]
    return regs, features(pd.concat(tabs, ignore_index=True)), pd.concat(acqs, ignore_index=True)


def loeo(regs, df, acq, rows_csv):
    preds = []
    results = []
    coefs = []
    for eid in df.event.unique():
        tr, te = df[df.event != eid], df[df.event == eid]
        acq_tr, acq_te = acq[acq.event != eid], acq[acq.event == eid]
        ql = _quicklook_dates(rows_csv.get(eid, {}))
        for kind in MODELS:
            if kind == "heur":
                p_tr, p_te = tr.score.values, te.score.values
            else:
                algo, feats = MODELS[kind]
                p_te, coef = fit_predict(tr, te, algo, feats)
                p_tr, _ = fit_predict(tr, tr, algo, feats)
                if kind == "lr_gated":
                    p_te, p_tr = p_te * gate_factor(te["flags"]), p_tr * gate_factor(tr["flags"])
                if kind == "lr_calm":
                    p_te, p_tr = p_te * calm_factor(te), p_tr * calm_factor(tr)
                if coef:
                    coefs.append(dict(model=kind, held_out=eid, **coef))
            thrs = {}
            for fa in FA_TARGETS:
                thr = threshold_for_fa(p_tr, tr, acq_tr, fa)
                thrs[f"thr_fa{fa}"] = thr
                r = eval_event(eid, regs[eid], te, acq_te, p_te, thr, ql)
                results.append(dict(model=kind, fa_target=fa, **r))
            preds.append(te[["event", "acq_id", "obj", "label"]].assign(model=kind, p=p_te, **thrs))
    return pd.DataFrame(results), pd.concat(preds, ignore_index=True), pd.DataFrame(coefs)


def pooled_auc(preds):
    from sklearn.metrics import roc_auc_score
    out = {}
    for m, g in preds[preds.label.isin(["POS", "NEG"])].groupby("model"):
        out[m] = float(roc_auc_score((g.label == "POS").astype(int), g.p))
    return out


def single_feature_auc(df):
    from sklearn.metrics import roc_auc_score
    d = df[df.label.isin(["POS", "NEG"])]
    y = (d.label == "POS").astype(int)
    rows = []
    for f in FEATS_HV + ["score"]:
        x = d[f].astype(float)
        ok = x.notna()
        if ok.sum() < 20 or y[ok].nunique() < 2:
            continue
        auc = roc_auc_score(y[ok], x[ok])
        rows.append(dict(feature=f, auc=auc, n=int(ok.sum())))
    return pd.DataFrame(rows).assign(sep=lambda t: (t.auc - 0.5).abs() * 2).sort_values("sep", ascending=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args()
    import csv
    rows_csv = {r["id"]: r for r in csv.DictReader(open(PROJECT / "events" / "candidate_events.csv"))}
    OUT.mkdir(parents=True, exist_ok=True)
    regs, df, acq = build_dataset(a.ids or None)
    df.drop(columns=["outline"], errors="ignore").to_csv(OUT / "objects_labelled.csv", index=False)
    acq.to_csv(OUT / "acquisitions_all.csv", index=False)
    summary = df.groupby(["event", "label"]).size().unstack(fill_value=0)
    print(summary)
    res, preds, coefs = loeo(regs, df, acq, rows_csv)
    res.to_csv(OUT / "loeo_results.csv", index=False)
    preds.to_csv(OUT / "loeo_predictions.csv", index=False)
    coefs.to_csv(OUT / "loeo_lr_coefficients.csv", index=False)
    sf = single_feature_auc(df)
    sf.to_csv(OUT / "single_feature_auc.csv", index=False)
    pa = pooled_auc(preds)
    (OUT / "pooled_auc.json").write_text(json.dumps(pa, indent=1))
    print("pooled LOEO AUC:", pa)
    # final transparent model on all events (coefficients of standardised features)
    _, coef = fit_predict(df, df.head(1), "lr", FEATS_CLEAN)
    (OUT / "lr_all_events_coefficients.json").write_text(json.dumps({k: round(float(v), 4) for k, v in
                                                                     sorted(coef.items(), key=lambda kv: -abs(kv[1]))}, indent=1))
    print(res[res.fa_target == FA_TARGET].to_string())


if __name__ == "__main__":
    main()
