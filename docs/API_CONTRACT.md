# API-контракт (Data & API Contract): Dancing with the SARs

**Проєкт:** Карта радарного моніторингу розливів нафти (`NISAR L2 GCOV`)  
**Версія контракту:** `1.1`  
**Статус:** Єдине джерело істини (Single Source of Truth) між Backend (`FastAPI`) та Frontend (`React + TypeScript + Leaflet`)  
**Дата:** 15 листопада 2026 р.  
**Суміжні документи:** `BACKEND_TECHNICAL_SPEC.md` · `FRONTEND_WORK_PLAN.md`

> [!IMPORTANT]
> Цей файл описує жорсткий формат обміну даними між сервером і браузером. Бекенд зобов'язаний повертати рівно ці поля, типи й одиниці вимірювання, а фронтенд (включно з моками у `frontend/public/mock/`) будується строго під цю структуру.

---

## 0. Що змінилося у версії 1.1 (порівняно з 1.0)

| Що | Зміна | Чому |
| :--- | :--- | :--- |
| `SnapshotStep.before_url`, `before_date`, `track`, `polarization` | **Нові обов'язкові поля.** У кожного зрізу «Після» своя пара «До» з **того самого треку й поляризації** | NISAR знімає район різними треками (вдень/вночі) і в різних поляризаціях (HH/VV). Над морем VV на кілька дБ яскравіший за HH, різні й кут огляду та покриття. Шторка «До/Після» між різними треками показує різницю режимів зйомки, а не нафту |
| `baseline_date`, `baseline_before_url` | Залишаються для сумісності: дорівнюють «До» першого зрізу | — |
| `SnapshotStep.label_source`, `note` | Нові поля: звідки підпис (`manual` / `auto`) і попередження (штиль, неповне покриття) | Для відомих подій підписи пишемо вручну за хронологією; автоматичні підписи — пізніше, для невідомих районів |
| `contour.geojson` | **Одна пляма = одна `Feature`** із класом, оцінкою та прапорцями сумніву | Щоб фронтенд міг розфарбовувати плями за класом і показувати, чому пляма сумнівна |
| `sources.geojson` (новий, опціональний) | Знайдене джерело розливу та відоме джерело (для перевірки) | Головний результат методу: звідки тече, а не лише де пляма |
| `targets_<step_id>.geojson` (новий, опціональний) | Судна, платформи й берегові споруди на дату зрізу | Контекст: судно поруч зі свіжою плямою, платформа біля джерела |
| Растри | Ресемплюються на сітку, рівномірну в `EPSG:3857`; шкала яскравості рахується на пару «До/Після» одного треку | Точне накладання через `L.imageOverlay`; коректне порівняння «До/Після» |
| Приклади | Дати, треки, площі та джерела — реальні значення прогону по Оману; геометрії контурів і точки суден у прикладах — ілюстративні | Приклад 1.0 містив неіснуючі дати NISAR і координати сусіднього острова |

Нові опціональні поля можна ігнорувати, доки фронтенд їх не відмальовує: нічого не ламається.

---

## 1. Загальні правила та конвенції

Дотримання цих конвенцій запобігає найчастішим багам на стику карти, GIS-даних і UI.

### 1.1. Базові URL та префікси
- **Локальна адреса бекенду:** `http://localhost:8000`
- **Префікс REST API:** `/api/v1` (усі JSON/GeoJSON-ендпоінти)
- **Роздача статичних файлів (растри, вектор, маніфести):** `/data/locations/{id}/...` (монтується через FastAPI `StaticFiles`)
- **Відносні посилання у відповідях API:** бекенд повертає шляхи від кореня (наприклад, `/data/locations/oman-caroline-bezengi-2026/before_056A_VV.webp`), щоб фронтенд однаково працював як напряму, так і через Vite proxy (`/api` і `/data` -> `http://localhost:8000`).

