/**
 * Єдиний TypeScript-контракт даних (API_CONTRACT.md v1.0 + FRONTEND_WORK_PLAN.md).
 * Цей файл фіксується на Етапі 0 і є спільним джерелом правди для обох розробників.
 */

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

export interface AppState {
  locations: LocationSummary[];
  activeLocationId: string | null;
  activeDetail: LocationDetail | null;
  /** -1 = T0 ("До аварії" / baseline_before_url), 0..N-1 = індекс у snapshots[] */
  activeStepIdx: number;
  /** Прозорість шару підсвітки розливу (0.0 .. 1.0) */
  spillOpacity: number;
  /** Показ векторного контуру активного кроку */
  showContour: boolean;
  /** Показ контурів попередніх етапів і вектора дрейфу (клієнтський розрахунок) */
  showTrajectory: boolean;
  /** Автопрогравання кроків таймлайну T0 -> Tn */
  isPlaying: boolean;
  /** Позиція шторки (0.05 .. 0.95): Звичайна карта ↔ SAR-накладення */
  splitRatio: number;
  loading: boolean;
  error: string | null;
}
