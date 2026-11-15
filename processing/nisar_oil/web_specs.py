"""Hand-written location specs for the web export (docs/API_CONTRACT.md 1.2): which acquisitions of a
pipeline run become timeline snapshots, their 'before' of the same track and polarisation, manual labels
(label_source = manual) and notes. Texts are in Ukrainian, as the frontend."""
from pathlib import Path


_EARLY = ("Пляму біля танкера взято з еталонної розмітки відомої події (батарея методів, origin = reference): "
          "автоматичний конвеєр на ранній стадії хронічного витоку її не виділяє")
_MISS = ("На цю дату пляму біля танкера не виділяє ні автоматичний конвеєр, ні еталонна розмітка "
         "(слабкий контраст у VV)")
_OFF = "Місце виходу нафти на берег (Рас-Мадрака, південь Масіри) — за межами кадру"

OMAN = dict(
    region="oman_2026",
    id="oman-caroline-bezengi-2026",
    title="Острови Халланіят, Оман",
    description=("Танкер Caroline Bezengi після підозри на вибух (8.06.2026) сів на мілину біля острова Аль-Кіблія "
                 "(острови Халланіят) 30.06.2026, приблизно за 41 км від Шарбітату. Нафтовий шлейф дрейфує на "
                 "північний схід; 12.08 нафта вийшла на берег біля Рас-Мадраки та південної Масіри. Плями виділено "
                 "автоматично за знімками NISAR L-band; оцінка «схоже на нафту» — ранжування для перевірки, а не доказ."),
    source_url="https://www.aljazeera.com/news/2026/8/13/oman-says-massive-oil-spill-reaches-coastline-what-damage-could-it-do",
    known_source=(56.341, 17.5),
    known_source_label="Танкер Caroline Bezengi на мілині (відоме джерело)",
    snapshots=[
        dict(acq_id="056A_20260630_0140_VV", reference="VV_0630", before="056A_20260618_0140_VV", label="День посадки на мілину", note=_EARLY),
        dict(acq_id="150D_20260706_1449", reference="HH_0706", before="150D_20260624_1449", label="6-й день після посадки", note=_EARLY),
        dict(acq_id="056A_20260712_0140_VV", reference="VV_0712", before="056A_20260618_0140_VV", label="12-й день після посадки", note=_EARLY),
        dict(acq_id="150D_20260718_1449", reference="HH_0718", before="150D_20260624_1449", label="18-й день після посадки", note=_EARLY),
        dict(acq_id="056A_20260724_0140_VV", reference="VV_0724", before="056A_20260618_0140_VV", label="24-й день після посадки", note=_MISS),
        dict(acq_id="150D_20260811_1449", reference="HH_0811", before="150D_20260624_1449", label="Напередодні виходу нафти на берег", note=_EARLY),
        dict(acq_id="056A_20260817_0140_VV", before="056A_20260618_0140_VV", label="5 днів після виходу на берег", note=_OFF),
        dict(acq_id="150D_20260823_1449", before="150D_20260624_1449", label="11 днів після виходу на берег", note=_OFF),
        dict(acq_id="056A_20260829_0140_VV", before="056A_20260618_0140_VV", label="17 днів після виходу на берег", note=_OFF),
        dict(acq_id="150D_20260904_1449", before="150D_20260624_1449", label="Широкий шлейф на північний схід", note=None),
        dict(acq_id="056A_20260910_0140_VV", before="056A_20260618_0140_VV", label="Найбільша площа плями", note=None),
        dict(acq_id="150D_20260916_1449", before="150D_20260624_1449", label="Останній знімок серії", note=None),
    ],
)

SPECS = {"oman": OMAN}


# ------------------------------------------------------------------ known events (events/candidate_events.csv)
# Labels follow the event chronology; notes are composed from the evidence of each date:
# ERA5 wind at the source, independent observations (NOAA analyst reports, Sentinel-1 / Cerulean slicks of the
# same day, visual check of NISAR quicklooks by the known-events review) and whether the pipeline outlines a
# slick near the source. Facts below are copied from events/candidate_events.md / .csv.
def _num(v, nd=1):
    return f"{v:.{nd}f}".replace(".", ",")


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


_CLS_UA = {"probable": "схоже на нафту", "possible": "можливо нафта"}
SCORES = {}      # event id -> DataFrame(acq_id, obj, score, class): alternative scoring used in the notes


