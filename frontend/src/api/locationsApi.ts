import type {
  LocationDetail,
  LocationsListResponse,
  LocationSummary,
  SpillContourFeatureCollection
} from "../types/location";

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

const detailCache = new Map<string, Promise<LocationDetail>>();
const geoJsonCache = new Map<string, Promise<SpillContourFeatureCollection>>();

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: не вдалося завантажити ${url}`);
  }
  return (await res.json()) as T;
}

export async function fetchLocations(): Promise<LocationSummary[]> {
  const url = USE_MOCK ? "/mock/locations.json" : "/api/v1/locations";
  const data = await fetchJson<LocationsListResponse>(url);
  return data.locations;
}

export async function fetchLocationDetail(id: string): Promise<LocationDetail> {
  const cached = detailCache.get(id);
  if (cached) {
    return cached;
  }

  const url = USE_MOCK
    ? `/mock/locations/${encodeURIComponent(id)}.json`
    : `/api/v1/locations/${encodeURIComponent(id)}`;

  const request = fetchJson<LocationDetail>(url).catch((err) => {
    detailCache.delete(id);
    throw err;
  });

  detailCache.set(id, request);
  return request;
}

export async function fetchGeoJson(url: string): Promise<SpillContourFeatureCollection> {
  const cached = geoJsonCache.get(url);
  if (cached) {
    return cached;
  }

  const request = fetchJson<SpillContourFeatureCollection>(url).catch((err) => {
    geoJsonCache.delete(url);
    throw err;
  });

  geoJsonCache.set(url, request);
  return request;
}
