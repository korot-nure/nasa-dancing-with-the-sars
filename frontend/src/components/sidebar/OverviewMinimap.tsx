import type { LocationSummary } from "../../types/location";

export interface OverviewMinimapProps {
  locations: LocationSummary[];
  activeLocationId: string | null;
  onSelectLocation: (id: string) => void;
}

/**
 * [Dev 1 — Lead] SVG-мінікарта світу з помаранчевими пінами подій.
 * На Етапі 1 сюди переноситься SVG-проєкція континентів із mockup/index.html.
 */
export function OverviewMinimap({
  locations,
  activeLocationId,
  onSelectLocation
}: OverviewMinimapProps) {
  return (
    <div
      className="panel-placeholder"
      style={{ height: 150, display: "flex", flexDirection: "column", justifyContent: "space-between" }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="section-title">OverviewMinimap (Stage 0)</span>
        <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
          {locations.length} подій
        </span>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {locations.map((loc) => (
          <button
            key={loc.id}
            type="button"
            className="btn"
            style={{
              borderColor: loc.id === activeLocationId ? "var(--accent-pin)" : "var(--border)"
            }}
            onClick={() => onSelectLocation(loc.id)}
          >
            {loc.title.split(":")[0].split(",")[0]}
          </button>
        ))}
      </div>
    </div>
  );
}
