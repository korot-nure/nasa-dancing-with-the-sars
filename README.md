# Dancing with the SARs (Frontend MVP)

Interactive geospatial web interface for **NASA Space Apps Challenge** designed to visualize **NISAR L2 GCOV** Synthetic Aperture Radar (SAR) oil spill detections, drift trajectories, and multi-temporal area changes.

> **Current repository scope:** Frontend planning, JSON/GeoJSON data contract, and interactive UI prototype (no backend files or satellite binaries are included yet).

---

## Documentation (`docs/`)

- [`docs/FRONTEND_WORK_PLAN.md`](./docs/FRONTEND_WORK_PLAN.md) — Frontend architecture (React + Vite + TypeScript + Leaflet), `AppState` design, and zero-conflict task split for 2 developers (`Dev 1` stage map & `Dev 2` sidebar/timeline).
- [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md) — Shared JSON & GeoJSON schema contract (`v1.0`) used to structure `frontend/public/mock/` data, TypeScript interfaces (`src/types/location.ts`), and future API integration.

---

## Interactive UI Prototype (`mockup/`)

- [`mockup/index.html`](./mockup/index.html) — Standalone browser-ready MVP prototype featuring:
  - **Human Map ↔ SAR Overlay Split Curtain**: draggable comparison between a readable cartographic basemap on the left and SAR backscatter + segmented `#ef4444` oil slick mask & GeoJSON contour on the right.
  - **Multi-Temporal Snapshot Timeline (`T0..T3`) + Auto-Play**: baseline `T0 · База (до аварії)`, tracking start marker `T1 · Старт`, relative `+Nд` offsets, and `Старт / Пауза` animation.
  - **Drift Trajectory Overlay**: previous-step dashed outlines, computed GeoJSON centroids, directional drift arrows, and step-to-step `Δ км²` readouts.
  - **Spill Opacity Slider & Overview Minimap**: live opacity/contour controls, multi-event minimap/select navigation, HUD coordinates, and a built-in `v1.0` JSON contract inspector.

Open `mockup/index.html` directly in any modern browser to preview the interface.

---

## Planned Frontend Structure

```text
NASA_Dancing_with_the_SARs/
├── .gitignore
├── README.md
├── docs/
│   ├── API_CONTRACT.md
│   └── FRONTEND_WORK_PLAN.md
├── mockup/
│   └── index.html
└── frontend/          # Upcoming: Vite + React + TypeScript + Leaflet app
    ├── public/mock/   # Static mock JSON/WebP/GeoJSON datasets (contract v1.0)
    └── src/
```

---

## Team Git Workflow

1. **`main` always runs cleanly** — never push unfinished code directly to `main`.
2. **Feature branches per module:**
   - `feat/stage-map` — Dev 1 (`frontend/src/components/stage/`)
   - `feat/sidebar-timeline` — Dev 2 (`frontend/src/api/`, `sidebar/`, `timeline/`)
   - `feat/api-integration` — Connecting `frontend` to live endpoints later
3. **Contract-first changes:** Any change to mock/API data structures or shared TypeScript interfaces must update `docs/API_CONTRACT.md`, `docs/FRONTEND_WORK_PLAN.md`, and `src/types/location.ts` together.