### 1.2. Порядок координат і проєкція (КРИТИЧНО)
- **Система координат:** всюди в API та статиці для вебу використовується географічна СК **`EPSG:4326` (WGS 84, градуси)**.
- **Точки (`coords`) та GeoJSON (`geometry.coordinates`):** порядок строго **`[lon, lat]`** (спочатку довгота, потім широта — за стандартом RFC 7946 / GeoJSON).
- **Обмежувальний прямокутник (`bbox`):** порядок строго **`[west, south, east, north]`** (`[min_lon, min_lat, max_lon, max_lat]`).
- **Растри:** межі задаються `bbox` у `EPSG:4326`, але пікселі рівномірні в `EPSG:3857` (Web Mercator) — див. розділ 3.

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
| `area_km2` | `number` (`float`) | км² | Округлення до 1 знака після коми (наприклад, `919.4`) |
| `baseline_date`, `latest_date`, `date`, `before_date`, `first_date`, `last_date` | `string` | `YYYY-MM-DD` (ISO 8601) | Дата зйомки SAR-сцени за UTC |
| `track` | `string` | номер треку + напрям (`A` висхідний / `D` низхідний) | Наприклад, `056A`, `150D` |
| `polarization` | `string` | `"HH"` \| `"VV"` | Основна поляризація знімка |
| `score` | `number` (`float`) | `0.0 .. 1.0` | Оцінка «схоже на нафту». Це ранжування для перевірки, а не ймовірність |
| `source_url` | `string \| null` | Повний HTTP/HTTPS URL | Опціональне поле (посилання на новину/звіт) |

---

## 2. Специфікація REST-ендпоінтів і JSON-відповідей

