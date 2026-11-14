import type { LocationSummary } from "../../types/location";

export interface EventSelectProps {
  locations: LocationSummary[];
  activeLocationId: string | null;
  onSelectLocation: (id: string) => void;
}

/**
 * TODO (Dev 2 — UI):
 * Компонент вибору інциденту розливу нафти (ліва панель).
 *
 * Зараз тут базовий робочий прототип (Stage 0), щоб застосунок запускався і працював.
 * Твоє завдання на Stage 1:
 * 1. Оформити випадаючий список у темному інженерному стилі (див. mockup/index.html та CSS-токени в src/index.css).
 * 2. Відобразити для кожного варіанту назву події та поточну площу у км² (табулярні цифри `.mono`).
 * 3. Передбачити акуратний стан, якщо список `locations` ще порожній (disabled + текст очікування).
 * 4. Не змінюй `EventSelectProps` і назву експорту `EventSelect`.
 */
export function EventSelect({
  locations,
  activeLocationId,
  onSelectLocation,
}: EventSelectProps) {
  return (
    <div
      style={{
        padding: "10px 12px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        gap: "6px",
      }}
    >
      <label htmlFor="event-select-input" className="section-title">
        Активна подія ({locations.length})
      </label>

      <select
        id="event-select-input"
        value={activeLocationId ?? ""}
        disabled={locations.length === 0}
        onChange={(e) => onSelectLocation(e.target.value)}
        style={{
          width: "100%",
          height: "32px",
          padding: "0 8px",
          background: "var(--bg-surface)",
          color: "var(--text-primary)",
          border: "1px solid var(--border)",
          borderRadius: "4px",
          fontSize: "12px",
          cursor: locations.length === 0 ? "not-allowed" : "pointer",
        }}
      >
        {locations.length === 0 ? (
          <option value="">Завантаження списку подій...</option>
        ) : (
          locations.map((loc) => (
            <option key={loc.id} value={loc.id}>
              {loc.title} ({loc.area_km2.toFixed(1)} км²)
            </option>
          ))
        )}
      </select>
    </div>
  );
}
