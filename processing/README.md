# Processing pipeline: NISAR L-band oil-slick and source detection

This folder contains the data-processing side of **Dancing with the SARs**. It turns NASA-ISRO NISAR L2 GCOV radar products into the slick masks, contours, bright targets and source points that the web application shows (`../data/locations/`, contract `../docs/API_CONTRACT.md`).

- [`docs/ALGORITHM.md`](docs/ALGORITHM.md): the processing algorithm, step by step, with parameters.
- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md): physical basis, how the method was developed and validated on 9 known events, results, limitations and future work.

## Layout

| Path | What it is |
|---|---|
| `nisar_oil/` | The pipeline (Python package): ingest, detection, objects, scoring, sources, report, web export, known-events runner and validation |
| `nisar_oil/calibration_oman.json` | Statistics the current oil-likeness score uses (from the Oman reference case) |
| `oman_case/battery/` | Method battery (M0–M21) tested on the reference case (Oman, tanker *Caroline Bezengi*, 2026) |
| `oman_case/scripts/` | Data extraction and analysis scripts used for the reference case |
| `oman_case/results/` | Per-method result tables of the reference case; `objects.csv` is the labelled object table the score is calibrated on |
| `events/candidate_events.csv` | The 9 known events (7 oil events and 2 oil-free "twins"): coordinates, activity windows, NISAR coverage, independent evidence |
| `events/scripts/` | Event selection: NISAR coverage (ASF), ERA5 wind statistics, Sentinel-1 slick matches (Cerulean), quicklooks |
| `events/data/` | Independent evidence: NOAA/NESDIS marine pollution reports, Cerulean Sentinel-1 slick polygons |
| `events/results/` | Validation results: per-event metrics, model weights, per-event source and acquisition tables (`regions/`) |

## Running

Python 3.12. Install the dependencies:

```bash
pip install -r nisar_oil/requirements.txt
```

Before running:
- **NASA Earthdata credentials.** Put them in `~/.netrc` (machine `urs.earthdata.nasa.gov`). NISAR GCOV granules are read remotely from ASF with HTTP range requests; only the area of interest is downloaded.
- **Natural Earth 10 m land polygons.** Download `ne_10m_land` to `oman_case/data_cache/natural_earth_land/ne_10m_land.shp`.
- **Wind, precipitation and currents.** These come from Open-Meteo (ERA5 archive and marine API), no account needed.

```bash
# any area and period
python -m nisar_oil.run --name my_area --bbox 54.9,25.2,56.0,26.1 --start 2026-09-15 --end 2026-11-13

# the 9 known events, then the validation
python -m nisar_oil.events
python -m nisar_oil.evaluate

# web data package (contract 1.2) for all known events
python -m nisar_oil.export_all --out web_data oman ei316 gc600 wreck1487 neft cop uae canary baltic
```

Outputs go to `runs/<region>/`:
- `output/objects.csv` and `output/objects.geojson`: every candidate slick with its features, score and class;
- `output/sources.csv` and `output/sources.geojson`: candidate source points;
- `output/bright_targets.csv`: ships, platforms and coastal targets;
- figures and `output/report.md`.

## What is not in this repository

- **Input data, regenerable from public archives with the code above:**
  - NISAR granules and region cut-outs (~1–2 GB per region);
  - intermediate acquisitions and detection maps;
  - weather caches.
- **The full per-object tables of the validation** (`objects_labelled.csv`, `loeo_predictions.csv`, ~8 MB). `python -m nisar_oil.evaluate` recreates them from the run outputs.
- **NISAR S-band data and its downloader.** 41 S-band products over the Oman case were obtained from ISRO Bhoonidhi but have not been analysed yet, so they do not enter any result.
- **Working notes in Russian.** Their content is summarised in the two documents in `docs/`.

Two other pieces of text are not in English:
- the per-run markdown report and some figure captions produced by the scripts are in Russian;
- the location titles, labels and notes for the web application (`nisar_oil/web_specs.py`) are in Ukrainian.
