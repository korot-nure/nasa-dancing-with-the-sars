"""Scene loading: mosaic GCOV cut-outs of one acquisition onto a common UTM grid.

A "scene" (config.SCENES) = one track, one date, one or two frames. Output arrays are on the
AOI grid (config.AOI) and cached as .npz so the notebook can rerun offline.
"""
import json
from functools import lru_cache

import numpy as np
import shapefile
from matplotlib.path import Path as MPath
from matplotlib.transforms import Bbox
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage

from . import config as C

TO_UTM = Transformer.from_crs(4326, C.EPSG, always_xy=True)
TO_LL = Transformer.from_crs(C.EPSG, 4326, always_xy=True)
MOSAICS = C.CACHE / "mosaics"


def db(a):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(a)


@lru_cache(maxsize=None)
def grid(aoi):
    """Common UTM grid for an AOI: xs, ys (pixel centres, m) and resolution."""
    lon0, lat0, lon1, lat1, res = C.AOI[aoi]
    bx, by = TO_UTM.transform([lon0, lon1, lon1, lon0], [lat0, lat0, lat1, lat1])
    xs = np.arange(min(bx), max(bx), res) + res / 2
    ys = np.arange(max(by), min(by), -res) - res / 2
    return xs, ys, float(res)


def meshgrid(aoi):
    xs, ys, _ = grid(aoi)
    return np.meshgrid(xs, ys)


@lru_cache(maxsize=None)
def land_mask(aoi, buffer_m=1000):
    """Natural Earth 10m land rasterised on the AOI grid, dilated by buffer_m."""
    cache = MOSAICS / f"land_{aoi}_{buffer_m}.npy"
    if cache.exists():
        return np.load(cache)
    xs, ys, res = grid(aoi)
    lon0, lat0, lon1, lat1, _ = C.AOI[aoi]
    canvas = Image.new("1", (len(xs), len(ys)), 0)
    draw = ImageDraw.Draw(canvas)
    box = Bbox([[lon0 - 0.3, lat0 - 0.3], [lon1 + 0.3, lat1 + 0.3]])
    for shp in shapefile.Reader(str(C.LAND_SHP)).shapes():
        b = shp.bbox
        if b[2] < lon0 - 0.5 or b[0] > lon1 + 0.5 or b[3] < lat0 - 0.5 or b[1] > lat1 + 0.5:
            continue
        parts = list(shp.parts) + [len(shp.points)]
        for a, e in zip(parts[:-1], parts[1:]):
            clipped = MPath(np.array(shp.points[a:e])).clip_to_bbox(box, inside=True)
            clipped.should_simplify = False   # paths >= 128 vertices are otherwise simplified in degree units (~0.1 deg)
            for poly in clipped.to_polygons():
                if len(poly) < 3:
                    continue
                px, py = TO_UTM.transform(poly[:, 0], poly[:, 1])
                cols = (np.asarray(px) - xs[0]) / res
                rows = (ys[0] - np.asarray(py)) / res
                draw.polygon(list(zip(cols.tolist(), rows.tolist())), fill=1)
    land = np.array(canvas, dtype=bool)
    raw = land.copy()
    if buffer_m > 0:
        land = ndimage.binary_dilation(land, iterations=max(1, int(round(buffer_m / res))))
    MOSAICS.mkdir(parents=True, exist_ok=True)
    np.save(cache, land)
    np.save(MOSAICS / f"land_{aoi}_raw.npy", raw)
    return land


def land_raw(aoi):
    land_mask(aoi)
    return np.load(MOSAICS / f"land_{aoi}_raw.npy")


def _put(dst, d, key, XX, YY):
    if key not in d:
        return False
    x, y, a = d["x"], d["y"], d[key]
    ci = np.rint((XX - x[0]) / (x[1] - x[0])).astype(int)
    ri = np.rint((YY - y[0]) / (y[1] - y[0])).astype(int)
    ok = (ci >= 0) & (ci < len(x)) & (ri >= 0) & (ri < len(y))
    v = np.full(XX.shape, np.nan, np.float32)
    v[ok] = a[ri[ok], ci[ok]]
    m = np.isfinite(v)
    dst[m] = v[m]
    return m


