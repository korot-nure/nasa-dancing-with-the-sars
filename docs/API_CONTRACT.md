# Data & API Contract: Dancing with the SARs

**Project:** Radar oil-spill monitoring map (`NISAR L2 GCOV`)  
**Contract version:** `1.2`  
**Status:** Single Source of Truth between the Backend (`FastAPI`) and the Frontend (`React + TypeScript + Leaflet`)  
**Date:** November 15, 2026  
**Related documents:** `BACKEND_TECHNICAL_SPEC.md` · `FRONTEND_WORK_PLAN.md`

> [!IMPORTANT]
> This file defines the strict data exchange format between the server and the browser. The backend must return exactly these fields, types, and units of measurement, and the frontend (including the mocks in `frontend/public/mock/`) is built strictly around this structure.

---

## 0. What changed

**Version 1.2** (compared to 1.1): an optional `origin` field (`"pipeline"` | `"reference"`) has been added to contour `properties`. `reference` means the slick was taken from the reference annotation of a known event rather than found by the automated pipeline. Such slicks are included in the snapshot's mask and area. UI recommendation: a separate label in the tooltip ("reference annotation").

**Version 1.1** (compared to 1.0):

| What | Change | Why |
| :--- | :--- | :--- |
| `SnapshotStep.before_url`, `before_date`, `track`, `polarization` | **New required fields.** Each "after" snapshot has its own "before" image from **the same track and polarization** | NISAR images the area from different tracks (day/night) and in different polarizations (HH/VV). Over the sea, VV is several dB brighter than HH, and the look angle and coverage differ as well. A before/after slider across different tracks shows the difference in acquisition modes, not oil |
| `baseline_date`, `baseline_before_url` | Kept for compatibility: equal to the "before" image of the first snapshot | — |
| `SnapshotStep.label_source`, `note` | New fields: where the label comes from (`manual` / `auto`) and a warning (calm sea, incomplete coverage) | For known events, labels are written manually from the event timeline; automatic labels come later, for unknown areas |
| `contour.geojson` | **One slick = one `Feature`** with a class, a score, and doubt flags | So the frontend can color slicks by class and show why a slick is doubtful |
| `sources.geojson` (new, optional) | The detected spill source and the known source (for validation) | The main result of the method: where the oil is coming from, not just where the slick is |
| `targets_<step_id>.geojson` (new, optional) | Ships, platforms, and coastal structures on the snapshot date | Context: a ship next to a fresh slick, a platform near the source |
| Rasters | Resampled onto a grid that is uniform in `EPSG:3857`; the brightness scale is computed per before/after pair of a single track | Exact overlay via `L.imageOverlay`; correct before/after comparison |
| Examples | Dates, tracks, areas, and sources are real values from the Oman run; contour geometries and ship points in the examples are illustrative | The 1.0 example contained non-existent NISAR dates and the coordinates of a neighboring island |

New optional fields can be ignored until the frontend renders them: nothing breaks.

---

## 1. General rules and conventions

Following these conventions prevents the most common bugs at the junction of the map, GIS data, and UI.

### 1.1. Base URLs and prefixes
- **Local backend address:** `http://localhost:8000`
- **REST API prefix:** `/api/v1` (all JSON/GeoJSON endpoints)
- **Static file serving (rasters, vectors, manifests):** `/data/locations/{id}/...` (mounted via FastAPI `StaticFiles`)
- **Relative links in API responses:** the backend returns root-relative paths (for example, `/data/locations/oman-caroline-bezengi-2026/before_056A_VV.webp`), so that the frontend works the same way both directly and through the Vite proxy (`/api` and `/data` -> `http://localhost:8000`).

