/**
 * Single TypeScript data contract (API_CONTRACT.md v1.2 + FRONTEND_WORK_PLAN.md).
 * Shared source of truth for both developers.
 */

export interface LocationSummary {
  id: string;
  title: string;
  /** Event centre as [lon, lat] (EPSG:4326) */
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
  /** 1.1: pass track, e.g. "056A" */
  track: string;
  /** 1.1: pass polarization */
  polarization: Polarization;
  /** 1.1: "Before" image of the same track and polarization */
  before_url: string;
  /** 1.1: YYYY-MM-DD */
  before_date: string;
  label: string;
  /** 1.1: manual = human-written label, auto = rule-based label derived from data */
  label_source: LabelSource;
  /** 1.1: warning (calm wind, partial coverage) */
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
  /** Event centre as [lon, lat] (EPSG:4326) */
  coords: [number, number];
  /** Image bounds [west, south, east, north] (EPSG:4326) */
  bbox: [number, number, number, number];
  /** = before_date of the first snapshot (1.0 compatibility) */
  baseline_date: string; // YYYY-MM-DD
  /** = before_url of the first snapshot (1.0 compatibility) */
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
  /** 1.1: 0..1, a ranking score, not a probability */
  score: number;
  /** 1.1: reasons the score was lowered */
  flags: SlickFlag[];
  /** 1.2: pipeline = detected by the pipeline, reference = reference annotation of a known event */
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

export interface AppState {
  locations: LocationSummary[];
  activeLocationId: string | null;
  activeDetail: LocationDetail | null;
  /** -1 = T0 ("Before incident" / baseline_before_url), 0..N-1 = index into snapshots[] */
  activeStepIdx: number;
  /** Opacity of the spill highlight layer (0.0 .. 1.0) */
  spillOpacity: number;
  /** Show the vector contour of the active step */
  showContour: boolean;
  /** Show contours of previous steps and the drift vector (computed client-side) */
  showTrajectory: boolean;
  /** Autoplay of timeline steps T0 -> Tn */
  isPlaying: boolean;
  /** Curtain position (0.05 .. 0.95): base map / SAR "Before" ↔ SAR "After" */
  splitRatio: number;
  loading: boolean;
  error: string | null;
}
