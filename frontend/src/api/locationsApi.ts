import type {
  LocationDetail,
  LocationsListResponse,
  LocationSummary,
  SpillContourFeatureCollection
} from "../types/location";

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

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
  const url = USE_MOCK
    ? `/mock/locations/${encodeURIComponent(id)}.json`
    : `/api/v1/locations/${encodeURIComponent(id)}`;
  return fetchJson<LocationDetail>(url);
}

export async function fetchGeoJson(url: string): Promise<SpillContourFeatureCollection> {
  return fetchJson<SpillContourFeatureCollection>(url);
}