def load_scene(sid, edge_m=600):
    """Return dict with gamma0/sigma0 (linear), noise, incidence, masks for a scene.

    Keys: g0 (main pol gamma0), s0 (sigma0 = gamma0*cos(inc), flat-sea approximation),
    neb (noise-equivalent backscatter of main pol), g0_hv/neb_hv (if HV), inc (deg),
    sea (valid sea pixels: data present, not land, >= edge_m from data edge), land, meta.
    """
    sc = C.scene(sid)
    cache = MOSAICS / f"{sid}.npz"
    if cache.exists():
        d = dict(np.load(cache, allow_pickle=False))
        d["meta"] = json.loads(str(d["meta"]))
        return d
    XX, YY = meshgrid(sc["aoi"])
    pol = sc["pol"]
    lay = {k: np.full(XX.shape, np.nan, np.float32) for k in ("g0", "neb", "g0_hv", "neb_hv", "inc")}
    keymap = {"g0": pol, "neb": "neb_" + pol, "g0_hv": "HV", "neb_hv": "neb_HV", "inc": "inc"}
    src = np.full(XX.shape, -1, np.int8)                 # which frame file provided the pixel
    for i, fn in enumerate(sc["files"]):
        d = np.load(C.CUTOUTS / fn)
        for k, key in keymap.items():
            m = _put(lay[k], d, key, XX, YY)
            if k == "g0" and m is not False:
                src[m] = i
    _, _, res = grid(sc["aoi"])
    land = land_mask(sc["aoi"])
    data = np.isfinite(lay["g0"]) & (lay["g0"] > 0)
    it = max(1, int(round(edge_m / res)))
    inner = ndimage.binary_erosion(data, iterations=it)
    # seam between frames: small radiometric steps there create straight artificial "lines"
    seam = np.zeros_like(data)
    if len(sc["files"]) > 1:
        for i in range(len(sc["files"])):
            seam |= ndimage.binary_dilation(src == i, iterations=1) & (src != i) & (src >= 0)
        seam = ndimage.binary_dilation(seam, iterations=it)
    sea = inner & ~land & ~seam
    out = {
        "g0": lay["g0"], "neb": lay["neb"], "inc": lay["inc"],
        "s0": (lay["g0"] * np.cos(np.deg2rad(lay["inc"]))).astype(np.float32),
        "sea": sea, "land": land,
    }
    if np.isfinite(lay["g0_hv"]).any():
        out["g0_hv"], out["neb_hv"] = lay["g0_hv"], lay["neb_hv"]
    meta = {k: sc[k] for k in ("id", "aoi", "pol", "track", "time", "role")}
    meta["res"] = res
    MOSAICS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, meta=json.dumps(meta), **out)
    out["meta"] = meta
    return out


def source_xy():
    return TO_UTM.transform(*C.SOURCE_LONLAT)


def source_distance(aoi):
    XX, YY = meshgrid(aoi)
    sx, sy = source_xy()
    return np.hypot(XX - sx, YY - sy)


# ---------------------------------------------------------------- generic image helpers
def smooth(lin, k):
    """Boxcar mean over finite pixels (NaN-aware), k x k."""
    if k <= 1:
        return lin.copy()
    m = np.isfinite(lin)
    s = ndimage.uniform_filter(np.where(m, lin, 0.0), k)
    c = ndimage.uniform_filter(m.astype(float), k)
    r = np.where(c > 0.5, s / np.maximum(c, 1e-12), np.nan)
    r[~m] = np.nan
    return r


def block_background(lin, res, block_m=20000, min_frac=0.15):
    """Smooth background: median of finite pixels in block_m blocks, log-bilinear upsampling."""
    B = max(4, int(block_m / res))
    ny, nx = int(np.ceil(lin.shape[0] / B)), int(np.ceil(lin.shape[1] / B))
    med = np.full((ny, nx), np.nan)
    for i in range(ny):
        for j in range(nx):
            blk = lin[i * B:(i + 1) * B, j * B:(j + 1) * B]
            blk = blk[np.isfinite(blk)]
            if blk.size > min_frac * B * B:
                med[i, j] = np.median(blk)
    if np.isnan(med).all():
        return np.full(lin.shape, np.nan)
    idx = ndimage.distance_transform_edt(np.isnan(med), return_distances=False, return_indices=True)
    med = med[tuple(idx)]
    bg = ndimage.zoom(np.log(med), (lin.shape[0] / ny, lin.shape[1] / nx), order=1)
    return np.exp(bg[: lin.shape[0], : lin.shape[1]])


def clean_mask(mask, res, min_km2, opening=1):
    """Morphological opening + removal of components smaller than min_km2. Returns (mask, labels, n)."""
    m = ndimage.binary_opening(mask, iterations=opening) if opening else mask.copy()
    lab, n = ndimage.label(m)
    if n == 0:
        return m, lab, 0
    px_km2 = (res / 1000.0) ** 2
    sizes = ndimage.sum(m, lab, range(1, n + 1)) * px_km2
    keep_ids = np.nonzero(sizes >= min_km2)[0] + 1
    keep = np.isin(lab, keep_ids)
    lab, n = ndimage.label(keep)
    return keep, lab, n


def source_linked(lab, aoi, radius_m=None):
    radius_m = radius_m or C.SOURCE_RADIUS_M
    near = source_distance(aoi) < radius_m
    ids = np.unique(lab[near & (lab > 0)])
    return np.isin(lab, ids[ids > 0])
