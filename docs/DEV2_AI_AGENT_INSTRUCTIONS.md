# Instructions for the AI Agent of Developer `Dev 2 (UI)`

**Project:** *Dancing with the SARs* — a web map for radar monitoring of oil spills (`NISAR / Sentinel-1 SAR`)  
**User role:** `Dev 2 (UI)`  
**Git working branch:** `feat/ui-components`

> [!IMPORTANT]
> Before changing even a single line of code, read this document in full and study the project files listed below. Your task is to carefully refine only 3 isolated UI components without breaking anything in the map core, the API and the timeline, which your teammate (`Dev 1`) is responsible for.

---

## 1. Required reading before you start

Read these files in the order given:
1. `docs/FRONTEND_WORK_PLAN.md` — frontend architecture, role split and project goals.
2. `frontend/src/types/location.ts` — the exact TypeScript interfaces (`LocationSummary`, `LocationDetail`, `SnapshotStep`).
3. `frontend/src/index.css` — CSS variables and ready-made styling classes (`.section-head`, `.section-title`, `.kv-grid`, `.kv-cell`, `.kv-label`, `.kv-val`, `.kv-sub`, `.kv-delta`, `.btn`, `.mono`).
4. `mockup/index.html` — the reference visual style (dark engineering interface).
5. All 3 of your target files with the current Stage 0 scaffolds and `TODO` comments:
   - `frontend/src/components/sidebar/EventSelect.tsx`
   - `frontend/src/components/sidebar/EventDetailsCard.tsx`
   - `frontend/src/components/controls/SpillOpacitySlider.tsx`

---

## 2. Strict change boundaries (File Scope)

### You may edit ONLY these 3 files:
1. `frontend/src/components/sidebar/EventSelect.tsx`
2. `frontend/src/components/sidebar/EventDetailsCard.tsx`
3. `frontend/src/components/controls/SpillOpacitySlider.tsx`

### It is strictly FORBIDDEN to modify, delete or rename:
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
- any files in `docs/`

**Why this is critical:** `Dev 1` is working in parallel in a separate branch, `feat/core-map`. If you change only your 3 files and keep their `Props` contracts, the branch merge (`Pull Request`) will go through without a single Git conflict.

---

## 3. Untouchable contracts (`Props` and exports)

You must not change the names of the exported components or the fields of their `Props` interfaces (you must not even add required props, because `App.tsx` passes exactly this set):

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
  activeStepIdx: number; // -1 = T0 ("Pre-event"), 0..N-1 = index into snapshots[]
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

## 4. Design, language and TypeScript rules

1. **Interface language (UI):** the application is bilingual, with **English** as the default and a Ukrainian localisation; every user-visible text must have both an `en` and a `uk` variant (see `frontend/src/i18n.tsx`).
2. **Visual style (`no-slop-ui` + `src/index.css`):**
   - Use the dark matte palette from `src/index.css`:
     - backgrounds: `var(--bg-canvas)` (`#09090b`), `var(--bg-panel)` (`#111113`), `var(--bg-surface)` (`#18181b`), `var(--bg-hover)` (`#1f1f23`);
     - borders: `var(--border)` (`#27272a`), `var(--border-strong)` (`#3f3f46`);
     - text: `var(--text-primary)` (`#f4f4f5`), `var(--text-secondary)` (`#a1a1aa`), `var(--text-muted)` (`#71717a`);
     - accents: `var(--accent-signal)` (`#3b82f6`), `var(--accent-pin)` (`#f97316`), `var(--accent-spill)` (`#ef4444`), `var(--accent-drift)` (`#fbbf24`).
   - **FORBIDDEN:** `linear-gradient`, `radial-gradient`, `box-shadow` with a colored/neon glow, `backdrop-filter: blur(...)`, "glass" cards, nested cards with large border radii, and **Unicode emoji** (no `🛢️`, `📍`, `🛰️`, `✅` — if needed, use minimalist inline `<svg>` with `stroke="currentColor"`).
   - For all numeric values (area in `km²`, dates, percentages, coordinates, offsets `+N d`, `Δ`), apply the `.mono` CSS class (`font-variant-numeric: tabular-nums`) so that the digits do not "jump" when switching steps on the timeline.
