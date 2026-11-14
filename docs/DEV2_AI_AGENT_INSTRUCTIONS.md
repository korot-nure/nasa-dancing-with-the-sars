# Инструкция для ИИ-агента разработчика `Dev 2 (UI)`

**Проект:** *Dancing with the SARs* — веб-карта радарного мониторинга нефтяных разливов (`NISAR / Sentinel-1 SAR`)  
**Роль пользователя:** `Dev 2 (UI)`  
**Рабочая ветка Git:** `feat/ui-components`

> [!IMPORTANT]
> Перед тем как менять хотя бы одну строку кода, прочитай этот документ целиком и изучи указанные ниже файлы проекта. Твоя задача — аккуратно доработать только 3 изолированных UI-компонента, ничего не сломав в ядре карты, API и таймлайне, которыми занимается напарник (`Dev 1`).

---

## 1. Обязательное чтение перед началом работы

Прочитай эти файлы в указанном порядке:
1. `docs/FRONTEND_WORK_PLAN.md` — архитектура фронтенда, распределение ролей и цели проекта.
2. `frontend/src/types/location.ts` — точные TypeScript-интерфейсы (`LocationSummary`, `LocationDetail`, `SnapshotStep`).
3. `frontend/src/index.css` — CSS-переменные и готовые классы оформления (`.section-head`, `.section-title`, `.kv-grid`, `.kv-cell`, `.kv-label`, `.kv-val`, `.kv-sub`, `.kv-delta`, `.btn`, `.mono`).
4. `mockup/index.html` — эталон визуального стиля (тёмный инженерный интерфейс).
5. Все 3 твоих целевых файла с текущими Stage 0 заготовками и `TODO`-комментариями:
   - `frontend/src/components/sidebar/EventSelect.tsx`
   - `frontend/src/components/sidebar/EventDetailsCard.tsx`
   - `frontend/src/components/controls/SpillOpacitySlider.tsx`

---

## 2. Строгие границы изменений (File Scope)

### Разрешено редактировать ТОЛЬКО эти 3 файла:
1. `frontend/src/components/sidebar/EventSelect.tsx`
2. `frontend/src/components/sidebar/EventDetailsCard.tsx`
3. `frontend/src/components/controls/SpillOpacitySlider.tsx`

### Категорически ЗАПРЕЩЕНО изменять, удалять или переименовывать:
- `frontend/src/App.tsx`
- `frontend/src/types/location.ts`
- `frontend/src/api/locationsApi.ts`
- `frontend/src/index.css`
- `frontend/src/main.tsx`
- `frontend/src/components/sidebar/OverviewMinimap.tsx`
- `frontend/src/components/stage/*` (`MainComparisonMap.tsx`, `SplitCurtainControl.tsx`)
- `frontend/src/components/timeline/SnapshotTimeline.tsx`
- `frontend/package.json`, `frontend/tsconfig*.json`, `frontend/vite.config.ts`
- `frontend/public/mock/*`
- любые файлы в `docs/`

**Почему это критично:** `Dev 1` параллельно работает в отдельной ветке `feat/core-map`. Если ты будешь менять только свои 3 файла и сохранишь их `Props`-контракты, слияние веток (`Pull Request`) пройдёт без единого Git-конфликта.

---

## 3. Неприкосновенные контракты (`Props` и экспорты)

Нельзя менять имена экспортируемых компонентов и поля их `Props`-интерфейсов (даже добавлять обязательные пропсы нельзя, потому что `App.tsx` передаёт ровно этот набор):

### 3.1. `EventSelect.tsx`
```ts
export interface EventSelectProps {
  locations: LocationSummary[];
  activeLocationId: string | null;
  onSelectLocation: (id: string) => void;
}
export function EventSelect(props: EventSelectProps): JSX.Element
```

### 3.2. `EventDetailsCard.tsx`
```ts
export interface EventDetailsCardProps {
  detail: LocationDetail | null;
  activeStepIdx: number; // -1 = T0 ("До аварії"), 0..N-1 = індекс у snapshots[]
  loading?: boolean;
}
export function EventDetailsCard(props: EventDetailsCardProps): JSX.Element
```

### 3.3. `SpillOpacitySlider.tsx`
```ts
export interface SpillOpacitySliderProps {
  spillOpacity: number; // 0.0 .. 1.0
  showContour: boolean;
  showTrajectory: boolean;
  onOpacityChange: (value: number) => void;
  onToggleContour: (checked: boolean) => void;
  onToggleTrajectory: (checked: boolean) => void;
}
export function SpillOpacitySlider(props: SpillOpacitySliderProps): JSX.Element
```

---

## 4. Правила дизайна, языка и TypeScript

