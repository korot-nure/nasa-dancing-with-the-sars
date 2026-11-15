"""Oil-likeness score of candidate objects.

The supervised classifier (M8a) did not generalise on the Oman case, so the score is an
interpretable weighted evidence sum calibrated on Oman object statistics
(oman_case/results/objects.csv: POS = source-linked slicks, NEG = control-scene objects):

  evidence_f = clip((x - median_NEG) / (median_POS - median_NEG), 0, 1)
  score      = sum(w_f * evidence_f) / sum(w_f)  x  quality gates

Weights = Oman separation |AUC-0.5|*2, HV down-weighted (only 3 POS examples), detector agreement
and drift alignment get fixed moderate weights (not measurable on Oman as features).
Gates down-weight objects where a dark patch is more likely a look-alike or not interpretable.
This is a heuristic calibrated on ONE case; treat classes as a ranking for review, not as truth.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

CAL_PATH = Path(__file__).with_name("calibration_oman.json")
OMAN_OBJECTS = Path(__file__).resolve().parents[1] / "oman_case" / "results" / "objects.csv"
EVIDENCE = ["contrast_p10_db", "cv_ratio_in_out", "edge_step_db", "hv_contrast_db"]
SIM_FEATS = ["log_area", "compactness", "elongation", "solidity", "contrast_med_db", "contrast_p10_db",
             "cv_inside", "cv_ratio_in_out", "edge_step_db", "edge_grad_db_km"]
CLASS_EDGES = (0.4, 0.6)          # < 0.4 background, 0.4..0.6 possible, >= 0.6 probable
STATIC_IOU = 0.4                  # persist_iou threshold of the static-feature gate (objects.persistence)


def build_calibration():
    """Medians/separations from the Oman battery objects + library of Oman oil objects for similarity."""
    df = pd.read_csv(OMAN_OBJECTS)
    pos, neg = df[df.label == "POS"], df[df.label == "NEG"]
    from sklearn.metrics import roc_auc_score
    cal = {"features": {}, "library": {}, "scale": {}}
    for f in EVIDENCE:
        sub = df[df.label.isin(["POS", "NEG"])][[f, "label"]].dropna()
        auc = roc_auc_score((sub.label == "POS").astype(int), sub[f]) if sub.label.nunique() == 2 else 0.5
        cal["features"][f] = dict(neg=float(neg[f].median()), pos=float(pos[f].median()),
                                  sep=float(abs(auc - 0.5) * 2), n_pos=int(pos[f].notna().sum()), n_neg=int(neg[f].notna().sum()))
    cal["features"]["hv_contrast_db"]["weight_note"] = "down-weighted: only 3 POS examples"
    for f in SIM_FEATS:
        cal["scale"][f] = dict(mean=float(df[f].mean()), std=float(df[f].std()))
    cal["library"] = pos[SIM_FEATS + ["scene", "area_km2"]].round(4).to_dict("records")
    CAL_PATH.write_text(json.dumps(cal, indent=1))
    return cal


def load_calibration():
    return json.loads(CAL_PATH.read_text()) if CAL_PATH.exists() else build_calibration()


WEIGHTS = {"contrast_p10_db": None, "cv_ratio_in_out": None, "edge_step_db": None,
           "hv_contrast_db": 0.3, "agreement": 0.5, "drift": 0.3}


def score_objects(df, cal=None):
    cal = cal or load_calibration()
    df = df.copy()
    num = np.zeros(len(df))
    den = np.zeros(len(df))
    for f in EVIDENCE:
        c = cal["features"][f]
        w = WEIGHTS[f] if WEIGHTS[f] is not None else c["sep"]
        if f not in df:
            continue
        x = df[f].astype(float).values
        e = np.clip((x - c["neg"]) / (c["pos"] - c["neg"]), 0, 1)
        ok = np.isfinite(e)
        df[f"ev_{f}"] = e
        num[ok] += w * e[ok]
        den[ok] += w
    # detector agreement: share of the 4 detection layers (M2, M3b, M19, M8c) that see the object
    e = (df["n_detectors"].values - 1) / 3.0
    df["ev_agreement"] = np.clip(e, 0, 1)
    num += WEIGHTS["agreement"] * df["ev_agreement"].values
    den += WEIGHTS["agreement"]
    # drift alignment (M15): elongated objects aligned with current + 3 % wind
    if "drift_misalign_deg" in df:
        e = np.clip((60 - df["drift_misalign_deg"].astype(float).values) / 45.0, 0, 1)
        ok = np.isfinite(e)
        df["ev_drift"] = e
        num[ok] += WEIGHTS["drift"] * e[ok]
        den[ok] += WEIGHTS["drift"]
    base = num / np.maximum(den, 1e-9)
    gate = np.ones(len(df))
    flags = [[] for _ in range(len(df))]
    rules = [
        ("near_coast<2km", df["dist_land_km"].values < 2, 0.6),
        ("low_wind<3m/s", df.get("wind_ms", pd.Series(np.nan, index=df.index)).values < 3, 0.5),
        ("near_noise<1dB", df["margin_db"].values < 1, 0.5),
        ("rain>1mm", df.get("precip_3h", pd.Series(0, index=df.index)).fillna(0).values > 1, 0.6),
        ("small<2km2", df["area_km2"].values < 2, 0.8),
        # M13: same outline on most other dates of the track -> lagoon, harbour basin, wind shadow, mask error
        ("static_iou>=0.4", (df.get("persist_iou", pd.Series(np.nan, index=df.index)).values >= STATIC_IOU)
         & (df.get("n_cmp_dates", pd.Series(0, index=df.index)).fillna(0).values >= 2), 0.4),
    ]
    for name, cond, factor in rules:
        cond = np.nan_to_num(cond.astype(float), nan=0).astype(bool)
        gate[cond] *= factor
        for i in np.nonzero(cond)[0]:
            flags[i].append(name)
    df["score_raw"] = base
    df["score"] = base * gate
    df["flags"] = [",".join(f) for f in flags]
    df["class"] = np.select([df.score >= CLASS_EDGES[1], df.score >= CLASS_EDGES[0]], ["probable", "possible"], "background")
    # M8d: similarity to the Oman oil library (standardised Euclidean distance to the nearest example)
    sc = cal["scale"]
    lib = pd.DataFrame(cal["library"])
    Z = lambda frame: np.column_stack([(frame[f].astype(float) - sc[f]["mean"]) / sc[f]["std"] for f in SIM_FEATS])
    zl, zo = Z(lib), Z(df)
    zo = np.where(np.isfinite(zo), zo, 0.0)
    d = np.sqrt(((zo[:, None, :] - zl[None, :, :]) ** 2).sum(-1))
    df["oman_similarity_dist"] = d.min(1)
    df["oman_nearest"] = lib["scene"].values[d.argmin(1)]
    return df
