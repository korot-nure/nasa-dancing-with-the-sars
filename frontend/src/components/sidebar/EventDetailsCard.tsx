import type { LocationDetail } from "../../types/location";

export interface EventDetailsCardProps {
  detail: LocationDetail | null;
  activeStepIdx: number; // -1 = T0 ("До аварії"), 0..N-1 = індекс у snapshots[]
  loading?: boolean;
}

const MS_PER_DAY = 86_400_000;

/** Різниця в днях між двома датами YYYY-MM-DD (в UTC, без зсувів часового поясу). */
function daysBetween(fromIso: string, toIso: string): number | null {
  const parse = (iso: string): number | null => {
    const [y, m, d] = iso.split("-").map(Number);
    if (!y || !m || !d) return null;
    return Date.UTC(y, m - 1, d);
  };
  const from = parse(fromIso);
  const to = parse(toIso);
  if (from === null || to === null) return null;
  return Math.round((to - from) / MS_PER_DAY);
}

/** coords у форматі [lon, lat] -> "17.50°N, 56.02°E" (спочатку широта). */
function formatLatLon(coords: [number, number]): string {
  const [lon, lat] = coords;
  const latStr = `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? "N" : "S"}`;
  const lonStr = `${Math.abs(lon).toFixed(2)}°${lon >= 0 ? "E" : "W"}`;
  return `${latStr}, ${lonStr}`;
}

/** Українська множина: 1 знімок, 2 знімки, 5 знімків. */
function pluralSnapshots(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "знімок";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "знімки";
  return "знімків";
}

const scopedCss = `
.d2-skel {
  display: block;
  height: 10px;
  border-radius: 2px;
  background: var(--bg-surface);
  animation: d2-skel-pulse 1.4s ease-in-out infinite;
}
@keyframes d2-skel-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
@media (prefers-reduced-motion: reduce) {
  .d2-skel { animation: none; }
}
.d2-sar-hint {
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-surface);
}
.d2-sar-hint > summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.d2-sar-hint > summary::-webkit-details-marker { display: none; }
.d2-sar-hint > summary:hover { color: var(--text-primary); }
.d2-sar-hint > summary:focus-visible {
  outline: 2px solid var(--accent-signal);
  outline-offset: 1px;
  border-radius: 4px;
}
.d2-sar-hint .d2-chevron { transition: transform 0.12s ease; }
.d2-sar-hint[open] .d2-chevron { transform: rotate(90deg); }
`;

function SkeletonCard() {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      style={{ display: "flex", flexDirection: "column", borderBottom: "1px solid var(--border)" }}
    >
      <div className="section-head">
        <span className="section-title">Телеметрія знімка</span>
        <span className="mono" style={{ fontSize: "10px", color: "var(--text-muted)" }}>
          ЗАВАНТАЖЕННЯ
        </span>
      </div>
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border)" }}>
        <span className="d2-skel" style={{ width: "70%", height: "14px" }} />
      </div>
      <div className="kv-grid">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="kv-cell" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <span className="d2-skel" style={{ width: "50%", height: "8px" }} />
            <span className="d2-skel" style={{ width: "80%", height: "12px" }} />
            <span className="d2-skel" style={{ width: "60%", height: "8px" }} />
          </div>
        ))}
      </div>
      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: "6px" }}>
        <span className="d2-skel" style={{ width: "100%" }} />
        <span className="d2-skel" style={{ width: "92%" }} />
        <span className="d2-skel" style={{ width: "64%" }} />
      </div>
      <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
        Завантаження деталей події...
      </span>
    </div>
  );
}

/**
 * Картка телеметрії та опису вибраного розливу нафти (ліва панель).
 * Працює виключно від вхідних props, без fetch і Leaflet.
 */
