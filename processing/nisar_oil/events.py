"""Known-events set (events/candidate_events.csv, approved 15.11.2026): one pipeline region per event
and a sequential runner.

Point events get a square box around the source (half-size HALF_KM, larger for extended sources);
twins and the UAE event use their search box. The time window is the event's NISAR coverage
(nisar_first..nisar_last), so every group has enough dates for its own calibration. Event metadata
(type, source radius, activity window, control dates, labelling note) goes to Region.extra and is used
only for labelling/evaluation, never by detection.

  python -m nisar_oil.events                 # all approved events, sequentially
  python -m nisar_oil.events gc600 ei316     # selected events
"""
import argparse
import csv
import os
import shutil
import time
import traceback
from dataclasses import replace

import numpy as np

from .region import PRESETS, PROJECT, RUNS, Region

EVENTS_CSV = PROJECT / "events" / "candidate_events.csv"
APPROVED = ["oman_2026", "ei316", "gc600", "wreck1487", "neft_dashlari", "twin_canary_lee",
            "uae_gem2_2026", "twin_baltic_bloom", "coal_oil_point"]
HALF_KM = {"neft_dashlari": 50.0}          # complex spans several km and plumes reach tens of km
HALF_KM_DEFAULT = 40.0
# Shorter windows (15.11.2026, time budget): the Baltic twin keeps its bloom season only; Coal Oil Point keeps
# June-November 2026 (all three tracks), enough summer/autumn dates for a seep. Cached cut-outs stay valid.
WINDOW_OVERRIDE = {"twin_baltic_bloom": ("2026-06-19", "2026-08-31"), "coal_oil_point": ("2026-06-01", "2026-11-01")}
MIN_FREE_GB = 50                           # drop a finished region's cut-outs below this (S-band download shares the disk)


def _rows():
    with open(EVENTS_CSV, newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def _box(lon, lat, half_km):
    dlat = half_km / 111.32
    dlon = half_km / (111.32 * np.cos(np.deg2rad(lat)))
    return tuple(round(float(v), 4) for v in (lon - dlon, lat - dlat, lon + dlon, lat + dlat))


def _meta(r):
    num = lambda v: float(v) if v not in ("", None) else None
    return dict(event_id=r["id"], event_type=r["type"], event_name=r["name"],
                source_radius_km=num(r["source_radius_km"]),
                active_start=r["active_start"], active_end=r["active_end"],
                control_dates=r["control_dates"], search_bbox=r["search_bbox"],
                polarizations=r["polarizations"], confidence=r["confidence"],
                label_note=r["recommendation"])


def event_region(eid, rows=None):
    rows = rows or _rows()
    r = rows[eid]
    meta = _meta(r)
    if eid == "oman_2026":
        # regression run already exists with this name: reuse its cache; dates after the activity window are 'unknown'
        reg = PRESETS["oman_2026"]
        return replace(reg, extra={**reg.extra, **meta})
    if eid == "uae_gem2_2026":
        # same box as the blind-test run (cut-outs are reused), window extended back for control dates
        reg = PRESETS["uae_uaq_2026"]
        return Region(name="ev_uae_gem2_2026", bbox=reg.bbox, start=r["nisar_first"], end=r["nisar_last"],
                      notes=f"Known event (event-level check): {r['name']}", extra=meta)
    if r["search_bbox"]:
        bbox = tuple(float(v) for v in r["search_bbox"].split(","))
        src = None
    else:
        src = (float(r["lon"]), float(r["lat"]))
        bbox = _box(*src, HALF_KM.get(eid, HALF_KM_DEFAULT))
    start, end = WINDOW_OVERRIDE.get(eid, (r["nisar_first"], r["nisar_last"]))
    return Region(name=f"ev_{eid}", bbox=bbox, start=start, end=end,
                  known_source=src, notes=f"Known event: {r['name']}", extra=meta)


def event_regions(ids=None):
    rows = _rows()
    return {e: event_region(e, rows) for e in (ids or APPROVED)}


def _reuse_cutouts(src_name, region):
    """Hard-link cut-outs and ancillary (ERA5/currents) of an earlier run on the same grid and box
    (no extra disk, no re-download)."""
    n = 0
    for sub, dst in (("cutouts", region.cutouts), ("ancillary", region.ancillary_dir)):
        src = RUNS / src_name / sub
        if not src.exists():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for p in src.glob("*.npz"):
            q = dst / p.name
            if not q.exists():
                os.link(p, q)
                n += 1
    return n


def _free_gb():
    return shutil.disk_usage(RUNS).free / 2**30


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help=f"event ids (default: {' '.join(APPROVED)})")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--refresh-ingest", action="store_true")
    a = ap.parse_args()
    from .run import run                    # heavy imports only when running

    regions = event_regions(a.ids or None)
    for eid, reg in regions.items():
        t0 = time.time()
        log_path = RUNS / f"run_{reg.name}.log"
        with open(log_path, "a") as lf:
            def log(msg):
                print(msg, file=lf, flush=True)
                print(f"[{eid}] {msg}", flush=True)
            log(f"=== {eid}: region {reg.name}, bbox {reg.bbox}, {reg.start}..{reg.end}")
            if eid == "uae_gem2_2026":
                log(f"reused cut-outs: {_reuse_cutouts('uae_uaq_2026', reg)}")
            try:
                run(reg, workers=a.workers, refresh_ingest=a.refresh_ingest, log=log)
            except Exception:
                log("FAILED\n" + traceback.format_exc())
            free = _free_gb()
            if free < MIN_FREE_GB and reg.cutouts.exists() and reg.name != "oman_2026":
                shutil.rmtree(reg.cutouts)
                log(f"free disk {free:.0f} GB < {MIN_FREE_GB}: removed cut-outs of {reg.name}")
            log(f"=== {eid}: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
