# План роботи над фронтендом для 2 розробників (v1.2)

**Проєкт:** Dancing with the SARs — Карта моніторингу розливів нафти (`NISAR L2 GCOV`)  
**Стек:** React + Vite + TypeScript + Leaflet (`L.imageOverlay` + `L.geoJSON`)  
**Версія документа:** `1.2` (синхронізовано з [API_CONTRACT.md](./API_CONTRACT.md) v1.2)  
**Дата:** 15 листопада 2026 р.

---

## 0. Що змінилося у фронтенді під контракт `v1.2`

1. **Поле походження плями `origin?: "pipeline" | "reference"` (`v1.2`) і реальний набір Оману (`t1..t12`):**
   - Локація `oman-caroline-bezengi-2026` підключена на реальних `12` зрізах `NISAR L2 GCOV` (`t1..t12`, з `2026-06-30` по `2026-09-16`, треки `056A VV` та `150D HH`) із растрами `.webp` (`1200x770` у `EPSG:3857`), контурами `contour_t*.geojson`, цілями `targets_t*.geojson` і джерелами `sources.geojson`.
   - У `SpillContourProperties` додано `origin?: "pipeline" | "reference"`. Для `t1..t4` та `t6` ранні плями біля танкера мають `"origin": "reference"` — спливаючі підказки контурів показують «еталонна розмітка».
2. **Парне порівняння «До / Після» в межах одного треку й поляризації:**
   - У кожного `SnapshotStep` тепер є власні `before_url`, `before_date`, `track` (`056A`, `150D`) та `polarization` (`HH` / `VV`).
   - При перемиканні кроку на таймлайні (`T0..Tn`) на карті **оновлюються обидві сторони шторки**: ліворуч — `before_url` (`sarLeftPane`), праворуч — `after_url` + маска (`sarRightPane`).
3. **Контури за класами достовірності (`contour.geojson`):**
   - Одна пляма = одна `Feature` з полями `slick_id`, `class` (`"probable" | "possible"`), `score` (`0..1`), `flags` (`near_coast`, `low_wind`, `near_noise`, `rain`, `small`, `static`) та `origin`.
   - `probable`: суцільний `#ef4444` контур + заливка (керується `spillOpacity`); `possible`: пунктирний `#fbbf24` контур без заливки.
4. **Примітки до зрізів (`note`, `label_source`):**
   - Якщо `note` заповнено (наприклад, штиль, слабкий контраст у VV на `t5`, еталонна розмітка або вихід на берег за межами кадру), картка події та кнопка кроку на таймлайні виводять попередження.
5. **Опціональні контекстні шари:**
   - `sources.geojson` — відоме та знайдене алгоритмом джерело розливу (`detected` / `known`).
   - `targets_<step_id>.geojson` — точкові радарні цілі на дату знімка (`ship` / `platform` / `coastal`).

---

## 1. Декомпозиція макета інтерфейсу на 6 компонентів

Інтерфейс поділяється на **лівий сайдбар (`~30%` ширини)** і **праву робочу сцену (`~70%` ширини)** (на екранах `<= 900px` сайдбар складається зверху з прокруткою):

```text
+-------------------------------+---------------------------------------------------+
| [1] OverviewMinimap      [⛶] | [SAR ДО: before_date · track · pol]  [Темна|OSM] |
|   Міні-карта з пінами подій   |                                                   |
+-------------------------------+       [4] MainComparisonMap                       |
| [2] EventSelect (dropdown)    |           - Ліворуч: підкладка + SAR «До»         |
+-------------------------------+           - Праворуч: SAR «Після» + маска         |
| [3] EventDetailsCard          |           - Контури (probable/possible),          |
|   - Назва, координати         |             траєкторія дрейфу, джерела і цілі   |
|   - Етап, площа (км²) + Δ     +---------------------------------------------------+
|   - Трек · Поляризація + «До» | [5] SpillOpacitySlider ("прозорість маски")       |
|   - Попередження note, опис   +---------------------------------------------------+
|   - Посилання та «Чому SAR?»  | [6] SnapshotTimeline (T0 До + T1..Tn + Старт)     |
+-------------------------------+---------------------------------------------------+
```

