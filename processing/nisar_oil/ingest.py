"""Discovery of NISAR GCOV granules (ASF), cut-out of the region from each granule by HTTP range
reads (Earthdata login from ~/.netrc), and mosaicking of frames into acquisitions on the
region grid."""
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import fsspec
import h5py
import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from scipy import ndimage
from scipy.interpolate import RegularGridInterpolator

ASF = "https://api.daac.asf.alaska.edu/services/search/param"
RETRIES, RETRY_WAIT_S = 3, 20
_session = None


# ------------------------------------------------------------------ remote access
def _sess():
    global _session
    if _session is None:
        _session = requests.Session()           # trust_env=True -> ~/.netrc for urs.earthdata.nasa.gov
    return _session


def _crid(name):
    """Composite release id: P05xxx = science products, X05xxx = pre-release BETA products (late 2025)."""
    return next(p for p in name.split("_") if len(p) == 6 and p[0] in "PX" and p[1:].isdigit())


def granule_url(name):
    ptype = name.split("_")[3]
    crid = _crid(name)
    maturity = "BETA_V1" if crid.startswith("X") else "PROVISIONAL_V1" if crid == "P05023" else "V1"
    level = "L2" if "_L2_" in name else "L1"
    return f"https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_{level}_{ptype}_{maturity}/{name}/{name}.h5"


def open_h5(name, block_size=4 * 2**20):
    r = _sess().get(granule_url(name), headers={"Range": "bytes=0-0"}, allow_redirects=True, timeout=180, stream=True)
    r.close()
    if r.status_code not in (200, 206):
        raise RuntimeError(f"access failed HTTP {r.status_code}: {name}")
    fobj = fsspec.filesystem("http").open(r.url, mode="rb", block_size=block_size, cache_type="blockcache")
    return h5py.File(fobj, "r")


# ------------------------------------------------------------------ discovery
def parse_name(name):
    p = name.split("_")
    return dict(name=name, cycle=p[4], track=p[5], direction=p[6], frame=p[7], mode=p[8], pol=p[9],
                start=p[11], crid=_crid(name), full=p[-3] if len(p) > 14 else "")


def discover(region):
    """All GCOV granules intersecting the region in the time window, de-duplicated."""
    lon0, lat0, lon1, lat1 = region.bbox
    q = dict(platform="NISAR", processingLevel="GCOV", bbox=f"{lon0},{lat0},{lon1},{lat1}",
             start=f"{region.start}T00:00:00Z", end=f"{region.end}T23:59:59Z", maxResults="2000", output="geojson")
    with urllib.request.urlopen(ASF + "?" + urllib.parse.urlencode(q), timeout=180) as r:
        fc = json.load(r)
    rows = []
    for f in fc["features"]:
        d = parse_name(f["properties"]["fileID"])
        d["time"] = f["properties"]["startTime"][:19]
        rows.append(d)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # main channel: HH from frequency A when present, else VV (e.g. NASV = frequency B only, VV)
    df["main_pol"] = np.where(df.pol.str.contains("H"), "HH", np.where(df.pol.str.contains("V"), "VV", ""))
    df = df[df.main_pol != ""]
    df["bw"] = df["mode"].str[:2].astype(int)                 # range bandwidth of frequency A (MHz), 0 if absent
    df["has_hv"] = df.pol.str.startswith("DH") | df.pol.str.startswith("QP")
    # de-duplicate reprocessed versions of the same product (same track/frame/start/mode/pol):
    # keep the newest CRID. Products of the same frame in DIFFERENT modes (e.g. 20 and 40 MHz) are kept:
    # they can cover different parts of the swath and are mosaicked together.
    df["crid_rank"] = df.crid.str[0].map({"P": 1, "X": 0}).astype(str) + df.crid.str[1:]   # science over BETA, then newest
    df = df.sort_values(["crid_rank", "has_hv", "bw"], ascending=False)
    df = df.drop_duplicates(subset=["track", "direction", "frame", "start", "mode", "pol"], keep="first")
    df["date"] = df.time.str[:10]
    df["acq_id"] = df.apply(lambda r: f"{r.track}{r.direction}_{r.date.replace('-', '')}_{r.time[11:13]}{r.time[14:16]}", axis=1)
    # frames of one pass share the acquisition id (start times differ by < 2 min): normalise the id
    df = df.sort_values("time")
    acq = []
    last = {}
    for r in df.itertuples():
        key = (r.track, r.direction, r.date)
        t = pd.Timestamp(r.time)
        if key in last and (t - last[key][1]).total_seconds() < 300:
            acq.append(last[key][0])
        else:
            last[key] = (r.acq_id, t)
            acq.append(r.acq_id)
        last[key] = (acq[-1], t)
    df["acq_id"] = acq
    return df.reset_index(drop=True)