3. **Critically important about coordinates (`EPSG:4326`):**
   - In the `LocationSummary.coords` and `LocationDetail.coords` objects, coordinates are stored in GeoJSON format: **`[lon, lat]`** (`coords[0]` = longitude, `coords[1]` = latitude).
   - When displaying them to a human in `EventDetailsCard`, output latitude first, then longitude, in a readable format (for example, `17.50°N, 56.02°E`), destructuring the array as `const [lon, lat] = detail.coords;`.
4. **Strict TypeScript (`tsconfig.app.json`):**
   - `"strict": true`, `"noUnusedLocals": true`, `"noUnusedParameters": true` are enabled.
   - `any`, `@ts-ignore`, unused imports and unused variables are forbidden.
5. **Component purity:**
   - No `fetch(...)` and no direct access to `Leaflet` inside these 3 components — they work exclusively from the incoming `props`.

---

## 5. Detailed technical specification for each file

### 5.1. `frontend/src/components/sidebar/EventSelect.tsx`
**Purpose:** selecting the active oil spill incident in the left sidebar.

What to implement:
- A clear section heading (`.section-title`): `Active Event` + a counter of available locations in `.mono`.
- A stylish dark dropdown selector (`<select>` or a custom accessible listbox/dropdown with keyboard support that does not break focus).
- For each item, show the title (`loc.title`) and the latest recorded area (`loc.area_km2.toFixed(1) + " km²"`), and, if possible, the date of the latest snapshot (`loc.latest_date`).
- If `locations.length === 0`, the element must be neatly `disabled` with a clear waiting text (`Loading events...`).
- Mandatory accessibility: an associated `<label htmlFor=...>` and a visible keyboard focus (`focus-visible`).
- Compact height (do not take up extra space in the sidebar; width `100%`; a crisp `var(--border)` border, `var(--border-strong)` on hover).

### 5.2. `frontend/src/components/sidebar/EventDetailsCard.tsx`
**Purpose:** telemetry of the active snapshot and the incident description in the left sidebar.

What to implement:
1. **Event title and status/snapshot badge:**
   - Show `detail.title` (so that it is clear which incident is open even without opening the select).
   - `loading === true` state indicator: if `detail` is still `null`, show a neat skeleton/placeholder without layout "jumps"; if `detail` is already present and a new location is loading, show a compact `.mono` `UPDATING` marker in the section heading.
   - If `!detail && !loading` — a clear placeholder: `Select an event from the list or the overview map.`
2. **Computing the data of the current step (`activeStepIdx`):**
   - When `activeStepIdx === -1`: this is the baseline snapshot before the accident (`T0 · Pre-event (baseline)`), date = `detail.baseline_date`, area = `0.0 km²`, delta = `Baseline` (class `.kv-delta.is-neutral`), offset = `Before incident`.
   - When `activeStepIdx >= 0` (index into `detail.snapshots`):
     - `activeSnap = detail.snapshots[activeStepIdx]`
     - `firstSnap = detail.snapshots[0]` (explicit reference point: **`Start T1: ${firstSnap.date}`**)
     - `prevSnap = activeStepIdx > 0 ? detail.snapshots[activeStepIdx - 1] : null`
     - **Offset in days from `T1`:** compute the difference in days between `activeSnap.date` and `firstSnap.date` (`+0 d (Start)` for `T1`, `+N d from T1` for the following snapshots).
     - **Area delta (`Δ km²`):**
       - If `prevSnap` exists: `diff = activeSnap.area_km2 - prevSnap.area_km2`. Format `+X.X km²` (class `.kv-delta.is-up`) or `-X.X km²` (class `.kv-delta.is-down`) with the caption `vs previous` (or `no change`, class `.is-neutral`, if `Math.abs(diff) < 0.05`).
       - If `activeStepIdx === 0`: `Initial detection` (`.kv-delta.is-up`).
