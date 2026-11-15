# Frontend Work Plan for 2 Developers (v1.2)

**Project:** Dancing with the SARs — Oil Spill Monitoring Map (`NISAR L2 GCOV`)  
**Stack:** React + Vite + TypeScript + Leaflet (`L.imageOverlay` + `L.geoJSON`)  
**Document version:** `1.2` (synchronized with [API_CONTRACT.md](./API_CONTRACT.md) v1.2)  
**Date:** November 15, 2026

---

## 0. What changed in the frontend for contract `v1.2`

1. **Slick origin field `origin?: "pipeline" | "reference"` (`v1.2`) and the real Oman dataset (`t1..t12`):**
   - The `oman-caroline-bezengi-2026` location is wired to the real `12` `NISAR L2 GCOV` snapshots (`t1..t12`, from `2026-06-30` to `2026-09-16`, tracks `056A VV` and `150D HH`) with `.webp` rasters (`1200x770` in `EPSG:3857`), `contour_t*.geojson` contours, `targets_t*.geojson` targets and `sources.geojson` sources.
   - `origin?: "pipeline" | "reference"` was added to `SpillContourProperties`. For `t1..t4` and `t6`, the early slicks near the tanker have `"origin": "reference"` — contour tooltips show "reference annotation".
2. **Paired "Before / After" comparison within a single track and polarization:**
   - Each `SnapshotStep` now has its own `before_url`, `before_date`, `track` (`056A`, `150D`) and `polarization` (`HH` / `VV`).
   - When the step is switched on the timeline (`T0..Tn`), **both sides of the curtain are updated** on the map: on the left — `before_url` (`sarLeftPane`), on the right — `after_url` + mask (`sarRightPane`).
3. **Contours by confidence class (`contour.geojson`):**
   - One slick = one `Feature` with the fields `slick_id`, `class` (`"probable" | "possible"`), `score` (`0..1`), `flags` (`near_coast`, `low_wind`, `near_noise`, `rain`, `small`, `static`) and `origin`.
   - `probable`: solid `#ef4444` outline + fill (controlled by `spillOpacity`); `possible`: dashed `#a78bfa` outline without fill.
4. **Snapshot notes (`note`, `label_source`):**
   - If `note` is set (for example, calm sea, weak contrast in VV on `t5`, reference annotation, or the slick reaching the shore outside the frame), the event card and the timeline step button display a warning.
5. **Optional context layers:**
   - `sources.geojson` — the known spill source and the source found by the algorithm (`detected` / `known`).
   - `targets_<step_id>.geojson` — point radar targets on the acquisition date (`ship` / `platform` / `coastal`).

---

## 1. Breaking the UI mockup down into 6 components

The interface is split into a **left sidebar (`~30%` of the width)** and a **right working stage (`~70%` of the width)** (on screens `<= 900px` the sidebar stacks on top and scrolls):

```text
+-------------------------------+---------------------------------------------------+
| [1] OverviewMinimap      [⛶] | [SAR BEFORE: before_date · track · pol] [Dark|OSM] |
|   Minimap with event pins     |                                                   |
+-------------------------------+       [4] MainComparisonMap                       |
| [2] EventSelect (dropdown)    |           - Left: basemap + SAR "Before"          |
+-------------------------------+           - Right: SAR "After" + mask             |
| [3] EventDetailsCard          |           - Contours (probable/possible),         |
|   - Title, coordinates        |             drift trajectory, sources, targets    |
|   - Stage, area (km²) + Δ     +---------------------------------------------------+
|   - Track · Pol. + "Before"   | [5] SpillOpacitySlider ("mask opacity")           |
|   - note warning, description +---------------------------------------------------+
|   - Links and "Why SAR?"      | [6] SnapshotTimeline (T0 Before + T1..Tn + Play)  |
+-------------------------------+---------------------------------------------------+
```

### Component breakdown
1. **`OverviewMinimap`** (top left): SVG world minimap with orange event markers and `World` / `Region` modes.
2. **`EventSelect`** (middle left): event dropdown, synchronized with the minimap.
3. **`EventDetailsCard`** (bottom left): telemetry card: title, coordinates (`lat, lon` with `N/S/E/W`), **area of `probable` slicks (`area_km2`) and its change `Δ km²`**, **track and polarization (`track · polarization`) + date of the paired "Before" snapshot (`before_date`)**, warning (`note`), description, `source_url` and the "Why does SAR see this?" hint.
4. **`MainComparisonMap`** (main right area): a `Leaflet` map constrained to the world bounds (`WORLD_BOUNDS`, `noWrap: true`), with a basemap (`Dark` / `OSM` / `Satellite`) and a two-sided curtain (`splitRatio`):
   - **left of the curtain (`sarLeftPane`)** — basemap + paired SAR "Before" (`before_url`);
   - **right of the curtain (`sarRightPane`)** — SAR "After" (`after_url`), spill mask (`mask_url`), contours (`probable` / `possible`) and the centroid drift trajectory;
   - **optional markers** — sources (`sources.geojson`) and point targets (`targets_<step_id>.geojson`).
5. **`SpillOpacitySlider`** (panel below the card): opacity control `0%–100%` (`0%`, `50%`, `100%`) and the `Vector Slick Contour` and `Drift Trajectory` toggles.
6. **`SnapshotTimeline`** (bottom panel): `T0 · Baseline (pre-event)` (`idx = -1`) and steps `T1..Tn` with date, area, a `track · polarization` caption, a `note` warning icon, `←` / `→` navigation and `▶ Play / Pause`.

---

## 2. Single data and state contract (`src/types/location.ts`)

