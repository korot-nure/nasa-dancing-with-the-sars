# План роботи над фронтендом для 2 розробників (MVP)

**Проєкт:** Dancing with the SARs — Карта моніторингу розливів нафти (`NISAR L2 GCOV`)  
**Стек:** React + Vite + TypeScript + Leaflet (`L.imageOverlay` + `L.geoJSON`)  
**Версія документа:** 1.0 (синхронізовано з [API_CONTRACT.md](./API_CONTRACT.md) v1.0)  
**Дата:** 14 листопада 2026 р.

---

## 1. Декомпозиція макета інтерфейсу на 6 компонентів

Інтерфейс чітко поділяється на **лівий сайдбар (`~30%` ширини)** і **праву робочу сцену (`~70%` ширини)**:

```text
+-------------------------------+---------------------------------------------------+
| [1] OverviewMinimap      [⛶] |                                                   |
|   Міні-карта з пінами подій   |                                                   |
+-------------------------------+       [4] MainComparisonMap                       |
| [2] EventSelect (dropdown)    |           Головна карта локації:                  |
+-------------------------------+           - Шторка "Звичайна карта ↔ SAR-шар"     |
| [3] EventDetailsCard          |           - Шар підсвітки розливу (mask/GeoJSON)  |
|   - Назва                     |                                                   |
|   - Координати                +---------------------------------------------------+
|   - Площа плями (км²)         | [5] SpillOpacitySlider ("підсвітка розливу")      |
|   - Опис події                +---------------------------------------------------+
|   - Посилання на джерело      | [6] SnapshotTimeline (T0 До аварії + T1, T2, T3)  |
+-------------------------------+---------------------------------------------------+
```

### Склад компонентів
1. **`OverviewMinimap`** (лівий верх): міні-карта з помаранчевими маркерами всіх подій; активний маркер виділено обведенням; кнопка у правому верхньому куті скидає огляд до всіх локацій або розгортає карту.
2. **`EventSelect`** (ліва середина): випадаючий список подій (`<select>` або доступний кастомний селект), синхронізований із міні-картою.
3. **`EventDetailsCard`** (лівий низ): картка події з лаконічним набором полів: назва, координати (`lat, lon`), **площа плями на активну дату (`area_km2`, км²) та зміна `Δ км²` до попереднього зрізу**, опорна база `T0` (`baseline_date`), дата старту відстеження (`T1`, `snapshots[0].date`), зміщення `+N дн.` для активного знімка та короткий опис із посиланням на джерело.
4. **`MainComparisonMap`** (права основна зона): головна карта (`Leaflet`) із зрозумілою для людини базовою підкладкою (`OSM / супутник`) для вибраної локації, автоматичним перельотом камери (`flyToBounds(bbox)`) та вертикальною шторкою (`splitRatio`): **ліворуч від шторки видно звичайну карту**, **праворуч — накладений SAR-радар** (`baseline_before_url` на кроці `T0` або `snapshots[activeStepIdx].after_url` на кроках `T1..Tn`) + шар підсвітки розливу (`mask_url` / `contour_geojson_url`) + опціональний шар **«Траєкторія руху»** (пунктирні контури попередніх зрізів та стрілка дрейфу центроїдів).
5. **`SpillOpacitySlider`** (перший повзунок під картою): горизонтальний регулятор **«підсвітка розливу»** (`0%–100%`), що миттєво змінює прозорість (`opacity` / `fillOpacity`) шару розливу поверх SAR-знімка, а також перемикачі `GeoJSON контур` і `Траєкторія руху` без запитів до бекенда.
6. **`SnapshotTimeline`** (нижня панель): горизонтальний **«таймлайн знімків зі змінами»** з дискретними засічками дат і кнопкою **`▶ Старт / Пауза`** для автопрогравання динаміки: першою точкою відображається базовий стан **«До» (`T0`, `baseline_date`, `0 км²`)**, далі — **`T1 · Старт`** (`snapshots[0]`) і наступні прольоти супутника (`T2`, `T3`...) із відносними днями `+Nд`.

---

## 2. Єдиний контракт стану та даних (API Contract)

Перед початком паралельної роботи обидва розробники фіксують спільний файл типів `src/types/location.ts` (строго за [API_CONTRACT.md](./API_CONTRACT.md) v1.0):