### 1.2. Coordinate order and projection (CRITICAL)
- **Coordinate system:** the geographic CRS **`EPSG:4326` (WGS 84, degrees)** is used everywhere in the API and in the static files for the web.
- **Points (`coords`) and GeoJSON (`geometry.coordinates`):** strictly **`[lon, lat]`** order (longitude first, then latitude — per the RFC 7946 / GeoJSON standard).
- **Bounding box (`bbox`):** strictly **`[west, south, east, north]`** order (`[min_lon, min_lat, max_lon, max_lat]`).
- **Rasters:** bounds are given by `bbox` in `EPSG:4326`, but the pixels are uniform in `EPSG:3857` (Web Mercator) — see section 3.

> [!WARNING]
> **Reminder for the frontend (`Leaflet`):**
> The `Leaflet` library expects coordinates in the reverse order — **`[lat, lon]`**. Therefore, the client must convert them:
> - Marker / center: `coords` `[lon, lat]` $\rightarrow$ `[coords[1], coords[0]]`
> - Bounds for `L.imageOverlay` / `map.fitBounds`: `bbox` `[west, south, east, north]` $\rightarrow$ `[[bbox[1], bbox[0]], [bbox[3], bbox[2]]]` (`[[south, west], [north, east]]`)
> - For `L.geoJSON(...)` you do **not** need to flip the coordinates — `Leaflet` reads GeoJSON in `[lon, lat]` format on its own.

### 1.3. Units of measurement, types, and formats
| Field | Type | Units / Format | Note |
| :--- | :--- | :--- | :--- |
| `id`, `step_id` | `string` | kebab-case / snake_case | URL-safe identifiers (`oman-caroline-bezengi-2026`, `t1`, `t2`) |
| `area_km2` | `number` (`float`) | km² | Rounded to 1 decimal place (for example, `919.4`) |
| `baseline_date`, `latest_date`, `date`, `before_date`, `first_date`, `last_date` | `string` | `YYYY-MM-DD` (ISO 8601) | Acquisition date of the SAR scene in UTC |
| `track` | `string` | track number + direction (`A` ascending / `D` descending) | For example, `056A`, `150D` |
| `polarization` | `string` | `"HH"` \| `"VV"` | Primary polarization of the image |
| `score` | `number` (`float`) | `0.0 .. 1.0` | "Looks like oil" score. This is a ranking for review, not a probability |
| `source_url` | `string \| null` | Full HTTP/HTTPS URL | Optional field (link to a news article/report) |

---

## 2. REST endpoint and JSON response specification