def _event_snapshots(eid, groups, label_fn, ql=(), noaa=(), s1=None, source_word="джерела", extra_notes=None):
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
                parts.append(f"Біля {source_word} проходить шов між кадрами знімка (смуга без даних)")
            w = _wind_at(region, aid, lon, lat)
            if w is not None:
                q = ("; майже штиль: темні ділянки можуть бути не нафтою" if w < 2 else
                     "; сильний вітер: тонкі плями погано видно" if w > 8 else "")
                ws = "<1" if w < 1 else f"~{_num(w, 0)}"
                parts.append(f"Вітер біля {source_word} {ws} м/с (ERA5){q}")
            evidence = False
            if date in noaa:
                parts.append("Аналітики NOAA бачили пляму в цей день на знімках інших супутників")
                evidence = True
            if date in s1:
                parts.append(f"Sentinel-1 цього дня, на ~11 год раніше: пляма {_num(s1[date])} км² біля вента (Cerulean, машинна детекція)")
                evidence = True
            if date in ql:
                parts.append(f"Візуально на знімку видно пляму біля {source_word}")
                evidence = True
            near = d[(d.d_src_km <= R) & d["class"].isin(["probable", "possible"])].sort_values("score", ascending=False)
            if len(near):
                r = near.iloc[0]
                txt = f"Конвеєр виділяє пляму біля {source_word} («{_CLS_UA[r['class']]}», оцінка {_num(r.score, 2)})"
                if r.area_km2 > 200 and (w is not None and w < 3.5):
                    txt += f"; ділянка {int(round(r.area_km2))} км² — це переважно штиль, вона більша за саму пляму"
                parts.append(txt)
            elif evidence:
                parts.append(f"Конвеєр пляму біля {source_word} не виділяє")
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
            return "Слід від точки ще до першого повідомлення NOAA" if ev == "ql" else "До першого повідомлення NOAA (03.08)"
        if d <= "2026-09-21":
            n = (D.fromisoformat(d) - D.fromisoformat(start)).days
            return f"{n}-й день після першого повідомлення"
        return "Після останнього звіту NOAA (20.09)"
    # 156D 'before' = 20.01.2026 (BETA product, clean sea): on 07.07 and 19.07 a thin plume from the point is
    # already visible (checked on full-resolution crops, 15.11.2026), so July dates cannot serve as 'before'
    groups = {"156D_20260120_0045": ["156D_20260707_0045_HH", "156D_20260719_0045_HH", "156D_20260812_0045_HH", "156D_20260824_0045_HH", "156D_20260905_0045_HH",
                                     "156D_20260917_0045_HH", "156D_20260929_0045_HH", "156D_20261011_0045_HH"],
              "033A_20260710_1126": ["033A_20260722_1126", "033A_20260815_1126", "033A_20260827_1126",
                                     "033A_20260908_1126", "033A_20260920_1126", "033A_20261002_1126", "033A_20261014_1126"]}
    return dict(
        region="ev_ei316", id="eugene-island-316-2026",
        title="Eugene Island 316, Мексиканська затока",
        description=("Повторювана нафтова пляма в блоці Eugene Island 316 біля узбережжя Луїзіани. З 03.08 до 20.09.2026 "
                     "аналітики NOAA/NESDIS щоразу бачили її в одній і тій самій точці й пов'язують із трубопроводом; "
                     "офіційно джерело не встановлене, берегова охорона США та BSEE розслідують. Плями виділено автоматично "
                     "за знімками NISAR L-band (HH, 40 МГц); оцінка «схоже на нафту» — ранжування для перевірки, а не доказ. "
                     "На знімках NISAR 07.07 і 19.07 тонкий шлейф від тієї самої точки видно ще до першого повідомлення. "
                     "«До» — знімок того самого треку без сліду біля точки: для треку 156D це 20.01.2026, для 033A — 10.07.2026."),
        source_url="https://incidentnews.noaa.gov/incident/11216",
        known_source=(-91.61861, 28.26278),
        known_source_label="Точка витоку за звітами NOAA (відоме джерело)",
        snapshots=_event_snapshots("ei316", groups, label, ql={"2026-07-07", "2026-07-19", "2026-08-12", "2026-08-27", "2026-09-05",
                                                                "2026-09-20", "2026-10-14"},
                                   noaa={"2026-08-15", "2026-08-27", "2026-09-08", "2026-09-17", "2026-09-20"}, source_word="точки витоку",
                                   extra_notes={"2026-10-11": "Велика ділянка ~1130 км² на півночі кадру з оцінкою «схоже на нафту» — "
                                                              "це плямиста зона слабкого вітру, а не нафта (перевірено візуально); "
                                                              "поточна оцінка тут помиляється"}))