```ts
export interface LocationSummary {
  id: string;
  title: string;
  coords: [number, number]; // [lon, lat]
  baseline_date: string;
  latest_date: string;
  area_km2: number;
}

export interface SnapshotStep {
  step_id: string;
  date: string;             // YYYY-MM-DD
  label: string;            // наприклад: "Пік розливу"
  area_km2: number;
  after_url: string;
  mask_url: string;
  contour_geojson_url: string;
}

export interface LocationDetail {
  id: string;
  title: string;
  coords: [number, number]; // [lon, lat]
  bbox: [number, number, number, number]; // [west, south, east, north]
  baseline_date: string;
  baseline_before_url: string;
  description: string;
  source_url?: string;
  snapshots: SnapshotStep[];
}

export interface AppState {
  locations: LocationSummary[];
  activeLocationId: string | null;
  activeDetail: LocationDetail | null;
  activeStepIdx: number;    // -1 = T0 ("До" / baseline_before_url), 0..N-1 = індекс у snapshots[]
  spillOpacity: number;     // 0.0 .. 1.0 (для повзунка "підсвітка розливу")
  showTrajectory: boolean;  // Показ контурів попередніх етапів і вектора дрейфу (клієнтський розрахунок)
  isPlaying: boolean;       // Автопрогравання кроків таймлайну T0 -> Tn
  splitRatio: number;       // 0.05 .. 0.95 (позиція шторки: Звичайна карта ↔ SAR-накладення)
  loading: boolean;
  error: string | null;
}
```

---

## 3. Асиметричний розподіл завдань (Lead + UI, Zero Merge Conflicts)

Файли розділено так, щоб **`Dev 1 (Lead)`** закривав усю складну інфраструктуру, карту `Leaflet`, API, координати та таймлайн, а **`Dev 2 (UI / із підтримкою AI)`** відповідав за **3 ізольовані, прості презентаційні UI-компоненти** за готовими `Props` і візуальним еталоном [mockup/index.html](../mockup/index.html). Після Етапу 0 розробники **не редагують одні й ті самі файли**.

### Структура репозиторію фронтенду

```text
frontend/
├── public/
│   └── mock/                       # [Dev 1] Моки до готовності бекенда (спільна точка опори)
├── src/
│   ├── api/                        # [Dev 1] fetch-клієнт, хуки, mock-фолбек
│   │   └── locationsApi.ts
│   ├── types/                      # [Dev 1, фіксується на Етапі 0]
│   │   └── location.ts
│   ├── components/
│   │   ├── stage/                  # [Dev 1] Права картографічна сцена
│   │   │   ├── MainComparisonMap.tsx
│   │   │   └── SplitCurtainControl.tsx
│   │   ├── controls/               # [Dev 2] Панель прозорості та перемикачів
│   │   │   └── SpillOpacitySlider.tsx
│   │   ├── sidebar/
│   │   │   ├── OverviewMinimap.tsx # [Dev 1] SVG-мінікарта з координатами світу
│   │   │   ├── EventSelect.tsx     # [Dev 2] Випадаючий список подій
│   │   │   └── EventDetailsCard.tsx# [Dev 2] Картка події + підказка «Чому SAR?»
│   │   └── timeline/               # [Dev 1] Нижній таймлайн дат і Play/Pause
│   │       └── SnapshotTimeline.tsx
│   ├── App.tsx                     # [Dev 1] 2-колонковий Grid, стейт і таймер Play
│   └── main.tsx
├── package.json
└── vite.config.ts
```

