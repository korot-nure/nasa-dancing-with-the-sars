import type { LocationDetail } from "../../types/location";

export interface SnapshotTimelineProps {
  detail: LocationDetail | null;
  activeStepIdx: number; // -1 = T0 ("До аварії"), 0..N-1 = індекс у snapshots[]
  isPlaying: boolean;
  onSelectStep: (idx: number) => void;
  onTogglePlay: () => void;
}

/**
 * [Dev 1 — Lead] Нижній таймлайн знімків (T0 + T1..Tn) із кнопкою автопрогравання.
 */
export function SnapshotTimeline({
  detail,
  activeStepIdx,
  isPlaying,
  onSelectStep,
  onTogglePlay
}: SnapshotTimelineProps) {
  if (!detail) {
    return (
      <div
        style={{
          height: 82,
          padding: "0 14px",
          display: "flex",
          alignItems: "center",
          borderTop: "1px solid var(--border)",
          background: "var(--bg-panel)",
          color: "var(--text-muted)"
        }}
      >
        Завантаження таймлайну...
      </div>
    );
  }

  return (
    <div
      style={{
        height: 82,
        padding: "0 14px",
        display: "flex",
        alignItems: "center",
        gap: 12,
        borderTop: "1px solid var(--border)",
        background: "var(--bg-panel)"
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
        <button
          type="button"
          className="btn"
          disabled={activeStepIdx <= -1}
          onClick={() => onSelectStep(activeStepIdx - 1)}
        >
          &lt;
        </button>
        <button
          type="button"
          className="btn mono"
          style={{
            borderColor: isPlaying ? "var(--accent-signal)" : "var(--border)",
            color: isPlaying ? "var(--accent-signal)" : "var(--text-primary)"
          }}
          onClick={onTogglePlay}
        >
          {isPlaying ? "Пауза" : "Старт"}
        </button>
        <button
          type="button"
          className="btn"
          disabled={activeStepIdx >= detail.snapshots.length - 1}
          onClick={() => onSelectStep(activeStepIdx + 1)}
        >
          &gt;
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, flex: 1, overflowX: "auto" }}>
        <button
          type="button"
          className="btn mono"
          style={{
            height: 44,
            flex: 1,
            borderColor: activeStepIdx === -1 ? "var(--text-primary)" : "var(--border)"
          }}
          onClick={() => onSelectStep(-1)}
        >
          T0 · {detail.baseline_date} (0.0 км²)
        </button>
        {detail.snapshots.map((snap, idx) => (
          <button
            key={snap.step_id}
            type="button"
            className="btn mono"
            style={{
              height: 44,
              flex: 1,
              borderColor: idx === activeStepIdx ? "var(--text-primary)" : "var(--border)"
            }}
            onClick={() => onSelectStep(idx)}
          >
            {snap.step_id.toUpperCase()} · {snap.date} ({snap.area_km2.toFixed(1)} км²)
          </button>
        ))}
      </div>
    </div>
  );
}