| Метод | Ендпоінт | Призначення | Content-Type |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/locations` | Список усіх подій для міні-карти та `<select>` | `application/json` |
| `GET` | `/api/v1/locations/{id}` | Детальна картка події + масив зрізів `snapshots[]` | `application/json` |
| `GET` | `/api/v1/locations/{id}/snapshots/{step_id}/contour.geojson` | Контури плям на вибрану дату (одна пляма = одна `Feature`) | `application/geo+json` |
| `GET` | `/api/v1/locations/{id}/sources.geojson` | **Нове (1.1), опціональне.** Знайдене та відоме джерела | `application/geo+json` |
| `GET` | `/api/v1/locations/{id}/snapshots/{step_id}/targets.geojson` | **Нове (1.1), опціональне.** Судна, платформи, берегові споруди | `application/geo+json` |

---

### 2.1. `GET /api/v1/locations` — Список усіх оброблених подій

Використовується при старті застосунку для відображення маркерів на `OverviewMinimap` і заповнення випадаючого списку `EventSelect`. Без змін порівняно з 1.0.

**Поля відповіді:**
- `total` (`number`): кількість локацій у масиві.
- `locations` (`LocationSummary[]`):
  - `id` (`string`): унікальний ідентифікатор локації.
  - `title` (`string`): назва події для UI.
  - `coords` (`[number, number]`): центр локації у форматі `[lon, lat]` (для відомих подій — відоме джерело).
  - `baseline_date` (`string`): дата знімка «До» першого зрізу (`YYYY-MM-DD`).
  - `latest_date` (`string`): дата останнього зрізу (`YYYY-MM-DD`).
  - `area_km2` (`number`): площа плям класу `probable` на останньому зрізі (км²).

**Приклад відповіді `200 OK`:**

```json
{
  "total": 2,
  "locations": [
    {
      "id": "oman-caroline-bezengi-2026",
      "title": "Острови Халланіят, Оман",
      "coords": [56.341, 17.5],
      "baseline_date": "2026-06-18",
      "latest_date": "2026-09-10",
      "area_km2": 919.4
    },
    {
      "id": "uae-umm-al-quwain-2026",
      "title": "Умм-ель-Кайвайн, ОАЕ",
      "coords": [55.55, 25.6],
      "baseline_date": "2026-09-23",
      "latest_date": "2026-10-29",
      "area_km2": 2.3
    }
  ]
}
```

---

### 2.2. `GET /api/v1/locations/{id}` — Детальна інформація про подію

Викликається при виборі події користувачем. Повертає межі `bbox`, опис для картки `EventDetailsCard` та впорядкований за часом масив зрізів `snapshots[]` для `SnapshotTimeline`.

**Поля відповіді:**
- `id` (`string`): ідентифікатор локації.
- `title` (`string`): назва події.
- `coords` (`[number, number]`): `[lon, lat]`.
- `bbox` (`[number, number, number, number]`): географічні межі растрів `[west, south, east, north]`.
- `baseline_date` (`string`): дата «До» першого зрізу (`YYYY-MM-DD`). *Залишено для сумісності з 1.0.*
- `baseline_before_url` (`string`): URL «До» першого зрізу. *Залишено для сумісності з 1.0.*
- `description` (`string`): короткий опис інциденту для лівої картки.
- `source_url` (`string | null`, опціонально): посилання на першоджерело / новину.
- `sources_geojson_url` (`string | null`, **нове, опціональне**): URL `sources.geojson`.
- `snapshots` (`SnapshotStep[]`): хронологічно відсортовані кроки «Після» (`t1`, `t2`, ...):
  - `step_id` (`string`): ідентифікатор зрізу (`"t1"`, `"t2"`).
  - `date` (`string`): дата знімка «Після» (`YYYY-MM-DD`).
  - `track` (`string`, **нове**): трек знімка (`"056A"`).
  - `polarization` (`"HH" | "VV"`, **нове**): поляризація знімка.
  - `before_url` (`string`, **нове**): URL растру «До» **того самого треку й поляризації**.
  - `before_date` (`string`, **нове**): дата знімка «До» (`YYYY-MM-DD`).
  - `label` (`string`): короткий підпис на таймлайні.
  - `label_source` (`"manual" | "auto"`, **нове**): `manual` — підпис написаний людиною за хронологією події; `auto` — згенерований за правилами з даних. Поки для відомих подій лише `manual`.
  - `note` (`string | null`, **нове, опціональне**): попередження до зрізу (наприклад, «Штиль — оцінка ненадійна», «Район покрито частково»).
  - `area_km2` (`number`): площа плям класу `probable` на цю дату (км²).
  - `after_url` (`string`): URL растру `after_<step_id>.webp`.
  - `mask_url` (`string`): URL прозорої растрової маски `mask_<step_id>.webp` (лише клас `probable`).
  - `contour_geojson_url` (`string`): URL контурів плям на цю дату.
  - `targets_geojson_url` (`string | null`, **нове, опціональне**): URL `targets_<step_id>.geojson`.

> [!NOTE]
> **Для фронтенду:** при перемиканні зрізу на таймлайні треба міняти **обидві** картинки шторки — і `after_url`, і `before_url`. У зрізів одного треку `before_url` однаковий (файл не дублюється).

**Приклад відповіді `200 OK`:**

```json
{
  "id": "oman-caroline-bezengi-2026",
  "title": "Острови Халланіят, Оман",
  "coords": [56.341, 17.5],
  "bbox": [56.2, 17.2, 58.0, 18.3],
  "baseline_date": "2026-06-18",
  "baseline_before_url": "/data/locations/oman-caroline-bezengi-2026/before_056A_VV.webp",
  "description": "Танкер Caroline Bezengi після вибуху сів на мілину біля острова Аль-Кіблія (острови Халланіят) 30.06.2026. Нафтовий шлейф дрейфує на північний схід, 12–13.08 нафта дійшла до берега.",
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
      "label": "Через 5 днів після виходу нафти на берег",
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
      "label": "Широкий шлейф на північний схід",
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
      "label": "Найбільша площа плями",
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

### 2.3. `GET /api/v1/locations/{id}/snapshots/{step_id}/contour.geojson` — Контури плям

Повертає контури всіх плям на дату для накладання через `L.geoJSON(...)`. Заголовок відповіді: `Content-Type: application/geo+json`.

**Зміна 1.1:** одна пляма = одна `Feature` (раніше — одна `Feature` з `MultiPolygon` на всю дату). Повертаються плями класів `probable` і `possible`; клас `background` не повертається.

**Поля `properties` кожної `Feature`:**
- `location_id` (`string`), `step_id` (`string`) — як у 1.0.
- `area_km2` (`number`): площа **цієї плями** (км²).
- `slick_id` (`string`, **нове**): ідентифікатор плями в межах зрізу (`"t1-07"`).
- `class` (`"probable" | "possible"`, **нове**): `probable` — ймовірно нафта, `possible` — можливо. Рекомендація: `probable` — суцільна заливка `#ef4444`, `possible` — пунктирний контур без заливки.
- `score` (`number`, **нове**): оцінка «схоже на нафту», `0.0 .. 1.0`.
- `flags` (`string[]`, **нове**): чому оцінку знижено; порожній масив, якщо сумнівів немає:
  - `near_coast` — ближче 2 км до берега;
  - `low_wind` — вітер < 3 м/с (штиль виглядає як нафта);
  - `near_noise` — сигнал менше ніж на 1 дБ вище шуму приладу;
  - `rain` — опади;
  - `small` — пляма менша за 2 км²;
  - `static` — та сама темна область повторюється на інших датах (лагуна, мілина, вітрова тінь).

**Приклад відповіді `200 OK`:**

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
        "flags": []
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
        "flags": ["near_coast"]
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

### 2.4. `GET /api/v1/locations/{id}/sources.geojson` — Джерела (нове, опціональне)

Точки: знайдене алгоритмом джерело (кластер точок початку плям, що повторюється на кількох датах) і, для відомих подій, відоме джерело — щоб було видно точність.

**Поля `properties`:**
- `kind` (`"detected" | "known"`): знайдене алгоритмом / відоме з новин і звітів.
- `rank` (`number | null`): номер знайденого джерела за надійністю (`1` — найнадійніше); `null` для `known`.
- `n_dates` (`number | null`): на скількох датах плями починаються з цього місця.
- `first_date`, `last_date` (`string | null`): перша й остання така дата.
- `dist_known_km` (`number | null`): відстань до відомого джерела (км), якщо воно задане.
- `label` (`string`): підпис для спливаючої підказки.

**Приклад відповіді `200 OK`:**

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
        "label": "Знайдене джерело №1: 5 дат, 3,6 км від танкера"
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
        "label": "Танкер Caroline Bezengi (відоме джерело)"
      },
      "geometry": { "type": "Point", "coordinates": [56.341, 17.5] }
    }
  ]
}
```

---

### 2.5. `GET /api/v1/locations/{id}/snapshots/{step_id}/targets.geojson` — Судна й споруди (нове, опціональне)

Яскраві точкові цілі на радарному знімку цієї дати.

**Поля `properties`:**
- `kind` (`"ship" | "platform" | "coastal"`):
  - `ship` — разова ціль у морі (судно);
  - `platform` — ціль, що повторюється на кількох датах у тому ж місці (платформа, якірна стоянка, танкер на мілині);
  - `coastal` — ціль ближче 2 км до берега (порт, споруди).
- `snr_db` (`number`): перевищення над фоном моря, дБ.
- `date` (`string`): дата знімка (`YYYY-MM-DD`).

**Приклад відповіді `200 OK`:**

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

### 2.6. Формат помилок

Усі 4xx/5xx помилки повертаються у стандартному форматі FastAPI з полем `detail`:

- **`404 Not Found`** (невідома локація або `step_id`, або відсутній опціональний шар):

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

Якщо опціонального шару для локації немає, відповідне поле `*_geojson_url` дорівнює `null`, а ендпоінт повертає `404`.

---

## 3. Контракт статичних файлів (`/data/locations/{id}/`)

Усі підготовлені файли локації зберігаються на сервері у папці `data/locations/{id}/` і роздаються як статика по URL `/data/locations/{id}/<filename>`.

| Файл | Формат | Вміст і візуальні вимоги |
| :--- | :--- | :--- |
| `before_<track>_<pol>.webp` | RGBA WebP | **Змінено (1.1):** «До» для кожної пари трек + поляризація (наприклад, `before_056A_VV.webp`). Радіолокаційна яскравість у градаціях сірого (`0..255`), шкала — див. гарантію 3; `NaN`-пікселі (немає зйомки, суша) мають `alpha = 0` |
| `after_<step_id>.webp` | RGBA WebP | Яскравість «Після» у тій самій шкалі, що й відповідний `before_<track>_<pol>.webp`; `NaN`-пікселі мають `alpha = 0` |
| `mask_<step_id>.webp` | RGBA WebP | Пікселі плям класу `probable` — **суцільний `#ef4444`** (`rgba(239, 68, 68, 255)`, `alpha = 255`); усі інші пікселі — **повністю прозорі** (`rgba(0, 0, 0, 0)`, `alpha = 0`) |
| `contour_<step_id>.geojson` | GeoJSON (`EPSG:4326`) | `FeatureCollection`, одна пляма = одна `Feature` (`Polygon`), властивості — див. 2.3 |
| `sources.geojson` | GeoJSON (`EPSG:4326`) | **Нове (1.1), опціональне.** Див. 2.4 |
| `targets_<step_id>.geojson` | GeoJSON (`EPSG:4326`) | **Нове (1.1), опціональне.** Див. 2.5 |
| `meta.json` | JSON | Маніфест локації (ідентичний за структурою до відповіді `GET /api/v1/locations/{id}`) |

