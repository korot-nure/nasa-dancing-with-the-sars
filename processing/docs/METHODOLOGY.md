# Methodology

## 1. Question and approach

**Question.** Can NISAR L-band radar alone find oil slicks at sea and point to where they come from, in an area where the answer is not known in advance?

**Approach in three steps:**
1. **Method battery on one well-documented event.** Test many detection methods on a single known spill and keep those that work.
2. **Pipeline that transfers the kept methods to any area and period.** It calibrates itself from the data and needs no clean reference date or known source.
3. **Validation on a set of independent known events.** The set includes oil-free "twins" that look like oil on radar. Each event is checked with one uniform rule, and any learned combination of features is tested on events it has not seen.

## 2. Physical basis

**How oil shows on radar.**
- Over the sea, L-band radar (wavelength ≈ 24 cm) is backscattered mainly by short wind waves of about half the radar wavelength: Bragg scattering, waves of ~12–15 cm.
- An oil film raises surface viscosity and damps these waves, so the slick returns less energy and appears **dark**.
- The contrast exists only when there are waves to damp, roughly at 3–10 m/s wind:
  - in calm the whole sea is dark;
  - in strong wind the film is broken up and mixed.

**What else looks dark (look-alikes)** — any process that damps or removes short waves:
- **low-wind zones** and **island wind shadows**;
- **rain cells**: a dark core with a bright rim;
- **biogenic films**: algal and cyanobacteria blooms, natural surfactants along fronts and eddies;
- **upwelling of cold water**;
- **internal waves.**

Separating oil from look-alikes is the core difficulty. A single feature does not do it, which is why the pipeline combines several.

**Polarisations and frequencies.**
- **HH and VV (co-polarised channels)** carry the slick contrast. In the reference case the contrast was −1.1…−1.7 dB in HH and −1.4…−2.7 dB in VV.
- **HV (cross-polarised)** over the sea is close to the noise floor. It helps as a supporting feature only where the noise margin allows.
- **Dielectric/polarimetric methods** need simultaneous full polarisation (quad-pol). No quad-pol data over the sea were available at the sites checked.
- **NISAR S-band** was obtained for the reference case (41 products from ISRO Bhoonidhi) but is not yet analysed. An L/S damping ratio is future work (§8).

**Time series.**
- A **chronic source** (seep, leaking wreck, pipeline, production field) produces slicks that start from the same place on many dates but drift in different directions.
- A **static look-alike** (lagoon mouth, shoal, wind shadow) repeats with the **same outline**.
- **Ship discharges** are one-off.

The pipeline uses all three patterns: source clustering (M14) and the static-outline gate (M13).

**Context.**
- **Wind** sets whether a slick can be seen at all.
- **Expected drift** (current + ~3 % of wind) checks whether an elongated slick is plausibly oil (M15).
- **Bright targets** at the head of a slick (a platform or a ship) are strong evidence of a human source (M18).

## 3. Step 1: method battery on the reference case (Oman, 2026)

**Reference case.**
- **What happened.** The tanker *Caroline Bezengi* grounded at Al-Qibliyah island (Hallaniyat Islands, Oman) on 30.06.2026. The oil slick drifted north-east and reached the coast near Ras Madrakah on 12.08.2026.
- **NISAR data.** 28 passes in June–September 2026: track 056A (VV, night) and track 150D (HH, day).
- **Labels.** Slicks linked to the tanker are oil; objects on the control dates before the grounding (18.06 and 24.06) are background.

| Method | Result on the reference case | Verdict |
|---|---|---|
| M0 noise margin | HH/VV far above noise, HV near noise | required quality filter |
| M1 incidence normalisation + global threshold | 1.5–5× more false alarms than M2 | pre-processing only |
| **M2 local contrast** | plume on 10 of 11 dates, false area 0–1.2 km² per 1000 km² | **works**, base detector |
| M3a CFAR with theoretical threshold | threshold too low, up to 19 km² false per 1000 km² | does not work |
| **M3b CFAR calibrated on data** | fewest false alarms (0.5–0.8), misses large slicks | **partly**: small and narrow slicks |
| M4 damping vs. wind model | thousands of km² false on oil dates | does not work without an L-band wind model (GMF) |
| M5 wind from SAR | VV only, error 1.6–7.9 m/s | partly |
| **M6 texture and edge sharpness** | homogeneity inside vs. surroundings, AUC 0.20 (i.e. 0.80 inverted) | **works** against look-alikes |
| M7 shape | AUC 0.55–0.70 | weak alone |
| M8a supervised classifier | AUC 0.43 on held-out scenes | does not work with one event |
| **M8c anomaly detection** | AUC 0.98–1.00, also catches thin filaments | **works** |
| **M8d similarity search** | 7 of the 10 nearest objects are oil | **works** |
| M9 HV contrast | nothing alone, strong as a feature (3 examples) | supporting |
| M10–M11 polarimetry | no quad-pol over the site | not tested |
| M12 L vs. S band | S-band not available at the time | not tested |
| M13 track reference series | loses a chronic source, sees large new slicks | partly |
| **M14 source clustering** | found the tanker 1.9 km away without being told where | **works**, key method |
| M15 drift consistency | slick axis 36° from expected drift vs. 50° from wind | soft feature |
| M16–M17 sub-looks and Doppler (RSLC) | no signal for oil; weak Doppler on large slicks | not used |
| M18 bright targets | ships and anchorages; grounded tanker not separable from the island | context |
| **M19 thin dark lines** | filaments and slick edges | **complement** |
| M20 external data | upwelling coincides with oil; no rain | context, not hard rules |
| M21 coastline change | no signal | not used |