| Method | Endpoint | Purpose | Content-Type |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/locations` | List of all events for the minimap and the `<select>` | `application/json` |
| `GET` | `/api/v1/locations/{id}` | Detailed event card + array of snapshots `snapshots[]` | `application/json` |
| `GET` | `/api/v1/locations/{id}/snapshots/{step_id}/contour.geojson` | Slick contours for the selected date (one slick = one `Feature`) | `application/geo+json` |
| `GET` | `/api/v1/locations/{id}/sources.geojson` | **New (1.1), optional.** Detected and known sources | `application/geo+json` |
| `GET` | `/api/v1/locations/{id}/snapshots/{step_id}/targets.geojson` | **New (1.1), optional.** Ships, platforms, coastal structures | `application/geo+json` |

---

### 2.1. `GET /api/v1/locations` — List of all processed events

Used at application startup to display markers on the `OverviewMinimap` and to populate the `EventSelect` dropdown. Unchanged from 1.0.

**Response fields:**
- `total` (`number`): number of locations in the array.
- `locations` (`LocationSummary[]`):
  - `id` (`string`): unique location identifier.
  - `title` (`string`): event name for the UI.
  - `coords` (`[number, number]`): location center in `[lon, lat]` format (for known events — the known source).
  - `baseline_date` (`string`): date of the "before" image of the first snapshot (`YYYY-MM-DD`).
  - `latest_date` (`string`): date of the latest snapshot (`YYYY-MM-DD`).
  - `area_km2` (`number`): area of `probable`-class slicks in the latest snapshot (km²).

**Example `200 OK` response:**

```json
{
  "total": 2,
  "locations": [
    {
      "id": "oman-caroline-bezengi-2026",
      "title": "Hallaniyat Islands, Oman",
      "coords": [56.341, 17.5],
      "baseline_date": "2026-06-18",
      "latest_date": "2026-09-10",
      "area_km2": 919.4
    },
    {
      "id": "uae-umm-al-quwain-2026",
      "title": "Umm Al Quwain, UAE",
      "coords": [55.55, 25.6],
      "baseline_date": "2026-09-23",
      "latest_date": "2026-10-29",
      "area_km2": 2.3
    }
  ]
}
```

---

### 2.2. `GET /api/v1/locations/{id}` — Event details

Called when the user selects an event. Returns the `bbox` bounds, the description for the `EventDetailsCard`, and the chronologically ordered `snapshots[]` array for the `SnapshotTimeline`.

**Response fields:**
- `id` (`string`): location identifier.
- `title` (`string`): event name.
- `coords` (`[number, number]`): `[lon, lat]`.
- `bbox` (`[number, number, number, number]`): geographic bounds of the rasters `[west, south, east, north]`.
- `baseline_date` (`string`): date of the "before" image of the first snapshot (`YYYY-MM-DD`). *Kept for compatibility with 1.0.*
- `baseline_before_url` (`string`): URL of the "before" image of the first snapshot. *Kept for compatibility with 1.0.*
- `description` (`string`): short incident description for the left card.
- `source_url` (`string | null`, optional): link to the primary source / news article.
- `sources_geojson_url` (`string | null`, **new, optional**): URL of `sources.geojson`.
- `snapshots` (`SnapshotStep[]`): chronologically sorted "after" steps (`t1`, `t2`, ...):
  - `step_id` (`string`): snapshot identifier (`"t1"`, `"t2"`).
  - `date` (`string`): date of the "after" image (`YYYY-MM-DD`).
  - `track` (`string`, **new**): image track (`"056A"`).
  - `polarization` (`"HH" | "VV"`, **new**): image polarization.
  - `before_url` (`string`, **new**): URL of the "before" raster from **the same track and polarization**.
  - `before_date` (`string`, **new**): date of the "before" image (`YYYY-MM-DD`).
  - `label` (`string`): short label on the timeline.
  - `label_source` (`"manual" | "auto"`, **new**): `manual` — the label was written by a person based on the event timeline; `auto` — generated by rules from the data. For now, known events use only `manual`.
  - `note` (`string | null`, **new, optional**): a warning for the snapshot (for example, "Calm sea — score is unreliable", "Area is only partially covered").
  - `area_km2` (`number`): area of `probable`-class slicks on this date (km²).
  - `after_url` (`string`): URL of the `after_<step_id>.webp` raster.
  - `mask_url` (`string`): URL of the transparent raster mask `mask_<step_id>.webp` (`probable` class only).
  - `contour_geojson_url` (`string`): URL of the slick contours on this date.
  - `targets_geojson_url` (`string | null`, **new, optional**): URL of `targets_<step_id>.geojson`.

> [!NOTE]
> **For the frontend:** when switching snapshots on the timeline, you must swap **both** slider images — both `after_url` and `before_url`. Snapshots from the same track share the same `before_url` (the file is not duplicated).

**Example `200 OK` response:**

```json
{
  "id": "oman-caroline-bezengi-2026",
  "title": "Hallaniyat Islands, Oman",
  "coords": [56.341, 17.5],
  "bbox": [56.2, 17.2, 58.0, 18.3],
  "baseline_date": "2026-06-18",
  "baseline_before_url": "/data/locations/oman-caroline-bezengi-2026/before_056A_VV.webp",
  "description": "After an explosion, the tanker Caroline Bezengi ran aground off Al Qibliyah Island (Hallaniyat Islands) on 30.06.2026. The oil plume is drifting north-east; on 12–13.08 the oil reached the shore.",
  "source_url": "https://www.aljazeera.com/news/2026/8/13/oman-says-massive-oil-spill-reaches-coastline-what-damage-could-it-do",
  "sources_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/sources.geojson",
  "snapshots": [
    {
      "step_id": "t1",
      "date": "2026-08-17",
      "track": "056A",
      "polarization": "VV",
      "before_url": "/data/locations/oman-caroline-bezengi-2026/before_056A_VV.webp",
      "before_date": "2026-06-18",
      "label": "5 days after the oil reached the shore",
      "label_source": "manual",
      "note": null,
      "area_km2": 149.1,
      "after_url": "/data/locations/oman-caroline-bezengi-2026/after_t1.webp",
      "mask_url": "/data/locations/oman-caroline-bezengi-2026/mask_t1.webp",
      "contour_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/snapshots/t1/contour.geojson",
      "targets_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/snapshots/t1/targets.geojson"
    },
    {
      "step_id": "t2",
      "date": "2026-09-04",
      "track": "150D",
      "polarization": "HH",
      "before_url": "/data/locations/oman-caroline-bezengi-2026/before_150D_HH.webp",
      "before_date": "2026-06-24",
      "label": "Wide plume to the north-east",
      "label_source": "manual",
      "note": null,
      "area_km2": 219.8,
      "after_url": "/data/locations/oman-caroline-bezengi-2026/after_t2.webp",
      "mask_url": "/data/locations/oman-caroline-bezengi-2026/mask_t2.webp",
      "contour_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/snapshots/t2/contour.geojson",
      "targets_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/snapshots/t2/targets.geojson"
    },
    {
      "step_id": "t3",
      "date": "2026-09-10",
      "track": "056A",
      "polarization": "VV",
      "before_url": "/data/locations/oman-caroline-bezengi-2026/before_056A_VV.webp",
      "before_date": "2026-06-18",
      "label": "Largest slick area",
      "label_source": "manual",
      "note": null,
      "area_km2": 919.4,
      "after_url": "/data/locations/oman-caroline-bezengi-2026/after_t3.webp",
      "mask_url": "/data/locations/oman-caroline-bezengi-2026/mask_t3.webp",
      "contour_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/snapshots/t3/contour.geojson",
      "targets_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/snapshots/t3/targets.geojson"
    }
  ]
}
```

---

### 2.3. `GET /api/v1/locations/{id}/snapshots/{step_id}/contour.geojson` — Slick contours

Returns the contours of all slicks on the date for overlaying via `L.geoJSON(...)`. Response header: `Content-Type: application/geo+json`.

**Change in 1.1:** one slick = one `Feature` (previously, a single `Feature` with a `MultiPolygon` for the whole date). Slicks of the `probable` and `possible` classes are returned; the `background` class is not returned.

**`properties` fields of each `Feature`:**
- `location_id` (`string`), `step_id` (`string`) — as in 1.0.
- `area_km2` (`number`): area of **this slick** (km²).
- `slick_id` (`string`, **new**): slick identifier within the snapshot (`"t1-07"`).
- `class` (`"probable" | "possible"`, **new**): `probable` — likely oil, `possible` — possibly oil. Recommendation: `probable` — solid `#ef4444` fill, `possible` — dashed outline with no fill.
- `score` (`number`, **new**): "looks like oil" score, `0.0 .. 1.0`.
- `origin` (`"pipeline" | "reference"`, **new in 1.2, optional**, defaults to `pipeline`): `pipeline` — the slick was found by the automated pipeline; `reference` — the slick was taken from the reference annotation of a known event (for dates on which the pipeline does not see the event). For `reference`, the score and flags are computed with the same formula.
- `flags` (`string[]`, **new**): why the score was lowered; an empty array if there are no doubts:
  - `near_coast` — closer than 2 km to the shore;
  - `low_wind` — wind < 3 m/s (a calm sea looks like oil);
  - `near_noise` — signal less than 1 dB above the instrument noise floor;
  - `rain` — precipitation;
  - `small` — slick smaller than 2 km²;
  - `static` — the same dark area recurs on other dates (lagoon, shoal, wind shadow).