def _gc600():
    ql = {"2026-06-25", "2026-07-07", "2026-07-19", "2026-07-27", "2026-08-12", "2026-09-08", "2026-09-13", "2026-09-17",
          "2026-09-29", "2026-10-14"}
    s1 = {"2026-06-21": 11.67, "2026-08-15": 7.11, "2026-09-08": 19.81, "2026-09-20": 2.44, "2026-10-14": 1.44}

    def label(d, ev):
        return {"ql": "Пляму біля вента видно на знімку", "s1": "Sentinel-1 бачив пляму цього дня"}.get(ev, "Без незалежного підтвердження")
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
        title="Green Canyon 600, Мексиканська затока",
        description=("Природні нафтові сипи на глибині ~1180 м (вент Mega Plume). Нафта піднімається з дна постійно; пляма на "
                     "поверхні з'являється біля вента при вітрі ~2–7 м/с і живе кілька годин. У районі є й інші сипи Green "
                     "Canyon, тому плями далеко від вента — не обов'язково помилки. Знімки NISAR L-band, VV 5 МГц (грубіша "
                     "роздільність); оцінка «схоже на нафту» — ранжування для перевірки, а не доказ. Сип діє постійно, тому "
                     "«До» — знімок того самого треку, на якому плями біля вента не видно (може бути пізнішим за інші дати)."),
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC7387546",
        known_source=(-90.5743, 27.36986),
        known_source_label="Вент Mega Plume (відоме джерело)",
        snapshots=_event_snapshots("gc600", groups, label, ql=ql, s1=s1, source_word="вента"))


_RAIN = ("Велика ділянка ~{a} км² {where} з оцінкою «схоже на нафту» — темна пляма з яскравою облямівкою, типова для "
         "дощової комірки, а не нафти (перевірено візуально); поточна оцінка тут помиляється")


def _wreck1487():
    ql = {"2026-06-16", "2026-06-21", "2026-08-20", "2026-09-01", "2026-09-08", "2026-09-20"}
    noaa = {"2026-06-16", "2026-07-03", "2026-07-27", "2026-08-15", "2026-08-20", "2026-09-01", "2026-09-08",
            "2026-10-02", "2026-10-07"}

    def label(d, ev):
        return {"ql": "Пляму біля судна видно на знімку", "noaa": "Аналітики NOAA бачили пляму цього дня"}.get(
            ev, "Без незалежного підтвердження")
    # 'before': strong wind (~12 m/s) and no NOAA report within +-1 day
    groups = {"040D_20260722_2335": ["040D_20260616_2335", "040D_20260628_2335", "040D_20260710_2335", "040D_20260815_2335",
                                     "040D_20260827_2335", "040D_20260908_2335", "040D_20260920_2335", "040D_20261002_2335",
                                     "040D_20261014_2335", "040D_20261026_2335"],
              "104A_20261019_0941": ["104A_20260621_0942", "104A_20260703_0942", "104A_20260715_0942_VV",
                                     "104A_20260727_0942_VV", "104A_20260820_0941", "104A_20260901_0941_VV",
                                     "104A_20260925_0941", "104A_20261007_0941", "104A_20261031_0941_VV"]}
    return dict(
        region="ev_wreck1487", id="wreck-1487-nantucket-2026",
        title="Wreck 1487, південніше Нантакета (США)",
        description=("Затонуле судно (Wreck 1487) приблизно за 90 морських миль на південь від Нантакета. Звідси постійно "
                     "виходять невеликі плями нафти: аналітики NOAA повідомляли про них у 68 днів з 03.10.2025 до 06.11.2026, "
                     "площа плям 0,02–6,5 км². Знімки NISAR L-band, VV 5 МГц (груба роздільність): такі малі плями на межі "
                     "можливостей знімка, і автоматичний конвеєр біля судна їх майже не виділяє. Оцінка «схоже на нафту» — "
                     "ранжування для перевірки, а не доказ. «До» — знімок того самого треку при сильному вітрі (~12 м/с) "
                     "без звітів NOAA за ±1 день."),
        source_url="https://www.ospo.noaa.gov/data/ocean/marinepollution/2026/20260912_1048_SENTINEL1C_OIL.txt",
        known_source=(-69.9175, 40.10056),
        known_source_label="Затонуле судно Wreck 1487 (відоме джерело)",
        snapshots=_event_snapshots("wreck1487", groups, label, ql=ql, noaa=noaa, source_word="судна", extra_notes={
            "2026-08-27": _RAIN.format(a=160, where="на південному заході кадру"),
            "2026-09-08": _RAIN.format(a=290, where="на північному сході кадру")}))


