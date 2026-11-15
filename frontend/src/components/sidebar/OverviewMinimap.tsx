import { useMemo, useState } from "react";
import type { LocationSummary } from "../../types/location";
import { formatLatLon } from "../../utils/format";
import { formatArea, localizeTitle, useI18n } from "../../i18n";

export interface OverviewMinimapProps {
  locations: LocationSummary[];
  activeLocationId: string | null;
  onSelectLocation: (id: string) => void;
}

const WORLD_OUTLINES_LONLAT: [number, number][][] = [
  // North & Central America
  [[-168, 65], [-140, 70], [-95, 70], [-65, 58], [-55, 48], [-76, 35], [-81, 25], [-96, 20], [-88, 16], [-80, 9], [-85, 11], [-105, 20], [-115, 32], [-125, 48], [-152, 60]],
  // South America
  [[-79, 9], [-72, 12], [-62, 10], [-50, 1], [-35, -6], [-39, -18], [-48, -28], [-64, -41], [-68, -54], [-74, -52], [-72, -33], [-71, -18], [-81, -5]],
  // Europe + Eurasia + Asia
  [[-9, 36], [-9, 43], [-2, 43], [-4, 48], [6, 53], [10, 58], [18, 69], [40, 68], [72, 72], [115, 73], [168, 66], [160, 55], [140, 52], [130, 40], [122, 31], [109, 20], [103, 2], [97, 16], [89, 22], [78, 8], [70, 21], [58, 25], [56, 22], [52, 15], [44, 13], [35, 29], [36, 37], [28, 41], [32, 46], [37, 45], [39, 47], [29, 44], [24, 38], [16, 38], [9, 44], [2, 41]],
  // Africa
  [[-17, 15], [-13, 28], [-5, 36], [10, 37], [32, 31], [43, 12], [51, 11], [41, -2], [40, -16], [32, -26], [19, -35], [14, -22], [10, 3], [2, 6], [-13, 8]],
  // Australia
  [[114, -22], [130, -12], [142, -11], [153, -27], [149, -37], [138, -36], [122, -34], [114, -29]],
  // Greenland
  [[-52, 60], [-42, 60], [-20, 74], [-35, 82], [-68, 76]]
];

function lonLatToMini(lon: number, lat: number): [number, number] {
  return [((lon + 180) / 360) * 320, ((90 - lat) / 180) * 150];
}

/**
 * [Dev 1 — Lead] SVG world minimap with interactive event pins and regional focus.
 */
