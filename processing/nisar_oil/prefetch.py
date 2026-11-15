"""Speed-ups for a running event: fetch cut-outs from the END of the granule list (a second downloader next to
the running ingest, which works from the start; finished cut-outs are skipped by both) and prefetch ERA5 /
currents for every acquisition listed in granules.csv, so detection does not wait for the weather service.

  python -m nisar_oil.prefetch cutouts coal_oil_point --workers 14
  python -m nisar_oil.prefetch weather twin_baltic_bloom coal_oil_point
"""
import argparse
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from . import ancillary as ANC
from .events import event_region
from .ingest import extract_all


def cutouts(eid, workers):
    reg = event_region(eid)
    gr = pd.read_csv(reg.root / "granules.csv")
    todo = gr[[not (reg.cutouts / f"{n}.npz").exists() for n in gr.name]].iloc[::-1]
    print(f"{eid}: {len(todo)} cut-outs to fetch (reverse order)", flush=True)
    extract_all(reg, todo, workers=workers, log=lambda m: print(m, flush=True))


def weather(eid):
    reg = event_region(eid)
    gr = pd.read_csv(reg.root / "granules.csv")
    # acquisition id as ingest names it: suffix _HH/_VV only when a pass mixes main polarisations
    npol = gr.groupby("acq_id").main_pol.nunique()
    jobs = []
    for (aid, pol), g in gr.groupby(["acq_id", "main_pol"]):
        name = f"{aid}_{pol}" if npol[aid] > 1 else aid
        jobs.append((name, g.time.min()))

    def one(j):
        name, t = j
        try:
            ANC.era5(reg, name, t)
            ANC.currents(reg, name, t)
            return None
        except Exception as e:
            return f"{name}: {e!r}"
    with ThreadPoolExecutor(max_workers=6) as ex:
        errs = [e for e in ex.map(one, jobs) if e]
    print(f"{eid}: weather for {len(jobs)} acquisitions, errors {len(errs)} {errs[:3]}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["cutouts", "weather"])
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    for eid in a.ids:
        cutouts(eid, a.workers) if a.what == "cutouts" else weather(eid)


if __name__ == "__main__":
    main()
