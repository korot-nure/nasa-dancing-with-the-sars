"""Hand-written location specs for the web export (docs/API_CONTRACT.md 1.2): which acquisitions of a
pipeline run become timeline snapshots, their 'before' of the same track and polarisation, manual labels
(label_source = manual) and notes. Texts are in English."""
from pathlib import Path


_EARLY = ("The slick at the tanker is taken from the reference labelling of this known event (method battery, origin = reference): "
          "the automatic pipeline does not outline it at this early stage of the chronic leak")
_MISS = ("On this date neither the automatic pipeline nor the reference labelling outlines the slick at the tanker "
         "(weak contrast in VV)")
_OFF = "The place where the oil reached the shore (Ras Madrakah, southern Masirah) is outside the frame"

OMAN = dict(
    region="oman_2026",
    id="oman-caroline-bezengi-2026",
    title="Hallaniyat Islands, Oman",
    description=("After a suspected explosion (08.06.2026) the tanker Caroline Bezengi ran aground at Al-Qibliyah island "
                 "(Hallaniyat Islands) on 30.06.2026, about 41 km from Shuwaymiyah. The oil plume drifts to the north-east; "
                 "on 12.08 oil reached the shore near Ras Madrakah and southern Masirah. Slicks are outlined automatically "
                 "from NISAR L-band images; the 'oil-likeness' score is a ranking for review, not proof."),
    source_url="https://www.aljazeera.com/news/2026/8/13/oman-says-massive-oil-spill-reaches-coastline-what-damage-could-it-do",
    known_source=(56.341, 17.5),
    known_source_label="Tanker Caroline Bezengi aground (known source)",
    snapshots=[
        dict(acq_id="056A_20260630_0140_VV", reference="VV_0630", before="056A_20260618_0140_VV", label="Grounding day", note=_EARLY),
        dict(acq_id="150D_20260706_1449", reference="HH_0706", before="150D_20260624_1449", label="Day 6 after grounding", note=_EARLY),
        dict(acq_id="056A_20260712_0140_VV", reference="VV_0712", before="056A_20260618_0140_VV", label="Day 12 after grounding", note=_EARLY),
        dict(acq_id="150D_20260718_1449", reference="HH_0718", before="150D_20260624_1449", label="Day 18 after grounding", note=_EARLY),
        dict(acq_id="056A_20260724_0140_VV", reference="VV_0724", before="056A_20260618_0140_VV", label="Day 24 after grounding", note=_MISS),
        dict(acq_id="150D_20260811_1449", reference="HH_0811", before="150D_20260624_1449", label="Day before the oil reached the shore", note=_EARLY),
        dict(acq_id="056A_20260817_0140_VV", before="056A_20260618_0140_VV", label="5 days after the oil reached the shore", note=_OFF),
        dict(acq_id="150D_20260823_1449", before="150D_20260624_1449", label="11 days after the oil reached the shore", note=_OFF),
        dict(acq_id="056A_20260829_0140_VV", before="056A_20260618_0140_VV", label="17 days after the oil reached the shore", note=_OFF),
        dict(acq_id="150D_20260904_1449", before="150D_20260624_1449", label="Wide plume to the north-east", note=None),
        dict(acq_id="056A_20260910_0140_VV", before="056A_20260618_0140_VV", label="Largest slick area", note=None),
        dict(acq_id="150D_20260916_1449", before="150D_20260624_1449", label="Last image of the series", note=None),
    ],
)

SPECS = {"oman": OMAN}


# ------------------------------------------------------------------ known events (events/candidate_events.csv)
# Labels follow the event chronology; notes are composed from the evidence of each date:
# ERA5 wind at the source, independent observations (NOAA analyst reports, Sentinel-1 / Cerulean slicks of the
# same day, visual check of NISAR quicklooks by the known-events review) and whether the pipeline outlines a
# slick near the source. Facts below are copied from events/candidate_events.md / .csv.
def _num(v, nd=1):
    return f"{v:.{nd}f}"


def _ddmm(d):
    return f"{d[8:10]}.{d[5:7]}"