3. **Telemetry grid (`.kv-grid` of 4 cells):**
   - Cell 1: **Stage & Date** — `activeSnap ? activeSnap.label : "T0 · Pre-event"` + date in `.mono` + offset `+N d from T1` (or `Start T1: ...`).
   - Cell 2: **Spill Area** — `areaKm2.toFixed(1) km²` (`.mono`) + colored delta `Δ km²`.
   - Cell 3: **Center Coords** — latitude/longitude in the format `17.50°N, 56.02°E` (remember that `detail.coords` stores `[lon, lat]`, longitude first!) + caption `WGS-84`.
   - Cell 4: **Series Dynamics** — total number of snapshots (`detail.snapshots.length`) + date `Start T1: ${detail.snapshots[0]?.date ?? "—"}`.
4. **Description and source:**
   - Paragraph `detail.description` in a readable `12px` font, `color: var(--text-secondary)`, `line-height: 1.5`.
   - If `detail.source_url` is present, a `.btn` link button with the text `Incident Report` (`target="_blank"`, `rel="noopener noreferrer"`).
5. **Optional collapsible hint "Why does SAR see this?" (from the Post-MVP section of `FRONTEND_WORK_PLAN.md`):**
   - You may add a compact `<details>` / accordion button with 1–2 sentences (English, with a Ukrainian variant) about SAR physics: an oil film dampens capillary waves on the water and causes specular reflection away from the antenna, so the radar records a dark zone of signal loss by day, by night and through dense clouds. It must be **collapsed** by default so as not to inflate the sidebar height.

### 5.3. `frontend/src/components/controls/SpillOpacitySlider.tsx`
**Purpose:** control panel for the mask, contour and drift trajectory layers.

What to implement:
- Heading `Spill Mask Opacity` + the exact value in `.mono` (`0%`–`100%`).
- Slider `<input type="range" min={0} max={1} step={0.05} value={spillOpacity} ... />`.
- **Quick preset buttons** (`0%`, `50%`, `100%`) based on `.btn`, calling `onOpacityChange(0)`, `onOpacityChange(0.5)`, `onOpacityChange(1)`. The active button (when `Math.abs(spillOpacity - preset) < 0.01`) must be visually highlighted with a `var(--border-strong)` border and a `var(--bg-hover)` background / white text.
- **Two layer toggles:**
  - `Vector Slick Contour` (`checked={showContour}`, `onToggleContour`) — may be accompanied by a small red color marker (an `8px` square/circle in `var(--accent-spill)`).
  - `Drift Trajectory` (`checked={showTrajectory}`, `onToggleTrajectory`) — may be accompanied by a yellow color marker (`var(--accent-drift)`).
- Full keyboard accessibility (`label`, `htmlFor`, `type="button"` on the preset buttons so that they do not trigger an unwanted submit).

---

## 6. Mandatory checks before finishing

After making your changes, run these checks and report the results to the user:

1. **TypeScript + Vite build check:**
   Run in the `frontend` directory:
   ```powershell
   npm run build
   ```
   (or `npm.cmd run build` if scripts are restricted in PowerShell). The command must finish with exit code `0`, without errors or warnings.

2. **Style check (`no-slop-ui`):**
   Make sure that your 3 files contain no `linear-gradient`, `radial-gradient`, `box-shadow`, `backdrop-filter` or Unicode emoji.

3. **Git boundaries check:**
   Run:
   ```powershell
   git status --short
   ```
   The list of changed files must contain **only**:
   - `frontend/src/components/sidebar/EventSelect.tsx`
   - `frontend/src/components/sidebar/EventDetailsCard.tsx`
   - `frontend/src/components/controls/SpillOpacitySlider.tsx`

If any other file was accidentally touched, revert the changes in it before replying to the user.