> [!CAUTION]
> **Обов'язкові гарантії для растрових шарів однієї локації:**
> 1. **Попіксельне суміщення:** усі `before_*.webp`, `after_<step_id>.webp` та `mask_<step_id>.webp` в межах однієї локації мають **абсолютно однакову ширину та висоту в пікселях (`W × H`)** (до `1200 px` по довгій стороні) і прив'язуються на карту строго в **один і той самий `bbox` у `EPSG:4326`**. Завдяки цьому шторка «До / Після» та маска не «їдуть» одна відносно одної.
> 2. **Сітка в проєкції карти (нове, 1.1):** `L.imageOverlay` розтягує картинку лінійно між кутами `bbox` у проєкції карти (`EPSG:3857`). Тому бекенд ресемплює растри (з UTM, у якому ведеться розрахунок) на сітку, **рівномірну в `EPSG:3857`** у межах `bbox`. Фронтенду нічого робити не треба — просто `L.imageOverlay(url, bounds)`.
> 3. **Спільна шкала яскравості для пари (змінено, 1.1):** перцентилі `[2%, 98%]` рахуються на пару «До / Після» **одного треку й поляризації** (`before_<track>_<pol>` + усі `after_*` цього треку). Між різними треками шкали різні — порівнювати яскравість між треками не можна.
> 4. **Чиста прозорість маски:** бекенд **не запікає** напівпрозорість у `mask_<step_id>.webp` (`alpha` тільки `255` або `0`). Інтенсивність підсвітки регулюється виключно на фронтенді повзунком (`spillOpacity: 0.0 .. 1.0`).

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