export function OverviewMinimap({
  locations,
  activeLocationId,
  onSelectLocation
}: OverviewMinimapProps) {
  const { lang } = useI18n();
  const [regionZoom, setRegionZoom] = useState(false);

  const continentPaths = useMemo(
    () =>
      WORLD_OUTLINES_LONLAT.map((poly) => {
        const pts = poly.map(([lon, lat]) => {
          const [x, y] = lonLatToMini(lon, lat);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        });
        return `M ${pts.join(" L ")} Z`;
      }),
    []
  );

  const activeLocation = useMemo(
    () => locations.find((loc) => loc.id === activeLocationId) ?? null,
    [locations, activeLocationId]
  );

  const isRegionMode = regionZoom && activeLocation !== null;
  const scaleFactor = isRegionMode ? 0.45 : 1;

  const viewBox = useMemo(() => {
    if (!isRegionMode || !activeLocation) {
      return "0 0 320 150";
    }
    const [cx, cy] = lonLatToMini(activeLocation.coords[0], activeLocation.coords[1]);
    const w = 110;
    const h = 51.56;
    const x0 = Math.max(0, Math.min(320 - w, cx - w / 2));
    const y0 = Math.max(0, Math.min(150 - h, cy - h / 2));
    return `${x0.toFixed(1)} ${y0.toFixed(1)} ${w} ${h}`;
  }, [isRegionMode, activeLocation]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        borderBottom: "1px solid var(--border)",
        background: "var(--bg-canvas)"
      }}
    >
      <div
        style={{
          position: "relative",
          height: 148,
          background: "#09090b",
          overflow: "hidden"
        }}
      >
        <svg
          viewBox={viewBox}
          width="100%"
          height="100%"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={
            lang === "uk" ? "Оглядова міні-карта подій розливів" : "Global oil spill overview minimap"
          }
          style={{ display: "block" }}
        >
          <rect x="0" y="0" width="320" height="150" fill="#09090b" />

          <g stroke="#141417" strokeWidth={0.7 * scaleFactor}>
            <line x1="0" y1="37.5" x2="320" y2="37.5" />
            <line x1="0" y1="75" x2="320" y2="75" />
            <line x1="0" y1="112.5" x2="320" y2="112.5" />
            <line x1="80" y1="0" x2="80" y2="150" />
            <line x1="160" y1="0" x2="160" y2="150" />
            <line x1="240" y1="0" x2="240" y2="150" />
          </g>

          <g
            fill="#18181b"
            stroke="#27272a"
            strokeWidth={0.8 * scaleFactor}
            strokeLinejoin="round"
          >
            {continentPaths.map((d, idx) => (
              <path key={idx} d={d} />
            ))}
          </g>

          <g>
            {locations.map((loc) => {
              const [lon, lat] = loc.coords;
              const [px, py] = lonLatToMini(lon, lat);
              const isActive = loc.id === activeLocationId;

              const localizedTitle = localizeTitle(loc.id, loc.title, lang);
              return (
                <g
                  key={loc.id}
                  role="button"
                  tabIndex={0}
                  aria-label={localizedTitle}
                  onClick={() => onSelectLocation(loc.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectLocation(loc.id);
                    }
                  }}
                  style={{ cursor: "pointer" }}
                >
                  <title>{`${localizedTitle} (${formatArea(loc.area_km2, lang)})`}</title>
                  <circle
                    cx={px.toFixed(1)}
                    cy={py.toFixed(1)}
                    r={(10 * scaleFactor).toFixed(2)}
                    fill="transparent"
                  />
                  {isActive && (
                    <>
                      <circle
                        cx={px.toFixed(1)}
                        cy={py.toFixed(1)}
                        r={(8.5 * scaleFactor).toFixed(2)}
                        fill="none"
                        stroke="#f4f4f5"
                        strokeWidth={(1.3 * scaleFactor).toFixed(2)}
                      />
                      <line
                        x1={(px - 11 * scaleFactor).toFixed(1)}
                        y1={py.toFixed(1)}
                        x2={(px + 11 * scaleFactor).toFixed(1)}
                        y2={py.toFixed(1)}
                        stroke="#f97316"
                        strokeWidth={(0.8 * scaleFactor).toFixed(2)}
                        opacity="0.7"
                      />
                      <line
                        x1={px.toFixed(1)}
                        y1={(py - 11 * scaleFactor).toFixed(1)}
                        x2={px.toFixed(1)}
                        y2={(py + 11 * scaleFactor).toFixed(1)}
                        stroke="#f97316"
                        strokeWidth={(0.8 * scaleFactor).toFixed(2)}
                        opacity="0.7"
                      />
                    </>
                  )}
                  <circle
                    cx={px.toFixed(1)}
                    cy={py.toFixed(1)}
                    r={((isActive ? 4.2 : 3.2) * scaleFactor).toFixed(2)}
                    fill="#f97316"
                    stroke="#09090b"
                    strokeWidth={(1.1 * scaleFactor).toFixed(2)}
                  />
                </g>
              );
            })}
          </g>
        </svg>

        <button
          type="button"
          className="btn mono"
          disabled={!activeLocation}
          onClick={() => setRegionZoom((prev) => !prev)}
          title={
            isRegionMode
              ? lang === "uk"
                ? "Показати всю карту світу"
                : "Show full world map"
              : lang === "uk"
                ? "Наблизити активну локацію"
                : "Zoom to active location"
          }
          style={{
            position: "absolute",
            top: 8,
            right: 8,
            height: 22,
            padding: "0 7px",
            fontSize: 10,
            background: "var(--bg-panel)",
            borderColor: isRegionMode ? "var(--accent-pin)" : "var(--border)"
          }}
        >
          <svg width="11" height="11" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M2 6V2H6M10 2H14V6M14 10V14H10M6 14H2V10"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>
            {isRegionMode
              ? lang === "uk"
                ? "Світ"
                : "World"
              : lang === "uk"
                ? "Регіон"
                : "Region"}
          </span>
        </button>

        <div
          className="mono"
          style={{
            position: "absolute",
            left: 8,
            bottom: 6,
            padding: "1px 6px",
            borderRadius: 3,
            border: "1px solid var(--border)",
            background: "var(--bg-panel)",
            color: "var(--text-secondary)",
            fontSize: 10,
            pointerEvents: "none"
          }}
        >
          {isRegionMode && activeLocation
            ? `${lang === "uk" ? "РЕГІОН" : "REGION"} · ${formatLatLon(activeLocation.coords, 1, " ")}`
            : `${lang === "uk" ? "СВІТ" : "WORLD"} · ${locations.length} ${
                lang === "uk"
                  ? locations.length === 1
                    ? "ПОДІЯ"
                    : locations.length >= 2 && locations.length <= 4
                      ? "ПОДІЇ"
                      : "ПОДІЙ"
                  : locations.length === 1
                    ? "EVENT"
                    : "EVENTS"
              }`}
        </div>
      </div>

      {locations.length > 0 && (
        <div
          style={{
            display: "flex",
            gap: 4,
            flexWrap: "wrap",
            padding: "6px 12px",
            borderTop: "1px solid var(--border)",
            background: "var(--bg-panel)"
          }}
        >
          {locations.map((loc) => {
            const isActive = loc.id === activeLocationId;
            return (
              <button
                key={loc.id}
                type="button"
                className="btn"
                onClick={() => onSelectLocation(loc.id)}
                style={{
                  height: 22,
                  padding: "0 7px",
                  fontSize: 11,
                  borderColor: isActive ? "var(--accent-pin)" : "var(--border)",
                  background: isActive ? "var(--bg-hover)" : "var(--bg-surface)",
                  color: isActive ? "var(--text-primary)" : "var(--text-secondary)"
                }}
              >
                {localizeTitle(loc.id, loc.title, lang).split(":")[0].split(",")[0]}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
