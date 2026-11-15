import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import type { LocationDetail } from "../../types/location";

export interface SnapshotTimelineProps {
  detail: LocationDetail | null;
  activeStepIdx: number; // -1 = T0 ("До аварії"), 0..N-1 = індекс у snapshots[]
  isPlaying: boolean;
  onSelectStep: (idx: number) => void;
  onTogglePlay: () => void;
}

function diffDaysFromIso(startIso: string, endIso: string): number {
  const startMs = Date.parse(`${startIso}T00:00:00Z`);
  const endMs = Date.parse(`${endIso}T00:00:00Z`);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return 0;
  return Math.max(0, Math.round((endMs - startMs) / 86_400_000));
}

/**
 * [Dev 1 — Lead] Нижній таймлайн знімків (T0 + T1..Tn) із автопрограванням та навігацією ← / →.
 */
export function SnapshotTimeline({
  detail,
  activeStepIdx,
  isPlaying,
  onSelectStep,
  onTogglePlay
}: SnapshotTimelineProps) {
  const activeBtnRef = useRef<HTMLButtonElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const dragStateRef = useRef<{
    active: boolean;
    startX: number;
    startScrollLeft: number;
    moved: boolean;
    pointerId: number | null;
  }>({
    active: false,
    startX: 0,
    startScrollLeft: 0,
    moved: false,
    pointerId: null
  });
  const suppressClickRef = useRef(false);
  const [isDragging, setIsDragging] = useState(false);

  const handlePointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.pointerType === "touch" || e.button !== 0) return;
    const el = scrollContainerRef.current;
    if (!el) return;

    dragStateRef.current = {
      active: true,
      startX: e.clientX,
      startScrollLeft: el.scrollLeft,
      moved: false,
      pointerId: e.pointerId
    };
    suppressClickRef.current = false;
  };

  const handlePointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragStateRef.current;
    const el = scrollContainerRef.current;
    if (!drag.active || !el) return;

    const dx = e.clientX - drag.startX;
    if (!drag.moved && Math.abs(dx) > 4) {
      drag.moved = true;
      suppressClickRef.current = true;
      setIsDragging(true);
      if (drag.pointerId !== null && !el.hasPointerCapture(drag.pointerId)) {
        el.setPointerCapture(drag.pointerId);
      }
    }

    if (drag.moved) {
      el.scrollLeft = drag.startScrollLeft - dx;
    }
  };

  const endDrag = (e: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragStateRef.current;
    const el = scrollContainerRef.current;
    if (!drag.active) return;

    if (el && drag.pointerId !== null && el.hasPointerCapture(drag.pointerId)) {
      el.releasePointerCapture(drag.pointerId);
    }
    dragStateRef.current.active = false;
    dragStateRef.current.pointerId = null;
    setIsDragging(false);

    if (drag.moved) {
      // Запобігаємо випадковому кліку по картці одразу після перетягування
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
    }
    void e;
  };

  const handleClickCapture = (e: React.MouseEvent<HTMLDivElement>) => {
    if (suppressClickRef.current) {
      e.preventDefault();
      e.stopPropagation();
      suppressClickRef.current = false;
    }
  };

  const handleWheel = (e: ReactWheelEvent<HTMLDivElement>) => {
    const el = scrollContainerRef.current;
    if (!el) return;
    if (e.deltaY !== 0 && Math.abs(e.deltaX) < Math.abs(e.deltaY)) {
      el.scrollLeft += e.deltaY;
    }
  };

  useEffect(() => {
    activeBtnRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "nearest"
    });
  }, [activeStepIdx, detail?.id]);

  useEffect(() => {
    if (!detail) return;
    const maxStep = detail.snapshots.length - 1;

    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (target?.getAttribute("role") === "slider") return;

      if (e.key === "ArrowLeft" && activeStepIdx > -1) {
        e.preventDefault();
        onSelectStep(activeStepIdx - 1);
      } else if (e.key === "ArrowRight" && activeStepIdx < maxStep) {
        e.preventDefault();
        onSelectStep(activeStepIdx + 1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [detail, activeStepIdx, onSelectStep]);

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

  const totalSteps = detail.snapshots.length + 1;
  const currentStepNumber = activeStepIdx < 0 ? 1 : activeStepIdx + 2;
  const t1Date = detail.snapshots[0]?.date ?? detail.baseline_date;

  return (
    <div
      style={{
        height: 82,
        padding: "0 14px",
        display: "flex",
        alignItems: "center",
        gap: 14,
        borderTop: "1px solid var(--border)",
        background: "var(--bg-panel)",
        flexShrink: 0
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
          flexShrink: 0,
          width: 205
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="section-title">Таймлайн дрейфу</span>
          <span className="mono" style={{ fontSize: 11, color: "var(--text-secondary)" }}>
            {currentStepNumber} / {totalSteps}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button
            type="button"
            className="btn"
            aria-label="Попередній знімок"
            title="Попередній знімок (←)"
            disabled={activeStepIdx <= -1}
            onClick={() => onSelectStep(activeStepIdx - 1)}
            style={{ width: 28, height: 24, padding: 0 }}
          >
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M10 3L5 8L10 13"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          <button
            type="button"
            className="btn mono"
            onClick={onTogglePlay}
            title="Автопрогравання динаміки (T0 → Tn)"
            style={{
              flex: 1,
              height: 24,
              borderColor: isPlaying ? "var(--accent-signal)" : "var(--border)",
              background: isPlaying ? "var(--bg-hover)" : "var(--bg-surface)",
              color: isPlaying ? "var(--accent-signal)" : "var(--text-primary)"
            }}
          >
            {isPlaying ? (
              <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <rect x="4" y="3" width="3" height="10" />
                <rect x="9" y="3" width="3" height="10" />
              </svg>
            ) : (
              <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M4 3L13 8L4 13V3Z" />
              </svg>
            )}
            <span>{isPlaying ? "Пауза" : "Старт"}</span>
          </button>

          <button
            type="button"
            className="btn"
            aria-label="Наступний знімок"
            title="Наступний знімок (→)"
            disabled={activeStepIdx >= detail.snapshots.length - 1}
            onClick={() => onSelectStep(activeStepIdx + 1)}
            style={{ width: 28, height: 24, padding: 0 }}
          >
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M6 3L11 8L6 13"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>

      <div
        ref={scrollContainerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onClickCapture={handleClickCapture}
        onWheel={handleWheel}
        style={{
          display: "flex",
          gap: 8,
          flex: 1,
          overflowX: "auto",
          minWidth: 0,
          cursor: isDragging ? "grabbing" : "grab",
          userSelect: "none"
        }}
      >
        {/* T0: База до аварії */}
        <button
          ref={activeStepIdx === -1 ? activeBtnRef : undefined}
          type="button"
          className="btn"
          onClick={() => onSelectStep(-1)}
          style={{
            height: 52,
            flex: "1 1 0",
            minWidth: 155,
            padding: "6px 10px",
            flexDirection: "column",
            alignItems: "flex-start",
            justifyContent: "center",
            gap: 2,
            borderColor: activeStepIdx === -1 ? "var(--text-primary)" : "var(--border)",
            background: activeStepIdx === -1 ? "var(--bg-hover)" : "var(--bg-surface)"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
            <span className="mono" style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 600 }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: activeStepIdx === -1 ? "var(--accent-signal)" : "var(--text-muted)"
                }}
              />
              T0 · {detail.baseline_date}
            </span>
            <span className="mono" style={{ fontSize: 11, color: "var(--text-secondary)" }}>
              0.0 км²
            </span>
          </div>
          <span
            style={{
              fontSize: 11,
              color: activeStepIdx === -1 ? "var(--text-secondary)" : "var(--text-muted)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              maxWidth: "100%"
            }}
          >
            База (до аварії)
          </span>
        </button>

        {/* T1..Tn: Кроки дрейфу */}
        {detail.snapshots.map((snap, idx) => {
          const isActive = idx === activeStepIdx;
          const isPassed = activeStepIdx > idx;
          const daysOffset = diffDaysFromIso(t1Date, snap.date);
          const stepTag = idx === 0 ? "Старт" : `+${daysOffset} дн.`;

          const dotColor = isActive
            ? "var(--accent-spill)"
            : isPassed
              ? "var(--accent-drift)"
              : "var(--text-muted)";

          return (
            <button
              ref={isActive ? activeBtnRef : undefined}
              key={snap.step_id}
              type="button"
              className="btn"
              title={snap.note ?? undefined}
              onClick={() => onSelectStep(idx)}
              style={{
                height: 52,
                flex: "1 1 0",
                minWidth: 210,
                padding: "6px 10px",
                flexDirection: "column",
                alignItems: "flex-start",
                justifyContent: "center",
                gap: 2,
                borderColor: isActive ? "var(--text-primary)" : "var(--border)",
                background: isActive ? "var(--bg-hover)" : "var(--bg-surface)"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", gap: 6 }}>
                <span className="mono" style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor }} />
                  {snap.step_id.toUpperCase()} · {snap.date}
                </span>
                <span
                  className="mono"
                  style={{
                    fontSize: 11,
                    whiteSpace: "nowrap",
                    color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                    fontWeight: isActive ? 600 : 400
                  }}
                >
                  {snap.area_km2.toFixed(1)} км²
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  width: "100%",
                  gap: 6,
                  fontSize: 11,
                  color: isActive ? "var(--text-secondary)" : "var(--text-muted)"
                }}
              >
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4, minWidth: 0 }}>
                  {snap.note && (
                    <svg
                      width="11"
                      height="11"
                      viewBox="0 0 16 16"
                      fill="none"
                      aria-label={snap.note}
                      style={{ flexShrink: 0, color: "#fbbf24" }}
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
                  )}
                  <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {snap.label}
                  </span>
                </span>
                <span
                  className="mono"
                  style={{ fontSize: 10, flexShrink: 0, color: isActive ? "var(--accent-drift)" : "var(--text-muted)" }}
                >
                  {snap.track} · {snap.polarization} · {stepTag}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
