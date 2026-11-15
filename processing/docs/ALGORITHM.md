# Processing algorithm

The pipeline (`nisar_oil/`) takes an area of interest and a period. It returns candidate oil slicks, an "oil-likeness" score for each, bright targets (ships, platforms) and candidate source points. It needs no prior knowledge of the event: no clean reference date, no known source position.

```
ASF search ─► remote HDF5 cut-out ─► per-pass mosaic ─► detection layers ─► group self-calibration
   ─► detector masks ─► candidate objects + features + weather context ─► persistence (time series)
   ─► oil-likeness score ─► bright targets ─► source clustering ─► report / web export
```

## 1. Area grid and land mask

- **Grid.** The area (lon/lat box) is projected to its UTM zone with a 60 m grid.
- **Land.** Land comes from Natural Earth 10 m polygons. Rings are combined even-odd, so inland seas such as the Caspian, which are holes in the Eurasia polygon, count as water.
- **Sea mask.** Sea = not land, more than 1 km from the coast, inside the radar swath, not on a frame edge or seam.

## 2. Data discovery and ingest (`ingest.py`)

1. **Discovery.** The ASF Search API lists every NISAR L2 GCOV granule that intersects the area in the period. Reprocessed duplicates are dropped: the newest science product is kept, then pre-release BETA products.
2. **Remote cut-out.** Each granule is opened over HTTPS with NASA Earthdata login, and only the area is read (HTTP range reads through `fsspec` + `h5py`). Layers per granule:
   - **main polarisation:** HH from frequency A, or VV when the pass only has frequency B (NASV mode, 5 MHz);
   - **cross-polarisation:** HV or VH;
   - **noise-equivalent backscatter;**
   - **incidence angle;**
   - **validity mask.**

   Layers are multilooked to about 60 m and resampled onto the area grid. Failed reads are retried, and cut-outs are cached with atomic writes.
3. **Per-pass mosaic.** Frames of one pass (same track, direction, date, less than 5 minutes apart) form one acquisition. When a pass mixes HH and VV frames, it becomes two acquisitions: HH and VV over the sea differ by several dB and must not be mixed.
4. **Grouping.** Acquisitions are grouped by track, direction and polarisation, for example `150D_HH`. Detection thresholds are calibrated per group (step 4).

## 3. Detection layers per acquisition (`detect.py`)

All layers use γ0 of the main polarisation over the sea mask. Method numbers refer to the method battery (`oman_case/battery`, see METHODOLOGY).

| Layer | Method | Definition |
|---|---|---|
| Noise margin | M0 | γ0 − noise-equivalent γ0, dB. Low margin means the "dark" area may be just the noise floor |
| Local contrast | M2 | Smoothed γ0 (5 × 5) relative to the median background of 20 km blocks, dB |
| Censored CFAR ratio | M3b | γ0 relative to the mean of a 4 km ring with a 1 km guard. Ring pixels more than 6 dB above the background (ships, platforms, breakwaters) are excluded, so bright targets do not inflate the ring |
| Thin dark lines | M19 | Sato ridge filter (σ = 2, 4, 6 px) for dark valleys; 3 km coastal strip excluded |
| Block anomaly | M8c | Isolation-forest score of 1 km blocks (mean, 10th percentile and spread of contrast, mean valley response) |
| Cross-pol contrast | M9 | HV (or VH) contrast to its own background, its noise margin and the depolarisation difference (HV − HH) |

## 4. Self-calibration per track group

Oil covers a tiny share of the sea on almost every date. Thresholds are therefore taken from the data of the group itself, with no clean control date:

| Detector | Threshold |
|---|---|
| M3b | median over dates of the per-date 0.1 % quantile of the CFAR ratio |
| M19 | median over dates of the per-date 99.5 % quantile of the valley response |
| M8c | isolation forest trained on 1 km blocks pooled from all dates; threshold = 99.5 % quantile of the anomaly score |
| M2 | fixed: −0.8 dB for HH, −1.0 dB for VV (from the reference case) |

**Detector masks:**
- M2 mask: contrast below its threshold, components of at least 2 km²;
- M3b mask: ratio below its threshold, components of at least 1 km²;
- M19 mask: valley response above its threshold, components of at least 0.5 km².

## 5. Candidate objects and features (`objects.py`)

A candidate object is a connected component of at least 1 km² in the union of the M2, M3b and M19 masks. Each object gets these features:

| Group | Features |
|---|---|
| Size and shape | area, compactness, elongation, solidity, orientation |
| Radiometry | median and 10th-percentile contrast; texture inside vs. surroundings (coefficient of variation and its ratio); edge step and edge gradient (dB/km); noise margin |
| Detectors | which of M2, M3b, M19, M8c see the object; their number ("agreement"); mean anomaly score |
| Polarisation | HV contrast, HV noise margin, depolarisation difference (where a cross-pol channel exists) |
| Context | distance to land; ERA5 10 m wind speed and direction; precipitation over the previous 3 h; surface current (Open-Meteo marine, SMOC) |
| Drift (M15) | expected drift = current + 3 % of wind; misalignment between the object's long axis and the drift (elongated objects only) |
| Origin | the upwind end of the object: where a slick from a point source starts |

**Persistence (M13, time series).** For every other date of the same track that sees at least half of the object, the candidates touching it are compared with the object by intersection over union (IoU) over pixels seen on both dates. The median over dates gives `persist_iou`:
- drifting oil changes shape between 12-day passes, so IoU ≈ 0;
- lagoon mouths, shoals, harbour basins and coastal wind shadows repeat with the same outline, so IoU is around 0.45–0.7.

## 6. Oil-likeness score (`scoring.py`)

An interpretable weighted sum, calibrated on the labelled objects of the reference case (oil = source-linked slicks, background = objects on control dates):

1. **Evidence per feature.** `e = clip((x − median_background) / (median_oil − median_background), 0, 1)` for contrast (10th percentile), texture ratio, edge step and HV contrast.
2. **Weights.** Each feature's weight is its separation on the reference case, `|AUC − 0.5| × 2`. HV gets weight 0.3 (only 3 oil examples with HV), detector agreement 0.5, drift alignment 0.3.
3. **Quality gates** multiply the score:

   | Condition | Multiplier |
   |---|---|
   | within 2 km of the coast | × 0.6 |
   | ERA5 wind < 3 m/s | × 0.5 |
   | noise margin < 1 dB | × 0.5 |
   | rain > 1 mm in 3 h | × 0.6 |
   | area < 2 km² | × 0.8 |
   | static outline (IoU ≥ 0.4 on ≥ 2 other dates) | × 0.4 |

4. **Classes:**
   - **probable:** score ≥ 0.6;
   - **possible:** 0.4–0.6;
   - **background:** below 0.4.

   This is a ranking for human review, not a probability. The gate names are stored per object as `flags`.

## 7. Bright targets (M18, `sources.py`)

- **Detection.** CFAR on unsmoothed γ0: gamma clutter model with the equivalent number of looks estimated from the scene; 2 km window, 300 m guard; false-alarm probability 10⁻⁶; minimum SNR 13 dB.
- **Classes:**
  - **coastal:** within 2 km of land;
  - **platform:** offshore, and a target within 600 m on another date;
  - **ship:** all other offshore targets.

## 8. Source finding (M14)

1. **Objects used:** score ≥ 0.4 and area ≥ 2 km².
2. **Clustering.** The objects' origin points are clustered with DBSCAN (radius 5 km, at least 3 objects).
3. **Candidate sources.** Clusters seen on at least 2 dates are kept and ranked by number of dates, then by total slick area. Each gets the distance to the nearest platform and the nearest ship.

A chronic source shows up as many slicks starting from the same place on different dates.

## 9. Outputs and web export

- **Tables and figures.** Objects (CSV + GeoJSON outlines), sources, bright targets, per-pass event flags, per-group calibration, overview figures, timeline and a markdown report.
- **Web export (`export_web.py`, contract 1.2).**
  - Rasters are resampled to a grid regular in EPSG:3857 inside the location's lon/lat box (what `L.imageOverlay` expects).
  - Brightness is stretched to the 2–98 % percentiles per track/polarisation pair, so "before" and "after" share one scale. Rasters are lossless WebP with transparent no-data and land.
  - Per snapshot: the probable mask (`#ef4444`), one GeoJSON contour per probable or possible slick (class, score, flags), bright targets, sources.
  - Timeline labels and notes: hand-written for the reference case; for the known events, generated from the evidence of each date (`web_specs.py`):
    - ERA5 wind at the source;
    - NOAA analyst reports;
    - Sentinel-1/Cerulean slicks of the same day;
    - visual checks of the radar image;
    - whether the pipeline outlines a slick near the source.

## Engineering notes

- **Parallelism.** Ingest runs 6–10 parallel range readers per area. Detection runs one process per acquisition. Persistence runs one process per track group.
- **Weather requests.** ERA5 is requested on a 0.25° grid (0.5° for the runs of 15.11.2026 after the API quota was hit) and currents on a 1/3° grid. The free Open-Meteo quota is handled: an hourly limit is waited out; on the daily limit the request fails fast and the data are filled in later (`backfill_ancillary.py`).
- **Speed.** About 5–15 s of detection per pass on one core. Download time dominates: ~1 MB/s per range reader.