### Зона відповідальності `Dev 1 (Lead)` — Каркас, карта, API та таймлайн
- **Файли:** `src/types/location.ts`, `src/api/locationsApi.ts`, `src/components/stage/`, `OverviewMinimap.tsx`, `SnapshotTimeline.tsx`, `App.tsx`, `public/mock/`
- **Завдання:**
  1. **Етап 0:** підняти Vite + React + TypeScript + Leaflet, зафіксувати типи в `src/types/location.ts`, покласти mock-дані, створити базову dark-тему CSS (за `mockup/index.html`) і порожні файли-заглушки з точними `Props` для `Dev 2`.
  2. **`locationsApi.ts`:** реалізувати `fetchLocations()`, `fetchLocationDetail(id)`, `fetchGeoJson(url)` із перемикачем `VITE_USE_MOCK=true`, обробкою `loading` та помилок.
  3. **`MainComparisonMap` + `SplitCurtainControl`:**
     - Налаштувати `Leaflet` зі зрозумілою базовою підкладкою (`OSM / супутник`) та `map.fitBounds([[south, west], [north, east]])`.
     - Накласти активний SAR-шар (`baseline_before_url` при `activeStepIdx === -1`, інакше `snapshots[activeStepIdx].after_url`) та підсвітку (`mask_url` / `contour_geojson_url`) праворуч від шторки `splitRatio`. **Контракт [API_CONTRACT.md](./API_CONTRACT.md) (`v1.0`) не змінюється.**
     - Реалізувати шар **«Траєкторія руху»** (`showTrajectory`): пунктирні контури попередніх кроків `snapshots[0..activeStepIdx-1]` та пунктирну стрілку дрейфу між центроїдами GeoJSON-полігонів на клієнті.
  4. **`OverviewMinimap`:** SVG-мінікарта світу з помаранчевими пінами подій і кнопкою скидання масштабу.
  5. **`SnapshotTimeline`:** шкала `T0 · База (до аварії)` (`idx = -1`), `T1 · Старт`, `T2 · +Nд`..., підтримка `←` / `→` та кнопка **`▶ Старт / Пауза`** (`isPlaying`).

### Зона відповідальності `Dev 2 (UI)` — 3 ізольовані презентаційні компоненти
- **Файли:** `EventSelect.tsx`, `EventDetailsCard.tsx`, `SpillOpacitySlider.tsx` *(працюють лише від вхідних `Props`, без доступу до `Leaflet` або `fetch`)*
- **Завдання (із готовими контрактами пропсів для зручної роботи з AI):**
  1. **`EventSelect.tsx`** (~40–50 рядків) — випадаючий список подій, синхронізований із вибраною локацією:
     ```ts
     export interface EventSelectProps {
       locations: LocationSummary[];
       activeLocationId: string | null;
       onSelectLocation: (id: string) => void;
     }
     ```
  2. **`EventDetailsCard.tsx`** (~80–120 рядків) — охайна картка події в сайдбарі + (за бажанням) коротка згортана плашка **«Чому це бачить саме SAR?»**:
     ```ts
     export interface EventDetailsCardProps {
       detail: LocationDetail | null;
       activeStepIdx: number; // -1 = T0 ("До аварії"), 0..N-1 = індекс у snapshots[]
       loading?: boolean;
     }
     ```
     - Виводить `title`, `coords` (`17.50°N, 56.02°E`), площу `area_km2` (`0.0 км²` на `T0` + приріст/спад `Δ км²` до попереднього зрізу), `baseline_date` (`T0`), явну дату **`Старт T1: <snapshots[0].date>`**, зсув `+N дн. від T1`, `description` та кнопку-посилання `source_url`.
  3. **`SpillOpacitySlider.tsx`** (~60–80 рядків) — панель керування під картою:
     ```ts
     export interface SpillOpacitySliderProps {
       spillOpacity: number;    // 0.0 .. 1.0
       showContour: boolean;
       showTrajectory: boolean;
       onOpacityChange: (value: number) => void;
       onToggleContour: (checked: boolean) => void;
       onToggleTrajectory: (checked: boolean) => void;
     }
     ```
     - Повзунок `0%–100%`, кнопки швидких значень (`0%`, `50%`, `100%`) і два чекбокси (`GeoJSON контур`, `Траєкторія руху`).

---

## 4. Поетапний план робіт (Roadmap)

### Етап 0. Старт, каркас і заглушки для `Dev 2` (робить `Dev 1`)
- Ініціалізувати Vite + React + TypeScript (`npm create vite@latest`), підключити `leaflet` і `@types/leaflet`.
- Створити `src/types/location.ts`, покласти 2–3 mock-кейси в `public/mock/`, перенести базові dark-стилі з `mockup/index.html`.
- Створити порожні компоненти-заглушки `EventSelect.tsx`, `EventDetailsCard.tsx`, `SpillOpacitySlider.tsx` з уже описаними `Props`-інтерфейсами і 2-колонковий `App.tsx`.
- Зафіксувати гілку `main`, щоб `Dev 2` міг одразу бачити свій UI наживо через `npm run dev`.