1. **Язык интерфейса (UI):** весь видимый пользователю текст в компонентах должен быть на **украинском языке** (как в остальном приложении).
2. **Визуальный стиль (`no-slop-ui` + `src/index.css`):**
   - Используй тёмную матовую палитру из `src/index.css`:
     - фоны: `var(--bg-canvas)` (`#09090b`), `var(--bg-panel)` (`#111113`), `var(--bg-surface)` (`#18181b`), `var(--bg-hover)` (`#1f1f23`);
     - границы: `var(--border)` (`#27272a`), `var(--border-strong)` (`#3f3f46`);
     - текст: `var(--text-primary)` (`#f4f4f5`), `var(--text-secondary)` (`#a1a1aa`), `var(--text-muted)` (`#71717a`);
     - акценты: `var(--accent-signal)` (`#3b82f6`), `var(--accent-pin)` (`#f97316`), `var(--accent-spill)` (`#ef4444`), `var(--accent-drift)` (`#fbbf24`).
   - **ЗАПРЕЩЕНО:** `linear-gradient`, `radial-gradient`, `box-shadow` с цветным/неоновым свечением, `backdrop-filter: blur(...)`, «стеклянные» карточки, вложенные карточки с крупными скруглениями и **Unicode-эмодзи** (никаких `🛢️`, `📍`, `🛰️`, `✅` — при необходимости используй минималистичные inline `<svg>` с `stroke="currentColor"`).
   - Для всех числовых значений (площадь `км²`, даты, проценты, координаты, смещения `+N дн.`, `Δ`) применяй CSS-класс `.mono` (`font-variant-numeric: tabular-nums`), чтобы цифры не «прыгали» при переключении таймлайном.
3. **Критически важно про координаты (`EPSG:4326`):**
   - В объектах `LocationSummary.coords` и `LocationDetail.coords` координаты хранятся в формате GeoJSON: **`[lon, lat]`** (`coords[0]` = долгота, `coords[1]` = широта).
   - Для отображения человеку в `EventDetailsCard` выводи сначала широту, потом долготу в понятном формате (например, `17.50°N, 56.02°E`), раскладывая массив как `const [lon, lat] = detail.coords;`.
4. **Строгий TypeScript (`tsconfig.app.json`):**
   - Включены `"strict": true`, `"noUnusedLocals": true`, `"noUnusedParameters": true`.
   - Запрещены `any`, `@ts-ignore`, неиспользуемые импорты и переменные.
5. **Чистота внутри компонента:**
   - Никаких `fetch(...)` и прямого обращения к `Leaflet` внутри этих 3 компонентов — они работают исключительно от входящих `props`.

---

## 5. Детальное техническое задание по каждому файлу

### 5.1. `frontend/src/components/sidebar/EventSelect.tsx`
**Назначение:** выбор активного инцидента разлива нефти в левом сайдбаре.

Что нужно реализовать:
- Чёткий заголовок секции (`.section-title`): `Активна подія` + счётчик доступных локаций в `.mono`.
- Стильный тёмный выпадающий селектор (`<select>` или кастомный доступный listbox/dropdown с поддержкой клавиатуры, без слома фокуса).
- Для каждого элемента отображать название (`loc.title`) и последнюю зафиксированную площадь (`loc.area_km2.toFixed(1) + " км²"`), при возможности — дату последнего снимка (`loc.latest_date`).
- Если `locations.length === 0`, элемент должен быть аккуратно `disabled` с понятным текстом ожидания (`Завантаження подій...`).
- Обязательная доступность: связанный `<label htmlFor=...>`, видимый фокус с клавиатуры (`focus-visible`).
- Компактная высота (не занимать лишнее место в сайдбаре, ширина `100%`, чёткая рамка `var(--border)` / `var(--border-strong)` при наведении).

### 5.2. `frontend/src/components/sidebar/EventDetailsCard.tsx`
**Назначение:** телеметрия активного снимка и описание инцидента в левом сайдбаре.

Что нужно реализовать:
1. **Заголовок события и бейдж статуса/среза:**
   - Показать `detail.title` (чтобы даже без открытия select было понятно, какой инцидент открыт).
   - Индикатор состояния `loading === true`: если `detail` ещё `null` — показать аккуратный skeleton/placeholder без «прыжков» вёрстки; если `detail` уже есть, а загружается новая локация — показать компактный маркер `.mono` `ОНОВЛЕННЯ` в заголовке секции.
   - Если `!detail && !loading` — понятная заглушка: `Оберіть подію зі списку або на оглядовій карті.`
2. **Расчёт данных текущего шага (`activeStepIdx`):**
   - При `activeStepIdx === -1`: это базовый снимок до аварии (`T0 · До аварії (база)`), дата = `detail.baseline_date`, площадь = `0.0 км²`, дельта = `Базовий фон` (класс `.kv-delta.is-neutral`), смещение = `До початку інциденту`.
   - При `activeStepIdx >= 0` (индекс в `detail.snapshots`):
     - `activeSnap = detail.snapshots[activeStepIdx]`
     - `firstSnap = detail.snapshots[0]` (явная точка отсчёта: **`Старт T1: ${firstSnap.date}`**)
     - `prevSnap = activeStepIdx > 0 ? detail.snapshots[activeStepIdx - 1] : null`
     - **Сдвиг в днях от `T1`:** посчитай разницу в днях между `activeSnap.date` и `firstSnap.date` (`+0 дн. (Старт)` для `T1`, `+N дн. від T1` для следующих снимков).
     - **Дельта площади (`Δ км²`):**
       - Если `prevSnap` есть: `diff = activeSnap.area_km2 - prevSnap.area_km2`. Формат `+X.X км²` (класс `.kv-delta.is-up`) или `-X.X км²` (класс `.kv-delta.is-down`) с подписью `від попереднього` (или `без змін`, класс `.is-neutral`, если `Math.abs(diff) < 0.05`).
       - Если `activeStepIdx === 0`: `Початкова фіксація` (`.kv-delta.is-up`).