def _wind_at(region, acq_id, lon, lat):
    import numpy as np
    from scipy.interpolate import RegularGridInterpolator
    p = region.ancillary_dir / f"era5_{acq_id}.npz"
    if not p.exists():
        return None
    d = np.load(p)
    return float(RegularGridInterpolator((d["lat"], d["lon"]), d["wspd"])((lat, lon)))


_CLS_UA = {"probable": "probable oil", "possible": "possible oil"}
SCORES = {}      # event id -> DataFrame(acq_id, obj, score, class): alternative scoring used in the notes


def _event_snapshots(eid, groups, label_fn, ql=(), noaa=(), s1=None, source_word="the source", extra_notes=None):
    """groups: {before_acq_id: [acq_id, ...]} of the same track/polarisation."""
    from .evaluate import event_table
    from .events import event_region
    region = event_region(eid)
    df, _ = event_table(eid, region)
    if eid in SCORES:
        df = df.drop(columns=["score", "class"]).merge(SCORES[eid], on=["acq_id", "obj"], how="left")
    R = region.extra["source_radius_km"]
    lon, lat = region.known_source
    s1 = s1 or {}
    from .ingest import load_acquisition
    kx, ky = region.lonlat_to_xy(lon, lat)
    xs, ys = region.grid
    r0, c0 = int((ys[0] - ky) / region.res), int((kx - xs[0]) / region.res)
    k = int(1000 / region.res)

    def coverage(aid):                     # share of valid sea pixels within ~1 km of the source
        return float(load_acquisition(region, aid)["sea"][r0 - k:r0 + k + 1, c0 - k:c0 + k + 1].mean())
    snaps = []
    for before, acqs in groups.items():
        if coverage(before) < 0.9:
            raise ValueError(f"{eid}: before {before} does not cover the source")
        for aid in acqs:
            cov = coverage(aid)
            if cov < 0.5:                  # source outside the swath or in a gap between frames: nothing to show
                continue
            d = df[df.acq_id == aid]
            date = f"{aid[5:9]}-{aid[9:11]}-{aid[11:13]}"
            parts = []
            if cov < 0.9:
                parts.append(f"A seam between image frames (no-data strip) passes near {source_word}")
            w = _wind_at(region, aid, lon, lat)
            if w is not None:
                q = ("; near calm: dark areas may not be oil" if w < 2 else
                     "; strong wind: thin slicks are hard to see" if w > 8 else "")
                ws = "<1" if w < 1 else f"~{_num(w, 0)}"
                parts.append(f"Wind near {source_word} {ws} m/s (ERA5){q}")
            evidence = False
            if date in noaa:
                parts.append("NOAA analysts reported a slick on this day from other satellites")
                evidence = True
            if date in s1:
                parts.append(f"Sentinel-1 on this day, ~11 h earlier: slick of {_num(s1[date])} km² near the vent (Cerulean, machine detection)")
                evidence = True
            if date in ql:
                parts.append(f"A slick near {source_word} is visible on the image")
                evidence = True
            near = d[(d.d_src_km <= R) & d["class"].isin(["probable", "possible"])].sort_values("score", ascending=False)
            if len(near):
                r = near.iloc[0]
                txt = f"The pipeline outlines a slick near {source_word} ({_CLS_UA[r['class']]}, score {_num(r.score, 2)})"
                if r.area_km2 > 200 and (w is not None and w < 3.5):
                    txt += f"; the {int(round(r.area_km2))} km² area is mostly calm water, larger than the slick itself"
                parts.append(txt)
            elif evidence:
                parts.append(f"The pipeline does not outline a slick near {source_word}")
            if extra_notes and date in extra_notes:
                parts.append(extra_notes[date])
            ev = "ql" if date in ql else "s1" if date in s1 else "noaa" if date in noaa else None
            snaps.append(dict(acq_id=aid, before=before, label=label_fn(date, ev), note=". ".join(parts) + "." if parts else None))
    return snaps