**Example `200 OK` response:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "location_id": "oman-caroline-bezengi-2026",
        "step_id": "t1",
        "slick_id": "t1-07",
        "area_km2": 40.4,
        "class": "probable",
        "score": 0.74,
        "flags": [],
        "origin": "pipeline"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[56.69, 17.55], [56.75, 17.59], [56.73, 17.61], [56.67, 17.57], [56.69, 17.55]]]
      }
    },
    {
      "type": "Feature",
      "properties": {
        "location_id": "oman-caroline-bezengi-2026",
        "step_id": "t1",
        "slick_id": "t1-12",
        "area_km2": 3.1,
        "class": "possible",
        "score": 0.45,
        "flags": ["near_coast"],
        "origin": "pipeline"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[56.31, 17.86], [56.33, 17.87], [56.32, 17.88], [56.31, 17.86]]]
      }
    }
  ]
}
```

---

### 2.4. `GET /api/v1/locations/{id}/sources.geojson` — Sources (new, optional)

Points: the source detected by the algorithm (a cluster of slick origin points that recurs across several dates) and, for known events, the known source — so that the accuracy is visible.

**`properties` fields:**
- `kind` (`"detected" | "known"`): detected by the algorithm / known from news and reports.
- `rank` (`number | null`): rank of the detected source by reliability (`1` — the most reliable); `null` for `known`.
- `n_dates` (`number | null`): on how many dates slicks originate from this location.
- `first_date`, `last_date` (`string | null`): the first and the last such date.
- `dist_known_km` (`number | null`): distance to the known source (km), if one is specified.
- `label` (`string`): label for the tooltip.

**Example `200 OK` response:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "kind": "detected",
        "rank": 1,
        "n_dates": 5,
        "first_date": "2026-08-17",
        "last_date": "2026-09-16",
        "dist_known_km": 3.6,
        "label": "Detected source #1: 5 dates, 3.6 km from the known source"
      },
      "geometry": { "type": "Point", "coordinates": [56.322, 17.473] }
    },
    {
      "type": "Feature",
      "properties": {
        "kind": "known",
        "rank": null,
        "n_dates": null,
        "first_date": null,
        "last_date": null,
        "dist_known_km": null,
        "label": "Tanker Caroline Bezengi aground (known source)"
      },
      "geometry": { "type": "Point", "coordinates": [56.341, 17.5] }
    }
  ]
}
```