SPECS.update({"ei316": _ei316, "gc600": _gc600, "wreck1487": _wreck1487})


# ------------------------------------------------------------------ remaining known events: automatic specs
# Same rules as above, chosen automatically: the two track/polarisation groups with most acquisitions that see
# the source (or the area); 'before' of a group = date with no candidate object near the source (or the fewest
# objects for an area event) and the wind closest to 7 m/s; notes from wind, independent evidence and the
# pipeline; large 'probable' areas in near-calm are flagged in the note as probable calm zones.
_CALM_NOTE = ("Велика ділянка ~{a} км² з оцінкою «схоже на нафту» при майже штилі (~{w} м/с) — найімовірніше, "
              "зона штилю, а не нафта")


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
                q = ("; майже штиль: темні ділянки можуть бути не нафтою" if w < 2 else
                     "; сильний вітер: тонкі плями погано видно" if w > 8 else "")
                ws = "<1" if w < 1 else f"~{_num(w, 0)}"
                parts.append(f"Вітер {('біля ' + source_word) if source_word else 'в районі'} {ws} м/с (ERA5){q}")
            evidence = False
            if date in noaa:
                parts.append("Аналітики NOAA бачили пляму в цей день на знімках інших супутників")
                evidence = True
            if date in s1:
                parts.append(s1[date])
                evidence = True
            if date in ql:
                parts.append(f"Візуально на знімку видно пляму{(' біля ' + source_word) if source_word else ''}")
                evidence = True
            if has_src:
                near = o[(o.d_src_km <= R) & o["class"].isin(["probable", "possible"])].sort_values("score", ascending=False)
                if len(near):
                    r = near.iloc[0]
                    parts.append(f"Конвеєр виділяє пляму біля {source_word} («{_CLS_UA[r['class']]}», оцінка {_num(r.score, 2)})")
                elif evidence:
                    parts.append(f"Конвеєр пляму біля {source_word} не виділяє")
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
        when = f"на ~{int(round(h))} год {'раніше' if p['dt_hours_nisar_minus_s1'] > 0 else 'пізніше'}" if h >= 1 else "майже одночасно"
        out[d] = f"Sentinel-1 цього дня ({when}): пляма {_num(p['area_km2'])} км² {word} (Cerulean)"
    return out


def _neft():
    ql = _ql_dates("neft_dashlari")
    return dict(region="ev_neft_dashlari", id="neft-dashlari-caspian-2026", title="Нафтові Камені, Каспійське море",
                description=("Нафтові Камені (Neft Daşları) — морський промисел на палях у Каспійському морі, видобуток з 1949 року. "
                             "Біля комплексу регулярно видно плями: витоки з платформ і трубопроводів, а також природні сипи. "
                             "Плями виділено автоматично за знімками NISAR L-band (HH, 20/40 МГц); оцінка «схоже на нафту» — "
                             "ранжування для перевірки, а не доказ. «До» — знімок того самого треку без плям біля комплексу."),
                source_url="https://en.wikipedia.org/wiki/Neft_Da%C5%9Fları", known_source=(50.8583, 40.2361),
                known_source_label="Промисел Нафтові Камені (відоме джерело)",
                snapshots=_auto_snapshots("neft_dashlari", lambda d, ev: "Пляму біля промислу видно на знімку" if ev == "ql"
                                          else "Без незалежного підтвердження", ql=ql, source_word="промислу"))


