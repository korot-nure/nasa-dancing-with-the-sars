"""M8: machine-learning variants on the Oman case.

M8a  classifier on object features (random forest), leave-one-scene-out (LOSO) evaluation
M8b  CNN segmentation transferred from Sentinel-1 datasets  -> not run (no training data here)
M8c  unsupervised anomaly detection on 1 km blocks (isolation forest trained on control scenes)
M8d  similarity search: rank all objects by feature distance to a known oil object
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from . import config as C
from . import detect as M
from .data import db, load_scene, smooth


def _xy(df, features):
    X = df[features].astype(float).values
    med = np.nanmedian(X, axis=0)
    X = np.where(np.isfinite(X), X, med)
    return X


# ------------------------------------------------------------------------- M8a
def m8a_classifier(df, features, seed=0):
    lab = df[df.label.isin(["POS", "NEG"])].copy()
    scenes = lab.scene.unique()
    oof = pd.Series(np.nan, index=lab.index)
    for s in scenes:
        tr, te = lab[lab.scene != s], lab[lab.scene == s]
        if tr.label.nunique() < 2:
            continue
        clf = RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=2,
                                     class_weight="balanced", random_state=seed)
        clf.fit(_xy(tr, features), (tr.label == "POS").astype(int))
        oof.loc[te.index] = clf.predict_proba(_xy(te, features))[:, 1]
    y = (lab.label == "POS").astype(int)
    auc = roc_auc_score(y, oof) if oof.notna().all() else np.nan
    clf = RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=2,
                                 class_weight="balanced", random_state=seed).fit(_xy(lab, features), y)
    imp = pd.Series(clf.feature_importances_, index=features).sort_values(ascending=False)
    unl = df[df.label == "UNL"].copy()
    unl["p_oil"] = clf.predict_proba(_xy(unl, features))[:, 1]
    lab["p_oil_oof"] = oof
    return {"auc_loso": float(auc), "importance": imp, "labelled": lab, "unlabelled": unl, "model": clf}


# ------------------------------------------------------------------------- M8c
def block_features(sid, block_m=1000):
    """Per-block features (~1 km): mean/p10 local contrast, texture (std of dB), gradient."""
    sc = load_scene(sid)
    res = sc["meta"]["res"]
    B = max(4, int(round(block_m / res)))
    r = M.m2_contrast(sc)
    delta = r["score"]
    s_db = db(smooth(np.where(sc["sea"], sc["g0"], np.nan), 3))
    gy, gx = np.gradient(np.nan_to_num(s_db, nan=np.nanmedian(s_db)))
    grad = np.hypot(gx, gy)
    ny, nx = delta.shape[0] // B, delta.shape[1] // B
    rows = []
    for i in range(ny):
        for j in range(nx):
            sl = (slice(i * B, (i + 1) * B), slice(j * B, (j + 1) * B))
            sea = sc["sea"][sl]
            if sea.mean() < 0.9:
                continue
            d = delta[sl][sea]
            rows.append(dict(scene=sid, i=i, j=j, B=B,
                             d_mean=np.nanmean(d), d_p10=np.nanpercentile(d, 10),
                             tex=np.nanstd(s_db[sl][sea]), grad=np.nanmean(grad[sl][sea]),
                             in_strict=float(r["mask"][sl][sea].mean())))
    return pd.DataFrame(rows)


def m8c_anomaly(train_scenes, test_scenes, source_masks, seed=0):
    """Isolation forest trained on half of the control blocks; evaluated on the other half
    (negatives) vs blocks inside the strict source-linked slick (positives)."""
    feats = ["d_mean", "d_p10", "tex", "grad"]
    tr_all = pd.concat([block_features(s) for s in train_scenes], ignore_index=True)
    rng = np.random.default_rng(seed)
    half = rng.random(len(tr_all)) < 0.5
    model = IsolationForest(n_estimators=300, random_state=seed).fit(tr_all[half][feats].values)
    neg = tr_all[~half].copy()
    neg["anom"] = -model.score_samples(neg[feats].values)
    test = pd.concat([block_features(s) for s in test_scenes], ignore_index=True)
    test["anom"] = -model.score_samples(test[feats].values)
    pos_rows = []
    for s, m in source_masks.items():
        t = test[test.scene == s]
        for idx, row in t.iterrows():
            B = int(row.B)
            if m[int(row.i) * B:(int(row.i) + 1) * B, int(row.j) * B:(int(row.j) + 1) * B].mean() > 0.5:
                pos_rows.append(idx)
    pos = test.loc[pos_rows]
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    sc = np.r_[pos.anom.values, neg.anom.values]
    auc = roc_auc_score(y, sc) if len(pos) and len(neg) else np.nan
    thr = np.percentile(neg.anom, 99)          # 1 % false-alarm level on held-out control blocks
    test["flag"] = test.anom > thr
    return {"auc": float(auc), "n_pos_blocks": int(len(pos)), "n_neg_blocks": int(len(neg)),
            "thr_99": float(thr), "test": test, "model": model,
            "recall_at_1pct_fa": float((pos.anom > thr).mean()) if len(pos) else np.nan}


# ------------------------------------------------------------------------- M8d
def m8d_similarity(df, features, query_index, exclude_scene=True, k=(10, 20, 50)):
    X = _xy(df, features)
    Xs = StandardScaler().fit_transform(X)
    q = Xs[df.index.get_loc(query_index)]
    dist = np.sqrt(((Xs - q) ** 2).sum(axis=1))
    out = df.copy()
    out["dist"] = dist
    qscene = df.loc[query_index, "scene"]
    if exclude_scene:
        out = out[out.scene != qscene]
    out = out.sort_values("dist")
    lab = out[out.label.isin(["POS", "NEG"])]
    prec = {f"precision@{kk}_labelled": float((lab.head(kk).label == "POS").mean()) for kk in k}
    neg_rank = lab.reset_index(drop=True)
    first_neg = int(neg_rank.index[neg_rank.label == "NEG"][0]) + 1 if (neg_rank.label == "NEG").any() else None
    return {"ranked": out, "precision": prec, "first_neg_rank_among_labelled": first_neg, "query_scene": qscene}