---

### 2.5. `GET /api/v1/locations/{id}/snapshots/{step_id}/targets.geojson` — Ships and structures (new, optional)

Bright point targets in the radar image for this date.

**`properties` fields:**
- `kind` (`"ship" | "platform" | "coastal"`):
  - `ship` — a one-off target at sea (a ship);
  - `platform` — a target that recurs at the same location on several dates (platform, anchorage, grounded tanker);
  - `coastal` — a target closer than 2 km to the shore (port, structures).
- `snr_db` (`number`): excess over the sea background, dB.
- `date` (`string`): image date (`YYYY-MM-DD`).

**Example `200 OK` response:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "kind": "ship", "snr_db": 18.2, "date": "2026-09-04" },
      "geometry": { "type": "Point", "coordinates": [56.71, 17.62] }
    },
    {
      "type": "Feature",
      "properties": { "kind": "coastal", "snr_db": 24.8, "date": "2026-09-04" },
      "geometry": { "type": "Point", "coordinates": [56.545, 18.123] }
    }
  ]
}
```

---

### 2.6. Error format

All 4xx/5xx errors are returned in the standard FastAPI format with a `detail` field:

- **`404 Not Found`** (unknown location or `step_id`, or a missing optional layer):

```json
{
  "detail": "Location 'unknown-id' not found"
}
```

```json
{
  "detail": "Snapshot 't99' not found for location 'oman-caroline-bezengi-2026'"
}
```

If a location has no optional layer, the corresponding `*_geojson_url` field is `null`, and the endpoint returns `404`.

---

## 3. Static file contract (`/data/locations/{id}/`)

All prepared files of a location are stored on the server in the `data/locations/{id}/` folder and served as static files at the URL `/data/locations/{id}/<filename>`.

| File | Format | Content and visual requirements |
| :--- | :--- | :--- |
| `before_<track>_<pol>.webp` | RGBA WebP | **Changed (1.1):** a "before" image for each track + polarization pair (for example, `before_056A_VV.webp`). Radar brightness in grayscale (`0..255`), scale — see guarantee 3; `NaN` pixels (no coverage, land) have `alpha = 0` |
| `after_<step_id>.webp` | RGBA WebP | "After" brightness on the same scale as the corresponding `before_<track>_<pol>.webp`; `NaN` pixels have `alpha = 0` |
| `mask_<step_id>.webp` | RGBA WebP | Pixels of `probable`-class slicks (including `origin: reference`) — **solid `#ef4444`** (`rgba(239, 68, 68, 255)`, `alpha = 255`); all other pixels — **fully transparent** (`rgba(0, 0, 0, 0)`, `alpha = 0`) |
| `contour_<step_id>.geojson` | GeoJSON (`EPSG:4326`) | `FeatureCollection`, one slick = one `Feature` (`Polygon`), properties — see 2.3 |
| `sources.geojson` | GeoJSON (`EPSG:4326`) | **New (1.1), optional.** See 2.4 |
| `targets_<step_id>.geojson` | GeoJSON (`EPSG:4326`) | **New (1.1), optional.** See 2.5 |
| `meta.json` | JSON | Location manifest (structurally identical to the `GET /api/v1/locations/{id}` response) |