The pipeline (ALGORITHM.md) uses M0, M2, M3b (with bright-target censoring), M6, M8c, M9, M13, M14, M15, M18 and M19. The supervised classifier failed with one event (M8a). The lesson: a learned model needs **several independent events**, which led to Step 3.

## 4. Step 2: the pipeline

The pipeline's self-calibration replaces the control dates the battery relied on: thresholds come from the median over all dates of a track group. Bugs found on the way were fixed, each with a regression run on the reference case (results unchanged):
- **Censored CFAR ring.** Bright platforms and ships inflated the CFAR background by several dB.
- **Static gate by IoU.** It replaced a coverage test that also flagged real slicks.
- **Exact land rasterisation.** Polygon simplification shifted the coast by ~0.1°, and inland seas were filled as land.
- **Polarisations kept separate.** A pass can mix HH and VV frames; they are now separate acquisitions.

**Regression on the reference case:**
- 244 candidate objects;
- the top-ranked source is **3.6 km from the tanker**, seen on 5 dates and both tracks;
- the slick reaching the coast is outlined on the late dates.

**Early dates of the chronic leak.** The automatic pipeline misses the slick at the tanker on the early dates (30.06–11.08). For the web application these dates are filled with the battery's reference outlines (`origin: reference`).

**Blind test (UAE, October 2026).** Tanker leak off Umm Al Quwain; the source position was not published. Wind during the leak was 2–3 m/s. The L-band contrast of the slick was indistinguishable from calm water, and the run produced several false "probable" slicks along the coast. This exposed the main weaknesses — calm water and coastal look-alikes — and motivated the multi-event validation.

## 5. Step 3: validation on known events

### 5.1 Event selection

**Selection criteria:**
- the event is documented by an independent source (published coordinates, analyst reports, Sentinel-1 detections);
- the activity window is known;
- there are enough NISAR L-band passes over the source in 2025–2026 (ASF archive);
- wind is mostly 3–10 m/s (ERA5).

**Twins** are oil-free areas with strong look-alikes; they measure false alarms. Candidates were also checked and rejected; most fall into the NISAR archive gap of mid-January to mid-June 2026.

| Event | Type | Source and evidence | NISAR passes used | Polarisation |
|---|---|---|---|---|
| Oman, *Caroline Bezengi* | one-off tanker grounding | tanker position; reference case | 28 | VV + HH |
| Eugene Island 316, Gulf of Mexico | chronic leak (suspected pipeline) | NOAA/NESDIS analyst reports 03.08–20.09.2026 at one point | 73 | HH (40 MHz) + VV |
| Green Canyon 600, Gulf of Mexico | natural seeps | published vent position (Mega Plume, ~1180 m depth); Sentinel-1 slicks every month (Cerulean) | 51 | VV (5 MHz) + HH |
| Wreck 1487, south of Nantucket | chronic leak from a shipwreck | NOAA reports on 68 days 10.2025–11.2026; slicks 0.02–6.5 km² | 67 | VV (5 MHz) + HH |
| Neft Daşları, Caspian Sea | offshore production field | complex position; recurring slicks in literature | 47 | HH |
| Coal Oil Point, Santa Barbara | natural seep field (100–150 bbl/day) | field position; Sentinel-1 slicks (Cerulean) | 33 (Jun–Nov 2026) | HH |
| UAE, Umm Al Quwain | one-off tanker leak 19–30.10.2026 | Sentinel-1 slick polygon 40 min after the NISAR pass (21.10, 134 km²) | 33 | HH |
| Twin: Tenerife – La Gomera | wind shadow of an island | no oil production; lee calms and fronts | 32 | HH |
| Twin: Gotland Basin, Baltic | cyanobacteria bloom, summer 2026 | SMHI algae reports | 18 (bloom season) | HH + VV |