def _ei316():
    from datetime import date as D
    start, last = "2026-08-03", "2026-09-20"

    def label(d, ev):
        if d < start:
            return "Trace from the point before the first NOAA report" if ev == "ql" else "Before the first NOAA report (03.08)"
        if d <= "2026-09-21":
            n = (D.fromisoformat(d) - D.fromisoformat(start)).days
            return f"Day {n} after the first report"
        return "After the last NOAA report (20.09)"
    # 156D 'before' = 20.01.2026 (BETA product, clean sea): on 07.07 and 19.07 a thin plume from the point is
    # already visible (checked on full-resolution crops, 15.11.2026), so July dates cannot serve as 'before'
    groups = {"156D_20260120_0045": ["156D_20260707_0045_HH", "156D_20260719_0045_HH", "156D_20260812_0045_HH", "156D_20260824_0045_HH", "156D_20260905_0045_HH",
                                     "156D_20260917_0045_HH", "156D_20260929_0045_HH", "156D_20261011_0045_HH"],
              "033A_20260710_1126": ["033A_20260722_1126", "033A_20260815_1126", "033A_20260827_1126",
                                     "033A_20260908_1126", "033A_20260920_1126", "033A_20261002_1126", "033A_20261014_1126"]}
    return dict(
        region="ev_ei316", id="eugene-island-316-2026",
        title="Eugene Island 316, Gulf of Mexico",
        description=("Recurring oil slick in block Eugene Island 316 off the coast of Louisiana. From 03.08 to 20.09.2026 "
                     "NOAA/NESDIS analysts saw it every time at the same point and attribute it to a pipeline; the source "
                     "is not officially confirmed, the US Coast Guard and BSEE are investigating. Slicks are outlined "
                     "automatically from NISAR L-band images (HH, 40 MHz); the 'oil-likeness' score is a ranking for review, "
                     "not proof. On the NISAR images of 07.07 and 19.07 a thin plume from the same point is visible before the "
                     "first report. 'Before' is an image of the same track with no trace at the point: 20.01.2026 for track "
                     "156D, 10.07.2026 for 033A."),
        source_url="https://incidentnews.noaa.gov/incident/11216",
        known_source=(-91.61861, 28.26278),
        known_source_label="Leak point from NOAA reports (known source)",
        snapshots=_event_snapshots("ei316", groups, label, ql={"2026-07-07", "2026-07-19", "2026-08-12", "2026-08-27", "2026-09-05",
                                                                "2026-09-20", "2026-10-14"},
                                   noaa={"2026-08-15", "2026-08-27", "2026-09-08", "2026-09-17", "2026-09-20"}, source_word="the leak point",
                                   extra_notes={"2026-10-11": "A large ~1130 km² area in the north of the frame scored as probable oil "
                                                              "is a patchy low-wind zone, not oil (checked visually); the current "
                                                              "score is wrong here"}))


