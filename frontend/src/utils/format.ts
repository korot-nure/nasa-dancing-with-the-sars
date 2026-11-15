/** Українська множина: pluralUk(1, ["подія", "події", "подій"]) -> "подія". */
export function pluralUk(n: number, forms: [string, string, string]): string {
  const mod10 = Math.abs(n) % 10;
  const mod100 = Math.abs(n) % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}

/** Координати [lon, lat] -> "17.5°N 56.0°E" з урахуванням півкуль (S / W для від'ємних). */
export function formatLatLon(coords: [number, number], digits = 2, separator = ", "): string {
  const [lon, lat] = coords;
  const latStr = `${Math.abs(lat).toFixed(digits)}°${lat >= 0 ? "N" : "S"}`;
  const lonStr = `${Math.abs(lon).toFixed(digits)}°${lon >= 0 ? "E" : "W"}`;
  return `${latStr}${separator}${lonStr}`;
}
