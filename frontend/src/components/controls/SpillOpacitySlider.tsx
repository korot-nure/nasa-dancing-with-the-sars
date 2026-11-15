export interface SpillOpacitySliderProps {
  spillOpacity: number; // 0.0 .. 1.0
  showContour: boolean;
  showTrajectory: boolean;
  onOpacityChange: (value: number) => void;
  onToggleContour: (checked: boolean) => void;
  onToggleTrajectory: (checked: boolean) => void;
}

const RANGE_ID = "spill-opacity-range";
const PRESETS = [0, 0.5, 1] as const;

/** Локальні стилі повзунка, пресетів і перемикачів (плаский темний стиль, без тіней). */
const scopedCss = `
.d2-range {
  width: 100%;
  height: 4px;
  margin: 6px 0;
  appearance: none;
  -webkit-appearance: none;
  background: var(--border-strong);
  border-radius: 2px;
  cursor: pointer;
}
.d2-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: var(--text-primary);
  border: 1px solid var(--bg-canvas);
  cursor: ew-resize;
}
.d2-range::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: var(--text-primary);
  border: 1px solid var(--bg-canvas);
  cursor: ew-resize;
}
.d2-range::-moz-range-progress {
  height: 4px;
  border-radius: 2px;
  background: var(--accent-spill);
}
.d2-preset {
  flex: 1;
  color: var(--text-secondary);
}
.d2-preset.is-active {
  border-color: var(--border-strong);
  background: var(--bg-hover);
  color: var(--text-primary);
}
.d2-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-surface);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  transition: background-color 0.12s ease, border-color 0.12s ease;
}
.d2-toggle:hover {
  border-color: var(--border-strong);
  background: var(--bg-hover);
  color: var(--text-primary);
}
.d2-toggle input {
  margin: 0 0 0 auto;
  cursor: pointer;
}
`;

function LayerToggle({
  id,
  label,
  color,
  dashed,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  color: string;
  dashed?: boolean;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label htmlFor={id} className="d2-toggle">
      <span
        aria-hidden="true"
        style={{
          width: "8px",
          height: "8px",
          borderRadius: "2px",
          flexShrink: 0,
          background: dashed ? "transparent" : color,
          border: dashed ? `1px dashed ${color}` : "none",
          opacity: checked ? 1 : 0.4,
        }}
      />
      <span>{label}</span>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ accentColor: color }}
      />
    </label>
  );
}

/**
 * Панель керування шарами маски розливу: прозорість, пресети, контур і траєкторія.
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
        gap: "8px",
        marginTop: "auto",
        borderTop: "1px solid var(--border)",
        background: "var(--bg-panel)",
        flexShrink: 0,
      }}
    >
      <style>{scopedCss}</style>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <label htmlFor={RANGE_ID} className="section-title">
          Прозорість маски розливу
        </label>
        <span
          className="mono"
          aria-hidden="true"
          style={{
            minWidth: "40px",
            textAlign: "right",
            fontSize: "12px",
            fontWeight: 600,
            color: "var(--text-primary)",
          }}
        >
          {opacityPercent}%
        </span>
      </div>

      <input
        id={RANGE_ID}
        className="d2-range"
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={spillOpacity}
        aria-valuetext={`${opacityPercent}%`}
        onChange={(e) => onOpacityChange(Number(e.target.value))}
      />

      <div role="group" aria-label="Швидкі значення прозорості" style={{ display: "flex", gap: "6px" }}>
        {PRESETS.map((preset) => {
          const isActive = Math.abs(spillOpacity - preset) < 0.01;
          return (
            <button
              key={preset}
              type="button"
              className={`btn mono d2-preset${isActive ? " is-active" : ""}`}
              aria-pressed={isActive}
              onClick={() => onOpacityChange(preset)}
            >
              {Math.round(preset * 100)}%
            </button>
          );
        })}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "6px", paddingTop: "2px" }}>
        <LayerToggle
          id="toggle-contour-layer"
          label="Векторний контур плями"
          color="var(--accent-spill)"
          checked={showContour}
          onChange={onToggleContour}
        />
        <LayerToggle
          id="toggle-trajectory-layer"
          label="Траєкторія руху (дрейф)"
          color="var(--accent-drift)"
          dashed
          checked={showTrajectory}
          onChange={onToggleTrajectory}
        />
      </div>
    </div>
  );
}