def _cop():
    s1 = _s1_notes("coal_oil_point", "біля поля сипів")
    ql = {d for d in _ql_dates("coal_oil_point") if d >= "2026-06-01"}
    return dict(region="ev_coal_oil_point", id="coal-oil-point-seeps-2026", title="Coal Oil Point, протока Санта-Барбара",
                description=("Одне з найбільших у світі полів природних нафтових сипів біля узбережжя Каліфорнії: 100–150 барелів "
                             "нафти на добу. Плями добре видно ввечері при слабкому вітрі; ранкові проходи часто в штиль. Поруч є "
                             "нафтові платформи. Плями виділено автоматично за знімками NISAR L-band; оцінка «схоже на нафту» — "
                             "ранжування для перевірки, а не доказ. «До» — знімок того самого треку без плям біля поля сипів."),
                source_url="https://en.wikipedia.org/wiki/Coal_Oil_Point_seep_field", known_source=(-119.8833, 34.4),
                known_source_label="Поле сипів Coal Oil Point (відоме джерело)",
                snapshots=_auto_snapshots("coal_oil_point", lambda d, ev: {"ql": "Пляму біля сипів видно на знімку",
                                                                           "s1": "Sentinel-1 бачив пляму цього дня"}.get(ev, "Без незалежного підтвердження"),
                                          ql=ql, s1=s1, source_word="поля сипів"))


def _uae():
    s1 = _s1_notes("uae_uaq", "у районі витоку")

    def label(d, ev):
        if d < "2026-10-09":
            return "До ураження танкера (контроль)"
        if d < "2026-10-19":
            return "Після ураження танкера, до помітного витоку"
        if d <= "2026-10-30":
            return "Виток: Sentinel-1 бачив пляму цього дня" if ev == "s1" else "Виток триває"
        return "Після зупинки витоку (30.10): залишки плями" if ev == "s1" else "Після зупинки витоку (30.10)"
    return dict(region="ev_uae_gem2_2026", id="uae-gem2-umm-al-quwain-2026", title="Умм-ель-Кайвайн, ОАЕ",
                description=("Супертанкер (за даними аналітиків — GEM No. 2) уражено 09.10.2026; з 19.10 з нього витікала нафта "
                             "приблизно за 25 км від Умм-ель-Кайвайна, 22.10 нафта дійшла до берега, 30.10 виток зупинено. Точне "
                             "місце танкера не опубліковано. Під час витоку майже штиль (~2–3 м/с), тому на L-band пляму важко "
                             "відрізнити від штилю. Плями виділено автоматично за знімками NISAR L-band (HH); оцінка «схоже на "
                             "нафту» — ранжування для перевірки, а не доказ. Дати до 09.10 — контроль без витоку."),
                source_url="https://thenationalnews.com/news/uae/2026/11/13/hundreds-of-workers-continue-to-clean-oil-spilt-off-the-uae",
                known_source=None,
                snapshots=_auto_snapshots("uae_gem2_2026", label, s1=s1, point=(55.635, 25.78), date_from="2026-08-01",
                                          max_per_group=8, before_max="2026-10-08"))


def _canary():
    return dict(region="ev_twin_canary_lee", id="canary-lee-twin-2026", title="Тенерифе – Ла-Гомера (двійник без нафти)",
                description=("Контрольний район без нафти: вітрова тінь острова Тенерифе в протоці до Ла-Гомери. За пасатом "
                             "утворюються штильові смуги й фронти, які на радарі темні, як нафта. Нафтовидобутку тут немає. Усе, "
                             "що конвеєр тут позначає як «схоже на нафту», — хибні тривоги; набір показує, як часто вони трапляються."),
                source_url="https://api.cerulean.skytruth.org/", known_source=None,
                snapshots=_auto_snapshots("twin_canary_lee", lambda d, ev: "Вітрова тінь: нафти немає", ql=set(),
                                          twin_note="Нафти в районі немає: позначені плями — хибні тривоги"))


def _baltic():
    return dict(region="ev_twin_baltic_bloom", id="baltic-bloom-twin-2026", title="Готландська западина, Балтика (двійник без нафти)",
                description=("Контрольний район без нафти: влітку 2026 року тут цвіли ціанобактерії (звіт SMHI № 8, 25.08.2026). "
                             "Поверхневі скупчення водоростей гасять дрібні хвилі й на радарі темні, як нафта. Усе, що конвеєр тут "
                             "позначає як «схоже на нафту», — хибні тривоги; набір показує, як часто вони трапляються."),
                source_url="https://www.smhi.se/en/publications-from-smhi/publications/2026-08-25-algae-report-number-8-2026",
                known_source=None,
                snapshots=_auto_snapshots("twin_baltic_bloom", lambda d, ev: "Цвітіння ціанобактерій: нафти немає",
                                          date_from="2026-06-19", twin_note="Нафти в районі немає: позначені плями — хибні тривоги"))


SPECS.update({"neft": _neft, "cop": _cop, "uae": _uae, "canary": _canary, "baltic": _baltic})
