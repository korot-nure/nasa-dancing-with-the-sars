# Dancing with the SARs

**All-weather, day-and-night marine oil spill detection, drift tracking, and multi-temporal impact visualization powered by NASA-ISRO SAR (NISAR) L2 GCOV data.**

- **Live Demo (GitHub Pages):** https://korot-nure.github.io/nasa-dancing-with-the-sars/
- **Repository:** https://github.com/korot-nure/nasa-dancing-with-the-sars
- **Submission & Demo Pack:** [`docs/SUBMISSION_GUIDE_PACK.md`](./docs/SUBMISSION_GUIDE_PACK.md)

---

## Overview

Optical satellites are blind through thick clouds, smoke, and polar or tropical night—precisely when maritime disasters and illegal bilge dumping often go unnoticed. **Dancing with the SARs** transforms **NASA NISAR Level 2 Geocoded Covariance (L2 GCOV)** Synthetic Aperture Radar products into an interactive, browser-based geospatial intelligence tool for rapid oil spill response.

Because oil dampens sea-surface capillary waves, it produces a distinct dark backscatter signature ($\gamma^0_{HH}$ / $\gamma^0_{HV}$) in L-band SAR imagery. Our platform pairs this radar physics with an intuitive **Split-Curtain Map**, **Multi-Temporal Snapshot Timeline**, and **Drift Trajectory Overlay** so responders, researchers, and environmental agencies can inspect spills in seconds.

---

## Key Features

- **Cartographic Basemap ↔ SAR Split Curtain:** Drag a live comparison curtain between a readable geographic map on the left and calibrated SAR backscatter + segmented `#ef4444` oil slick masks and GeoJSON contours on the right.
- **Multi-Temporal Snapshot Timeline (`T0..Tn`) + Auto-Play:** Step through pre-event baselines (`T0`), initial detections (`T1`), and follow-up satellite passes (`+N` days) with play/pause animation.
- **Drift Trajectory & Area Delta (`Δ km²`):** Automatically computes GeoJSON slick centroids, directional drift vectors between passes, previous-step dashed outlines, and step-to-step area changes.
- **Live Layer Controls & Multi-Event Minimap:** Adjust slick mask opacity (`0%–100%`), toggle contour outlines, inspect coordinate HUDs, and jump across global spill/seep case studies.

---

## Included NISAR Case Studies

1. **Al Hallaniyat Islands, Oman (`oman-caroline-bezengi-2026`)** — Major oil spill following the grounding of the tanker *Caroline Bezengi* in the Arabian Sea (138.2 km² peak tracked area).
2. **Green Canyon 600, Gulf of Mexico (`green-canyon-600-seeps-2026`)** — Natural hydrocarbon seeps and surface slick dynamics monitored across multi-pass NISAR acquisitions.
3. **Eugene Island 316, Gulf of Mexico (`eugene-island-316-2026`)** — Persistent offshore infrastructure and surface slick monitoring.

---

## Tech Stack & Architecture

- **Frontend:** React 18, TypeScript, Vite, Leaflet (`frontend/`)
- **Data Pipeline & Spec:** Python / HDF5 (`NISAR L2 GCOV`) → dB radiometric calibration, background offset compensation, speckle filtering, slick segmentation → georeferenced WebP rasters + GeoJSON contours + `v1.0` JSON contract (`docs/API_CONTRACT.md`, `docs/BACKEND_TECHNICAL_SPEC.md`)
- **Deployment:** Automated static build & deploy via GitHub Actions (`.github/workflows/deploy-pages.yml`)

```text
NASA_Dancing_with_the_SARs/
├── .github/workflows/   # GitHub Pages CI/CD
├── data/locations/      # Processed WebP, GeoJSON & metadata per event
├── docs/                # API contract, backend spec, frontend plan, submission pack
├── frontend/            # React + TypeScript + Vite + Leaflet web application
├── mockup/              # Standalone HTML prototype
├── processing/          # NISAR processing pipeline, validation and docs (see processing/README.md)
├── LICENSE              # MIT License
└── README.md
```

---

## Data Processing & Methodology

The slick masks, contours, bright targets and source points shown in the app come from the Python pipeline in [`processing/`](./processing/README.md):

- [`processing/docs/ALGORITHM.md`](./processing/docs/ALGORITHM.md) — the processing algorithm, step by step:
  - remote NISAR L2 GCOV cut-outs;
  - self-calibrated detectors;
  - candidate slicks with radiometric, shape, polarimetric, wind/drift and time-series features;
  - oil-likeness score;
  - bright targets and source clustering;
  - web export.
- [`processing/docs/METHODOLOGY.md`](./processing/docs/METHODOLOGY.md) — physical basis, method battery on the Oman reference spill, validation on 9 known events (7 oil events + 2 oil-free look-alike areas), results, limitations and future work.

---

## Local Development

```bash
cd frontend
npm install
npm run dev
```

To create a production build:

```bash
cd frontend
npm run build
```

---

## NASA Data Sources & Citations

- **NASA-ISRO Synthetic Aperture Radar (NISAR) Level 2 Geocoded Covariance (`L2 GCOV`)** — L-band $\gamma^0_{HH}$ and $\gamma^0_{HV}$ calibrated backscatter products accessed via NASA Earthdata / Alaska Satellite Facility (ASF DAAC).
- **Basemap & Reference Layers:** OpenStreetMap / CARTO basemap tiles for geographic context.

---

## License

This project is open source and licensed under the [MIT License](./LICENSE).