def _gc600():
    ql = {"2026-06-25", "2026-07-07", "2026-07-19", "2026-07-27", "2026-08-12", "2026-09-08", "2026-09-13", "2026-09-17",
          "2026-09-29", "2026-10-14"}
    s1 = {"2026-06-21": 11.67, "2026-08-15": 7.11, "2026-09-08": 19.81, "2026-09-20": 2.44, "2026-10-14": 1.44}

    def label(d, ev):
        return {"ql": "Slick near the vent visible on the image", "s1": "Sentinel-1 saw a slick on this day"}.get(ev, "No independent confirmation")
    groups = {"105A_20261019_1117": ["105A_20260621_1117", "105A_20260703_1117", "105A_20260715_1117", "105A_20260727_1117",
                                     "105A_20260820_1117", "105A_20260901_1117", "105A_20260913_1117", "105A_20260925_1117",
                                     "105A_20261007_1117", "105A_20261031_1117"],
              "156D_20261023_0045_VV": ["156D_20260625_0045_VV", "156D_20260707_0045_VV", "156D_20260719_0045_VV",
                                        "156D_20260812_0045_VV", "156D_20260824_0045_VV", "156D_20260905_0045_VV",
                                        "156D_20260917_0045_VV", "156D_20260929_0045_VV", "156D_20261011_0045_VV"],
              # 033A: the vent lies at the near-range edge; 28.06, 10.07 and 26.10 do not cover it (dropped automatically)
              "033A_20260722_1126_VV": ["033A_20260628_1126_VV", "033A_20260815_1126_VV",
                                        "033A_20260827_1126_VV", "033A_20260908_1126_VV", "033A_20260920_1126_VV",
                                        "033A_20261002_1126_VV", "033A_20261014_1126_VV", "033A_20261026_1126_VV"]}
    return dict(
        region="ev_gc600", id="green-canyon-600-seeps-2026",
        title="Green Canyon 600, Gulf of Mexico",
        description=("Natural oil seeps at ~1180 m depth (Mega Plume vent). Oil rises from the seafloor continuously; a slick "
                     "appears on the surface near the vent at ~2–7 m/s wind and lives for a few hours. There are other Green "
                     "Canyon seeps in the area, so slicks far from the vent are not necessarily errors. NISAR L-band images, "
                     "VV 5 MHz (coarser resolution); the 'oil-likeness' score is a ranking for review, not proof. The seep is "
                     "always active, so 'before' is an image of the same track with no slick at the vent (it can be later "
                     "than other dates)."),
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC7387546",
        known_source=(-90.5743, 27.36986),
        known_source_label="Mega Plume vent (known source)",
        snapshots=_event_snapshots("gc600", groups, label, ql=ql, s1=s1, source_word="the vent"))


_RAIN = ("A large ~{a} km² area {where} scored as probable oil is a dark patch with a bright rim, typical of a rain "
         "cell, not oil (checked visually); the current score is wrong here")


def _wreck1487():
    ql = {"2026-06-16", "2026-06-21", "2026-08-20", "2026-09-01", "2026-09-08", "2026-09-20"}
    noaa = {"2026-06-16", "2026-07-03", "2026-07-27", "2026-08-15", "2026-08-20", "2026-09-01", "2026-09-08",
            "2026-10-02", "2026-10-07"}

    def label(d, ev):
        return {"ql": "Slick near the wreck visible on the image", "noaa": "NOAA analysts saw a slick on this day"}.get(
            ev, "No independent confirmation")
    # 'before': strong wind (~12 m/s) and no NOAA report within +-1 day
    groups = {"040D_20260722_2335": ["040D_20260616_2335", "040D_20260628_2335", "040D_20260710_2335", "040D_20260815_2335",
                                     "040D_20260827_2335", "040D_20260908_2335", "040D_20260920_2335", "040D_20261002_2335",
                                     "040D_20261014_2335", "040D_20261026_2335"],
              "104A_20261019_0941": ["104A_20260621_0942", "104A_20260703_0942", "104A_20260715_0942_VV",
                                     "104A_20260727_0942_VV", "104A_20260820_0941", "104A_20260901_0941_VV",
                                     "104A_20260925_0941", "104A_20261007_0941", "104A_20261031_0941_VV"]}
    return dict(
        region="ev_wreck1487", id="wreck-1487-nantucket-2026",
        title="Wreck 1487, south of Nantucket (USA)",
        description=("A sunken ship (Wreck 1487) about 90 nautical miles south of Nantucket. Small oil slicks leak from it "
                     "continuously: NOAA analysts reported them on 68 days from 03.10.2025 to 06.11.2026, with slick areas of "
                     "0.02–6.5 km². NISAR L-band images, VV 5 MHz (coarse resolution): such small slicks are at the limit of "
                     "the image, and the automatic pipeline rarely outlines them near the wreck. The 'oil-likeness' score is "
                     "a ranking for review, not proof. 'Before' is an image of the same track in strong wind (~12 m/s) with no "
                     "NOAA reports within ±1 day."),
        source_url="https://www.ospo.noaa.gov/data/ocean/marinepollution/2026/20260912_1048_SENTINEL1C_OIL.txt",
        known_source=(-69.9175, 40.10056),
        known_source_label="Wreck 1487 (known source)",
        snapshots=_event_snapshots("wreck1487", groups, label, ql=ql, noaa=noaa, source_word="the wreck", extra_notes={
            "2026-08-27": _RAIN.format(a=160, where="in the south-west of the frame"),
            "2026-09-08": _RAIN.format(a=290, where="in the north-east of the frame")}))


