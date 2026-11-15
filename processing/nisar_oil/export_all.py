"""Export several locations (pipeline score) in parallel into one web data package (contract 1.2); locations
already in the package are kept, mock/locations.json is merged.

  python -m nisar_oil.export_all --out frontend_data neft cop uae canary baltic
"""
import argparse
import json
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def _job(args):
    name, out = args
    from .export_web import export_location
    from .region import Region
    from .web_specs import SPECS
    spec = SPECS[name]
    spec = spec() if callable(spec) else spec
    detail, _ = export_location(Region.load(spec["region"]), spec, out)
    return detail["id"], len(detail["snapshots"]), [s["area_km2"] for s in detail["snapshots"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="frontend_data")
    ap.add_argument("names", nargs="+")
    a = ap.parse_args()
    out = Path(a.out)
    tmp = [out / f".part_{n}" for n in a.names]
    with ProcessPoolExecutor(max_workers=len(a.names)) as ex:
        res = list(ex.map(_job, [(n, str(t)) for n, t in zip(a.names, tmp)]))
    lst_path = out / "mock" / "locations.json"
    lst = json.loads(lst_path.read_text()) if lst_path.exists() else {"total": 0, "locations": []}
    for t in tmp:
        for sub in ("data/locations", "mock"):
            for p in (t / sub).iterdir():
                if p.name == "locations.json":
                    new = json.loads(p.read_text())["locations"]
                    ids = {l["id"] for l in new}
                    lst["locations"] = [l for l in lst["locations"] if l["id"] not in ids] + new
                    continue
                dst = out / sub / p.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
                shutil.move(str(p), str(dst))
        shutil.rmtree(t)
    lst["total"] = len(lst["locations"])
    lst_path.write_text(json.dumps(lst, ensure_ascii=False, indent=2))
    for lid, n, areas in res:
        print(f"{lid}: {n} snapshots, probable km2 {areas}")


if __name__ == "__main__":
    main()
