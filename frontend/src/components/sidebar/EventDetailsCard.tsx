import type { LocationDetail } from "../../types/location";

export interface EventDetailsCardProps {
  detail: LocationDetail | null;
  activeStepIdx: number; // -1 = T0 ("До аварії"), 0..N-1 = індекс у snapshots[]
  loading?: boolean;
}

/**
 * TODO (Dev 2 — UI):
 * Картка телеметрії та опису вибраного розливу нафти (ліва панель).
 *
 * Зараз тут робочий Stage 0 шаблон із використанням сітки `.kv-grid` з src/index.css.
 * Твоє завдання на Stage 1:
 * 1. Коли `loading === true`, показати охайний стан завантаження (без стрибків висоти панелі).
 * 2. Для поточного кроку (`activeStepIdx === -1` -> базовий стан T0 "До аварії";
 *    `activeStepIdx >= 0` -> знімок `detail.snapshots[activeStepIdx]`) вивести:
 *    - Крок та дату зйомки (`T0`, `T1 (Старт)`, `+N дн.`)
 *    - Площу плями в км² і зміну `Δ км²` відносно попереднього знімка (`.kv-delta.is-up` / `.is-down`)
 *    - Координати `[lat, lon]` у моноширинному форматі (`.mono`)
 * 3. Нижче сітки показати `detail.description` і, якщо є `detail.source_url`, кнопку/посилання "Джерело".
 * 4. Не змінюй `EventDetailsCardProps` і назву експорту `EventDetailsCard`.
 */
export function EventDetailsCard({
  detail,
  activeStepIdx,
  loading = false,
}: EventDetailsCardProps) {
  if (loading && !detail) {
    return (
      <div className="panel-placeholder">
        Завантаження деталей події...
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="panel-placeholder">
        Оберіть подію зі списку або на оглядовій карті.
      </div>
    );
  }

  const isBaseline = activeStepIdx < 0;
  const activeSnap =
    !isBaseline && activeStepIdx < detail.snapshots.length
      ? detail.snapshots[activeStepIdx]
      : null;

  const prevSnap =
    !isBaseline && activeStepIdx > 0
      ? detail.snapshots[activeStepIdx - 1]
      : null;

  const displayDate = activeSnap ? activeSnap.date : detail.baseline_date;
  const displayLabel = activeSnap ? activeSnap.label : "До аварії (T0)";
  const areaKm2 = activeSnap ? activeSnap.area_km2 : 0;

  let deltaText = "Базовий фон";
  let deltaClass = "kv-delta is-neutral";

  if (activeSnap) {
    if (prevSnap) {
      const diff = activeSnap.area_km2 - prevSnap.area_km2;
      const sign = diff > 0 ? "+" : "";
      deltaText = `${sign}${diff.toFixed(1)} км² до поперед.`;
      deltaClass =
        diff > 0.05
          ? "kv-delta is-up"
          : diff < -0.05
            ? "kv-delta is-down"
            : "kv-delta is-neutral";
    } else {
      deltaText = "Початкова фіксація";
      deltaClass = "kv-delta is-up";
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div className="section-head">
        <span className="section-title">Телеметрія знімка</span>
        {loading && (
          <span className="mono" style={{ fontSize: "10px", color: "var(--text-muted)" }}>
            ОНОВЛЕННЯ
          </span>
        )}
      </div>

      <div className="kv-grid">
        <div className="kv-cell">
          <div className="kv-label">Етап</div>
          <div className="kv-val">{displayLabel}</div>
          <div className="kv-sub mono">{displayDate}</div>
        </div>

        <div className="kv-cell">
          <div className="kv-label">Площа плями</div>
          <div className="kv-val mono">{areaKm2.toFixed(1)} км²</div>
          <div className={`kv-sub mono ${deltaClass}`}>{deltaText}</div>
        </div>

        <div className="kv-cell">
          <div className="kv-label">Координати</div>
          <div className="kv-val mono">
            {detail.coords[0].toFixed(3)}, {detail.coords[1].toFixed(3)}
          </div>
          <div className="kv-sub">WGS-84</div>
        </div>

        <div className="kv-cell">
          <div className="kv-label">Серія SAR</div>
          <div className="kv-val mono">{detail.snapshots.length} знімки</div>
          <div className="kv-sub">База + дрейф</div>
        </div>
      </div>

      <div
        style={{
          padding: "10px 12px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: "12px",
            color: "var(--text-secondary)",
            lineHeight: 1.5,
          }}
        >
          {detail.description}
        </p>

        {detail.source_url && (
          <div>
            <a
              href={detail.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn"
            >
              Джерело звіту
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
