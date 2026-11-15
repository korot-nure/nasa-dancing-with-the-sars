# Dancing with the SARs

**All-weather, day-and-night marine oil spill detection, drift tracking, and multi-temporal impact visualization powered by NASA-ISRO SAR (NISAR) L2 GCOV data.**

- **Live Demo (GitHub Pages):** https://korot-nure.github.io/nasa-dancing-with-the-sars/
- **Repository:** https://github.com/korot-nure/nasa-dancing-with-the-sars
- **Submission & Demo Pack:** [`docs/SUBMISSION_GUIDE_PACK.md`](./docs/SUBMISSION_GUIDE_PACK.md)

---

## Overview

Optical satellites are blind through thick clouds, smoke, and polar or tropical night—precisely when maritime disasters and illegal bilge dumping often go unnoticed. **Dancing with the SARs** transforms **NASA NISAR Level 2 Geocoded Covariance (L2 GCOV)** Synthetic Aperture Radar products into an interactive, browser-based geospatial intelligence tool for rapid oil spill response.

Because oil dampens sea-surface capillary waves, it produces a distinct dark backscatter signature ($\gamma^0_{HH}$ / $\gamma^0_{VV}$) in L-band SAR imagery. Our platform pairs this radar physics with an intuitive **Split-Curtain Map**, **Multi-Temporal Snapshot Timeline**, and **Drift Trajectory Overlay** so responders, researchers, and environmental agencies can inspect spills in seconds.

---

## Key Features

- **Cartographic Basemap ↔ SAR Split Curtain:** Drag a live comparison curtain between a readable geographic map on the left and calibrated SAR backscatter + segmented `#ef4444` oil slick masks and GeoJSON contours on the right.
- **Multi-Temporal Snapshot Timeline (`T0..Tn`) + Auto-Play:** Step through pre-event baselines (`T0`), initial detections (`T1`), and follow-up satellite passes (`+N` days) with play/pause animation.
- **Drift Trajectory & Area Delta (`Δ km²`):** Automatically computes GeoJSON slick centroids, directional drift vectors between passes, previous-step dashed outlines, and step-to-step area changes.
- **Live Layer Controls & Multi-Event Minimap:** Adjust slick mask opacity (`0%–100%`), toggle contour outlines, inspect coordinate HUDs, and jump across global spill/seep case studies.

---

## Included NISAR Case Studies

Nine known events: seven with oil and two oil-free look-alike controls. All were processed with the same pipeline and checked against independent evidence (see [`processing/docs/METHODOLOGY.md`](./processing/docs/METHODOLOGY.md)).

1. **Al Hallaniyat Islands, Oman (`oman-caroline-bezengi-2026`)** — grounding of the tanker *Caroline Bezengi*. The top-ranked detected source lies 3.6 km from the tanker.
2. **Green Canyon 600, Gulf of Mexico (`green-canyon-600-seeps-2026`)** — natural deep-sea seeps. A detected source lies 4.3 km from the Mega Plume vent.
3. **Eugene Island 316, Gulf of Mexico (`eugene-island-316-2026`)** — recurring leak, suspected pipeline. A plume from the leak point is visible on NISAR ~4 weeks before the first NOAA report.
4. **Wreck 1487, south of Nantucket (`wreck-1487-nantucket-2026`)** — chronic leak from a shipwreck. Its slicks (≤ 6.5 km²) are at the resolution limit.
5. **Neft Daşları, Caspian Sea (`neft-dashlari-caspian-2026`)** — offshore oil field. The #1 detected source lies 2.5 km from the complex.
6. **Coal Oil Point, Santa Barbara Channel (`coal-oil-point-seeps-2026`)** — natural seep field next to the coast.
7. **Umm Al Quwain, UAE (`uae-gem2-umm-al-quwain-2026`)** — tanker leak during near-calm wind, with Sentinel-1 cross-check.
8. **Tenerife – La Gomera (`canary-lee-twin-2026`)** — oil-free control: island wind shadow.
9. **Gotland Basin, Baltic Sea (`baltic-bloom-twin-2026`)** — oil-free control: cyanobacteria bloom.

---

## Tech Stack & Architecture

- **Frontend:** React 18, TypeScript, Vite, Leaflet (`frontend/`)
- **Data Pipeline & Spec:** Python (`processing/`):
  - remote range reads of `NISAR L2 GCOV` HDF5;
  - self-calibrated slick detectors;
  - multi-feature oil-likeness score;
  - ship/platform detection and source clustering;
  - output: georeferenced WebP rasters + GeoJSON contours + `v1.2` JSON contract (`docs/API_CONTRACT.md`).
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

- **NASA-ISRO Synthetic Aperture Radar (NISAR) Level 2 Geocoded Covariance (`L2 GCOV`)** — L-band co- and cross-polarised (HH/VV, HV/VH) $\gamma^0$ backscatter products accessed via NASA Earthdata / Alaska Satellite Facility (ASF DAAC).
- **Basemap & Reference Layers:** OpenStreetMap / CARTO basemap tiles for geographic context.

---

## License

This project is open source and licensed under the [MIT License](./LICENSE).
