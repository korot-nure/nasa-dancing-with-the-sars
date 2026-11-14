# API-контракт (Data & API Contract): Dancing with the SARs

**Проєкт:** Карта радарного моніторингу розливів нафти (`NISAR L2 GCOV`)  
**Версія контракту:** `1.0`  
**Статус:** Єдине джерело істини (Single Source of Truth) між Backend (`FastAPI`) та Frontend (`React + TypeScript + Leaflet`)  
**Дата:** 14 листопада 2026 р.  
**Суміжні документи:** [BACKEND_TECHNICAL_SPEC.md](file:///d:/Dev/NASA_Dancing_with_the_SARs/docs/BACKEND_TECHNICAL_SPEC.md) · [FRONTEND_WORK_PLAN.md](file:///d:/Dev/NASA_Dancing_with_the_SARs/docs/FRONTEND_WORK_PLAN.md)

> [!IMPORTANT]
> Цей файл описує жорсткий формат обміну даними між сервером і браузером. Бекенд зобов'язаний повертати рівно ці поля, типи й одиниці вимірювання, а фронтенд (включно з моками у `frontend/public/mock/`) будується строго під цю структуру.

---

## 1. Загальні правила та конвенції

Дотримання цих конвенцій запобігає найчастішим багам на стику карти, GIS-даних і UI.

### 1.1. Базові URL та префікси
- **Локальна адреса бекенду:** `http://localhost:8000`
- **Префікс REST API:** `/api/v1` (усі JSON/GeoJSON-ендпоінти)
- **Роздача статичних файлів (растри, вектор, маніфести):** `/data/locations/{id}/...` (монтується через FastAPI `StaticFiles`)
- **Відносні посилання у відповідях API:** бекенд повертає шляхи від кореня (наприклад, `/data/locations/oman-caroline-bezengi-2026/before.webp`), щоб фронтенд однаково працював як напряму, так і через Vite proxy (`/api` і `/data` -> `http://localhost:8000`).

### 1.2. Порядок координат і проєкція (КРИТИЧНО)
- **Система координат:** всюди в API та статиці для вебу використовується географічна СК **`EPSG:4326` (WGS 84, градуси)**.
- **Точки (`coords`) та GeoJSON (`geometry.coordinates`):** порядок строго **`[lon, lat]`** (спочатку довгота, потім широта — за стандартом RFC 7946 / GeoJSON).
- **Обмежувальний прямокутник (`bbox`):** порядок строго **`[west, south, east, north]`** (`[min_lon, min_lat, max_lon, max_lat]`).

> [!WARNING]
> **Пам'ятка для фронтенду (`Leaflet`):**
> Бібліотека `Leaflet` очікує координати у зворотному порядку — **`[lat, lon]`**. Тому на клієнті потрібно робити перетворення:
> - Маркер / центр: `coords` `[lon, lat]` $\rightarrow$ `[coords[1], coords[0]]`
> - Межі для `L.imageOverlay` / `map.fitBounds`: `bbox` `[west, south, east, north]` $\rightarrow$ `[[bbox[1], bbox[0]], [bbox[3], bbox[2]]]` (`[[south, west], [north, east]]`)
> - Для `L.geoJSON(...)` перевертати координати **не потрібно** — `Leaflet` сам читає GeoJSON у форматі `[lon, lat]`.

### 1.3. Одиниці вимірювання, типи та формати
| Поле | Тип | Одиниці / Формат | Примітка |
| :--- | :--- | :--- | :--- |
| `id`, `step_id` | `string` | kebab-case / snake_case | URL-безпечні ідентифікатори (`oman-caroline-bezengi-2026`, `t1`, `t2`) |
| `area_km2` | `number` (`float`) | км² | Округлення до 1 знака після коми (наприклад, `2040.5`) |
| `baseline_date`, `latest_date`, `date` | `string` | `YYYY-MM-DD` (ISO 8601) | Дата зйомки SAR-сцени за UTC |
| `source_url` | `string \| null` | Повний HTTP/HTTPS URL | Опціональне поле (посилання на новину/звіт) |

---

## 2. Специфікація REST-ендпоінтів і JSON-відповідей

| Метод | Ендпоінт | Призначення | Content-Type |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/locations` | Список усіх подій для міні-карти та `<select>` | `application/json` |
| `GET` | `/api/v1/locations/{id}` | Детальна картка події + масив зрізів `snapshots[]` | `application/json` |
| `GET` | `/api/v1/locations/{id}/snapshots/{step_id}/contour.geojson` | Векторний контур плями на вибрану дату | `application/geo+json` |

---

### 2.1. `GET /api/v1/locations` — Список усіх оброблених подій

Використовується при старті застосунку для відображення маркерів на `OverviewMinimap` і заповнення випадаючого списку `EventSelect`.

**Поля відповіді:**
- `total` (`number`): кількість локацій у масиві.
- `locations` (`LocationSummary[]`):
  - `id` (`string`): унікальний ідентифікатор локації.
  - `title` (`string`): назва події для UI.
  - `coords` (`[number, number]`): центр локації у форматі `[lon, lat]`.
  - `baseline_date` (`string`): дата опорного знімка «До» (`YYYY-MM-DD`).
  - `latest_date` (`string`): дата останнього доступного знімка «Після» (`YYYY-MM-DD`).
  - `area_km2` (`number`): площа плями на останньому знімку (км²).

**Приклад відповіді `200 OK`:**

```json
{
  "total": 2,
  "locations": [
    {
      "id": "kerch-strait-2025",
      "title": "Керченська протока: аварія танкерів",
      "coords": [36.55, 45.12],
      "baseline_date": "2024-12-03",
      "latest_date": "2025-07-14",
      "area_km2": 142.8
    },
    {
      "id": "oman-caroline-bezengi-2026",
      "title": "Острови Халланіят, Оман",
      "coords": [56.02, 17.50],
      "baseline_date": "2026-06-01",
      "latest_date": "2026-08-18",
      "area_km2": 2040.5
    }
  ]
}
```

---

### 2.2. `GET /api/v1/locations/{id}` — Детальна інформація про подію

Викликається при виборі події користувачем. Повертає межі `bbox`, посилання на знімок «До», опис для картки `EventDetailsCard` та впорядкований за часом масив зрізів `snapshots[]` для `SnapshotTimeline`.

**Поля відповіді:**
- `id` (`string`): ідентифікатор локації.
- `title` (`string`): назва події.
- `coords` (`[number, number]`): `[lon, lat]`.
- `bbox` (`[number, number, number, number]`): географічні межі растру `[west, south, east, north]`.
- `baseline_date` (`string`): дата знімка «До» (`YYYY-MM-DD`).
- `baseline_before_url` (`string`): URL растру `before.webp`.
- `description` (`string`): короткий опис інциденту для лівої картки.
- `source_url` (`string | null`, опціонально): посилання на першоджерело / новину.
- `snapshots` (`SnapshotStep[]`): хронологічно відсортовані кроки «Після» (`t1`, `t2`, ...):
  - `step_id` (`string`): ідентифікатор зрізу (`"t1"`, `"t2"`).
  - `date` (`string`): дата знімка (`YYYY-MM-DD`).
  - `label` (`string`): коротка підпис на таймлайні (наприклад, `"Початковий шлейф"`, `"Максимум розливу"`).
  - `area_km2` (`number`): площа плями на цю дату (км²).
  - `after_url` (`string`): URL растру `after_<step_id>.webp`.
  - `mask_url` (`string`): URL прозорої растрової маски `mask_<step_id>.webp`.
  - `contour_geojson_url` (`string`): URL векторного контуру GeoJSON для цього зрізу.

**Приклад відповіді `200 OK`:**

```json
{
  "id": "oman-caroline-bezengi-2026",
  "title": "Острови Халланіят, Оман",
  "coords": [56.02, 17.50],
  "bbox": [55.35, 16.90, 56.85, 18.10],
  "baseline_date": "2026-06-01",
  "baseline_before_url": "/data/locations/oman-caroline-bezengi-2026/before.webp",
  "description": "Посадка на мілину танкера Caroline Bezengi після вибуху призвела до масштабного розливу нафти в Аравійському морі. На знімках NISAR чітко видно динаміку розширення темної плями біля заповідного острова Аль-Кіблія.",
  "source_url": "https://www.cbsnews.com/news/abandoned-russian-tanker-leaking-oil-off-oman-coast-threatening-environmental-disaster/",
  "snapshots": [
    {
      "step_id": "t1",
      "date": "2026-07-02",
      "label": "Початковий шлейф",
      "area_km2": 420.0,
      "after_url": "/data/locations/oman-caroline-bezengi-2026/after_t1.webp",
      "mask_url": "/data/locations/oman-caroline-bezengi-2026/mask_t1.webp",
      "contour_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/snapshots/t1/contour.geojson"
    },
    {
      "step_id": "t2",
      "date": "2026-08-18",
      "label": "Максимум розливу",
      "area_km2": 2040.5,
      "after_url": "/data/locations/oman-caroline-bezengi-2026/after_t2.webp",
      "mask_url": "/data/locations/oman-caroline-bezengi-2026/mask_t2.webp",
      "contour_geojson_url": "/api/v1/locations/oman-caroline-bezengi-2026/snapshots/t2/contour.geojson"
    }
  ]
}
```

---

### 2.3. `GET /api/v1/locations/{id}/snapshots/{step_id}/contour.geojson` — Векторний контур

Повертає векторну геометрію розливу для накладання через `L.geoJSON(...)` (наприклад, для відображення чіткої межі плями або ховеру). Заголовок відповіді: `Content-Type: application/geo+json`.

**Приклад відповіді `200 OK`:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "location_id": "oman-caroline-bezengi-2026",
        "step_id": "t2",
        "area_km2": 2040.5
      },
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [
          [[[55.98, 17.48], [56.05, 17.52], [56.01, 17.42], [55.98, 17.48]]]
        ]
      }
    }
  ]
}
```

---

### 2.4. Формат помилок

Усі 4xx/5xx помилки повертаються у стандартному форматі FastAPI з полем `detail`:

- **`404 Not Found`** (невідома локація або `step_id`):

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

---

## 3. Контракт статичних файлів (`/data/locations/{id}/`)

Усі підготовлені файли локації зберігаються на сервері у папці `data/locations/{id}/` і роздаються як статика по URL `/data/locations/{id}/<filename>`.

| Файл | Формат | Вміст і візуальні вимоги |
| :--- | :--- | :--- |
| `before.webp` | RGBA WebP | Радіолокаційна яскравість «До» у градаціях сірого (`0..255`), `[2%, 98%]` перцентилі, `NaN`-пікселі мають `alpha = 0` |
| `after_<step_id>.webp` | RGBA WebP | Яскравість «Після» у тій же шкалі `[2%, 98%]` перцентилів, що й `before.webp`, `NaN`-пікселі мають `alpha = 0` |
| `mask_<step_id>.webp` | RGBA WebP | Пікселі розливу — **суцільний `#ef4444`** (`rgba(239, 68, 68, 255)`, `alpha = 255`); усі інші пікселі — **повністю прозорі** (`rgba(0, 0, 0, 0)`, `alpha = 0`) |
| `contour_<step_id>.geojson` | GeoJSON (`EPSG:4326`) | Спрощений `FeatureCollection` із `MultiPolygon` / `Polygon` |
| `meta.json` | JSON | Маніфест локації (ідентичний за структурою до відповіді `GET /api/v1/locations/{id}`) |

> [!CAUTION]
> **Обов'язкові гарантії для растрових шарів однієї локації:**
> 1. **Попіксельне суміщення:** `before.webp`, усі `after_<step_id>.webp` та всі `mask_<step_id>.webp` в межах однієї локації повинні мати **абсолютно однакову ширину та висоту в пікселях (`W × H`)** (до `1200 px` по довгій стороні) і прив'язуватися на карту строго в **один і той самий `bbox` у `EPSG:4326`**. Завдяки цьому шторка «До / Після» та маска не «їдуть» одна відносно одної.
> 2. **Чиста прозорість маски:** бекенд **не запікає** напівпрозорість у `mask_<step_id>.webp` (`alpha` тільки `255` або `0`). Інтенсивність підсвітки регулюється виключно на фронтенді повзунком (`spillOpacity: 0.0 .. 1.0`).

---

## 4. Готові схеми для коду (Copy-Paste)

### 4.1. TypeScript (Frontend: `frontend/src/types/location.ts`)

```ts
export interface LocationSummary {
  id: string;
  title: string;
  /** Центр події у форматі [lon, lat] (EPSG:4326) */
  coords: [number, number];
  baseline_date: string; // YYYY-MM-DD
  latest_date: string;   // YYYY-MM-DD
  area_km2: number;
}

export interface LocationsListResponse {
  total: number;
  locations: LocationSummary[];
}

export interface SnapshotStep {
  step_id: string;
  date: string;          // YYYY-MM-DD
  label: string;
  area_km2: number;
  after_url: string;
  mask_url: string;
  contour_geojson_url: string;
}

export interface LocationDetail {
  id: string;
  title: string;
  /** Центр події у форматі [lon, lat] (EPSG:4326) */
  coords: [number, number];
  /** Межі зображення [west, south, east, north] (EPSG:4326) */
  bbox: [number, number, number, number];
  baseline_date: string; // YYYY-MM-DD
  baseline_before_url: string;
  description: string;
  source_url?: string | null;
  snapshots: SnapshotStep[];
}

export interface SpillContourProperties {
  location_id: string;
  step_id: string;
  area_km2: number;
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

export interface ApiError {
  detail: string;
}
```

---

### 4.2. Pydantic v2 (Backend: `backend/app/schemas.py`)

```python
from typing import Optional, Tuple
from pydantic import BaseModel, Field


class LocationSummary(BaseModel):
    id: str
    title: str
    coords: Tuple[float, float] = Field(
        ..., description="Центр події [lon, lat] у EPSG:4326"
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
    label: str
    area_km2: float = Field(..., ge=0.0)
    after_url: str
    mask_url: str
    contour_geojson_url: str


class LocationDetail(BaseModel):
    id: str
    title: str
    coords: Tuple[float, float] = Field(
        ..., description="Центр події [lon, lat] у EPSG:4326"
    )
    bbox: Tuple[float, float, float, float] = Field(
        ..., description="Межі растру [west, south, east, north] у EPSG:4326"
    )
    baseline_date: str = Field(..., description="YYYY-MM-DD")
    baseline_before_url: str
    description: str
    source_url: Optional[str] = None
    snapshots: list[SnapshotStep]


class ErrorResponse(BaseModel):
    detail: str
```

---

## 5. Як користуватися контрактом у команді (Workflow)

1. **Старт (Етап 0):**
   - **Фронтенд (Dev 1 + Dev 2):** копіюють інтерфейси з розділу `4.1` у `frontend/src/types/location.ts`, а JSON-приклади з розділу `2` — у `frontend/public/mock/` (`locations.json`, `oman-caroline-bezengi-2026.json`, `contour_t2.geojson`). Після цього обидва фронтендери можуть працювати повністю автономно, не чекаючи запуску FastAPI.
   - **Бекенд:** копіює класи з розділу `4.2` у `backend/app/schemas.py` і гарантує, що `prepare_location.py` генерує `meta.json`, `.webp` та `.geojson` строго за цим контрактом.
2. **Інтеграція (Етап 3):**
   - Фронтенд перемикає `VITE_USE_MOCK=false`, і реальні дані з `http://localhost:8000` лягають у UI без переписування жодного компонента.
3. **Правило внесення змін:**
   - Будь-яка зміна імені поля, типу, структури URL або порядку координат **спочатку фіксується в `docs/API_CONTRACT.md`** (зі збільшенням версії, наприклад `1.0` -> `1.1`) і узгоджується між бекендом і фронтендом. Змінювати JSON «тишком» на одній зі сторін заборонено.