The types are fully synchronized with section `4.1` of [API_CONTRACT.md](./API_CONTRACT.md) v1.2:
- `LocationSummary`, `LocationsListResponse`
- `Polarization = "HH" | "VV"`, `LabelSource = "manual" | "auto"`
- `SnapshotStep` (`track`, `polarization`, `before_url`, `before_date`, `label_source`, `note?`, `targets_geojson_url?` + `after_url`, `mask_url`, `contour_geojson_url`, `area_km2`)
- `LocationDetail` (`sources_geojson_url?`, `baseline_date`, `baseline_before_url`, `bbox`, `coords`, `snapshots`)
- `SlickClass`, `SlickFlag`, `SpillContourProperties` (added `origin?: "pipeline" | "reference"`), `SpillContourFeatureCollection`
- `SourceProperties`, `SourceFeatureCollection`, `TargetProperties`, `TargetFeatureCollection`
- `AppState`

---

## 3. Asymmetric task split (Lead + UI, Zero Merge Conflicts)

After the contract update to `v1.2`, the developers keep working within their own areas of responsibility to avoid conflicts during parallel work:

```text
frontend/
├── public/
│   ├── data/locations/oman-caroline-bezengi-2026/ # [Dev 1] Real WebP rasters and GeoJSON (12 snapshots t1..t12)
│   └── mock/                       # [Dev 1] Mock data v1.2 (locations, GeoJSON, sources, targets)
└── src/
    ├── api/locationsApi.ts         # [Dev 1] REST + GeoJSON client and resolveGeoJsonUrl for /api/v1/... in mock mode
    ├── types/location.ts           # [Dev 1] Single type contract v1.2
    ├── utils/format.ts             # [Dev 2 / Shared] pluralUk, formatLatLon
    ├── components/
    │   ├── stage/                  # [Dev 1] MainComparisonMap.tsx, SplitCurtainControl.tsx
    │   ├── timeline/               # [Dev 1] SnapshotTimeline.tsx
    │   ├── sidebar/
    │   │   ├── OverviewMinimap.tsx # [Dev 1] SVG world minimap
    │   │   ├── EventSelect.tsx     # [Dev 2] Event dropdown
    │   │   └── EventDetailsCard.tsx# [Dev 2] Telemetry card (Props preserved)
    │   └── controls/
    │       └── SpillOpacitySlider.tsx # [Dev 2] Mask opacity and layer toggles
    ├── App.tsx                     # [Dev 1] Grid layout, AppState and Play timer
    └── index.css                   # [Shared] Dark matte palette + mobile layout (<= 900px)
```

### What is in the `Dev 1 (Lead)` area — Architecture, map, API, timeline
1. **Stage 3.1 (Map and curtain v1.1 — basic implementation done):**
   - `sarLeftPane` (`before_url`) + `sarRightPane` (`after_url` + `mask_url`) are updated simultaneously when the step changes.
   - Contour styling by `class` (`probable` vs `possible`), trajectory focus on `probable` polygons, loading of `sources.geojson` and `targets_<step_id>.geojson`.
   - If needed (next iteration): visibility toggles for the `Ships/targets` and `Sources` layers, polygon tooltips with `score` and a breakdown of `flags` (`near_coast`, `low_wind`, `near_noise`, `rain`, `small`, `static`).
2. **Stage 3.2 (Timeline and API):**
   - Display of `track · polarization` and of the `note` indicator in `SnapshotTimeline.tsx`.
   - Caching of `fetchSourcesGeoJson` and `fetchTargetsGeoJson` in `locationsApi.ts`.
3. **Stage 4 (Integration with the real FastAPI backend):**
   - Switch to `VITE_USE_MOCK=false`, configure the Vite proxy (`/api` and `/data` $\rightarrow$ `http://localhost:8000`).
   - Verify the alignment of the real `before_<track>_<pol>.webp`, `after_<step>.webp` and `mask_<step>.webp` in `EPSG:3857` on `L.imageOverlay`.

### What is in the `Dev 2 (UI)` area — Polishing the UI components and the legend
1. **`EventDetailsCard.tsx`:**
   - Check and polish the `Track & Series` block (`track · polarization`, `Before pair: <before_date>`), the `note` warning badge and the responsive wrapping of values on narrow screens.
   - If needed: add a compact class legend (`Probable oil` — solid `#ef4444` vs `Possible` — dashed `#a78bfa`, `Source detected/known`) at the bottom of the card or next to the SAR hint.
2. **`EventSelect.tsx` and `SpillOpacitySlider.tsx`:**
   - Check visual consistency with the dark matte palette ([index.css](../frontend/src/index.css)) without gradients, shadows or emoji; test text overflow and keyboard focus.
   - When the layers are extended (as agreed with `Dev 1` in `App.tsx`), extra checkboxes (`Ships and structures`, `Uncertain slicks`) can be added once the new `Props` have been agreed.
3. **Live responsiveness check:**
   - Run `npm run build` and `npm run dev` in `frontend/`, check the desktop and mobile versions (`<= 900px`), the cases `note: null` vs `note: "..."`, and switching Oman (`056A VV` $\leftrightarrow$ `150D HH`) $\rightarrow$ Kerch $\rightarrow$ Maracaibo.

---

## 4. Git workflow rules and style requirements

1. **Branches:** `Dev 1` drives integration into `main` / `feat/core-map`; `Dev 2` works on `feat/ui-components` and syncs before each session (`git fetch origin && git merge origin/main`).
2. **Props contract:** the `Props` interfaces of `Dev 2` components may be changed only after prior agreement with `Dev 1` and an update of `App.tsx`.
3. **Design system (`no-slop-ui`):** strictly the dark matte palette from `index.css` (`#09090b`, `#111113`, `#18181b`, `#27272a`), no `linear-gradient` / `radial-gradient`, `box-shadow`, `backdrop-filter` and no Unicode emoji; all numeric values in `.mono` (`tabular-nums`).
