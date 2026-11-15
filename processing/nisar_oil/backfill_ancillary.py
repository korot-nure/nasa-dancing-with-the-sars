"""Fill in ERA5 wind / currents that a run could not fetch (Open-Meteo daily quota) and re-run detection.

Waits until the given pipeline process has finished and the Open-Meteo archive and marine APIs answer
again (the daily quota resets at 00:00 UTC), then, for every event region with acquisitions lacking
era5_/cur_ caches, re-runs nisar_oil.run.run(): ingest is cached, so only ancillary + detection are
recomputed. Regions are processed sequentially.

  python -m nisar_oil.backfill_ancillary [--wait-pid PID] [ids ...]
"""
import argparse
import os
import time
import urllib.request

import pandas as pd

from .events import APPROVED, event_regions

PROBES = ["https://archive-api.open-meteo.com/v1/archive?latitude=40&longitude=-70&start_date=2026-06-01&end_date=2026-06-01"
          "&hourly=wind_speed_10m&models=era5",
          "https://marine-api.open-meteo.com/v1/marine?latitude=40&longitude=-70&start_date=2026-06-01&end_date=2026-06-01"
          "&hourly=ocean_current_velocity"]


def _api_ok():
    for u in PROBES:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "nisar-oil-pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                r.read()
        except Exception:
            return False
    return True


def missing(region):
    acq = pd.read_csv(region.root / "acquisitions.csv")
    anc = region.ancillary_dir
    era = [a for a in acq.acq_id if not (anc / f"era5_{a}.npz").exists()]
    cur = [a for a in acq.acq_id if not (anc / f"cur_{a}.npz").exists()]
    return era, cur


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--wait-pid", type=int)
    a = ap.parse_args()
    from .run import run
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)
    if a.wait_pid:
        while True:
            try:
                os.kill(a.wait_pid, 0)
            except OSError:
                break
            time.sleep(60)
        log(f"pipeline process {a.wait_pid} finished")
    while not _api_ok():
        log("Open-Meteo quota not reset yet; next check in 10 min")
        time.sleep(600)
    log("Open-Meteo answers again")
    for eid, reg in event_regions(a.ids or APPROVED).items():
        if not (reg.root / "acquisitions.csv").exists():
            log(f"{eid}: no run, skipped")
            continue
        era, cur = missing(reg)
        if not era and not cur:
            log(f"{eid}: ancillary complete")
            continue
        log(f"{eid}: missing era5 {len(era)}, currents {len(cur)} -> re-running detection")
        t0 = time.time()
        try:
            run(reg, log=lambda m: None)
        except Exception as e:
            log(f"{eid}: FAILED {e!r}")
            continue
        era2, cur2 = missing(reg)
        log(f"{eid}: done in {time.time() - t0:.0f}s; still missing era5 {len(era2)}, currents {len(cur2)}")


if __name__ == "__main__":
    main()
