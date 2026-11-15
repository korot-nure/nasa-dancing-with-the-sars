import type {
  LocationDetail,
  LocationsListResponse,
  LocationSummary,
  SourceFeatureCollection,
  SpillContourFeatureCollection,
  TargetFeatureCollection
} from "../types/location";

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";
const BASE_URL = import.meta.env.BASE_URL || "/";

export function withBase(url: string): string {
  if (!url.startsWith("/") || url.startsWith("//")) {
    return url;
  }
  const prefix = BASE_URL.endsWith("/") ? BASE_URL.slice(0, -1) : BASE_URL;
  return `${prefix}${url}`;
}

const detailCache = new Map<string, Promise<LocationDetail>>();
const geoJsonCache = new Map<string, Promise<SpillContourFeatureCollection>>();
const sourcesCache = new Map<string, Promise<SourceFeatureCollection>>();
const targetsCache = new Map<string, Promise<TargetFeatureCollection>>();

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: failed to load ${url}`);
  }
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("text/html")) {
    throw new Error(`Expected JSON but received HTML (${url}). Reload the page (Ctrl+Shift+R).`);
  }
  return (await res.json()) as T;
}

function fetchCachedJson<T>(cache: Map<string, Promise<T>>, key: string, url: string): Promise<T> {
  const cached = cache.get(key);
  if (cached) {
    return cached;
  }

  const request = fetchJson<T>(url).catch((err) => {
    cache.delete(key);
    throw err;
  });

  cache.set(key, request);
  return request;
}

export async function fetchLocations(): Promise<LocationSummary[]> {
  const url = withBase(USE_MOCK ? "/mock/locations.json" : "/api/v1/locations");
  const data = await fetchJson<LocationsListResponse>(url);
  return data.locations;
}

export function fetchLocationDetail(id: string): Promise<LocationDetail> {
  const url = withBase(
    USE_MOCK
      ? `/mock/locations/${encodeURIComponent(id)}.json`
      : `/api/v1/locations/${encodeURIComponent(id)}`
  );
  return fetchCachedJson(detailCache, id, url);
}

export function resolveGeoJsonUrl(url: string): string {
  if (!USE_MOCK) {
    return withBase(url);
  }

  const sourcesMatch = url.match(/^\/api\/v1\/locations\/([^/]+)\/sources\.geojson$/);
  if (sourcesMatch) {
    return withBase(`/mock/${sourcesMatch[1]}/sources.geojson`);
  }

  const contourMatch = url.match(
    /^\/api\/v1\/locations\/([^/]+)\/snapshots\/([^/]+)\/contour\.geojson$/
  );
  if (contourMatch) {
    return withBase(`/mock/${contourMatch[1]}/contour_${contourMatch[2]}.geojson`);
  }

  const targetsMatch = url.match(
    /^\/api\/v1\/locations\/([^/]+)\/snapshots\/([^/]+)\/targets\.geojson$/
  );
  if (targetsMatch) {
    return withBase(`/mock/${targetsMatch[1]}/targets_${targetsMatch[2]}.geojson`);
  }

  return withBase(url);
}

export function fetchGeoJson(url: string): Promise<SpillContourFeatureCollection> {
  const resolved = resolveGeoJsonUrl(url);
  return fetchCachedJson(geoJsonCache, resolved, resolved);
}

export function fetchSourcesGeoJson(url: string): Promise<SourceFeatureCollection> {
  const resolved = resolveGeoJsonUrl(url);
  return fetchCachedJson(sourcesCache, resolved, resolved);
}

export function fetchTargetsGeoJson(url: string): Promise<TargetFeatureCollection> {
  const resolved = resolveGeoJsonUrl(url);
  return fetchCachedJson(targetsCache, resolved, resolved);
}