> [!CAUTION]
> **Mandatory guarantees for the raster layers of a single location:**
> 1. **Pixel-perfect alignment:** all `before_*.webp`, `after_<step_id>.webp`, and `mask_<step_id>.webp` within a single location have **exactly the same width and height in pixels (`W × H`)** (up to `1200 px` on the long side) and are placed on the map strictly within **the same `bbox` in `EPSG:4326`**. This keeps the before / after slider and the mask from drifting relative to each other.
> 2. **Grid in the map projection (new, 1.1):** `L.imageOverlay` stretches the image linearly between the `bbox` corners in the map projection (`EPSG:3857`). Therefore, the backend resamples the rasters (from UTM, in which the computation is performed) onto a grid that is **uniform in `EPSG:3857`** within the `bbox`. The frontend does not need to do anything — just `L.imageOverlay(url, bounds)`.
> 3. **Shared brightness scale per pair (changed, 1.1):** the `[2%, 98%]` percentiles are computed per before / after pair of **a single track and polarization** (`before_<track>_<pol>` + all `after_*` of that track). The scales differ between tracks — brightness cannot be compared across tracks.
> 4. **Clean mask transparency:** the backend **does not bake** semi-transparency into `mask_<step_id>.webp` (`alpha` is only `255` or `0`). The highlight intensity is controlled exclusively on the frontend with a slider (`spillOpacity: 0.0 .. 1.0`).

---

## 4. Ready-made schemas for code (Copy-Paste)

### 4.1. TypeScript (Frontend: `frontend/src/types/location.ts`)