SPECS.update({"ei316": _ei316, "gc600": _gc600, "wreck1487": _wreck1487})


# ------------------------------------------------------------------ remaining known events: automatic specs
# Same rules as above, chosen automatically: the two track/polarisation groups with most acquisitions that see
# the source (or the area); 'before' of a group = date with no candidate object near the source (or the fewest
# objects for an area event) and the wind closest to 7 m/s; notes from wind, independent evidence and the
# pipeline; large 'probable' areas in near-calm are flagged in the note as probable calm zones.
_CALM_NOTE = ("A large ~{a} km² area scored as probable oil in near-calm wind (~{w} m/s) is most likely a calm zone, "
              "not oil")


def _auto_snapshots(eid, label_fn, ql=(), noaa=(), s1=None, point=None, source_word=None, date_from="2026-06-01",
                    date_to="2026-12-31", n_groups=2, max_per_group=11, twin_note=None, before_max="9999"):
    from .evaluate import event_table
    from .events import event_region
    from .ingest import load_acquisition
    region = event_region(eid)
    df, acq = event_table(eid, region)
    acq = acq[(acq.time.str[:10] >= date_from) & (acq.time.str[:10] <= date_to)].copy()
    lon, lat = point or region.known_source or (0.5 * (region.bbox[0] + region.bbox[2]), 0.5 * (region.bbox[1] + region.bbox[3]))
    s1 = s1 or {}
    R = region.extra.get("source_radius_km")
    has_src = region.known_source is not None
    kx, ky = region.lonlat_to_xy(lon, lat)
    xs, ys = region.grid
    r0, c0 = int((ys[0] - ky) / region.res), int((kx - xs[0]) / region.res)
    k = int(1000 / region.res)
    if has_src:
        acq["cov"] = [float(load_acquisition(region, a)["sea"][r0 - k:r0 + k + 1, c0 - k:c0 + k + 1].mean()) for a in acq.acq_id]
    else:
        acq["cov"] = acq.sea_km2 / acq.groupby("group").sea_km2.transform("max")
    acq = acq[acq["cov"] >= (0.5 if has_src else 0.6)]
    groups = acq.group.value_counts().index[:n_groups]
    snaps = []
    for grp in groups:
        g = acq[acq.group == grp].sort_values("time")
        d = df[df.acq_id.isin(g.acq_id)]
        cand = []
        for a in g.itertuples():
            date = a.time[:10]
            if date in ql or date in s1 or date in noaa or date > before_max:
                continue
            o = d[d.acq_id == a.acq_id]
            bad = (len(o[(o.d_src_km <= (R or 0) + 3) & o["class"].isin(["probable", "possible"])]) if has_src
                   else len(o[o["class"].isin(["probable", "possible"])]))
            w = _wind_at(region, a.acq_id, lon, lat)
            cand.append((bad, abs((w if w is not None else 99) - 7), a.acq_id))
        before = sorted(cand)[0][2]
        rest = [a for a in g.acq_id if a != before][-max_per_group:]
        for aid in rest:
            o = d[d.acq_id == aid]
            date = f"{aid[5:9]}-{aid[9:11]}-{aid[11:13]}"
            parts = []
            w = _wind_at(region, aid, lon, lat)
            if w is not None:
                q = ("; near calm: dark areas may not be oil" if w < 2 else
                     "; strong wind: thin slicks are hard to see" if w > 8 else "")
                ws = "<1" if w < 1 else f"~{_num(w, 0)}"
                parts.append(f"Wind {('near ' + source_word) if source_word else 'in the area'} {ws} m/s (ERA5){q}")
            evidence = False
            if date in noaa:
                parts.append("NOAA analysts reported a slick on this day from other satellites")
                evidence = True
            if date in s1:
                parts.append(s1[date])
                evidence = True
            if date in ql:
                parts.append(f"A slick{(' near ' + source_word) if source_word else ''} is visible on the image")
                evidence = True
            if has_src:
                near = o[(o.d_src_km <= R) & o["class"].isin(["probable", "possible"])].sort_values("score", ascending=False)
                if len(near):
                    r = near.iloc[0]
                    parts.append(f"The pipeline outlines a slick near {source_word} ({_CLS_UA[r['class']]}, score {_num(r.score, 2)})")
                elif evidence:
                    parts.append(f"The pipeline does not outline a slick near {source_word}")
            big = o[(o["class"] == "probable") & (o.area_km2 > 300) & (o.wind_ms.astype(float) < 3.5)]
            if len(big):
                b = big.sort_values("area_km2").iloc[-1]
                parts.append(_CALM_NOTE.format(a=int(round(b.area_km2, -1)), w=_num(float(b.wind_ms), 0)))
            if twin_note:
                parts.append(twin_note)
            ev = "ql" if date in ql else "s1" if date in s1 else "noaa" if date in noaa else None
            snaps.append(dict(acq_id=aid, before=before, label=label_fn(date, ev), note=". ".join(parts) + "." if parts else None))
    return snaps