export function EventDetailsCard({
  detail,
  activeStepIdx,
  loading = false,
}: EventDetailsCardProps) {
  if (loading && !detail) {
    return (
      <>
        <style>{scopedCss}</style>
        <SkeletonCard />
      </>
    );
  }

  if (!detail) {
    return (
      <div className="panel-placeholder">
        Оберіть подію зі списку або на оглядовій карті.
      </div>
    );
  }

  const snapshots = detail.snapshots;
  const firstSnap = snapshots.length > 0 ? snapshots[0] : null;
  const activeSnap =
    activeStepIdx >= 0 && activeStepIdx < snapshots.length ? snapshots[activeStepIdx] : null;
  const prevSnap = activeSnap && activeStepIdx > 0 ? snapshots[activeStepIdx - 1] : null;

  // --- Етап і дата ---
  const stageBadge = activeSnap ? `T${activeStepIdx + 1}` : "T0";
  const stageLabel = activeSnap ? activeSnap.label : "T0 · До аварії (база)";
  const stageDate = activeSnap ? activeSnap.date : detail.baseline_date;

  let offsetText = "До початку інциденту";
  if (activeSnap && firstSnap) {
    const days = daysBetween(firstSnap.date, activeSnap.date);
    if (activeStepIdx === 0) {
      offsetText = "+0 дн. (Старт)";
    } else if (days !== null) {
      offsetText = `${days >= 0 ? "+" : ""}${days} дн. від T1`;
    } else {
      offsetText = `Старт T1: ${firstSnap.date}`;
    }
  }

  // --- Площа і дельта ---
  const areaKm2 = activeSnap ? activeSnap.area_km2 : 0;
  let deltaValue = "Базовий фон";
  let deltaCaption = "";
  let deltaClass = "is-neutral";

  if (activeSnap) {
    if (prevSnap) {
      const diff = activeSnap.area_km2 - prevSnap.area_km2;
      if (Math.abs(diff) < 0.05) {
        deltaValue = "без змін";
        deltaClass = "is-neutral";
      } else {
        deltaValue = `${diff > 0 ? "+" : "-"}${Math.abs(diff).toFixed(1)} км²`;
        deltaCaption = "від попереднього";
        deltaClass = diff > 0 ? "is-up" : "is-down";
      }
    } else {
      deltaValue = "Початкова фіксація";
      deltaClass = "is-up";
    }
  }

  const snapCount = snapshots.length;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        borderBottom: "1px solid var(--border)",
      }}
      aria-busy={loading}
    >
      <style>{scopedCss}</style>

      <div className="section-head">
        <span className="section-title">Телеметрія знімка</span>
        {loading && (
          <span
            className="mono"
            style={{ fontSize: "10px", color: "var(--text-muted)" }}
            aria-live="polite"
          >
            ОНОВЛЕННЯ
          </span>
        )}
      </div>

      {/* Назва інциденту + бейдж поточного зрізу */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "8px",
          padding: "10px 12px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <h2
          style={{
            margin: 0,
            display: "flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "14px",
            fontWeight: 600,
            lineHeight: 1.3,
            color: "var(--text-primary)",
            minWidth: 0,
          }}
        >
          <span
            aria-hidden="true"
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "2px",
              background: "var(--accent-spill)",
              flexShrink: 0,
            }}
          />
          <span style={{ overflowWrap: "anywhere" }}>{detail.title}</span>
        </h2>
        <span
          className="mono"
          title={activeSnap ? "Поточний знімок" : "Базовий знімок до аварії"}
          style={{
            flexShrink: 0,
            height: "20px",
            display: "inline-flex",
            alignItems: "center",
            padding: "0 6px",
            border: "1px solid var(--border-strong)",
            borderRadius: "3px",
            background: "var(--bg-surface)",
            fontSize: "10px",
            fontWeight: 600,
            color: activeSnap ? "var(--text-primary)" : "var(--text-secondary)",
          }}
        >
          {stageBadge} / T{snapCount}
        </span>
      </div>

      <div className="kv-grid">
        <div className="kv-cell">
          <div className="kv-label">Етап і дата</div>
          <div className="kv-val" style={{ fontSize: "12px" }}>{stageLabel}</div>
          <div className="kv-sub mono">{stageDate}</div>
          <div className="kv-sub mono">{offsetText}</div>
        </div>

        <div className="kv-cell">
          <div className="kv-label">Площа розливу</div>
          <div className="kv-val mono">{areaKm2.toFixed(1)} км²</div>
          <div className={`kv-sub mono kv-delta ${deltaClass}`}>{deltaValue}</div>
          {deltaCaption && <div className="kv-sub">{deltaCaption}</div>}
        </div>

        <div className="kv-cell">
          <div className="kv-label">Координати центру</div>
          <div className="kv-val mono" style={{ fontSize: "12px" }}>
            {formatLatLon(detail.coords)}
          </div>
          <div className="kv-sub mono">WGS-84</div>
        </div>

        <div className="kv-cell">
          <div className="kv-label">Динаміка серії</div>
          <div className="kv-val">
            <span className="mono">{snapCount}</span> {pluralSnapshots(snapCount)}
          </div>
          <div className="kv-sub">
            Старт T1: <span className="mono">{firstSnap?.date ?? "—"}</span>
          </div>
        </div>
      </div>

      <div
        style={{
          padding: "10px 12px",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        {detail.description && (
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
        )}

        {detail.source_url && (
          <div>
            <a
              href={detail.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn"
            >
              Джерело звіту
              <svg width="11" height="11" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path
                  d="M6 3H3V13H13V10M9 3H13V7M13 3L7 9"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </a>
          </div>
        )}

        <details className="d2-sar-hint">
          <summary>
            <svg
              className="d2-chevron"
              width="10"
              height="10"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M6 4L10 8L6 12"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Чому це бачить саме SAR?
          </summary>
          <p
            style={{
              margin: 0,
              padding: "0 8px 8px 24px",
              fontSize: "11px",
              lineHeight: 1.5,
              color: "var(--text-secondary)",
            }}
          >
            Нафтова плівка гасить дрібні капілярні хвилі на воді, і поверхня відбиває
            радарний сигнал дзеркально — убік від антени. Тому SAR фіксує пляму як темну
            зону падіння сигналу вдень, уночі та навіть крізь щільні хмари.
          </p>
        </details>
      </div>
    </div>
  );
}
