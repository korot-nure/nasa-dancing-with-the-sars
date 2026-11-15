/**
 * Єдиний TypeScript-контракт даних (API_CONTRACT.md v1.1 + FRONTEND_WORK_PLAN.md).
 * Спільне джерело правди для обох розробників.
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
  /** Позиція шторки (0.05 .. 0.95): Звичайна карта / SAR «До» ↔ SAR «Після» */
  splitRatio: number;
  loading: boolean;
  error: string | null;
}
