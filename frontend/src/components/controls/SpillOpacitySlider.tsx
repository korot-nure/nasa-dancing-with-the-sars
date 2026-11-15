import { useI18n } from "../../i18n";

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
  flex: 1;
  min-width: 0;
  height: 4px;
  margin: 0;
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
  min-width: 40px;
  height: 22px;
  padding: 0 6px;
  font-size: 10px;
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
  min-width: 0;
  height: 24px;
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
      <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {label}
      </span>
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
  const { lang } = useI18n();
  const opacityPercent = Math.round(spillOpacity * 100);

  return (
    <div
      style={{
        padding: "8px 12px",
        display: "flex",
        flexDirection: "column",
        gap: "7px",
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
          {lang === "uk" ? "Прозорість маски розливу" : "Spill Mask Opacity"}
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

      <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
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

        <div
          role="group"
          aria-label={lang === "uk" ? "Швидкі значення прозорості" : "Quick opacity presets"}
          style={{ display: "flex", gap: "4px", flexShrink: 0 }}
        >
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
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <LayerToggle
          id="toggle-contour-layer"
          label={lang === "uk" ? "Векторний контур плями" : "Vector Slick Contour"}
          color="var(--accent-spill)"
          checked={showContour}
          onChange={onToggleContour}
        />
        <LayerToggle
          id="toggle-trajectory-layer"
          label={lang === "uk" ? "Траєкторія руху (дрейф)" : "Drift Trajectory"}
          color="var(--accent-drift)"
          dashed
          checked={showTrajectory}
          onChange={onToggleTrajectory}
        />
      </div>
    </div>
  );
}
