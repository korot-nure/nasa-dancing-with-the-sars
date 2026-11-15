import type { LocationSummary } from "../../types/location";

export interface EventSelectProps {
  locations: LocationSummary[];
  activeLocationId: string | null;
  onSelectLocation: (id: string) => void;
}

const SELECT_ID = "event-select-input";
const META_ID = "event-select-meta";

/** Локальні стилі компонента (hover / disabled), без змін у глобальному index.css. */
const scopedCss = `
.d2-event-select {
  width: 100%;
  height: 32px;
  padding: 0 30px 0 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 500;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
  text-overflow: ellipsis;
  transition: background-color 0.12s ease, border-color 0.12s ease;
}
.d2-event-select:hover:not(:disabled) {
  border-color: var(--border-strong);
  background: var(--bg-hover);
}
.d2-event-select:disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}
.d2-event-select option {
  background: var(--bg-surface);
  color: var(--text-primary);
}
`;

/**
 * Вибір активного інциденту розливу нафти (ліва панель).
 * Нативний <select> — повна підтримка клавіатури та екранних читачів.
 */
export function EventSelect({
  locations,
  activeLocationId,
  onSelectLocation,
}: EventSelectProps) {
  const isEmpty = locations.length === 0;
  const activeLoc = locations.find((loc) => loc.id === activeLocationId) ?? null;

  return (
    <div
      style={{
        padding: "10px 12px",
        borderBottom: "1px solid var(--border)",
        background: "var(--bg-panel)",
        display: "flex",
        flexDirection: "column",
        gap: "6px",
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
        <label htmlFor={SELECT_ID} className="section-title">
          Активна подія
        </label>
        <span
          className="mono"
          style={{ fontSize: "10px", color: "var(--text-muted)" }}
          aria-label={`Доступно подій: ${locations.length}`}
        >
          {locations.length}
        </span>
      </div>

      <div style={{ position: "relative" }}>
        <select
          id={SELECT_ID}
          className="d2-event-select"
          value={activeLocationId ?? ""}
          disabled={isEmpty}
          aria-describedby={activeLoc ? META_ID : undefined}
          onChange={(e) => onSelectLocation(e.target.value)}
        >
          {isEmpty ? (
            <option value="">Завантаження подій...</option>
          ) : (
            <>
              {activeLocationId === null && (
                <option value="" disabled>
                  Оберіть подію
                </option>
              )}
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.title} · {loc.area_km2.toFixed(1)} км² · {loc.latest_date}
                </option>
              ))}
            </>
          )}
        </select>
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
          style={{
            position: "absolute",
            right: "10px",
            top: "50%",
            transform: "translateY(-50%)",
            pointerEvents: "none",
            color: isEmpty ? "var(--text-muted)" : "var(--text-secondary)",
          }}
        >
          <path
            d="M4 6L8 10L12 6"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {activeLoc && (
        <div
          id={META_ID}
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "8px",
            fontSize: "11px",
            color: "var(--text-secondary)",
          }}
        >
          <span>
            Площа: <span className="mono">{activeLoc.area_km2.toFixed(1)} км²</span>
          </span>
          <span>
            Останній знімок: <span className="mono">{activeLoc.latest_date}</span>
          </span>
        </div>
      )}
    </div>
  );
}