### Етап 1. Паралельна розробка у 2 гілках
- **Гілка `feat/core-map` (`Dev 1`):** розробляє `locationsApi`, `OverviewMinimap`, `MainComparisonMap`, `SplitCurtainControl` (`Звичайна карта ↔ SAR-накладення` + `Траєкторія руху`), `SnapshotTimeline` (`T0..Tn` + `Play`) та `App.tsx`.
- **Гілка `feat/ui-components` (`Dev 2`):** заповнює 3 файли (`EventSelect.tsx`, `EventDetailsCard.tsx`, `SpillOpacitySlider.tsx`) за готовим стилем із [mockup/index.html](../mockup/index.html) та прописаними `Props`.
- *Конфліктів у Git немає:* кожен редагує тільки свої файли.

### Етап 2. Збірка та синхронізація стейту (Pull Request у `main`)
- `Dev 1` перевіряє PR із `feat/ui-components`, мерджить обидві гілки в `main` і з'єднує всі пропси в `App.tsx`:
  - Клік по піну в `OverviewMinimap` або вибір в `EventSelect` $\rightarrow$ змінює `activeLocationId` $\rightarrow$ підвантажує `activeDetail` $\rightarrow$ встановлює `activeStepIdx` на останній знімок (`snapshots.length - 1`) $\rightarrow$ переносить камеру `MainComparisonMap`.
  - Клік по засічці в `SnapshotTimeline` (або автопрогравання `▶ Старт`) $\rightarrow$ оновлює `activeStepIdx` (`-1` для `T0 До` або `0..N-1`) $\rightarrow$ оновлює SAR-шар, `Траєкторію руху` та показники в `EventDetailsCard`.
  - Зміни в `SpillOpacitySlider` $\rightarrow$ оновлюють прозорість маски, контурів і траєкторії на карті.

### Етап 3. Інтеграція з бекендом і полірування
- Перемкнути `VITE_USE_MOCK=false`, налаштувати proxy у `vite.config.ts` на адресу FastAPI (`/api` та `/data` $\rightarrow$ `http://localhost:8000`).
- Перевірити стани завантаження (`loading`-скелетон), обробку одиничних `snapshots`, адаптацію на вузьких екранах та CORS на бекенді.

---

## 5. Правила роботи в Git

1. **`main` завжди запускається** — не пушити незавершений код напряму (працюємо через гілки та Pull Request).
2. **Гілки строго по ролях:** `feat/core-map` (`Dev 1 — Lead`), `feat/ui-components` (`Dev 2 — UI`), `feat/api-integration`.
3. **Якщо потрібно змінити формат API або інтерфейси `Props` / `LocationDetail`:** спочатку оновити `docs/API_CONTRACT.md`, `docs/FRONTEND_WORK_PLAN.md` і `src/types/location.ts`, щоб не зламати роботу напарника.

---

## 6. Post-MVP: наступний крок після MVP (для максимуму балів від журі NASA)

Ці два акценти **не входять у перший прохід MVP (Етапи 0–3)**, щоб не затримувати збірку базового продукту і не ламати контракт `v1.0`. Вони додаються поверх готового MVP перед фінальною демонстрацією:

1. **Інтерактивна підказка «Чому це бачить саме SAR?»:**
   - Коротка згортана плашка або тултип в `EventDetailsCard` (або під `SpillOpacitySlider`) з поясненням фізики на 1–2 речення: нафтова плівка (або спокійна вода при затопленні) гасить капілярні хвилі та дає дзеркальне відбиття убік від антени, тому радар NISAR фіксує темну зону падіння сигналу вдень, уночі та крізь щільні хмари.
   - Показує журі NASA, що команда розуміє відмінність активного мікрохвильового зондування від оптичних супутників.
2. **Візуальна підтримка двох типів подій (розливи нафти + повені/затоплення):**
   - Коли MVP на розливах нафти вже стабільно працює, можна додати пресети відкритих парних сцен `NISAR Sample Data Suite` із затопленнями.
   - На рівні UI у майбутньому розширенні контракту (`v1.1`) достатньо опціонального поля категорії події (`oil_spill` / `flood`), щоб перемикати підпис і колір бейджа/підсвітки (наприклад, сигнальний червоний `#ef4444` для нафти та синій для води), не переписуючи механіку карти й таймлайну.
