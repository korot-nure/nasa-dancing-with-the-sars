import { useEffect, useState } from "react";
import { fetchLocationDetail, fetchLocations } from "./api/locationsApi";
import { SpillOpacitySlider } from "./components/controls/SpillOpacitySlider";
import { EventDetailsCard } from "./components/sidebar/EventDetailsCard";
import { EventSelect } from "./components/sidebar/EventSelect";
import { OverviewMinimap } from "./components/sidebar/OverviewMinimap";
import { MainComparisonMap } from "./components/stage/MainComparisonMap";
import { SnapshotTimeline } from "./components/timeline/SnapshotTimeline";
import type { AppState } from "./types/location";
import { formatEventsCount, useI18n } from "./i18n";

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

export function App() {
  const { lang, setLang } = useI18n();
  const [state, setState] = useState<AppState>({
    locations: [],
    activeLocationId: null,
    activeDetail: null,
    activeStepIdx: 0,
    spillOpacity: 0.65,
    showContour: true,
    showTrajectory: true,
    isPlaying: false,
    splitRatio: 0.5,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function loadList() {
      try {
        const locations = await fetchLocations();
        if (cancelled) return;

        setState((prev) => ({
          ...prev,
          locations,
          activeLocationId:
            prev.activeLocationId ?? (locations.length > 0 ? locations[0].id : null),
          loading: locations.length > 0,
          error: null,
        }));
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "Не вдалося завантажити список подій";
        setState((prev) => ({ ...prev, loading: false, error: message }));
      }
    }

    loadList();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const locationId = state.activeLocationId;
    if (!locationId) return;

    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true, error: null, isPlaying: false }));

    async function loadDetail(id: string) {
      try {
        const detail = await fetchLocationDetail(id);
        if (cancelled) return;

        setState((prev) => ({
          ...prev,
          activeDetail: detail,
          activeStepIdx: detail.snapshots.length > 0 ? detail.snapshots.length - 1 : -1,
          loading: false,
          error: null,
        }));
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "Не вдалося завантажити деталі події";
        setState((prev) => ({ ...prev, loading: false, error: message }));
      }
    }

    loadDetail(locationId);
    return () => {
      cancelled = true;
    };
  }, [state.activeLocationId]);

  useEffect(() => {
    if (!state.isPlaying || !state.activeDetail) return;
    const totalSnapshots = state.activeDetail.snapshots.length;
    if (totalSnapshots === 0) return;

    const timer = window.setInterval(() => {
      setState((prev) => {
        if (!prev.activeDetail || prev.activeDetail.snapshots.length === 0) {
          return { ...prev, isPlaying: false };
        }
        const maxIdx = prev.activeDetail.snapshots.length - 1;
        const nextIdx = prev.activeStepIdx >= maxIdx ? -1 : prev.activeStepIdx + 1;
        return { ...prev, activeStepIdx: nextIdx };
      });
    }, 1400);

    return () => window.clearInterval(timer);
  }, [state.isPlaying, state.activeDetail]);

  const handleSelectLocation = (id: string) => {
    if (!id || id === state.activeLocationId) return;
    setState((prev) => ({
      ...prev,
      activeLocationId: id,
      isPlaying: false,
    }));
  };

  const handleSelectStep = (idx: number) => {
    setState((prev) => ({
      ...prev,
      activeStepIdx: idx,
      isPlaying: false,
    }));
  };

  const handleTogglePlay = () => {
    setState((prev) => ({
      ...prev,
      isPlaying: !prev.isPlaying,
    }));
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <div className="brand">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="4" />
              <line x1="12" y1="12" x2="19" y2="5" />
            </svg>
            <span>DANCING WITH THE SARS</span>
          </div>
          <div className="topbar-sep" />
          <span className="topbar-sub">
            {lang === "uk"
              ? "Моніторинг дрейфу нафтових розливів · NISAR / Sentinel-1 SAR"
              : "Oil Spill Drift Monitor · NISAR / Sentinel-1 SAR"}
          </span>
        </div>

        <div className="topbar-right">
          {state.error && (
            <span
              className="status-chip"
              style={{
                borderColor: "var(--accent-spill)",
                color: "#fca5a5",
              }}
              title={state.error}
            >
              {lang === "uk" ? "Помилка API" : "API Error"}
            </span>
          )}
          <div
            role="group"
            aria-label="Language switch"
            style={{
              display: "inline-flex",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              overflow: "hidden",
              background: "var(--bg-surface)",
            }}
          >
            <button
              type="button"
              className="mono"
              onClick={() => setLang("en")}
              aria-pressed={lang === "en"}
              style={{
                border: "none",
                padding: "3px 7px",
                fontSize: "10px",
                fontWeight: 600,
                cursor: "pointer",
                background: lang === "en" ? "var(--bg-hover)" : "transparent",
                color: lang === "en" ? "var(--text-primary)" : "var(--text-muted)",
              }}
            >
              EN
            </button>
            <button
              type="button"
              className="mono"
              onClick={() => setLang("uk")}
              aria-pressed={lang === "uk"}
              style={{
                border: "none",
                borderLeft: "1px solid var(--border)",
                padding: "3px 7px",
                fontSize: "10px",
                fontWeight: 600,
                cursor: "pointer",
                background: lang === "uk" ? "var(--bg-hover)" : "transparent",
                color: lang === "uk" ? "var(--text-primary)" : "var(--text-muted)",
              }}
            >
              UA
            </button>
          </div>
          <div className="status-chip mono">
            <span
              className="status-dot"
              style={{
                background: USE_MOCK ? "var(--accent-drift)" : "#22c55e",
              }}
            />
            <span>{USE_MOCK ? "MOCK DATA" : "LIVE API"}</span>
          </div>
        </div>
      </header>

      <main className="workspace">
        <aside className="sidebar">
          <div className="section-head">
            <span className="section-title">
              {lang === "uk" ? "Глобальний огляд" : "Global Overview"}
            </span>
            <span className="mono" style={{ fontSize: "10px", color: "var(--text-muted)" }}>
              {formatEventsCount(state.locations.length, lang)}
            </span>
          </div>

          <OverviewMinimap
            locations={state.locations}
            activeLocationId={state.activeLocationId}
            onSelectLocation={handleSelectLocation}
          />

          <EventSelect
            locations={state.locations}
            activeLocationId={state.activeLocationId}
            onSelectLocation={handleSelectLocation}
          />

          <div className="sidebar-scroll">
            <EventDetailsCard
              detail={state.activeDetail}
              activeStepIdx={state.activeStepIdx}
              loading={state.loading}
            />
          </div>

          <SpillOpacitySlider
            spillOpacity={state.spillOpacity}
            showContour={state.showContour}
            showTrajectory={state.showTrajectory}
            onOpacityChange={(value) =>
              setState((prev) => ({ ...prev, spillOpacity: value }))
            }
            onToggleContour={(checked) =>
              setState((prev) => ({ ...prev, showContour: checked }))
            }
            onToggleTrajectory={(checked) =>
              setState((prev) => ({ ...prev, showTrajectory: checked }))
            }
          />
        </aside>

        <section className="stage">
          {state.error && (
            <div
              role="alert"
              style={{
                padding: "8px 12px",
                background: "#2a1215",
                borderBottom: "1px solid var(--accent-spill)",
                color: "#fecaca",
                fontSize: "12px",
              }}
            >
              {state.error}
            </div>
          )}

          <div className="map-stage">
            <MainComparisonMap
              detail={state.activeDetail}
              activeStepIdx={state.activeStepIdx}
              spillOpacity={state.spillOpacity}
              showContour={state.showContour}
              showTrajectory={state.showTrajectory}
              splitRatio={state.splitRatio}
              onSplitChange={(ratio) =>
                setState((prev) => ({ ...prev, splitRatio: ratio }))
              }
            />
          </div>

          <SnapshotTimeline
            detail={state.activeDetail}
            activeStepIdx={state.activeStepIdx}
            isPlaying={state.isPlaying}
            onSelectStep={handleSelectStep}
            onTogglePlay={handleTogglePlay}
          />
        </section>
      </main>
    </div>
  );
}

export default App;
