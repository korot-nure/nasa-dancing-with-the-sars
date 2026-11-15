# NASA Space Apps Challenge — Submission, Video & Presentation Pack

**Project:** Dancing with the SARs  
**Repository:** https://github.com/korot-nure/nasa-dancing-with-the-sars  
**Live Demo (GitHub Pages):** https://korot-nure.github.io/nasa-dancing-with-the-sars/

> This document contains ready-to-use English copy for the **spaceappschallenge.org** submission form, a **30-second video demo script** (with English subtitles), and a **7-slide presentation / PDF deck** outline.

---

## 1. Space Apps Submission Form Fields (Copy-Paste Ready)

### Project Name
`Dancing with the SARs`

### High-Level Project Summary
> *Short elevator pitch (what it does, what problem it solves, why it matters).*

Dancing with the SARs is an interactive, all-weather geospatial web platform that turns NASA-ISRO Synthetic Aperture Radar (**NISAR L2 GCOV**) data into actionable marine oil spill intelligence. Optical satellites fail during cloud cover, smoke, and night—precisely when spills spread fastest or go unreported. By converting calibrated L-band SAR backscatter into multi-temporal slick masks, GeoJSON contours, and drift vectors, our tool lets responders track spill area changes (`Δ km²`) and movement trajectories in seconds.

### Project Details
> *Detailed technical explanation of functionality, architecture, and NASA data integration.*

**The Problem**  
Marine oil spills and illegal bilge discharges threaten coastal ecosystems, fisheries, and maritime infrastructure. Conventional optical Earth observation is blocked by clouds, haze, and darkness. Synthetic Aperture Radar (SAR) penetrates clouds day and night, and oil slicks strongly dampen sea-surface capillary waves—creating dark, detectable backscatter anomalies—yet raw HDF5 SAR products are too large and complex for rapid operational use in a browser.

**What Dancing with the SARs Does**  
- **Basemap ↔ SAR Split Curtain:** A draggable comparison view overlays calibrated SAR backscatter, segmented oil slick masks (`#ef4444`), and GeoJSON contours directly over a readable cartographic basemap.
- **Multi-Temporal Snapshot Timeline (`T0..Tn`):** Users step or auto-play through pre-event baselines (`T0`), initial detections (`T1`), and subsequent satellite passes (`+N` days) to observe how a spill evolves.
- **Drift Trajectory & Area Analytics:** Computes GeoJSON slick centroids, directional drift arrows between passes, previous-step dashed outlines, and step-to-step area deltas (`Δ km²`).
- **Interactive Controls & Multi-Event Minimap:** Supports live slick opacity adjustment (`0%–100%`), contour toggles, coordinate HUD readouts, and instant switching between global spill and natural seep events.

**How We Built It**  
1. **SAR Processing Pipeline:** Reads NASA **NISAR L2 GCOV** (`.h5`) grids (`HHHH` / `HVHV` covariance layers, validity masks, UTM coordinates, and `zeroDopplerStartTime`), converts linear power to decibels ($\gamma^0_{\text{dB}} = 10 \log_{10} P$), applies background offset compensation and speckle filtering, segments oil slicks, and exports lightweight georeferenced **WebP** rasters, **GeoJSON** contours, and `v1.0` JSON metadata.
2. **Frontend Web App:** Built with **React 18**, **TypeScript**, **Vite**, and **Leaflet**, featuring a custom split-curtain map stage, synchronized minimap, and responsive telemetry sidebar, deployed statically via **GitHub Actions** to **GitHub Pages**.

**Case Studies Included**  
- **Al Hallaniyat Islands, Oman** (*Caroline Bezengi* tanker grounding, 138.2 km² peak tracked slick)
- **Green Canyon 600, Gulf of Mexico** (natural hydrocarbon seeps)
- **Eugene Island 316, Gulf of Mexico** (offshore slick monitoring)

### NASA Data & Citations
- **NASA-ISRO Synthetic Aperture Radar (NISAR) Level 2 Geocoded Covariance (`L2 GCOV`)** — L-band $\gamma^0_{HH}$ and $\gamma^0_{HV}$ backscatter grids, pixel validity masks, and orbit/time metadata accessed via NASA Earthdata / Alaska Satellite Facility (ASF DAAC).
- **OpenStreetMap / CARTO** — Cartographic reference basemap tiles.
- **Open-Source Libraries:** React, TypeScript, Vite, Leaflet (all MIT/BSD/ISC-compatible).

---

## 2. 30-Second Video Demo Script (Alternative 1 / Pitch Video)

> **Rules Check:** Max **30 seconds**. Upload to YouTube (Unlisted/Public) or Google Drive (Anyone with the link can view). **English subtitles/captions are mandatory** if spoken audio is not English (recommended: clear English voiceover + burned-in English captions).