def _ql_dates(eid):
    import csv
    import re
    r = {x["id"]: x for x in csv.DictReader(open(Path(__file__).resolve().parents[1] / "events" / "candidate_events.csv"))}[eid]
    return {f"2026-{m}" for m in re.findall(r"\b(\d\d-\d\d)\b", r["nisar_quicklook"])}


def _s1_notes(event_id, word):
    import json
    fc = json.loads((Path(__file__).resolve().parents[1] / "events" / "data" / "cerulean_s1_slicks_near_nisar_dates.geojson").read_text())
    out = {}
    for f in fc["features"]:
        p = f["properties"]
        if p["event_id"] != event_id or abs(p["dt_hours_nisar_minus_s1"]) > 12:
            continue
        d = p["nisar_time_utc"][:10]
        h = abs(p["dt_hours_nisar_minus_s1"])
        when = f"~{int(round(h))} h {'earlier' if p['dt_hours_nisar_minus_s1'] > 0 else 'later'}" if h >= 1 else "almost simultaneously"
        out[d] = f"Sentinel-1 on this day ({when}): slick of {_num(p['area_km2'])} km² {word} (Cerulean)"
    return out


def _neft():
    ql = _ql_dates("neft_dashlari")
    return dict(region="ev_neft_dashlari", id="neft-dashlari-caspian-2026", title="Neft Daşları (Oil Rocks), Caspian Sea",
                description=("Neft Daşları (Oil Rocks) is an offshore oil field on stilts in the Caspian Sea, producing since 1949. "
                             "Slicks are regularly seen near the complex: leaks from platforms and pipelines, as well as natural "
                             "seeps. Slicks are outlined automatically from NISAR L-band images (HH, 20/40 MHz); the "
                             "'oil-likeness' score is a ranking for review, not proof. 'Before' is an image of the same track with "
                             "no slicks near the complex."),
                source_url="https://en.wikipedia.org/wiki/Neft_Da%C5%9Fları", known_source=(50.8583, 40.2361),
                known_source_label="Neft Daşları oil field (known source)",
                snapshots=_auto_snapshots("neft_dashlari", lambda d, ev: "Slick near the oil field visible on the image" if ev == "ql"
                                          else "No independent confirmation", ql=ql, source_word="the oil field"))