### Склад компонентів
1. **`OverviewMinimap`** (лівий верх): SVG-мінікарта світу з помаранчевими маркерами подій і режимами `Світ` / `Регіон`.
2. **`EventSelect`** (ліва середина): випадаючий список подій, синхронізований із міні-картою.
3. **`EventDetailsCard`** (лівий низ): картка телеметрії: назва, координати (`lat, lon` з урахуванням `N/S/E/W`), **площа `probable` плям (`area_km2`) та зміна `Δ км²`**, **трек і поляризація (`track · polarization`) + дата парного знімка «До» (`before_date`)**, попередження (`note`), опис, `source_url` та підказка «Чому це бачить саме SAR?».
4. **`MainComparisonMap`** (права основна зона): карта `Leaflet` з обмеженням меж світу (`WORLD_BOUNDS`, `noWrap: true`), базовою підкладкою (`Темна` / `OSM` / `Супутник`) та двосторонньою шторкою (`splitRatio`):
   - **ліворуч від шторки (`sarLeftPane`)** — підкладка + парний SAR «До» (`before_url`);
   - **праворуч від шторки (`sarRightPane`)** — SAR «Після» (`after_url`), маска розливу (`mask_url`), контури (`probable` / `possible`) та траєкторія дрейфу центроїдів;
   - **опціональні маркери** — джерела (`sources.geojson`) і точкові цілі (`targets_<step_id>.geojson`).
5. **`SpillOpacitySlider`** (панель під карткою): регулятор прозорості `0%–100%` (`0%`, `50%`, `100%`) і перемикачі `Векторний контур плями` та `Траєкторія руху (дрейф)`.
6. **`SnapshotTimeline`** (нижня панель): `T0 · База (до аварії)` (`idx = -1`) і кроки `T1..Tn` із датою, площею, підписом `track · polarization`, іконкою попередження `note`, навігацією `←` / `→` та `▶ Старт / Пауза`.

---

## 2. Єдиний контракт даних та стану (`src/types/location.ts`)

Типи повністю синхронізовано з розділом `4.1` документа [API_CONTRACT.md](./API_CONTRACT.md) v1.2:
- `LocationSummary`, `LocationsListResponse`
- `Polarization = "HH" | "VV"`, `LabelSource = "manual" | "auto"`
- `SnapshotStep` (`track`, `polarization`, `before_url`, `before_date`, `label_source`, `note?`, `targets_geojson_url?` + `after_url`, `mask_url`, `contour_geojson_url`, `area_km2`)
- `LocationDetail` (`sources_geojson_url?`, `baseline_date`, `baseline_before_url`, `bbox`, `coords`, `snapshots`)
- `SlickClass`, `SlickFlag`, `SpillContourProperties` (додано `origin?: "pipeline" | "reference"`), `SpillContourFeatureCollection`
- `SourceProperties`, `SourceFeatureCollection`, `TargetProperties`, `TargetFeatureCollection`
- `AppState`

---

## 3. Асиметричний розподіл завдань (Lead + UI, Zero Merge Conflicts)

Після оновлення контракту до `v1.2` розробники продовжують працювати у своїх зонах відповідальності, щоб уникати конфліктів при паралельній роботі:

```text
frontend/
├── public/
│   ├── data/locations/oman-caroline-bezengi-2026/ # [Dev 1] Реальні WebP-растри й GeoJSON (12 зрізів t1..t12)
│   └── mock/                       # [Dev 1] Mock-дані v1.2 (локації, GeoJSON, sources, targets)
└── src/
    ├── api/locationsApi.ts         # [Dev 1] REST + GeoJSON клієнт і resolveGeoJsonUrl для /api/v1/... у mock-режимі
    ├── types/location.ts           # [Dev 1] Єдиний контракт типів v1.2
    ├── utils/format.ts             # [Dev 2 / Shared] pluralUk, formatLatLon
    ├── components/
    │   ├── stage/                  # [Dev 1] MainComparisonMap.tsx, SplitCurtainControl.tsx
    │   ├── timeline/               # [Dev 1] SnapshotTimeline.tsx
    │   ├── sidebar/
    │   │   ├── OverviewMinimap.tsx # [Dev 1] SVG-мінікарта світу
    │   │   ├── EventSelect.tsx     # [Dev 2] Випадаючий список подій
    │   │   └── EventDetailsCard.tsx# [Dev 2] Картка телеметрії (Props збережено)
    │   └── controls/
    │       └── SpillOpacitySlider.tsx # [Dev 2] Прозорість маски та перемикачі шарів
    ├── App.tsx                     # [Dev 1] Grid-каркас, AppState і таймер Play
    └── index.css                   # [Shared] Темна матова палітра + мобільна адаптація (<= 900px)
```