```ts
export interface LocationSummary {
  id: string;
  title: string;
  /** Event center in [lon, lat] format (EPSG:4326) */
  coords: [number, number];
  baseline_date: string; // YYYY-MM-DD
  latest_date: string;   // YYYY-MM-DD
  area_km2: number;
}

export interface LocationsListResponse {
  total: number;
  locations: LocationSummary[];
}

export type Polarization = "HH" | "VV";
export type LabelSource = "manual" | "auto";

export interface SnapshotStep {
  step_id: string;
  date: string;          // YYYY-MM-DD
  /** 1.1: image track, e.g. "056A" */
  track: string;
  /** 1.1: image polarization */
  polarization: Polarization;
  /** 1.1: "before" image of the same track and polarization */
  before_url: string;
  /** 1.1: YYYY-MM-DD */
  before_date: string;
  label: string;
  /** 1.1: manual — label written by a person, auto — generated by rules from the data */
  label_source: LabelSource;
  /** 1.1: warning (calm sea, incomplete coverage) */
  note?: string | null;
  /** Area of probable-class slicks (km²) */
  area_km2: number;
  after_url: string;
  mask_url: string;
  contour_geojson_url: string;
  /** 1.1, optional */
  targets_geojson_url?: string | null;
}

export interface LocationDetail {
  id: string;
  title: string;
  /** Event center in [lon, lat] format (EPSG:4326) */
  coords: [number, number];
  /** Image bounds [west, south, east, north] (EPSG:4326) */
  bbox: [number, number, number, number];
  /** = before_date of the first snapshot (compatibility with 1.0) */
  baseline_date: string; // YYYY-MM-DD
  /** = before_url of the first snapshot (compatibility with 1.0) */
  baseline_before_url: string;
  description: string;
  source_url?: string | null;
  /** 1.1, optional */
  sources_geojson_url?: string | null;
  snapshots: SnapshotStep[];
}

export type SlickClass = "probable" | "possible";
export type SlickFlag = "near_coast" | "low_wind" | "near_noise" | "rain" | "small" | "static";

export interface SpillContourProperties {
  location_id: string;
  step_id: string;
  /** Area of this slick (km²) */
  area_km2: number;
  /** 1.1 */
  slick_id: string;
  /** 1.1 */
  class: SlickClass;
  /** 1.1: 0..1, a ranking, not a probability */
  score: number;
  /** 1.1: why the score was lowered */
  flags: SlickFlag[];
  /** 1.2: pipeline — found by the pipeline, reference — reference annotation of a known event */
  origin?: "pipeline" | "reference";
}

export interface SpillContourFeature {
  type: "Feature";
  properties: SpillContourProperties;
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: number[][][] | number[][][][];
  };
}

export interface SpillContourFeatureCollection {
  type: "FeatureCollection";
  features: SpillContourFeature[];
}

/** 1.1: sources.geojson */
export interface SourceProperties {
  kind: "detected" | "known";
  rank: number | null;
  n_dates: number | null;
  first_date: string | null; // YYYY-MM-DD
  last_date: string | null;  // YYYY-MM-DD
  dist_known_km: number | null;
  label: string;
}

export interface SourceFeature {
  type: "Feature";
  properties: SourceProperties;
  geometry: { type: "Point"; coordinates: [number, number] };
}

export interface SourceFeatureCollection {
  type: "FeatureCollection";
  features: SourceFeature[];
}

/** 1.1: targets_<step_id>.geojson */
export interface TargetProperties {
  kind: "ship" | "platform" | "coastal";
  snr_db: number;
  date: string; // YYYY-MM-DD
}

export interface TargetFeature {
  type: "Feature";
  properties: TargetProperties;
  geometry: { type: "Point"; coordinates: [number, number] };
}

export interface TargetFeatureCollection {
  type: "FeatureCollection";
  features: TargetFeature[];
}

export interface ApiError {
  detail: string;
}
```

---

### 4.2. Pydantic v2 (Backend: `backend/app/schemas.py`)