# ------------------------------------------------------------------ cut-out of one granule
def _multilook(a, L):
    if L <= 1:
        return a.astype(np.float32)
    ny, nx = a.shape[0] // L * L, a.shape[1] // L * L
    a = a[:ny, :nx].reshape(ny // L, L, nx // L, L)
    with np.errstate(invalid="ignore"):
        return np.nanmean(a, axis=(1, 3)).astype(np.float32)


def extract_granule(region, name, main_pol, overwrite=False):
    """Cut the region out of one remote (ASF) L-band GCOV granule; see extract_h5."""
    out = region.cutouts / f"{name}.npz"
    if out.exists() and not overwrite:
        return out, "cached"
    t0 = time.time()
    res = extract_h5(region, open_h5(name), main_pol)
    region.cutouts.mkdir(parents=True, exist_ok=True)
    _save_atomic(out, res)
    return out, f"{time.time() - t0:.0f}s, valid {np.isfinite(res['g0']).mean():.2f}"


def _save_atomic(out, res):
    """Write to a temporary name and rename: a killed run never leaves a truncated cache file that a
    later run would take as 'cached'."""
    tmp = out.with_name(out.name + ".tmp.npz")
    np.savez_compressed(tmp, **res)
    tmp.replace(out)


def extract_local(region, path, main_pol, out, overwrite=False):
    """Same cut-out from a local GCOV file of either band (e.g. S-band from ISRO Bhoonidhi)."""
    if out.exists() and not overwrite:
        return out, "cached"
    t0 = time.time()
    with h5py.File(path, "r") as f:
        res = extract_h5(region, f, main_pol)
    out.parent.mkdir(parents=True, exist_ok=True)
    _save_atomic(out, res)
    return out, f"{time.time() - t0:.0f}s, valid {np.isfinite(res['g0']).mean():.2f}"


CROSS = {"HH": "HV", "VV": "VH"}


def extract_h5(region, f, main_pol):
    """Cut the region out of an open GCOV HDF5 (L-band science/LSAR or S-band science/SSAR) and resample
    it onto the region grid (nearest). Returns g0 (main pol), g0_hv (cross-pol: HV for HH, VH for VV),
    neb, neb_hv, inc on the region grid."""
    band = next(k for k in f["science"].keys() if k.endswith("SAR"))
    root = f[f"science/{band}/GCOV"]
    freqs = [k for k in root["grids"].keys() if k.startswith("frequency")]
    freq = next((fr for fr in freqs if (main_pol + main_pol) in root[f"grids/{fr}"]), None)
    if freq is None:
        raise RuntimeError(f"no {main_pol}{main_pol} layer")
    g = root[f"grids/{freq}"]
    cross = CROSS[main_pol]
    epsg = int(g["projection"][()])
    x, y = g["xCoordinates"][:], g["yCoordinates"][:]
    dx, dy = float(g["xCoordinateSpacing"][()]), float(g["yCoordinateSpacing"][()])
    XX, YY = region.mesh()
    tr = Transformer.from_crs(region.epsg, epsg, always_xy=True)
    PX, PY = tr.transform(XX, YY)                                  # region grid in product coordinates
    c0 = max(0, int(np.floor((PX.min() - x[0]) / dx)) - 2)
    c1 = min(len(x), int(np.ceil((PX.max() - x[0]) / dx)) + 3)
    r0 = max(0, int(np.floor((PY.max() - y[0]) / dy)) - 2)
    r1 = min(len(y), int(np.ceil((PY.min() - y[0]) / dy)) + 3)
    if c1 <= c0 or r1 <= r0:
        raise RuntimeError("region outside product grid")
    L = max(1, int(round(region.res / abs(dx))))
    mask = g["mask"][r0:r1, c0:c1]
    valid = (mask != 0) & (mask != 255)
    pols = [p.decode() for p in g["listOfPolarizations"][:]]
    lay = {}
    for key, pol in (("g0", main_pol), ("g0_hv", cross)):
        if pol not in pols:
            continue
        a = g[pol + pol][r0:r1, c0:c1].astype(np.float32)
        a[~valid] = np.nan
        lay[key] = _multilook(a, L)
    xs = x[c0:c1][: (c1 - c0) // L * L].reshape(-1, L).mean(1)
    ys = y[r0:r1][: (r1 - r0) // L * L].reshape(-1, L).mean(1)
    ci = np.rint((PX - xs[0]) / (xs[1] - xs[0])).astype(int)
    ri = np.rint((PY - ys[0]) / (ys[1] - ys[0])).astype(int)
    ok = (ci >= 0) & (ci < len(xs)) & (ri >= 0) & (ri < len(ys))
    res = {}
    for k, a in lay.items():
        v = np.full(XX.shape, np.nan, np.float32)
        v[ok] = a[ri[ok], ci[ok]]
        res[k] = v
    # noise-equivalent backscatter and incidence angle (coarse metadata cubes -> grid)
    meta = root["metadata"]
    neb = meta[f"calibrationInformation/{freq}/noiseEquivalentBackscatter"]
    nx, ny = neb["xCoordinates"][:], neb["yCoordinates"][:]
    for key, pol in (("neb", main_pol), ("neb_hv", cross)):
        if pol in neb and (key == "neb" or "g0_hv" in res):
            cube = neb[pol][:]
            yy, cc = (ny, cube) if ny[0] < ny[-1] else (ny[::-1], cube[::-1])
            res[key] = RegularGridInterpolator((yy, nx), cc, bounds_error=False, fill_value=np.nan)((PY, PX)).astype(np.float32)
    rg = meta["radarGrid"]
    hgt = rg["heightAboveEllipsoid"][:] if "heightAboveEllipsoid" in rg else np.array([0.0])
    k = int(np.argmin(np.abs(hgt)))
    gx, gy = rg["xCoordinates"][:], rg["yCoordinates"][:]
    plane = rg["incidenceAngle"][k]
    yy, pp = (gy, plane) if gy[0] < gy[-1] else (gy[::-1], plane[::-1])
    res["inc"] = RegularGridInterpolator((yy, gx), pp, bounds_error=False, fill_value=np.nan)((PY, PX)).astype(np.float32)
    return res


def _extract_job(args):
    from .region import Region
    region_fields, name, pol = args
    region = Region(**region_fields)            # rebuilt in the worker (cached transformers are not pickled)
    err = None
    for attempt in range(RETRIES):              # transient HTTP drops (RemoteDisconnected, timeouts) are common
        try:
            path, msg = extract_granule(region, name, pol)
            return name, True, msg + (f" (attempt {attempt + 1})" if attempt else "")
        except Exception as e:  # report and continue with other granules
            err = e
            time.sleep(RETRY_WAIT_S * (attempt + 1))
    return name, False, repr(err)[:300]


def extract_all(region, granules, workers=6, log=print):
    from dataclasses import asdict
    fields = asdict(region)
    jobs = [(fields, r.name, r.main_pol) for r in granules.itertuples()]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_extract_job, j) for j in jobs]
        for fu in as_completed(futs):
            name, ok, msg = fu.result()
            results.append((name, ok, msg))
            log(f"  {'ok ' if ok else 'ERR'} {name[17:62]} {msg}")
    return results


# ------------------------------------------------------------------ mosaic frames -> acquisition
def build_acquisition(region, acq_id, rows, edge_m=600, overwrite=False):
    """Mosaic all frames of one pass; masks: valid sea (not land+1 km, not data edge, not frame seam)."""
    out = region.acquisitions_dir / f"{acq_id}.npz"
    if out.exists() and not overwrite:
        return out
    shape = region.shape
    lay = {k: np.full(shape, np.nan, np.float32) for k in ("g0", "g0_hv", "neb", "neb_hv", "inc")}
    src = np.full(shape, -1, np.int8)
    rows = rows.sort_values(["frame", "bw"])          # within a frame the wider-bandwidth product goes on top
    used = []
    for i, r in enumerate(rows.itertuples()):
        p = region.cutouts / f"{r.name}.npz"
        if not p.exists():
            continue
        d = np.load(p)
        used.append(r.name)
        for k in lay:
            if k in d:
                m = np.isfinite(d[k])
                lay[k][m] = d[k][m]
                if k == "g0":
                    src[m] = i
    data = np.isfinite(lay["g0"]) & (lay["g0"] > 0)
    if not data.any():                                # frames touch the bbox but have no valid pixels in it
        out.unlink(missing_ok=True)
        return None
    it = max(1, int(round(edge_m / region.res)))
    inner = ndimage.binary_erosion(data, iterations=it)
    seam = np.zeros(shape, bool)
    for i in np.unique(src[src >= 0]):
        seam |= ndimage.binary_dilation(src == i, iterations=1) & (src != i) & (src >= 0)
    if seam.any():
        seam = ndimage.binary_dilation(seam, iterations=it)
    sea = inner & ~region.land_buffered(1000) & ~seam
    r0 = rows.iloc[0]
    meta = dict(acq_id=acq_id, track=r0.track, direction=r0.direction, time=r0.time, date=r0.date,
                main_pol=r0.main_pol, frames=used, crid=sorted(rows.crid.unique().tolist()),
                bw=int(rows.bw.max()), has_hv=bool(np.isfinite(lay["g0_hv"]).any()))
    keep = {k: v for k, v in lay.items() if np.isfinite(v).any()}
    region.acquisitions_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, meta=json.dumps(meta), sea=sea, **keep)
    return out


