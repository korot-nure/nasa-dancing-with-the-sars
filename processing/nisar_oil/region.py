"""Region definition: bounding box, time window, analysis grid (UTM) and land mask."""
import json
from dataclasses import asdict, dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np
import shapefile
from matplotlib.path import Path as MPath
from matplotlib.transforms import Bbox
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage

PROJECT = Path(__file__).resolve().parents[1]
RUNS = PROJECT / "runs"
LAND_SHP = PROJECT / "oman_case" / "data_cache" / "natural_earth_land" / "ne_10m_land.shp"


@dataclass
class Region:
    name: str
    bbox: tuple                      # lon0, lat0, lon1, lat1
    start: str                       # YYYY-MM-DD (UTC)
    end: str
    res: float = 60.0                # analysis grid spacing, m
    known_source: tuple = None       # optional (lon, lat): used ONLY for evaluation, never by detection
    notes: str = ""
    extra: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ paths
    @property
    def root(self):
        return RUNS / self.name

    @property
    def cutouts(self):
        return self.root / "cutouts"

    @property
    def acquisitions_dir(self):
        return self.root / "acquisitions"

    @property
    def ancillary_dir(self):
        return self.root / "ancillary"

    @property
    def out(self):
        return self.root / "output"

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "region.json").write_text(json.dumps(asdict(self), indent=1))

    @classmethod
    def load(cls, name):
        return cls(**json.loads((RUNS / name / "region.json").read_text()))

    # ------------------------------------------------------------------ grid
    @cached_property
    def epsg(self):
        lon = 0.5 * (self.bbox[0] + self.bbox[2])
        lat = 0.5 * (self.bbox[1] + self.bbox[3])
        zone = int((lon + 180) // 6) + 1
        return (32600 if lat >= 0 else 32700) + zone

    @cached_property
    def to_utm(self):
        return Transformer.from_crs(4326, self.epsg, always_xy=True)

    @cached_property
    def to_ll(self):
        return Transformer.from_crs(self.epsg, 4326, always_xy=True)

    @cached_property
    def grid(self):
        lon0, lat0, lon1, lat1 = self.bbox
        lons = np.r_[np.linspace(lon0, lon1, 30), np.full(30, lon1), np.linspace(lon1, lon0, 30), np.full(30, lon0)]
        lats = np.r_[np.full(30, lat0), np.linspace(lat0, lat1, 30), np.full(30, lat1), np.linspace(lat1, lat0, 30)]
        bx, by = self.to_utm.transform(lons, lats)
        xs = np.arange(np.floor(min(bx)), max(bx), self.res) + self.res / 2
        ys = np.arange(np.ceil(max(by)), min(by), -self.res) - self.res / 2
        return xs, ys

    @cached_property
    def shape(self):
        xs, ys = self.grid
        return len(ys), len(xs)

    def mesh(self):
        xs, ys = self.grid
        return np.meshgrid(xs, ys)

    def extent_km(self):
        xs, ys = self.grid
        return [xs[0] / 1e3, xs[-1] / 1e3, ys[-1] / 1e3, ys[0] / 1e3]

    def lonlat_to_xy(self, lon, lat):
        return self.to_utm.transform(lon, lat)

    def xy_to_lonlat(self, x, y):
        return self.to_ll.transform(x, y)

    # ------------------------------------------------------------------ land
    @cached_property
    def land(self):
        """Natural Earth 10 m land on the grid (no buffer)."""
        cache = self.root / "land.npy"
        if cache.exists():
            return np.load(cache)
        xs, ys = self.grid
        lon0, lat0, lon1, lat1 = self.bbox
        # rings are combined even-odd (XOR): inner rings are holes, e.g. the Caspian Sea inside Eurasia
        land = np.zeros((len(ys), len(xs)), dtype=bool)
        box = Bbox([[lon0 - 0.3, lat0 - 0.3], [lon1 + 0.3, lat1 + 0.3]])
        for shp in shapefile.Reader(str(LAND_SHP)).shapes():
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
                    px, py = self.to_utm.transform(poly[:, 0], poly[:, 1])
                    cols = (np.asarray(px) - xs[0]) / self.res
                    rows = (ys[0] - np.asarray(py)) / self.res
                    ring = Image.new("1", (len(xs), len(ys)), 0)
                    ImageDraw.Draw(ring).polygon(list(zip(cols.tolist(), rows.tolist())), fill=1)
                    land ^= np.array(ring, dtype=bool)
        self.root.mkdir(parents=True, exist_ok=True)
        np.save(cache, land)
        return land

    @cached_property
    def dist_land_km(self):
        return ndimage.distance_transform_edt(~self.land) * self.res / 1000.0

    def land_buffered(self, buffer_m=1000):
        return self.dist_land_km < buffer_m / 1000.0


# ------------------------------------------------------------------ presets
PRESETS = {
    "oman_2026": Region(
        name="oman_2026", bbox=(56.2, 17.2, 58.0, 18.3), start="2026-06-15", end="2026-09-20",
        known_source=(56.341, 17.500),
        notes="Regression case: tanker Caroline Bezengi grounded at Al-Qibliyah island 2026-06-30."),
    "uae_uaq_2026": Region(
        name="uae_uaq_2026", bbox=(54.9, 25.2, 56.0, 26.1), start="2026-09-15", end="2026-11-13",
        notes="Blind test: tanker oil spill reported off Umm Al Quwain (UAE), detected ~2026-10-19..23; "
              "exact location and source not published."),
}