### 5.2 Uniform labelling

One rule for every event. The known source is used only for labelling and scoring, never by detection.

| Label | Rule |
|---|---|
| **Oil** | an object reaching within R km of the known source on an active date. R = 3 km for point sources, 4 km for the seep field, 6 km for the grounded tanker, 8 km for the production complex. For the UAE event: an object overlapping the Sentinel-1 slick polygon of the same pass |
| **Not oil** | every object in a twin area, and every object on a control date before the event |
| **Unknown** | everything else |

Other dark objects in seep and production scenes may also be oil, and dates outside a known activity window are not proof of absence, so both go to "unknown".

### 5.3 Metrics

**For each held-out event:**
- dates with a slick detected at the source;
- whether a candidate source was found within R + 5 km, at what rank and distance;
- false detections per 1000 km² of sea per pass, on twins and control dates.

The detection threshold is set so that the **training** "not oil" objects give at most 0.3 false detections per 1000 km² per pass.

**Leave-one-event-out.** To test whether a learned combination of all features (logistic regression) beats the current hand-calibrated score, the weights are fitted on 8 events and applied to the 9th, for each event in turn.

### 5.4 Results

**Pipeline as delivered (current score; this is what the web application shows):**

| Event | Candidate source nearest to the known one | Note |
|---|---|---|
| Oman | rank 1, 3.6 km | 5 dates, both tracks |
| Neft Daşları | rank 1, 2.5 km | 6 dates |
| Green Canyon 600 | rank 3, 4.3 km | 10 dates. Ranks 1–2 (24 and 42 km) are likely other Green Canyon seeps |
| Eugene Island 316 | rank 1 at 8.5 km; nearest rank 9 at 5.1 km | |
| Coal Oil Point | rank 1 at 8.6 km; nearest rank 6 at 5.6 km | |
| Wreck 1487 | none; nearest 18 km | slicks below what 5 MHz resolution resolves |
| UAE | source position not published | Sentinel-1 slick of 21.10 not separated from calm water |

| Oil-free areas | "Probable" slicks per 1000 km² per pass |
|---|---|
| Tenerife wind shadow | 0.06 |
| Baltic bloom | 0.02 |
| UAE (whole period, coastal) | 0.20 |

**Learned combination vs. current score (leave-one-event-out, same false-alarm-calibrated threshold):**

| Event | Dates with slick at source: current score | Learned (all features) | Learned, calm areas excluded |
|---|---|---|---|
| Oman | 6 / 11 | 11 / 11 | 11 / 11 |
| Neft Daşları | 9 / 26 | 26 / 26 | 24 / 26 |
| Green Canyon 600 | 10 / 17 | 14 / 17 | 8 / 17 |
| Eugene Island 316 | 3 / 5 | 3 / 5 | 1 / 5 |
| Coal Oil Point | 6 / 28 | 18 / 28 | 11 / 28 |
| Wreck 1487 | 1 / 7 | 5 / 7 | 1 / 7 |
| UAE | 0 / 1 | 1 / 1 | 0 / 1 |

| False detections per 1000 km² per pass | Current | Learned | Learned, calm excluded |
|---|---|---|---|
| Tenerife wind shadow | 0.47 | 0.21 | 0.30 |
| Baltic bloom | 0.04 | 0.07 | 0.10 |
| Oman, before grounding | 0.00 | 0.07 | 0.07 |
| UAE, before the leak | 1.01 | 1.95 | 1.73 |

Pooled oil vs. not-oil separation (AUC over all held-out events):

| Score | AUC |
|---|---|
| current | 0.64 |
| learned | 0.72 |
| learned, calm excluded | 0.58 |
| gradient boosting | 0.54 |

**Interpretation.** The learned combination looks better, but most of the gain is an artefact of the weak labels:
- In calm weather, large calm patches touch the source, and the uniform rule labels them "oil".
- The model learned "large dark area in near-calm = oil".
- Once large areas in near-calm wind (> 100 km² at < 3.5 m/s) are excluded, the gain holds only for Oman and Neft Daşları.
- Maps of the learned score also mark natural surface films along fronts and eddies in the Gulf of Mexico as oil.

