import type { LocationDetail } from "../../types/location";
import { formatLatLon } from "../../utils/format";
import {
  formatArea,
  formatSnapshotsCount,
  localizeDescription,
  localizeSnapshotLabel,
  localizeSnapshotNote,
  localizeTitle,
  useI18n,
} from "../../i18n";

export interface EventDetailsCardProps {
  detail: LocationDetail | null;
  activeStepIdx: number; // -1 = T0 ("Pre-event"), 0..N-1 = index into snapshots[]
  loading?: boolean;
}

const MS_PER_DAY = 86_400_000;

/** Difference in days between two YYYY-MM-DD dates (in UTC, no time zone offsets). */
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

const scopedCss = `
.d2-card { min-width: 0; }
.d2-card .section-head {
  position: sticky;
  top: 0;
  z-index: 1;
}
.d2-card .kv-cell { min-width: 0; }
.d2-card .kv-val,
.d2-card .kv-sub { overflow-wrap: anywhere; }
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

function SkeletonCard({ lang }: { lang: "en" | "uk" }) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      style={{ display: "flex", flexDirection: "column", borderBottom: "1px solid var(--border)" }}
    >
      <div className="section-head">
        <span className="section-title">
          {lang === "uk" ? "Телеметрія знімка" : "Scene Telemetry"}
        </span>
        <span className="mono" style={{ fontSize: "10px", color: "var(--text-muted)" }}>
          {lang === "uk" ? "ЗАВАНТАЖЕННЯ" : "LOADING"}
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
        {lang === "uk" ? "Завантаження деталей події..." : "Loading event details..."}
      </span>
    </div>
  );
}

/**
 * Telemetry and description card for the selected oil spill (left panel).
 * Driven purely by input props, with no fetch and no Leaflet.
 */
export function EventDetailsCard({
  detail,
  activeStepIdx,
  loading = false,
}: EventDetailsCardProps) {
  const { lang } = useI18n();

  if (loading && !detail) {
    return (
      <>
        <style>{scopedCss}</style>
        <SkeletonCard lang={lang} />
      </>
    );
  }

  if (!detail) {
    return (
      <div className="panel-placeholder">
        {lang === "uk"
          ? "Оберіть подію зі списку або на оглядовій карті."
          : "Select an event from the list or the overview map."}
      </div>
    );
  }

  const snapshots = detail.snapshots;
  const firstSnap = snapshots.length > 0 ? snapshots[0] : null;
  const activeSnap =
    activeStepIdx >= 0 && activeStepIdx < snapshots.length ? snapshots[activeStepIdx] : null;
  const prevSnap = activeSnap && activeStepIdx > 0 ? snapshots[activeStepIdx - 1] : null;

  // --- Stage and date ---
  const stageBadge = activeSnap ? `T${activeStepIdx + 1}` : "T0";
  const stageLabel = activeSnap
    ? localizeSnapshotLabel(activeSnap.label, lang)
    : lang === "uk"
      ? "T0 · До аварії (база)"
      : "T0 · Pre-event (baseline)";
  const stageDate = (activeSnap ? activeSnap.date : detail.baseline_date) || "—";

  let offsetText = lang === "uk" ? "До початку інциденту" : "Before incident";
  if (activeSnap && firstSnap) {
    const days = daysBetween(firstSnap.date, activeSnap.date);
    if (activeStepIdx === 0) {
      offsetText = lang === "uk" ? "+0 дн. (Старт)" : "+0 d (Start)";
    } else if (days !== null) {
      offsetText =
        lang === "uk"
          ? `${days >= 0 ? "+" : ""}${days} дн. від T1`
          : `${days >= 0 ? "+" : ""}${days} d from T1`;
    } else {
      offsetText = `${lang === "uk" ? "Старт" : "Start"} T1: ${firstSnap.date}`;
    }
  }

  // --- Area and delta ---
  const areaKm2 = activeSnap ? activeSnap.area_km2 : 0;
  let deltaValue = lang === "uk" ? "Базовий фон" : "Baseline";
  let deltaCaption = "";
  let deltaClass = "is-neutral";

  if (activeSnap) {
    if (prevSnap) {
      const diff = activeSnap.area_km2 - prevSnap.area_km2;
      if (Math.abs(diff) < 0.05) {
        deltaValue = lang === "uk" ? "без змін" : "no change";
        deltaClass = "is-neutral";
      } else {
        deltaValue = `${diff > 0 ? "+" : "-"}${formatArea(Math.abs(diff), lang)}`;
        deltaCaption = lang === "uk" ? "від попереднього" : "vs previous";
        deltaClass = diff > 0 ? "is-up" : "is-down";
      }
    } else {
      deltaValue = lang === "uk" ? "Початкова фіксація" : "Initial detection";
      deltaClass = "is-up";
    }
  }

  const snapCount = snapshots.length;
  const stageBadgeText = snapCount > 0 ? `${stageBadge} / T${snapCount}` : "T0";
  const trackPolText = activeSnap
    ? `${activeSnap.track} · ${activeSnap.polarization}`
    : firstSnap
      ? `${firstSnap.track} · ${firstSnap.polarization}`
      : "—";
  const pairBeforeDate = (activeSnap ? activeSnap.before_date : detail.baseline_date) || "—";
  const activeNote = localizeSnapshotNote(activeSnap?.note?.trim() ?? "", lang);
  const description = localizeDescription(detail.id, detail.description?.trim() ?? "", lang);
  const localizedTitle = localizeTitle(detail.id, detail.title, lang);
  const sourceUrl = detail.source_url?.trim() ?? "";

  return (
    <div
      className="d2-card"
      style={{
        display: "flex",
        flexDirection: "column",
        borderBottom: "1px solid var(--border)",
      }}
      aria-busy={loading}
    >
      <style>{scopedCss}</style>

      <div className="section-head">
        <span className="section-title">
          {lang === "uk" ? "Телеметрія знімка" : "Scene Telemetry"}
        </span>
        {loading && (
          <span
            className="mono"
            style={{ fontSize: "10px", color: "var(--text-muted)" }}
            aria-live="polite"
          >
            {lang === "uk" ? "ОНОВЛЕННЯ" : "UPDATING"}
          </span>
        )}
      </div>

      {/* Incident title + current snapshot badge */}
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
          <span style={{ overflowWrap: "anywhere" }}>{localizedTitle}</span>
        </h2>
        <span
          className="mono"
          title={
            activeSnap
              ? lang === "uk"
                ? "Поточний знімок"
                : "Current snapshot"
              : lang === "uk"
                ? "Базовий знімок до аварії"
                : "Pre-event baseline"
          }
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
          {stageBadgeText}
        </span>
      </div>

      <div className="kv-grid">
        <div className="kv-cell">
          <div className="kv-label">{lang === "uk" ? "Етап і дата" : "Stage & Date"}</div>
          <div className="kv-val" style={{ fontSize: "12px" }}>{stageLabel}</div>
          <div className="kv-sub mono">{stageDate}</div>
          <div className="kv-sub mono">{offsetText}</div>
        </div>

        <div className="kv-cell">
          <div className="kv-label">{lang === "uk" ? "Площа розливу" : "Spill Area"}</div>
          <div className="kv-val mono">{formatArea(areaKm2, lang)}</div>
          <div className={`kv-sub mono kv-delta ${deltaClass}`}>{deltaValue}</div>
          {deltaCaption && <div className="kv-sub">{deltaCaption}</div>}
        </div>

        <div className="kv-cell">
          <div className="kv-label">{lang === "uk" ? "Координати центру" : "Center Coords"}</div>
          <div className="kv-val mono" style={{ fontSize: "12px" }}>
            {formatLatLon(detail.coords)}
          </div>
          <div className="kv-sub mono">WGS-84</div>
        </div>

        <div className="kv-cell">
          <div className="kv-label">{lang === "uk" ? "Трек і серія" : "Track & Series"}</div>
          <div className="kv-val mono" style={{ fontSize: "12px" }}>{trackPolText}</div>
          <div className="kv-sub">
            {lang === "uk" ? "Пара «До»:" : "Before pair:"}{" "}
            <span className="mono">{pairBeforeDate}</span>
          </div>
          <div className="kv-sub">
            {lang === "uk" ? "Серія:" : "Series:"} <span className="mono">{formatSnapshotsCount(snapCount, lang)}</span>
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
        {activeNote && (
          <div
            role="note"
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
              padding: "7px 9px",
              border: "1px solid var(--border-strong)",
              borderLeft: "2px solid #fbbf24",
              borderRadius: "4px",
              background: "var(--bg-surface)",
              fontSize: "11px",
              lineHeight: 1.4,
              color: "var(--text-primary)",
            }}
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
              style={{ flexShrink: 0, marginTop: "1px", color: "#fbbf24" }}
            >
              <path
                d="M8 2L14.5 13.5H1.5L8 2Z"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinejoin="round"
              />
              <path d="M8 6.5V9.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              <circle cx="8" cy="11.5" r="0.7" fill="currentColor" />
            </svg>
            <span>{activeNote}</span>
          </div>
        )}

        {description && (
          <p
            style={{
              margin: 0,
              fontSize: "12px",
              color: "var(--text-secondary)",
              lineHeight: 1.5,
            }}
          >
            {description}
          </p>
        )}

        {sourceUrl && (
          <div>
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn"
            >
              {lang === "uk" ? "Джерело звіту" : "Incident Report"}
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
            {lang === "uk" ? "Чому це бачить саме SAR?" : "Why does SAR see this?"}
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
            {lang === "uk"
              ? "Нафтова плівка гасить дрібні капілярні хвилі на воді, і поверхня відбиває радарний сигнал дзеркально — убік від антени. Тому SAR фіксує пляму як темну зону падіння сигналу вдень, уночі та навіть крізь щільні хмари."
              : "Oil films dampen sea-surface capillary waves, causing specular reflection of the radar pulse away from the sensor. As a result, SAR detects slicks as sharp dark backscatter anomalies day or night—even through thick clouds."}
          </p>
        </details>
      </div>
    </div>
  );
}
