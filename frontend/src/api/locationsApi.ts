import type {
  LocationDetail,
  LocationsListResponse,
  LocationSummary,
  SourceFeatureCollection,
  SpillContourFeatureCollection,
  TargetFeatureCollection
} from "../types/location";

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

const detailCache = new Map<string, Promise<LocationDetail>>();
const geoJsonCache = new Map<string, Promise<SpillContourFeatureCollection>>();
const sourcesCache = new Map<string, Promise<SourceFeatureCollection>>();
const targetsCache = new Map<string, Promise<TargetFeatureCollection>>();

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: не вдалося завантажити ${url}`);
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
  const url = USE_MOCK ? "/mock/locations.json" : "/api/v1/locations";
  const data = await fetchJson<LocationsListResponse>(url);
  return data.locations;
}

export function fetchLocationDetail(id: string): Promise<LocationDetail> {
  const url = USE_MOCK
    ? `/mock/locations/${encodeURIComponent(id)}.json`
    : `/api/v1/locations/${encodeURIComponent(id)}`;
  return fetchCachedJson(detailCache, id, url);
}

export function fetchGeoJson(url: string): Promise<SpillContourFeatureCollection> {
  return fetchCachedJson(geoJsonCache, url, url);
}

export function fetchSourcesGeoJson(url: string): Promise<SourceFeatureCollection> {
  return fetchCachedJson(sourcesCache, url, url);
}

export function fetchTargetsGeoJson(url: string): Promise<TargetFeatureCollection> {
  return fetchCachedJson(targetsCache, url, url);
}
