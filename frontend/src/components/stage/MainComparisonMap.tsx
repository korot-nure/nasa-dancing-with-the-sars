import type { LocationDetail } from "../../types/location";
import { SplitCurtainControl } from "./SplitCurtainControl";

export interface MainComparisonMapProps {
  detail: LocationDetail | null;
  activeStepIdx: number;
  spillOpacity: number;
  showContour: boolean;
  showTrajectory: boolean;
  splitRatio: number;
  onSplitChange: (ratio: number) => void;
}

/**
 * [Dev 1 — Lead] Головна карта Leaflet:
 * - Ліворуч від шторки: звичайна карта (OSM / супутникові тайли)
 * - Праворуч від шторки: SAR-шар (T0 або after_<step>) + маска розливу + GeoJSON + траєкторія дрейфу
 */
export function MainComparisonMap({
  detail,
  activeStepIdx,
  spillOpacity,
  showContour,
  showTrajectory,
  splitRatio,
  onSplitChange
}: MainComparisonMapProps) {
  const activeSnap =
    detail && activeStepIdx >= 0 ? detail.snapshots[activeStepIdx] ?? detail.snapshots[0] : null;

  return (
    <div className="map-stage" style={{ display: "grid", placeItems: "center", padding: 24 }}>
      <SplitCurtainControl splitRatio={splitRatio} onSplitChange={onSplitChange} />
      <div
        style={{
          maxWidth: 540,
          padding: 16,
          border: "1px solid var(--border)",
          borderRadius: 4,
          background: "var(--bg-panel)",
          zIndex: 10
        }}
      >
        <div className="section-title" style={{ marginBottom: 8 }}>
          MainComparisonMap — Stage 0 Каркас (Dev 1)
        </div>
        <div style={{ color: "var(--text-secondary)", marginBottom: 10 }}>
          На Етапі 1 тут підключається <code>Leaflet</code> (<code>fitBounds</code>,{" "}
          <code>L.imageOverlay</code>, <code>L.geoJSON</code>, кліпінг шторки та вектор дрейфу).
        </div>
        {detail ? (
          <div className="mono" style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6 }}>
            <div>bbox: [{detail.bbox.join(", ")}]</div>
            <div>
              SAR-шар ({activeStepIdx < 0 ? "T0 базовий" : activeSnap?.step_id.toUpperCase()}):{" "}
              {activeStepIdx < 0 ? detail.baseline_before_url : activeSnap?.after_url}
            </div>
            <div>
              opacity={Math.round(spillOpacity * 100)}% | contour={String(showContour)} | trajectory=
              {String(showTrajectory)} | split={Math.round(splitRatio * 100)}%
            </div>
          </div>
        ) : (
          <div style={{ color: "var(--text-muted)" }}>Завантаження геоданих...</div>
        )}
      </div>
    </div>
  );
}