def load_acquisition(region, acq_id):
    d = dict(np.load(region.acquisitions_dir / f"{acq_id}.npz", allow_pickle=False))
    d["meta"] = json.loads(str(d["meta"]))
    if "inc" in d:
        d["s0"] = (d["g0"] * np.cos(np.deg2rad(d["inc"]))).astype(np.float32)
    return d


def ingest(region, workers=6, log=print):
    """Discover, extract and mosaic. Returns the acquisition table."""
    region.save()
    gr = discover(region)
    if gr.empty:
        raise RuntimeError("no NISAR GCOV granules found for the region/time window")
    gr.to_csv(region.root / "granules.csv", index=False)
    log(f"granules: {len(gr)} in {gr.acq_id.nunique()} acquisitions; extracting ...")
    res = extract_all(region, gr, workers=workers, log=log)
    failed = {n for n, ok, _ in res if not ok}
    rows = []
    # one acquisition = one pass in ONE main polarisation: a pass can mix frames of different modes
    # (e.g. NASV = frequency B VV next to DHDH = HH); HH and VV differ by several dB over the sea,
    # so they are mosaicked separately (acq_id gets a _HH/_VV suffix only when a pass has both)
    ok = gr[~gr.name.isin(failed)]
    npol = ok.groupby("acq_id").main_pol.nunique()
    for (acq_id, pol), g in ok.groupby(["acq_id", "main_pol"]):
        if npol[acq_id] > 1:
            acq_id = f"{acq_id}_{pol}"
        if build_acquisition(region, acq_id, g, overwrite=True) is None:
            log(f"  skip {acq_id}: no valid pixels in the region")
            continue
        a = load_acquisition(region, acq_id)
        sea_km2 = float(a["sea"].sum() * (region.res / 1000) ** 2)
        rows.append(dict(acq_id=acq_id, **{k: a["meta"][k] for k in ("track", "direction", "time", "main_pol", "has_hv", "bw")},
                         n_frames=len(a["meta"]["frames"]), sea_km2=sea_km2))
    acq = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
    acq = acq[acq.sea_km2 > 50]                       # ignore passes that barely touch the sea part of the region
    acq["group"] = acq.track + acq.direction + "_" + acq.main_pol
    acq.to_csv(region.root / "acquisitions.csv", index=False)
    if failed:
        log(f"failed granules: {len(failed)}")
    return acq