export type Polarization = "HH" | "VV";
export type LabelSource = "manual" | "auto";

export interface SnapshotStep {
  step_id: string;
  date: string;          // YYYY-MM-DD
  /** 1.1: трек знімка, напр. "056A" */
  track: string;
  /** 1.1: поляризація знімка */
  polarization: Polarization;
  /** 1.1: «До» того самого треку й поляризації */
  before_url: string;
  /** 1.1: YYYY-MM-DD */
  before_date: string;
  label: string;
  /** 1.1: manual — підпис людини, auto — за правилами з даних */
  label_source: LabelSource;
  /** 1.1: попередження (штиль, неповне покриття) */
  note?: string | null;
  /** Площа плям класу probable (км²) */
  area_km2: number;
  after_url: string;
  mask_url: string;
  contour_geojson_url: string;
  /** 1.1, опціонально */
  targets_geojson_url?: string | null;
}

export interface LocationDetail {
  id: string;
  title: string;
  /** Центр події у форматі [lon, lat] (EPSG:4326) */
  coords: [number, number];
  /** Межі зображення [west, south, east, north] (EPSG:4326) */
  bbox: [number, number, number, number];
  /** = before_date першого зрізу (сумісність з 1.0) */
  baseline_date: string; // YYYY-MM-DD
  /** = before_url першого зрізу (сумісність з 1.0) */
  baseline_before_url: string;
  description: string;
  source_url?: string | null;
  /** 1.1, опціонально */
  sources_geojson_url?: string | null;
  snapshots: SnapshotStep[];
}