### Що в зоні `Dev 1 (Lead)` — Архітектура, карта, API, таймлайн
1. **Етап 3.1 (Карта та шторка v1.1 — базово реалізовано):**
   - `sarLeftPane` (`before_url`) + `sarRightPane` (`after_url` + `mask_url`) оновлюються одночасно при перемиканні кроку.
   - Стилізація контурів за `class` (`probable` vs `possible`), фокус траєкторії на `probable`-полігонах, завантаження `sources.geojson` і `targets_<step_id>.geojson`.
   - За потреби (наступна ітерація): перемикачі видимості шарів `Судна/цілі` та `Джерела`, тултипи на полігонах із `score` і розшифровкою `flags` (`near_coast`, `low_wind`, `near_noise`, `rain`, `small`, `static`).
2. **Етап 3.2 (Таймлайн і API):**
   - Виведення `track · polarization` і індикації `note` у `SnapshotTimeline.tsx`.
   - Кешування `fetchSourcesGeoJson` та `fetchTargetsGeoJson` у `locationsApi.ts`.
3. **Етап 4 (Інтеграція з реальним FastAPI-бекендом):**
   - Перемкнути `VITE_USE_MOCK=false`, налаштувати Vite proxy (`/api` та `/data` $\rightarrow$ `http://localhost:8000`).
   - Перевірити вирівнювання реальних `before_<track>_<pol>.webp`, `after_<step>.webp` та `mask_<step>.webp` у `EPSG:3857` на `L.imageOverlay`.

### Що в зоні `Dev 2 (UI)` — Полірування UI-компонентів і легенди
1. **`EventDetailsCard.tsx`:**
   - Перевірити й відполірувати блок `Трек і серія` (`track · polarization`, `Пара «До»: <before_date>`), плашку попередження `note` і адаптивне перенесення значень на вузьких екранах.
   - За потреби: додати компактну легенду класів (`Ймовірно нафта` — суцільний `#ef4444` vs `Можливо` — пунктирний `#fbbf24`, `Джерело знайдене/відоме`) у нижній частині картки або поруч із підказкою SAR.
2. **`EventSelect.tsx` та `SpillOpacitySlider.tsx`:**
   - Перевірити візуальну узгодженість з темною матовою палітрою ([index.css](../frontend/src/index.css)) без градієнтів, тіней і емодзі; протестувати переповнення тексту та фокус з клавіатури.
   - При розширенні шарів (за узгодженням з `Dev 1` у `App.tsx`) можна додати додаткові чекбокси (`Судна та споруди`, `Сумнівні плями`) після узгодження нових `Props`.
3. **Жива перевірка адаптивності:**
   - Прогнати `npm run build` і `npm run dev` у `frontend/`, перевірити десктоп, мобільну версію (`<= 900px`), кейси з `note: null` vs `note: "..."`, перемикання Оман (`056A VV` $\leftrightarrow$ `150D HH`) $\rightarrow$ Керч $\rightarrow$ Маракайбо.

---

## 4. Правила роботи в Git і вимоги до стилю

1. **Гілки:** `Dev 1` веде інтеграцію в `main` / `feat/core-map`; `Dev 2` працює на `feat/ui-components` і перед початком кожної сесії синхронізується (`git fetch origin && git merge origin/main`).
2. **Контракт пропсів:** змінювати інтерфейси `Props` компонентів `Dev 2` можна лише за попереднім узгодженням із `Dev 1` і оновленням `App.tsx`.
3. **Дизайн-система (`no-slop-ui`):** строго темна матова палітра з `index.css` (`#09090b`, `#111113`, `#18181b`, `#27272a`), без `linear-gradient` / `radial-gradient`, `box-shadow`, `backdrop-filter` і без Unicode-емодзі; усі числові показники у `.mono` (`tabular-nums`).