def _cop():
    s1 = _s1_notes("coal_oil_point", "near the seep field")
    ql = {d for d in _ql_dates("coal_oil_point") if d >= "2026-06-01"}
    return dict(region="ev_coal_oil_point", id="coal-oil-point-seeps-2026", title="Coal Oil Point, Santa Barbara Channel",
                description=("One of the largest natural oil seep fields in the world, off the coast of California: 100–150 barrels "
                             "of oil per day. Slicks are best seen in the evening in light wind; morning passes are often calm. "
                             "There are oil platforms nearby. Slicks are outlined automatically from NISAR L-band images; the "
                             "'oil-likeness' score is a ranking for review, not proof. 'Before' is an image of the same track "
                             "with no slicks near the seep field."),
                source_url="https://en.wikipedia.org/wiki/Coal_Oil_Point_seep_field", known_source=(-119.8833, 34.4),
                known_source_label="Coal Oil Point seep field (known source)",
                snapshots=_auto_snapshots("coal_oil_point", lambda d, ev: {"ql": "Slick near the seeps visible on the image",
                                                                           "s1": "Sentinel-1 saw a slick on this day"}.get(ev, "No independent confirmation"),
                                          ql=ql, s1=s1, source_word="the seep field"))


def _uae():
    s1 = _s1_notes("uae_uaq", "in the leak area")

    def label(d, ev):
        if d < "2026-10-09":
            return "Before the tanker was struck (control)"
        if d < "2026-10-19":
            return "After the tanker was struck, before a visible leak"
        if d <= "2026-10-30":
            return "Leak: Sentinel-1 saw a slick on this day" if ev == "s1" else "Leak ongoing"
        return "After the leak was stopped (30.10): remains of the slick" if ev == "s1" else "After the leak was stopped (30.10)"
    return dict(region="ev_uae_gem2_2026", id="uae-gem2-umm-al-quwain-2026", title="Umm Al Quwain, UAE",
                description=("A supertanker (according to analysts, GEM No. 2) was struck on 09.10.2026; from 19.10 it leaked oil "
                             "about 25 km off Umm Al Quwain, on 22.10 oil reached the shore, on 30.10 the leak was stopped. The "
                             "exact position of the tanker was not published. During the leak the sea was almost calm (~2–3 m/s), "
                             "so on L-band the slick is hard to tell from calm water. Slicks are outlined automatically from NISAR "
                             "L-band images (HH); the 'oil-likeness' score is a ranking for review, not proof. Dates before 09.10 "
                             "are controls without the leak."),
                source_url="https://thenationalnews.com/news/uae/2026/11/13/hundreds-of-workers-continue-to-clean-oil-spilt-off-the-uae",
                known_source=None,
                snapshots=_auto_snapshots("uae_gem2_2026", label, s1=s1, point=(55.635, 25.78), date_from="2026-08-01",
                                          max_per_group=8, before_max="2026-10-08"))


def _canary():
    return dict(region="ev_twin_canary_lee", id="canary-lee-twin-2026", title="Tenerife – La Gomera (oil-free twin)",
                description=("Oil-free control area: the wind shadow of Tenerife in the channel to La Gomera. Downwind of the island "
                             "the trade winds leave calm bands and fronts that look as dark as oil on radar. There is no oil "
                             "production here. Everything the pipeline marks as probable oil here is a false alarm; this location "
                             "shows how often they occur."),
                source_url="https://api.cerulean.skytruth.org/", known_source=None,
                snapshots=_auto_snapshots("twin_canary_lee", lambda d, ev: "Wind shadow: no oil", ql=set(),
                                          twin_note="There is no oil in the area: marked slicks are false alarms"))


def _baltic():
    return dict(region="ev_twin_baltic_bloom", id="baltic-bloom-twin-2026", title="Gotland Basin, Baltic Sea (oil-free twin)",
                description=("Oil-free control area: in summer 2026 cyanobacteria bloomed here (SMHI algae report No. 8, "
                             "25.08.2026). Surface accumulations of algae damp short waves and look as dark as oil on radar. "
                             "Everything the pipeline marks as probable oil here is a false alarm; this location shows how often "
                             "they occur."),
                source_url="https://www.smhi.se/en/publications-from-smhi/publications/2026-08-25-algae-report-number-8-2026",
                known_source=None,
                snapshots=_auto_snapshots("twin_baltic_bloom", lambda d, ev: "Cyanobacteria bloom: no oil",
                                          date_from="2026-06-19", twin_note="There is no oil in the area: marked slicks are false alarms"))


SPECS.update({"neft": _neft, "cop": _cop, "uae": _uae, "canary": _canary, "baltic": _baltic})
