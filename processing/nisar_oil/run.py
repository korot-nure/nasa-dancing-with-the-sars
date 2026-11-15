"""Run the nisar_oil pipeline for a region.

Examples:
  python -m nisar_oil.run --preset uae_uaq_2026
  python -m nisar_oil.run --name my_area --bbox 54.9,25.2,56.0,26.1 --start 2026-09-15 --end 2026-11-13
Requires ~/.netrc with NASA Earthdata credentials for the first (ingest) step.
"""
import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict

import numpy as np
import pandas as pd

from . import ancillary as ANC
from . import report as REP
from .detect import calib_stats, calibrate_group, db, layers, masks, smooth
from .ingest import ingest, load_acquisition
from .objects import object_table, persistence
from .region import PRESETS, Region
from .scoring import load_calibration, score_objects
from .sources import attach_targets, bright_targets, classify_targets, event_flags, find_sources


DETECT_WORKERS = max(1, (os.cpu_count() or 2) - 2)     # detection is CPU-bound and independent per date


def _stats_job(args):
    fields, aid = args
    region = Region(**fields)
    a = load_acquisition(region, aid)
    return calib_stats(region, layers(region, a), a["sea"])


def _detect_job(args):
    """Detection, objects and context of one acquisition (pass 2); writes maps/<acq_id>.npz."""
    fields, aid, group, cal = args
    region = Region(**fields)
    maps_dir = region.root / "maps"
    a = load_acquisition(region, aid)
    lay = layers(region, a)
    mk = masks(region, a, lay, cal)
    t = a["meta"]["time"]
    wind = cur = None
    msgs = []
    try:
        e = ANC.era5(region, aid, t)
        wind = {k: ANC.to_grid(region, e["lon"], e["lat"], e[k]) for k in ("u10", "v10", "precip_3h")}
        c = ANC.currents(region, aid, t)
        if c is not None:
            cur = {k: ANC.to_grid(region, c["lon"], c["lat"], c[k]) for k in ("u", "v")}
    except Exception as ex:
        msgs.append(f"  [ancillary] {aid}: {ex!r}")
    df, lab = object_table(region, a, lay, mk, wind=wind, cur=cur)
    np.savez_compressed(maps_dir / f"{aid}.npz", labels=lab.astype(np.int32), sea=a["sea"],
                        g0_db=db(smooth(np.where(a["sea"], a["g0"], np.nan), 3)).astype(np.float16),
                        **{f"mask_{k}": v for k, v in mk.items() if k != "anom"})
    return aid, (df.assign(group=group) if len(df) else None), bright_targets(region, a), msgs


def run(region, workers=6, refresh_ingest=False, log=print, detect_workers=DETECT_WORKERS):
    t0 = time.time()
    region.save()
    acq_csv = region.root / "acquisitions.csv"
    if acq_csv.exists() and not refresh_ingest:
        acq = pd.read_csv(acq_csv)
        log(f"[ingest] cached: {len(acq)} acquisitions")
    else:
        acq = ingest(region, workers=workers, log=log)
        log(f"[ingest] {len(acq)} acquisitions ({time.time() - t0:.0f}s)")
    maps_dir = region.root / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    cal_oman = load_calibration()
    objs_all, targets_all, calib_rows = [], [], []
    fields = asdict(region)
    groups = {grp: g.sort_values("time").acq_id.tolist() for grp, g in acq.groupby("group")}
    with ProcessPoolExecutor(max_workers=detect_workers) as ex:
        # pass 1: per-date statistics -> group calibration (no control date needed); all dates in parallel
        jobs = {aid: ex.submit(_stats_job, (fields, aid)) for ids in groups.values() for aid in ids}
        cals = {}
        for group, ids in groups.items():
            cal = calibrate_group([jobs[aid].result() for aid in ids])
            cals[group] = cal
            calib_rows.append(dict(group=group, n_dates=cal["n_dates"], thr_ratio_db=cal["thr_ratio_db"],
                                   thr_valley=cal["thr_valley"], thr_anom=cal["thr_anom"], per_date_ratio_q=cal["per_date_ratio_q"]))
            log(f"[detect] {group}: {len(ids)} dates, CFAR thr {cal['thr_ratio_db']:.2f} dB, valley thr {cal['thr_valley']:.4f}")
        # pass 2: detection, objects, context; all dates in parallel
        jobs = {ex.submit(_detect_job, (fields, aid, group, cals[group])): aid for group, ids in groups.items() for aid in ids}
        for fu in as_completed(jobs):
            aid, df, tg, msgs = fu.result()
            for m in msgs:
                log(m)
            if df is not None and len(df):
                objs_all.append(df)
            if tg is not None and len(tg):
                targets_all.append(tg)
            log(f"  {aid}: {0 if df is None else len(df)} objects")
    # same row order as the sequential version (group, then time, then object id): DBSCAN and ranks depend on it
    order = {aid: k for k, aid in enumerate(aid for ids in groups.values() for aid in ids)}
    objs_all = sorted(objs_all, key=lambda d: order[d.acq_id.iloc[0]])
    targets_all = sorted(targets_all, key=lambda d: order[d.acq_id.iloc[0]]) or [pd.DataFrame()]
    objs = persistence(pd.concat(objs_all, ignore_index=True), maps_dir, workers=detect_workers)
    objs = score_objects(objs, cal_oman)
    targets = classify_targets(pd.concat([t for t in targets_all if len(t)], ignore_index=True)) if any(len(t) for t in targets_all) else pd.DataFrame()
    src, origins = find_sources(objs, region)
    src = attach_targets(src, targets)
    acq_ev = event_flags(objs, acq)
    REP.write_tables(region, acq_ev, objs, src, targets, calib_rows)
    figs = []
    for group in acq_ev.group.unique():
        p = region.out / f"overview_{group}.png"
        REP.fig_overview(region, acq_ev, objs, src, group, maps_dir, p)
        figs.append(p)
    p = region.out / "sources_map.png"
    REP.fig_sources(region, acq_ev, objs, src, targets, maps_dir, p)
    figs.insert(0, p)
    p = region.out / "timeline.png"
    REP.fig_timeline(region, acq_ev, p)
    figs.insert(1, p)
    (region.out / "report.md").write_text(REP.markdown(region, acq_ev, objs, src, targets, calib_rows, figs))
    log(f"[done] {region.name}: {len(objs)} objects ({(objs['class'] == 'probable').sum()} probable, "
        f"{(objs['class'] == 'possible').sum()} possible), {len(src)} sources, {time.time() - t0:.0f}s -> {region.out / 'report.md'}")
    return dict(acq=acq_ev, objects=objs, sources=src, targets=targets, calib=calib_rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--name")
    ap.add_argument("--bbox", help="lon0,lat0,lon1,lat1")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--res", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--refresh-ingest", action="store_true")
    a = ap.parse_args()
    if a.preset:
        region = PRESETS[a.preset]
    else:
        if not (a.name and a.bbox and a.start and a.end):
            ap.error("either --preset or --name/--bbox/--start/--end")
        region = Region(name=a.name, bbox=tuple(float(v) for v in a.bbox.split(",")), start=a.start, end=a.end, res=a.res)
    run(region, workers=a.workers, refresh_ingest=a.refresh_ingest)


if __name__ == "__main__":
    main()