| Time | Visual / Screen Recording | Voiceover / English Subtitles |
| :--- | :--- | :--- |
| **0:00 – 0:05** | Title card: **Dancing with the SARs** + quick flash of cloudy ocean vs. clear SAR slick detection. | *"Optical satellites can't see oil spills through clouds or at night. Meet **Dancing with the SARs**."* |
| **0:05 – 0:13** | Live screen recording of **Al Hallaniyat Islands, Oman** on GitHub Pages. Drag the **Split Curtain** left and right to reveal the red SAR oil slick mask over the map. | *"Using NASA **NISAR L2 GCOV** radar data, our web platform reveals oil slicks in any weather with an interactive basemap-to-SAR curtain."* |
| **0:13 – 0:22** | Click **Play** on the `T0..T3` timeline. Show the slick growing, dashed previous contours, drift arrows, and the `Δ km²` readout updating in the sidebar. | *"Responders can animate multi-temporal passes, measure area changes in square kilometers, and track drift trajectories automatically."* |
| **0:22 – 0:27** | Switch to **Green Canyon 600** via the minimap/selector and adjust the opacity slider. | *"From tanker disasters in Oman to Gulf of Mexico seeps, raw HDF5 radar becomes instant browser intelligence."* |
| **0:27 – 0:30** | End card with project logo, **MIT Open Source**, GitHub & Live Demo URLs. | *"Dancing with the SARs — all-weather ocean protection, powered by NASA NISAR."* |

---

## 3. 7-Slide Presentation / PDF Deck (Alternative 2)

> **Rules Check:** Maximum **7 slides** (including title slide). **Must be in English.** Export as PDF and host on Google Drive / GitHub with public view access (or use alongside the video).

### Slide 1 — Title Slide
- **Title:** Dancing with the SARs
- **Subtitle:** All-Weather Marine Oil Spill Detection & Drift Tracking with NASA NISAR
- **Metadata:** Team Name · NASA Space Apps Challenge · Live Demo & GitHub QR/URL

### Slide 2 — The Problem
- **Headline:** When Disasters Strike, Clouds & Darkness Blind Optical Satellites
- **3 Bullet Points:**
  - Up to ~70% of ocean surfaces are obscured by clouds at any given moment.
  - Oil spills spread rapidly in the first hours—delayed detection multiplies ecological and economic damage.
  - Raw Synthetic Aperture Radar (SAR) HDF5 files are gigabytes in size and require specialized GIS tools, slowing down responders.

### Slide 3 — Our Solution: Dancing with the SARs
- **Headline:** From Raw Radar Physics to Instant Browser Intelligence
- **Visual:** Clean screenshot of the live web app showing the **Split Curtain** on the Oman *Caroline Bezengi* spill.
- **Key Points:**
  - Interactive **Basemap ↔ SAR** split-curtain comparison.
  - **Multi-Temporal Timeline (`T0..Tn`)** with auto-play animation.
  - Automated **Drift Vectors** and **Area Delta (`Δ km²`)** telemetry.

### Slide 4 — NASA Data & Scientific Methodology
- **Headline:** Powered by NASA-ISRO SAR (`NISAR L2 GCOV`)
- **Pipeline Diagram:** `NISAR L2 GCOV (.h5)` → `dB Calibration (10·log10 γ⁰)` → `Background Offset & Speckle Filter` → `Slick Segmentation` → `WebP + GeoJSON + JSON v1.0`
- **Why L-Band SAR Works:** Oil dampens sea-surface capillary waves, creating sharp dark backscatter drops in $\gamma^0_{HH}$ (open water) and $\gamma^0_{HV}$ (coastal/vegetated zones).

### Slide 5 — Real-World Case Studies
- **Headline:** Validated Across 3 Diverse Marine Events
- **3-Column Comparison:**
  1. **Al Hallaniyat Islands, Oman:** *Caroline Bezengi* tanker grounding — tracked up to **138.2 km²** across multi-pass acquisitions.
  2. **Green Canyon 600, Gulf of Mexico:** Natural hydrocarbon seeps — recurring surface slick monitoring.
  3. **Eugene Island 316, Gulf of Mexico:** Offshore infrastructure zone monitoring.

### Slide 6 — Technical Architecture & Open Source
- **Headline:** Lightweight, Contract-First & Ready to Scale
- **Stack:**
  - **Frontend:** React 18, TypeScript, Vite, Leaflet (zero-backend static mode + live FastAPI-ready `v1.0` contract).
  - **CI/CD:** Automated GitHub Actions deployment to GitHub Pages.
  - **License:** 100% Open Source (**MIT License**).

### Slide 7 — Impact & Next Steps
- **Headline:** Faster Response. Cleaner Oceans.
- **Impact:** Enables coast guards, researchers, and NGOs to inspect SAR-verified spill boundaries and drift direction in seconds without GIS software.
- **Next Steps:** Live ASF/Earthdata webhook ingestion, automated AIS vessel correlation, and wind/current drift forecasting.
- **Links:** Live Demo (`https://korot-nure.github.io/nasa-dancing-with-the-sars/`) · GitHub Repo
