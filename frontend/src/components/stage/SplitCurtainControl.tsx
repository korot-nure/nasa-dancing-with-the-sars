export interface SplitCurtainControlProps {
  splitRatio: number; // 0.05 .. 0.95
  onSplitChange: (ratio: number) => void;
}

/**
 * [Dev 1 — Lead] Вертикальна шторка порівняння "Звичайна карта ↔ SAR-накладення".
 */
export function SplitCurtainControl({ splitRatio, onSplitChange }: SplitCurtainControlProps) {
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        bottom: 0,
        left: `${(splitRatio * 100).toFixed(2)}%`,
        width: 2,
        background: "#e4e4e7",
        zIndex: 450,
        pointerEvents: "none"
      }}
    >
      <button
        type="button"
        aria-label="Позиція шторки порівняння"
        onClick={() => onSplitChange(splitRatio > 0.5 ? 0.35 : 0.65)}
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          pointerEvents: "auto",
          width: 28,
          height: 28,
          borderRadius: 4,
          border: "1px solid var(--border-strong)",
          background: "var(--bg-panel)",
          color: "var(--text-primary)",
          cursor: "ew-resize"
        }}
      >
        ||
      </button>
    </div>
  );
}
