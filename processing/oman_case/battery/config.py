"""Shared configuration for the Oman oil-spill method battery.

Everything that defines the experiment lives here: paths, scenes, AOIs, event facts,
labelling rules. Other modules import from this file only.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # oman_case/
CACHE = ROOT / "data_cache"
CUTOUTS = CACHE / "cutouts"                          # .npz cut-outs from extract.py
ANCILLARY = CACHE / "ancillary"                      # ERA5 / SST / chlorophyll / rain / currents
RSLC_CACHE = CACHE / "rslc"                          # complex RSLC windows (M16, M17)
LAND_SHP = CACHE / "natural_earth_land" / "ne_10m_land.shp"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
EPSG = 32640                                         # WGS 84 / UTM 40N, grid of the GCOV products

# --- event facts (open sources) ------------------------------------------------
SOURCE_LONLAT = (56.341, 17.500)                     # Al-Qibliyah island, grounded tanker (from imagery)
SOURCE_RADIUS_M = 6000                               # object touching this circle = "source-linked"
GROUNDING_DATE = "2026-06-30"                        # exact hour unknown
LANDFALL_DATE = "2026-08-12"
OFFICIAL_AREAS = {"2026-08-04": (600, "Greenpeace"), "2026-08-10": (400, "Oman EA")}

# --- areas of interest -----------------------------------------------------------
AOI = {
    # name: (lon0, lat0, lon1, lat1, grid_res_m)
    "island_hh": (56.2, 17.35, 57.3, 18.3, 60),
    "island_vv": (56.25, 17.0, 58.3, 18.3, 80),
    "coast": (57.65, 18.85, 58.9, 20.45, 40),
    "gulf": (57.95, 19.25, 58.65, 20.1, 40),          # central Gulf of Masirah, no shoreline strip
}

# --- scenes ----------------------------------------------------------------------
# role: "control" = before grounding (no oil expected), "event" = after grounding,
#       "ambiguous" = grounding day (hour unknown)
# Each scene = one acquisition date on one track; cut-out files are mosaicked per scene.
SCENES = [
    # track 150 descending, 14:49 UTC, HH (+HV on DHDH dates), 20 MHz, inc ~45 deg
    dict(id="HH_0624", aoi="island_hh", pol="HH", track="150D", time="2026-06-24T14:49", role="control",
         files=["t150_023_079.npz", "t150_023_080.npz"], hv=True),
    dict(id="HH_0706", aoi="island_hh", pol="HH", track="150D", time="2026-07-06T14:49", role="event",
         files=["t150_024_079.npz", "t150_024_080.npz"], hv=False),
    dict(id="HH_0718", aoi="island_hh", pol="HH", track="150D", time="2026-07-18T14:49", role="event",
         files=["t150_025_079.npz", "t150_025_080.npz"], hv=True),
    dict(id="HH_0811", aoi="island_hh", pol="HH", track="150D", time="2026-08-11T14:49", role="event",
         files=["t150_027_079.npz", "t150_027_080.npz"], hv=True),
    dict(id="HH_0823", aoi="island_hh", pol="HH", track="150D", time="2026-08-23T14:49", role="event",
         files=["t150_028_079.npz", "t150_028_080.npz"], hv=False),
    dict(id="HH_0904", aoi="island_hh", pol="HH", track="150D", time="2026-09-04T14:49", role="event",
         files=["t150_029_079.npz", "t150_029_080.npz"], hv=True),
    dict(id="HH_0916", aoi="island_hh", pol="HH", track="150D", time="2026-09-16T14:49", role="event",
         files=["t150_030_079.npz", "t150_030_080.npz"], hv=False),
    # track 056 ascending, 01:40 UTC, VV only (frequency B, 5 MHz, joint L+S), inc ~40 deg
    dict(id="VV_0618", aoi="island_vv", pol="VV", track="056A", time="2026-06-18T01:40", role="control",
         files=["t056vv_023_010.npz"], hv=False),
    dict(id="VV_0630", aoi="island_vv", pol="VV", track="056A", time="2026-06-30T01:40", role="ambiguous",
         files=["t056vv_024_010.npz"], hv=False),
    dict(id="VV_0712", aoi="island_vv", pol="VV", track="056A", time="2026-07-12T01:40", role="event",
         files=["t056vv_025_010.npz"], hv=False),
    dict(id="VV_0724", aoi="island_vv", pol="VV", track="056A", time="2026-07-24T01:40", role="event",
         files=["t056vv_026_010.npz"], hv=False),
    dict(id="VV_0817", aoi="island_vv", pol="VV", track="056A", time="2026-08-17T01:40", role="event",
         files=["t056vv_028_010.npz"], hv=False),
    dict(id="VV_0829", aoi="island_vv", pol="VV", track="056A", time="2026-08-29T01:40", role="event",
         files=["t056vv_029_010.npz"], hv=False),
    dict(id="VV_0910", aoi="island_vv", pol="VV", track="056A", time="2026-09-10T01:40", role="event",
         files=["t056vv_030_010.npz"], hv=False),
    # coast Ras Madrakah - Masirah (landfall 2026-08-12), HH; pre-landfall dates are controls
    dict(id="CA_0717", aoi="coast", pol="HH", track="128A", time="2026-07-17T01:33", role="control",
         files=["coast_t128_025_011.npz", "coast_t128_025_012.npz"], hv=True),
    dict(id="CD_0723", aoi="coast", pol="HH", track="049D", time="2026-07-23T14:40", role="control",
         files=["coast_t049_026_079.npz"], hv=True),
    dict(id="CA_0810", aoi="coast", pol="HH", track="128A", time="2026-08-10T01:33", role="event",
         files=["coast_t128_027_011.npz", "coast_t128_027_012.npz"], hv=True),
    dict(id="CD_0816", aoi="coast", pol="HH", track="049D", time="2026-08-16T14:40", role="event",
         files=["coast_t049_028_079.npz"], hv=True),
    dict(id="CA_0822", aoi="coast", pol="HH", track="128A", time="2026-08-22T01:33", role="event",
         files=["coast_t128_028_011.npz", "coast_t128_028_012.npz"], hv=True),
    dict(id="CD_0828", aoi="coast", pol="HH", track="049D", time="2026-08-28T14:40", role="event",
         files=["coast_t049_029_079.npz"], hv=False),
    dict(id="CA_0903", aoi="coast", pol="HH", track="128A", time="2026-09-03T01:33", role="event",
         files=["coast_t128_029_011.npz", "coast_t128_029_012.npz"], hv=True),
]

ISLAND_SCENES = [s for s in SCENES if s["aoi"].startswith("island")]
COAST_SCENES = [s for s in SCENES if s["aoi"] == "coast"]


def scene(sid):
    return next(s for s in SCENES if s["id"] == sid)