**The current hand-calibrated score is therefore kept in the pipeline.** Two of the learned weights also tracked the composition of the event set rather than physics: VV polarisation and low wind. Removing them did not change the result (AUC 0.73 → 0.72).

### 5.5 Findings worth highlighting

- **Source finding works without prior knowledge** at the sources with recurring, well-developed slicks: the tanker (3.6 km), the Neft Daşları complex (2.5 km) and the Green Canyon 600 vent (4.3 km).
- **Early sign of the Eugene Island 316 leak.** On 07.07 and 19.07.2026, a thin plume from the very point NOAA later reported is visible on NISAR (track 156D, HH) — about four weeks before the first NRC report of 03.08.2026. It was found by visual inspection of the radar image; the automatic pipeline does not outline lines that thin.
- **Look-alikes are identified and explained, not hidden:**
  - rain cells: Wreck 1487 on 27.08 and 08.09;
  - a mottled low-wind zone of ~1130 km²: Eugene Island 316 on 11.10;
  - island wind shadows: Tenerife;
  - cyanobacteria films: Baltic.

  On the oil-free twins the false-alarm rate stays low.
- **Human vs. natural drivers.**
  - Human: the production field (Neft Daşları), a suspected pipeline (EI316), a shipwreck (Wreck 1487), tankers (Oman, UAE), ship traffic.
  - Natural: seeps (Green Canyon, Coal Oil Point), biological films, wind and rain.

  Bright targets at the head of slicks (platforms, ships) separate the human sources.

## 6. Limitations

- **Weak labels.** "Within R km of the source on an active date" includes calm patches and misses slicks that drifted away. Two events have very few labelled slicks: EI316 has 5 and UAE has 1. The detector itself outlines little near these sources: thin plumes there, calm water in the UAE.
- **Wind.** Below ~3 m/s, L-band does not separate oil from calm water. ERA5 (~25 km) misses local calms in island lees and near coasts.
- **Resolution.** In the 5 MHz modes (VV, Green Canyon and Wreck 1487) small slicks are at the limit of what the image resolves.
- **No independent ground truth.** Independent evidence comes from analyst reports and machine detections on other satellites; there is no in-situ sampling.
- **Coverage gap.** The NISAR archive has a gap from mid-January to mid-June 2026 over most sites, which removed several otherwise suitable spills.
- **Shortened windows.** Coal Oil Point (June–November 2026) and the Baltic twin (bloom season) were shortened for time.

## 7. Answers to the challenge questions

**What changes do we track?**
- Oil slicks appearing, growing, drifting and fading on the sea surface.
- Pass-to-pass changes in slick area and position, and recurrence at the same place.

**Physical drivers.** Damping of short wind waves by oil films (and by look-alikes):
- slick visibility is set by wind speed;
- slick drift is set by current + ~3 % of wind;
- slick recurrence is set by the source type: chronic vs. one-off.

**Which polarisations highlight the change?**
- The co-polarised channels (HH, VV) carry the contrast; VV shows it stronger than HH.
- HV over the sea is near the noise floor and only supports.

**Future NISAR applications:**
- routine, cloud-independent screening of production areas, pipelines and shipping lanes;
- early warning of chronic leaks: the EI316 plume was visible weeks before the first report;
- dual-frequency (L + S) discrimination of oil from biogenic films.

## 8. Future work

1. **L/S-band contrast** over the Oman tanker. NISAR S-band data for track 56 are downloaded: 5 dates, GCOV / RSLC / GSLC.
2. **Thin-plume detector.** Line tracing from a point to catch early chronic leaks such as EI316 in July.
3. **Cleaner labels.** Manual confirmation of slicks at sources; removal of calm patches; more events with different polarisation and wind mixes. Then a learned combination of features can be revisited.
4. **More context.** AIS ship tracks to confirm ship sources; an L-band wind model (GMF) for radar-derived wind.

## 9. Data and acknowledgements

- **NISAR L2 GCOV** (NASA-ISRO), L-band, via NASA Earthdata / ASF DAAC. NISAR S-band via ISRO Bhoonidhi.
- **ERA5 reanalysis** (ECMWF / Copernicus) and **SMOC surface currents** (Mercator / Météo-France), via the Open-Meteo APIs.
- **NOAA/NESDIS** Marine Pollution Surveillance Reports and NOAA IncidentNews.
- **Cerulean** (SkyTruth) Sentinel-1 slick detections.
- **SMHI** algae reports (Baltic).
- **Natural Earth** 10 m land polygons.
- Published sources for event positions: *Scientific Reports* 2020 for the Green Canyon 600 vent; news reports for the Oman and UAE events (links in `events/candidate_events.csv`).
