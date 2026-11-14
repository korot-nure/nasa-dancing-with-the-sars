export interface SpillOpacitySliderProps {
  spillOpacity: number; // 0.0 .. 1.0
  showContour: boolean;
  showTrajectory: boolean;
  onOpacityChange: (value: number) => void;
  onToggleContour: (checked: boolean) => void;
  onToggleTrajectory: (checked: boolean) => void;
}

/**
 * TODO (Dev 2 — UI):
 * Панель керування шарами маски розливу (ліва панель або блок керування).
 *
 * Зараз тут робочий Stage 0 компонент з повзунком прозорості та двома перемикачами.
 * Твоє завдання на Stage 1:
 * 1. Доопрацювати візуальний вигляд повзунка та чекбоксів/перемикачів у стилі темного інтерфейсу
 *    (без градієнтів, неонового світіння чи емодзі — див. docs/FRONTEND_WORK_PLAN.md).
 * 2. Відобразити точний відсоток прозорості (`0%` – `100%`) моноширинним шрифтом `.mono`.
 * 3. Перевірити доступність (`label`, `htmlFor`, фокус з клавіатури).
 * 4. Не змінюй `SpillOpacitySliderProps` і назву експорту `SpillOpacitySlider`.
 */
export function SpillOpacitySlider({
  spillOpacity,
  showContour,
  showTrajectory,
  onOpacityChange,
  onToggleContour,
  onToggleTrajectory,
}: SpillOpacitySliderProps) {
  const opacityPercent = Math.round(spillOpacity * 100);

  return (
    <div
      style={{
        padding: "10px 12px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        marginTop: "auto",
        borderTop: "1px solid var(--border)",
        background: "var(--bg-panel)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <label htmlFor="spill-opacity-range" className="section-title">
          Прозорість маски розливу
        </label>
        <span className="mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
          {opacityPercent}%
        </span>
      </div>

      <input
        id="spill-opacity-range"
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={spillOpacity}
        onChange={(e) => onOpacityChange(Number(e.target.value))}
        style={{
          width: "100%",
          accentColor: "var(--accent-signal)",
          cursor: "pointer",
        }}
      />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          paddingTop: "2px",
        }}
      >
        <label
          htmlFor="toggle-contour-layer"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "12px",
            color: "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          <span>Векторний контур плями</span>
          <input
            id="toggle-contour-layer"
            type="checkbox"
            checked={showContour}
            onChange={(e) => onToggleContour(e.target.checked)}
            style={{ accentColor: "var(--accent-spill)", cursor: "pointer" }}
          />
        </label>

        <label
          htmlFor="toggle-trajectory-layer"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "12px",
            color: "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          <span>Траєкторія руху (дрейф)</span>
          <input
            id="toggle-trajectory-layer"
            type="checkbox"
            checked={showTrajectory}
            onChange={(e) => onToggleTrajectory(e.target.checked)}
            style={{ accentColor: "var(--accent-drift)", cursor: "pointer" }}
          />
        </label>
      </div>
    </div>
  );
}