```python
from typing import Literal, Optional, Tuple
from pydantic import BaseModel, Field


class LocationSummary(BaseModel):
    id: str
    title: str
    coords: Tuple[float, float] = Field(
        ..., description="Event center [lon, lat] in EPSG:4326"
    )
    baseline_date: str = Field(..., description="YYYY-MM-DD")
    latest_date: str = Field(..., description="YYYY-MM-DD")
    area_km2: float = Field(..., ge=0.0)


class LocationsListResponse(BaseModel):
    total: int = Field(..., ge=0)
    locations: list[LocationSummary]


class SnapshotStep(BaseModel):
    step_id: str
    date: str = Field(..., description="YYYY-MM-DD")
    track: str = Field(..., description="Track, e.g. 056A (1.1)")
    polarization: Literal["HH", "VV"]
    before_url: str = Field(..., description="'Before' image of the same track and polarization (1.1)")
    before_date: str = Field(..., description="YYYY-MM-DD (1.1)")
    label: str
    label_source: Literal["manual", "auto"]
    note: Optional[str] = None
    area_km2: float = Field(..., ge=0.0, description="Area of probable-class slicks")
    after_url: str
    mask_url: str
    contour_geojson_url: str
    targets_geojson_url: Optional[str] = None


class LocationDetail(BaseModel):
    id: str
    title: str
    coords: Tuple[float, float] = Field(
        ..., description="Event center [lon, lat] in EPSG:4326"
    )
    bbox: Tuple[float, float, float, float] = Field(
        ..., description="Raster bounds [west, south, east, north] in EPSG:4326"
    )
    baseline_date: str = Field(..., description="= before_date of the first snapshot")
    baseline_before_url: str = Field(..., description="= before_url of the first snapshot")
    description: str
    source_url: Optional[str] = None
    sources_geojson_url: Optional[str] = None
    snapshots: list[SnapshotStep]


class SpillContourProperties(BaseModel):
    location_id: str
    step_id: str
    area_km2: float = Field(..., ge=0.0, description="Area of this slick")
    slick_id: str
    class_: Literal["probable", "possible"] = Field(..., alias="class")
    score: float = Field(..., ge=0.0, le=1.0)
    flags: list[Literal["near_coast", "low_wind", "near_noise", "rain", "small", "static"]] = []
    origin: Literal["pipeline", "reference"] = "pipeline"

    model_config = {"populate_by_name": True}


class SourceProperties(BaseModel):
    kind: Literal["detected", "known"]
    rank: Optional[int] = None
    n_dates: Optional[int] = None
    first_date: Optional[str] = None
    last_date: Optional[str] = None
    dist_known_km: Optional[float] = None
    label: str


class TargetProperties(BaseModel):
    kind: Literal["ship", "platform", "coastal"]
    snr_db: float
    date: str = Field(..., description="YYYY-MM-DD")


class ErrorResponse(BaseModel):
    detail: str
```

> [!NOTE]
> `class` is a reserved word in Python, so in Pydantic the field is named `class_` with `alias="class"`. When serializing, use `model_dump(by_alias=True)` so that the JSON contains exactly `"class"`.

---

## 5. How to use the contract in the team (Workflow)

1. **Start (Stage 0):**
   - **Frontend (Dev 1 + Dev 2):** copy the interfaces from section `4.1` into `frontend/src/types/location.ts`, and the JSON examples from section `2` into `frontend/public/mock/` (`locations.json`, `oman-caroline-bezengi-2026.json`, `contour_t1.geojson`, `sources.geojson`, `targets_t1.geojson`). After that, both frontend developers can work fully autonomously, without waiting for FastAPI to be running.
   - **Backend:** copies the classes from section `4.2` into `backend/app/schemas.py` and ensures that `prepare_location.py` generates `meta.json`, `.webp`, and `.geojson` strictly according to this contract.
2. **Integration (Stage 3):**
   - The frontend switches to `VITE_USE_MOCK=false`, and real data from `http://localhost:8000` lands in the UI without rewriting a single component.
3. **Change rule:**
   - Any change to a field name, type, URL structure, or coordinate order **is first recorded in `docs/API_CONTRACT.md`** (with a version bump, for example `1.2` -> `1.3`) and agreed between the backend and the frontend. Changing the JSON "silently" on one side is prohibited.