3. **Сетка телеметрии (`.kv-grid` из 4 ячеек):**
   - Ячейка 1: **Етап і дата** — `activeSnap ? activeSnap.label : "T0 · До аварії"` + дата `.mono` + сдвиг `+N дн. від T1` (или `Старт T1: ...`).
   - Ячейка 2: **Площа розливу** — `areaKm2.toFixed(1) км²` (`.mono`) + цветная дельта `Δ км²`.
   - Ячейка 3: **Координати центру** — широта/долгота в формате `17.50°N, 56.02°E` (помня, что в `detail.coords` сначала `[lon, lat]`!) + подпись `WGS-84`.
   - Ячейка 4: **Динаміка серії** — сколько всего снимков (`detail.snapshots.length`) + дата `Старт T1: ${detail.snapshots[0]?.date ?? "—"}`.
4. **Описание и источник:**
   - Абзац `detail.description` читаемым шрифтом `12px`, `color: var(--text-secondary)`, `line-height: 1.5`.
   - Если есть `detail.source_url`, кнопка-ссылка `.btn` с текстом `Джерело звіту` (`target="_blank"`, `rel="noopener noreferrer"`).
5. **Опциональная сворачиваемая подсказка «Чому це бачить саме SAR?» (из Post-MVP раздела `FRONTEND_WORK_PLAN.md`):**
   - Можно добавить компактный `<details>` / кнопку-аккордеон на 1–2 предложения на украинском о физике SAR: нафтова плівка гасить капілярні хвилі на воді й дає дзеркальне відбиття убік від антени, тому радар фіксує темну зону падіння сигналу вдень, уночі та крізь щільні хмари. По умолчанию должен быть **свёрнут**, чтобы не раздувать высоту сайдбара.

### 5.3. `frontend/src/components/controls/SpillOpacitySlider.tsx`
**Назначение:** панель управления слоями маски, контура и траектории дрейфа.

Что нужно реализовать:
- Заголовок `Прозорість маски розливу` + точное значение в `.mono` (`0%`–`100%`).
- Ползунок `<input type="range" min={0} max={1} step={0.05} value={spillOpacity} ... />`.
- **Кнопки быстрых пресетов** (`0%`, `50%`, `100%`) на базе `.btn`, вызывающие `onOpacityChange(0)`, `onOpacityChange(0.5)`, `onOpacityChange(1)`. Активная кнопка (когда `Math.abs(spillOpacity - preset) < 0.01`) должна визуально выделяться рамкой `var(--border-strong)` и фоном `var(--bg-hover)` / белым текстом.
- **Два переключателя слоёв:**
  - `Векторний контур плями` (`checked={showContour}`, `onToggleContour`) — можно сопроводить маленьким красным цветовым маркером (`8px` квадрат/кружок цвета `var(--accent-spill)`).
  - `Траєкторія руху (дрейф)` (`checked={showTrajectory}`, `onToggleTrajectory`) — можно сопроводить жёлтым цветовым маркером (`var(--accent-drift)`).
- Полная доступность с клавиатуры (`label`, `htmlFor`, `type="button"` у кнопок пресетов, чтобы не триггерить лишнюю отправку).

---

## 6. Обязательная проверка перед завершением

После внесения изменений выполни эти проверки и сообщи результаты пользователю:

1. **Проверка сборки TypeScript + Vite:**
   Запусти в директории `frontend`:
   ```powershell
   npm run build
   ```
   (или `npm.cmd run build`, если в PowerShell ограничены скрипты). Команда должна завершиться с кодом `0` без ошибок и предупреждений.

2. **Проверка стиля (`no-slop-ui`):**
   Убедись, что в твоих 3 файлах нет `linear-gradient`, `radial-gradient`, `box-shadow`, `backdrop-filter` и Unicode-эмодзи.

3. **Проверка границ Git:**
   Выполни:
   ```powershell
   git status --short
   ```
   В списке изменённых файлов должны быть **только**:
   - `frontend/src/components/sidebar/EventSelect.tsx`
   - `frontend/src/components/sidebar/EventDetailsCard.tsx`
   - `frontend/src/components/controls/SpillOpacitySlider.tsx`

Если случайно затронут любой другой файл — откати изменения в нём перед ответом пользователю.