export type SlickClass = "probable" | "possible";
export type SlickFlag = "near_coast" | "low_wind" | "near_noise" | "rain" | "small" | "static";

export interface SpillContourProperties {
  location_id: string;
  step_id: string;
  /** Площа цієї плями (км²) */
  area_km2: number;
  /** 1.1 */
  slick_id: string;
  /** 1.1 */
  class: SlickClass;
  /** 1.1: 0..1, ранжування, а не ймовірність */
  score: number;
  /** 1.1: чому оцінку знижено */
  flags: SlickFlag[];
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
    track: str = Field(..., description="Трек, напр. 056A (1.1)")
    polarization: Literal["HH", "VV"]
    before_url: str = Field(..., description="«До» того самого треку й поляризації (1.1)")
    before_date: str = Field(..., description="YYYY-MM-DD (1.1)")
    label: str
    label_source: Literal["manual", "auto"]
    note: Optional[str] = None
    area_km2: float = Field(..., ge=0.0, description="Площа плям класу probable")
    after_url: str
    mask_url: str
    contour_geojson_url: str
    targets_geojson_url: Optional[str] = None


class LocationDetail(BaseModel):
    id: str
    title: str
    coords: Tuple[float, float] = Field(
        ..., description="Центр події [lon, lat] у EPSG:4326"
    )
    bbox: Tuple[float, float, float, float] = Field(
        ..., description="Межі растру [west, south, east, north] у EPSG:4326"
    )
    baseline_date: str = Field(..., description="= before_date першого зрізу")
    baseline_before_url: str = Field(..., description="= before_url першого зрізу")
    description: str
    source_url: Optional[str] = None
    sources_geojson_url: Optional[str] = None
    snapshots: list[SnapshotStep]


class SpillContourProperties(BaseModel):
    location_id: str
    step_id: str
    area_km2: float = Field(..., ge=0.0, description="Площа цієї плями")
    slick_id: str
    class_: Literal["probable", "possible"] = Field(..., alias="class")
    score: float = Field(..., ge=0.0, le=1.0)
    flags: list[Literal["near_coast", "low_wind", "near_noise", "rain", "small", "static"]] = []

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
> `class` — зарезервоване слово в Python, тому в Pydantic поле називається `class_` з `alias="class"`. При серіалізації використовувати `model_dump(by_alias=True)`, щоб у JSON було саме `"class"`.

---

## 5. Як користуватися контрактом у команді (Workflow)

1. **Старт (Етап 0):**
   - **Фронтенд (Dev 1 + Dev 2):** копіюють інтерфейси з розділу `4.1` у `frontend/src/types/location.ts`, а JSON-приклади з розділу `2` — у `frontend/public/mock/` (`locations.json`, `oman-caroline-bezengi-2026.json`, `contour_t1.geojson`, `sources.geojson`, `targets_t1.geojson`). Після цього обидва фронтендери можуть працювати повністю автономно, не чекаючи запуску FastAPI.
   - **Бекенд:** копіює класи з розділу `4.2` у `backend/app/schemas.py` і гарантує, що `prepare_location.py` генерує `meta.json`, `.webp` та `.geojson` строго за цим контрактом.
2. **Інтеграція (Етап 3):**
   - Фронтенд перемикає `VITE_USE_MOCK=false`, і реальні дані з `http://localhost:8000` лягають у UI без переписування жодного компонента.
3. **Правило внесення змін:**
   - Будь-яка зміна імені поля, типу, структури URL або порядку координат **спочатку фіксується в `docs/API_CONTRACT.md`** (зі збільшенням версії, наприклад `1.1` -> `1.2`) і узгоджується між бекендом і фронтендом. Змінювати JSON «тишком» на одній зі сторін заборонено.