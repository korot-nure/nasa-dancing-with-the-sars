import { useRef } from "react";
import type { KeyboardEvent, PointerEvent } from "react";

export interface SplitCurtainControlProps {
  splitRatio: number; // 0.05 .. 0.95
  onSplitChange: (ratio: number) => void;
}

function clampRatio(value: number): number {
  return Math.min(0.95, Math.max(0.05, value));
}

/**
 * [Dev 1 — Lead] Інтерактивна вертикальна шторка порівняння "Звичайна карта ↔ SAR-накладення".
 */
export function SplitCurtainControl({ splitRatio, onSplitChange }: SplitCurtainControlProps) {
  const draggingRef = useRef(false);

  const updateFromClientX = (target: HTMLDivElement, clientX: number) => {
    const parentRect = target.parentElement?.getBoundingClientRect();
    if (!parentRect || parentRect.width <= 0) return;
    const nextRatio = (clientX - parentRect.left) / parentRect.width;
    onSplitChange(clampRatio(nextRatio));
  };

  const handlePointerDown = (e: PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    draggingRef.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    updateFromClientX(e.currentTarget, e.clientX);
  };

  const handlePointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return;
    e.stopPropagation();
    updateFromClientX(e.currentTarget, e.clientX);
  };

  const handlePointerEnd = (e: PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      onSplitChange(clampRatio(splitRatio - 0.04));
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      onSplitChange(clampRatio(splitRatio + 0.04));
    } else if (e.key === "Home") {
      e.preventDefault();
      onSplitChange(0.1);
    } else if (e.key === "End") {
      e.preventDefault();
      onSplitChange(0.9);
    }
  };

  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label="Шторка порівняння Звичайна карта та SAR Радар"
      aria-valuemin={5}
      aria-valuemax={95}
      aria-valuenow={Math.round(splitRatio * 100)}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerEnd}
      onPointerCancel={handlePointerEnd}
      onKeyDown={handleKeyDown}
      style={{
        position: "absolute",
        top: 0,
        bottom: 0,
        left: `${(splitRatio * 100).toFixed(2)}%`,
        width: 24,
        transform: "translateX(-50%)",
        zIndex: 450,
        cursor: "ew-resize",
        touchAction: "none",
        display: "flex",
        justifyContent: "center",
        userSelect: "none"
      }}
    >
      <div
        style={{
          width: 2,
          height: "100%",
          background: "#e4e4e7",
          pointerEvents: "none"
        }}
      />

      <div
        title="Перетягніть ліворуч/праворуч (або клавіші ← →)"
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: 28,
          height: 28,
          borderRadius: 4,
          border: "1px solid var(--border-strong)",
          background: "var(--bg-panel)",
          color: "var(--text-primary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none"
        }}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M5 5L2 8L5 11M11 5L14 8L11 11M8 2.5V13.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}
