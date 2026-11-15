import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import {
  fetchGeoJson,
  fetchSourcesGeoJson,
  fetchTargetsGeoJson
} from "../../api/locationsApi";
import type {
  LocationDetail,
  SlickFlag,
  SpillContourFeature,
  SpillContourFeatureCollection,
  SpillContourProperties,
  TargetProperties
} from "../../types/location";
import { SplitCurtainControl } from "./SplitCurtainControl";

export interface MainComparisonMapProps {
  detail: LocationDetail | null;
  activeStepIdx: number;
  spillOpacity: number;
  showContour: boolean;
  showTrajectory: boolean;
  splitRatio: number;
  onSplitChange: (ratio: number) => void;
}

type BaseMapStyle = "dark" | "osm" | "sat";

interface BaseTileConfig {
  label: string;
  url: string;
  options: L.TileLayerOptions;
}

const WORLD_BOUNDS: L.LatLngBoundsLiteral = [
  [-85.05112878, -180],
  [85.05112878, 180]
];

const BASE_TILE_CONFIGS: Record<BaseMapStyle, BaseTileConfig> = {
  dark: {
    label: "Темна",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    options: {
      maxZoom: 16,
      attribution: "&copy; Esri, HERE, Garmin, OpenStreetMap"
    }
  },
  osm: {
    label: "OSM",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }
  },
  sat: {
    label: "Супутник",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    options: {
      maxZoom: 18,
      attribution: "&copy; Esri World Imagery"
    }
  }
};

function formatDeg(value: number, posHem: string, negHem: string): string {
  return `${Math.abs(value).toFixed(3)}°${value >= 0 ? posHem : negHem}`;
}

function bboxToLeafletBounds(bbox: [number, number, number, number]): L.LatLngBoundsLiteral {
  const [west, south, east, north] = bbox;
  return [
    [south, west],
    [north, east]
  ];
}

function extractCentroid(fc: SpillContourFeatureCollection): [number, number] | null {
  const candidates: SpillContourFeature[] = fc.features.filter(
    (f) => f.properties.class !== "possible"
  );
  const pool = candidates.length > 0 ? candidates : fc.features;
  const primaryFeature = pool.reduce<SpillContourFeature | null>(
    (best, cur) =>
      !best || cur.properties.area_km2 > best.properties.area_km2 ? cur : best,
    null
  );
  if (!primaryFeature) return null;

  let ring: number[][] | undefined;
  if (primaryFeature.geometry.type === "Polygon") {
    const coords = primaryFeature.geometry.coordinates as number[][][];
    ring = coords[0];
  } else if (primaryFeature.geometry.type === "MultiPolygon") {
    const coords = primaryFeature.geometry.coordinates as number[][][][];
    ring = coords[0]?.[0];
  }

  if (!ring || ring.length === 0) return null;

  const isClosed =
    ring.length > 1 &&
    ring[0][0] === ring[ring.length - 1][0] &&
    ring[0][1] === ring[ring.length - 1][1];
  const count = isClosed ? ring.length - 1 : ring.length;
  if (count <= 0) return null;

  let sumLon = 0;
  let sumLat = 0;
  for (let i = 0; i < count; i += 1) {
    sumLon += ring[i][0];
    sumLat += ring[i][1];
  }

  return [sumLat / count, sumLon / count];
}

function buildArrowHead(
  fromPt: [number, number],
  toPt: [number, number]
): [number, number][] | null {
  const dLat = toPt[0] - fromPt[0];
  const cosLat = Math.max(0.2, Math.cos((toPt[0] * Math.PI) / 180));
  const dLonScaled = (toPt[1] - fromPt[1]) * cosLat;
  const segLen = Math.hypot(dLat, dLonScaled);
  if (segLen < 1e-4) return null;

  const armLen = Math.min(0.055, Math.max(0.018, segLen * 0.28));
  const angle = Math.atan2(dLat, dLonScaled);
  const spread = 0.48; // ~27 deg

  const wing1Lat = toPt[0] - armLen * Math.sin(angle - spread);
  const wing1Lon = toPt[1] - (armLen * Math.cos(angle - spread)) / cosLat;

  const wing2Lat = toPt[0] - armLen * Math.sin(angle + spread);
  const wing2Lon = toPt[1] - (armLen * Math.cos(angle + spread)) / cosLat;

  return [[wing1Lat, wing1Lon], toPt, [wing2Lat, wing2Lon]];
}

const TARGET_STYLE_MAP: Record<
  TargetProperties["kind"],
  { label: string; color: string; radius: number }
> = {
  ship: { label: "Судно", color: "#38bdf8", radius: 3.5 },
  platform: { label: "Платформа / об'єкт", color: "#f59e0b", radius: 4 },
  coastal: { label: "Берегова споруда", color: "#94a3b8", radius: 3 }
};

const FLAG_LABELS: Record<SlickFlag, string> = {
  near_coast: "біля берега (< 2 км)",
  low_wind: "слабкий вітер (< 3 м/с)",
  near_noise: "слабкий контраст",
  rain: "опади",
  small: "мала площа (< 2 км²)",
  static: "повторювана область"
};

function buildContourTooltipNode(props: SpillContourProperties | undefined): HTMLElement {
  const wrap = document.createElement("div");
  if (!props) {
    wrap.textContent = "Пляма";
    return wrap;
  }

  const classLabel = props.class === "possible" ? "Можлива пляма" : "Схоже на нафту";
  const originSuffix = props.origin === "reference" ? " · еталонна розмітка" : "";

  const title = document.createElement("div");
  title.textContent = `${classLabel}${originSuffix}`;
  wrap.appendChild(title);

  const metrics = document.createElement("div");
  metrics.textContent = `Площа: ${props.area_km2.toFixed(1)} км² · Оцінка: ${props.score.toFixed(2)}`;
  wrap.appendChild(metrics);

  if (props.flags && props.flags.length > 0) {
    const flagsLine = document.createElement("div");
    const labels = props.flags.map((flag) => FLAG_LABELS[flag] ?? flag).join(", ");
    flagsLine.textContent = `Фактори сумніву: ${labels}`;
    wrap.appendChild(flagsLine);
  }

  return wrap;
}

function contourStyleForFeature(
  renderer: L.SVG,
  props: SpillContourProperties | undefined,
  opacity: number
): L.PathOptions {
  if (props?.class === "possible") {
    return {
      renderer,
      color: "#fbbf24",
      weight: 1.6,
      dashArray: "4 4",
      fillColor: "#fbbf24",
      fillOpacity: 0.01
    };
  }
  return {
    renderer,
    color: "#ef4444",
    weight: 2.2,
    fillColor: "#ef4444",
    fillOpacity: Math.min(0.45, opacity * 0.35)
  };
}

/**
 * [Dev 1 — Lead] Головна карта Leaflet:
 * - Ліворуч від шторки (`sarLeftPane`): базова підкладка + парний SAR «До» (`before_url`)
 * - Праворуч від шторки (`sarRightPane` із `clip: rect(...)`):
 *   SAR «Після» (`after_url`) + маска розливу + GeoJSON-контури (`probable`/`possible`) + траєкторія дрейфу
 */
export function MainComparisonMap({
  detail,
  activeStepIdx,
  spillOpacity,
  showContour,
  showTrajectory,
  splitRatio,
  onSplitChange
}: MainComparisonMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const sarLeftPaneRef = useRef<HTMLElement | null>(null);
  const sarPaneRef = useRef<HTMLElement | null>(null);
  const sarRendererRef = useRef<L.SVG | null>(null);

  const baseLayerRef = useRef<L.TileLayer | null>(null);
  const referenceGroupRef = useRef<L.LayerGroup | null>(null);
  const sourcesGroupRef = useRef<L.LayerGroup | null>(null);
  const targetsGroupRef = useRef<L.LayerGroup | null>(null);
  const beforeImageLayerRef = useRef<L.ImageOverlay | null>(null);
  const sarImageLayerRef = useRef<L.ImageOverlay | null>(null);
  const maskImageLayerRef = useRef<L.ImageOverlay | null>(null);
  const vectorGroupRef = useRef<L.LayerGroup | null>(null);
  const activeContourLayerRef = useRef<L.GeoJSON | null>(null);

  const splitRatioRef = useRef(splitRatio);
  splitRatioRef.current = splitRatio;

  const spillOpacityRef = useRef(spillOpacity);
  spillOpacityRef.current = spillOpacity;

  const lastFittedIdRef = useRef<string | null>(null);

  const [baseStyle, setBaseStyle] = useState<BaseMapStyle>("dark");
  const [cursorCoords, setCursorCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [scaleKm, setScaleKm] = useState<number>(25);

  const activeSnap =
    detail && activeStepIdx >= 0 ? detail.snapshots[activeStepIdx] ?? null : null;

  const updateClip = useCallback(() => {
    const map = mapRef.current;
    const sarLeftPane = sarLeftPaneRef.current;
    const sarPane = sarPaneRef.current;
    if (!map || !sarPane) return;

    const size = map.getSize();
    if (size.x <= 0 || size.y <= 0) return;

    const splitX = Math.round(size.x * splitRatioRef.current);
    const nw = map.containerPointToLayerPoint([0, 0]);
    const splitPt = map.containerPointToLayerPoint([splitX, 0]);
    const se = map.containerPointToLayerPoint([size.x, size.y]);

    if (sarLeftPane) {
      sarLeftPane.style.clip = `rect(${nw.y}px, ${splitPt.x}px, ${se.y}px, ${nw.x}px)`;
    }
    sarPane.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${splitPt.x}px)`;
  }, []);

  const updateScaleBar = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;

    const size = map.getSize();
    if (size.x < 80 || size.y <= 0) return;

    const cx = Math.floor(size.x / 2);
    const cy = Math.floor(size.y / 2);
    const p1 = map.containerPointToLatLng([cx, cy]);
    const p2 = map.containerPointToLatLng([cx + 44, cy]);
    const meters = map.distance(p1, p2);
    if (Number.isFinite(meters) && meters > 0) {
      setScaleKm(meters / 1000);
    }
  }, []);

  const fitToDetailBounds = useCallback(() => {
    const map = mapRef.current;
    if (!map || !detail) return;
    map.fitBounds(bboxToLeafletBounds(detail.bbox), { padding: [24, 24] });
    updateClip();
    updateScaleBar();
  }, [detail, updateClip, updateScaleBar]);

  // 1. Ініціалізація екземпляра Leaflet, панелі sarRightPane та обробників подій
  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) return;

    container.style.setProperty("background", "#070709", "important");

    const map = L.map(container, {
      zoomControl: false,
      attributionControl: true,
      minZoom: 3,
      maxBounds: WORLD_BOUNDS,
      maxBoundsViscosity: 1.0,
      bounceAtZoomLimits: false
    });
    const initialMinZoom = Math.max(3, map.getBoundsZoom(WORLD_BOUNDS, true));
    map.setMinZoom(initialMinZoom);
    map.setView([20, 15], initialMinZoom);

    const sarLeftPane = map.createPane("sarLeftPane");
    sarLeftPane.style.zIndex = "405";
    sarLeftPane.style.pointerEvents = "none";

    const sarPane = map.createPane("sarRightPane");
    sarPane.style.zIndex = "410";
    sarPane.style.pointerEvents = "none";

    const markersPane = map.createPane("markersPane");
    markersPane.style.zIndex = "420";
    markersPane.style.pointerEvents = "none";

    const sarRenderer = L.svg({ pane: "sarRightPane" });
    const referenceGroup = L.layerGroup().addTo(map);
    const sourcesGroup = L.layerGroup().addTo(map);
    const targetsGroup = L.layerGroup().addTo(map);
    const vectorGroup = L.layerGroup().addTo(map);

    mapRef.current = map;
    sarLeftPaneRef.current = sarLeftPane;
    sarPaneRef.current = sarPane;
    sarRendererRef.current = sarRenderer;
    referenceGroupRef.current = referenceGroup;
    sourcesGroupRef.current = sourcesGroup;
    targetsGroupRef.current = targetsGroup;
    vectorGroupRef.current = vectorGroup;

    const handleViewChange = () => {
      updateClip();
      updateScaleBar();
    };

    const handleMouseMove = (e: L.LeafletMouseEvent) => {
      setCursorCoords({ lat: e.latlng.lat, lon: e.latlng.lng });
    };

    const handleMouseOut = () => {
      setCursorCoords(null);
    };

    map.on("move zoom viewreset moveend zoomend resize", handleViewChange);
    map.on("mousemove", handleMouseMove);
    map.on("mouseout", handleMouseOut);

    const resizeObserver = new ResizeObserver(() => {
      map.invalidateSize();
      const minZ = Math.max(3, map.getBoundsZoom(WORLD_BOUNDS, true));
      map.setMinZoom(minZ);
      if (map.getZoom() < minZ) {
        map.setZoom(minZ, { animate: false });
      }
      map.panInsideBounds(WORLD_BOUNDS, { animate: false });
      handleViewChange();
    });
    resizeObserver.observe(container);

    handleViewChange();

    return () => {
      resizeObserver.disconnect();
      map.off("move zoom viewreset moveend zoomend resize", handleViewChange);
      map.off("mousemove", handleMouseMove);
      map.off("mouseout", handleMouseOut);
      map.remove();
      mapRef.current = null;
      sarLeftPaneRef.current = null;
      sarPaneRef.current = null;
      sarRendererRef.current = null;
      baseLayerRef.current = null;
      referenceGroupRef.current = null;
      sourcesGroupRef.current = null;
      targetsGroupRef.current = null;
      beforeImageLayerRef.current = null;
      sarImageLayerRef.current = null;
      maskImageLayerRef.current = null;
      vectorGroupRef.current = null;
      activeContourLayerRef.current = null;
    };
  }, [updateClip, updateScaleBar]);

  // 2. Перемикання базової тайлової підкладки
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (baseLayerRef.current) {
      baseLayerRef.current.remove();
      baseLayerRef.current = null;
    }

    const cfg = BASE_TILE_CONFIGS[baseStyle];
    const layer = L.tileLayer(cfg.url, {
      ...cfg.options,
      noWrap: true,
      bounds: WORLD_BOUNDS
    }).addTo(map);
    baseLayerRef.current = layer;
  }, [baseStyle]);

  // 3. Оновлення кліпінгу шторки без перестворення шарів
  useEffect(() => {
    updateClip();
  }, [splitRatio, updateClip]);

  // 4. Позиціонування камери, маркер епіцентру та опціональний шар джерел (sources.geojson)
  useEffect(() => {
    const map = mapRef.current;
    const referenceGroup = referenceGroupRef.current;
    const sourcesGroup = sourcesGroupRef.current;
    if (!map || !referenceGroup || !sourcesGroup) return;

    referenceGroup.clearLayers();
    sourcesGroup.clearLayers();

    if (!detail) {
      lastFittedIdRef.current = null;
      return;
    }

    const bounds = bboxToLeafletBounds(detail.bbox);
    L.rectangle(bounds, {
      pane: "markersPane",
      color: "#3f3f46",
      weight: 1,
      dashArray: "4 4",
      fill: false,
      interactive: false
    }).addTo(referenceGroup);

    const [epLon, epLat] = detail.coords;
    L.circleMarker([epLat, epLon], {
      pane: "markersPane",
      radius: 5,
      color: "#09090b",
      weight: 1.5,
      fillColor: "#f97316",
      fillOpacity: 0.95,
      interactive: false
    }).addTo(referenceGroup);

    if (lastFittedIdRef.current !== detail.id) {
      lastFittedIdRef.current = detail.id;
      map.fitBounds(bounds, { padding: [24, 24] });
      updateClip();
      updateScaleBar();
    }

    if (!detail.sources_geojson_url) {
      return;
    }

    let cancelled = false;
    const sourcesUrl = detail.sources_geojson_url;

    async function loadSources() {
      try {
        const fc = await fetchSourcesGeoJson(sourcesUrl);
        if (cancelled || !sourcesGroupRef.current) return;
        const targetGroup = sourcesGroupRef.current;
        targetGroup.clearLayers();

        for (const feat of fc.features) {
          const [lon, lat] = feat.geometry.coordinates;
          const isDetected = feat.properties.kind === "detected";
          L.circleMarker([lat, lon], {
            pane: "markersPane",
            radius: isDetected ? 5.5 : 5,
            color: "#09090b",
            weight: 1.5,
            fillColor: isDetected ? "#22d3ee" : "#f97316",
            fillOpacity: 0.95
          })
            .bindTooltip(feat.properties.label, { direction: "top", opacity: 0.95 })
            .addTo(targetGroup);
        }
      } catch {
        // Опціональний шар джерел не має блокувати карту
      }
    }

    loadSources();
    return () => {
      cancelled = true;
    };
  }, [detail, updateClip, updateScaleBar]);

  // 5. Растрові шари SAR «До» (ліворуч), SAR «Після» (праворуч) і маски розливу
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (beforeImageLayerRef.current) {
      beforeImageLayerRef.current.remove();
      beforeImageLayerRef.current = null;
    }
    if (sarImageLayerRef.current) {
      sarImageLayerRef.current.remove();
      sarImageLayerRef.current = null;
    }
    if (maskImageLayerRef.current) {
      maskImageLayerRef.current.remove();
      maskImageLayerRef.current = null;
    }

    if (!detail) return;

    const bounds = bboxToLeafletBounds(detail.bbox);
    const snap = activeStepIdx >= 0 ? detail.snapshots[activeStepIdx] ?? null : null;
    const beforeUrl = snap ? snap.before_url : detail.baseline_before_url;
    const afterUrl = snap ? snap.after_url : detail.baseline_before_url;

    beforeImageLayerRef.current = L.imageOverlay(beforeUrl, bounds, {
      pane: "sarLeftPane",
      opacity: 0.9,
      interactive: false
    }).addTo(map);

    sarImageLayerRef.current = L.imageOverlay(afterUrl, bounds, {
      pane: "sarRightPane",
      opacity: 0.9,
      interactive: false
    }).addTo(map);

    if (snap && snap.mask_url) {
      maskImageLayerRef.current = L.imageOverlay(snap.mask_url, bounds, {
        pane: "sarRightPane",
        opacity: spillOpacityRef.current,
        interactive: false
      }).addTo(map);
    }

    updateClip();
  }, [detail, activeStepIdx, updateClip]);

  // 6. Плавне оновлення прозорості маски та заливки контуру (без заливки для possible)
  useEffect(() => {
    if (maskImageLayerRef.current) {
      maskImageLayerRef.current.setOpacity(spillOpacity);
    }
    if (activeContourLayerRef.current) {
      activeContourLayerRef.current.setStyle((feature) => {
        const isPossible =
          (feature?.properties as SpillContourProperties | undefined)?.class === "possible";
        return {
          fillOpacity: isPossible ? 0.01 : Math.min(0.45, spillOpacity * 0.35)
        };
      });
    }
  }, [spillOpacity]);

  // 7. Векторний GeoJSON-контур і траєкторія руху (дрейф)
  useEffect(() => {
    const vectorGroup = vectorGroupRef.current;
    const sarRenderer = sarRendererRef.current;
    if (!vectorGroup || !sarRenderer) return;

    vectorGroup.clearLayers();
    activeContourLayerRef.current = null;

    if (!detail || activeStepIdx < 0 || (!showContour && !showTrajectory)) {
      return;
    }

    const stepsToLoad = detail.snapshots.slice(0, activeStepIdx + 1);
    if (stepsToLoad.length === 0) return;

    let cancelled = false;

    async function renderVectors() {
      try {
        const collections = await Promise.all(
          stepsToLoad.map((snap) => fetchGeoJson(snap.contour_geojson_url))
        );
        if (cancelled || !vectorGroupRef.current || !sarRendererRef.current) return;

        const group = vectorGroupRef.current;
        const renderer = sarRendererRef.current;
        group.clearLayers();
        activeContourLayerRef.current = null;

        // Попередні пунктирні контури (клас probable) для відображення історії розтікання
        if (showTrajectory && collections.length > 1) {
          for (let i = 0; i < collections.length - 1; i += 1) {
            const histFc = collections[i];
            const probableOnly: SpillContourFeatureCollection = {
              type: "FeatureCollection",
              features: histFc.features.filter((f) => f.properties.class !== "possible")
            };
            if (probableOnly.features.length === 0) continue;

            L.geoJSON(probableOnly as unknown as Parameters<typeof L.geoJSON>[0], {
              pane: "sarRightPane",
              interactive: false,
              style: () => ({
                renderer,
                color: "#fbbf24",
                weight: 1.5,
                dashArray: "5 5",
                fillColor: "#fbbf24",
                fillOpacity: 0.06
              })
            }).addTo(group);
          }
        }

        // Активний векторний контур поточного кроку (probable = суцільний #ef4444, possible = пунктир без заливки)
        if (showContour && collections.length > 0) {
          const currentFc = collections[collections.length - 1];
          const contourLayer = L.geoJSON(currentFc as unknown as Parameters<typeof L.geoJSON>[0], {
            pane: "sarRightPane",
            interactive: true,
            style: (feature) =>
              contourStyleForFeature(
                renderer,
                feature?.properties as SpillContourProperties | undefined,
                spillOpacityRef.current
              ),
            onEachFeature: (feature, layer) => {
              const props = feature.properties as SpillContourProperties | undefined;
              layer.bindTooltip(buildContourTooltipNode(props), {
                sticky: true,
                direction: "top",
                opacity: 0.95
              });
            }
          }).addTo(group);
          activeContourLayerRef.current = contourLayer;
        }

        // Лінія та стрілка дрейфу центроїдів T1 -> ... -> Tk
        if (showTrajectory && detail) {
          const centroids = collections
            .map(extractCentroid)
            .filter((pt): pt is [number, number] => pt !== null);

          if (centroids.length > 0) {
            const [epLon, epLat] = detail.coords;
            const trailPoints: [number, number][] = [[epLat, epLon], ...centroids];

            L.polyline(trailPoints, {
              pane: "sarRightPane",
              renderer,
              interactive: false,
              color: "#fbbf24",
              weight: 2.2,
              dashArray: "6 4",
              opacity: 0.95
            }).addTo(group);

            centroids.forEach((pt, idx) => {
              const isLatest = idx === centroids.length - 1;
              L.circleMarker(pt, {
                pane: "sarRightPane",
                renderer,
                interactive: false,
                radius: isLatest ? 5 : 3.8,
                color: "#09090b",
                weight: 1.5,
                fillColor: isLatest ? "#ef4444" : "#fbbf24",
                fillOpacity: 1
              }).addTo(group);
            });

            if (trailPoints.length >= 2) {
              const prevPt = trailPoints[trailPoints.length - 2];
              const endPt = trailPoints[trailPoints.length - 1];
              const arrowPts = buildArrowHead(prevPt, endPt);
              if (arrowPts) {
                L.polyline(arrowPts, {
                  pane: "sarRightPane",
                  renderer,
                  interactive: false,
                  color: "#fbbf24",
                  weight: 2.2,
                  opacity: 0.95
                }).addTo(group);
              }
            }
          }
        }

        updateClip();
      } catch {
        // Окремі збої GeoJSON не мають ламати базову карту
      }
    }

    renderVectors();
    return () => {
      cancelled = true;
    };
  }, [detail, activeStepIdx, showContour, showTrajectory, updateClip]);

  // 8. Опціональні точкові цілі на дату знімка (targets_<step_id>.geojson)
  useEffect(() => {
    const targetsGroup = targetsGroupRef.current;
    if (!targetsGroup) return;

    targetsGroup.clearLayers();

    if (!activeSnap?.targets_geojson_url) {
      return;
    }

    let cancelled = false;
    const targetsUrl = activeSnap.targets_geojson_url;

    async function loadTargets() {
      try {
        const fc = await fetchTargetsGeoJson(targetsUrl);
        if (cancelled || !targetsGroupRef.current) return;
        const targetLayerGroup = targetsGroupRef.current;
        targetLayerGroup.clearLayers();

        for (const feat of fc.features) {
          const [lon, lat] = feat.geometry.coordinates;
          const cfg = TARGET_STYLE_MAP[feat.properties.kind] ?? TARGET_STYLE_MAP.ship;
          L.circleMarker([lat, lon], {
            pane: "markersPane",
            radius: cfg.radius,
            color: "#09090b",
            weight: 1,
            fillColor: cfg.color,
            fillOpacity: 0.9
          })
            .bindTooltip(`${cfg.label} · +${feat.properties.snr_db.toFixed(1)} dB (${feat.properties.date})`, {
              direction: "top",
              opacity: 0.95
            })
            .addTo(targetLayerGroup);
        }
      } catch {
        // Опціональний шар цілей не має блокувати карту
      }
    }

    loadTargets();
    return () => {
      cancelled = true;
    };
  }, [activeSnap]);

  const handleZoomIn = () => mapRef.current?.zoomIn();
  const handleZoomOut = () => mapRef.current?.zoomOut();

  const scaleLabel = scaleKm >= 1 ? `${Math.round(scaleKm)} км` : `${Math.round(scaleKm * 1000)} м`;

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", background: "#070709" }}>
      <div
        ref={containerRef}
        aria-label="Інтерактивна карта порівняння SAR-знімків"
        style={{ position: "absolute", inset: 0 }}
      />

      <SplitCurtainControl splitRatio={splitRatio} onSplitChange={onSplitChange} />

      {/* Лівий верхній бейдж SAR «До» + перемикач підкладки */}
      <div
        style={{
          position: "absolute",
          top: 12,
          left: 12,
          zIndex: 440,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 6,
          padding: "4px 8px",
          background: "var(--bg-panel)",
          border: "1px solid var(--border)",
          borderRadius: 4
        }}
      >
        <span
          className="mono"
          style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.05em",
            color: "var(--accent-signal)"
          }}
        >
          SAR ДО
        </span>
        {detail && (
          <span className="mono" style={{ fontSize: 10, color: "var(--text-secondary)" }}>
            {activeSnap
              ? `${activeSnap.before_date} · ${activeSnap.track} · ${activeSnap.polarization}`
              : `${detail.baseline_date} · БАЗА`}
          </span>
        )}
        <span style={{ color: "var(--border-strong)", fontSize: 10 }}>|</span>

        {(Object.keys(BASE_TILE_CONFIGS) as BaseMapStyle[]).map((styleKey) => {
          const isActive = baseStyle === styleKey;
          return (
            <button
              key={styleKey}
              type="button"
              className="btn"
              onClick={() => setBaseStyle(styleKey)}
              style={{
                height: 20,
                padding: "0 6px",
                fontSize: 10,
                borderColor: isActive ? "var(--border-strong)" : "transparent",
                background: isActive ? "var(--bg-hover)" : "transparent",
                color: isActive ? "var(--text-primary)" : "var(--text-muted)"
              }}
            >
              {BASE_TILE_CONFIGS[styleKey].label}
            </button>
          );
        })}
      </div>

      {/* Правий верхній бейдж SAR «Після» */}
      <div
        className="mono"
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          zIndex: 440,
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "5px 10px",
          background: "var(--bg-panel)",
          border: "1px solid var(--border)",
          borderRadius: 4,
          fontSize: 11,
          color: "var(--text-primary)",
          pointerEvents: "none"
        }}
      >
        <span style={{ color: "var(--accent-spill)", fontWeight: 600 }}>SAR ПІСЛЯ</span>
        <span style={{ color: "var(--border-strong)" }}>|</span>
        {detail ? (
          activeSnap ? (
            <>
              <span>{activeSnap.step_id.toUpperCase()}</span>
              <span>{activeSnap.date}</span>
              <span style={{ color: "var(--text-muted)" }}>
                {activeSnap.track} · {activeSnap.polarization}
              </span>
              <span style={{ color: "var(--text-secondary)" }}>{activeSnap.area_km2.toFixed(1)} км²</span>
            </>
          ) : (
            <>
              <span>T0 БАЗА</span>
              <span>{detail.baseline_date}</span>
              <span style={{ color: "var(--text-secondary)" }}>0.0 км²</span>
            </>
          )
        ) : (
          <span style={{ color: "var(--text-muted)" }}>Очікування...</span>
        )}
      </div>

      {/* Кнопки масштабу праворуч */}
      <div
        aria-label="Масштаб карти"
        style={{
          position: "absolute",
          top: 52,
          right: 12,
          zIndex: 440,
          display: "flex",
          flexDirection: "column",
          gap: 4
        }}
      >
        <button type="button" className="btn" onClick={handleZoomIn} title="Наблизити" style={{ width: 28, height: 28, padding: 0 }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M8 3V13M3 8H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
        <button type="button" className="btn" onClick={handleZoomOut} title="Віддалити" style={{ width: 28, height: 28, padding: 0 }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M3 8H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
        <button
          type="button"
          className="btn"
          disabled={!detail}
          onClick={fitToDetailBounds}
          title="Повернути камеру до меж події"
          style={{ width: 28, height: 28, padding: 0 }}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M2 6V2H6M10 2H14V6M14 10V14H10M6 14H2V10"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {/* Нижній лівий HUD (курсор + bbox) */}
      <div
        className="mono"
        style={{
          position: "absolute",
          left: 12,
          bottom: 12,
          zIndex: 440,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "4px 10px",
          background: "var(--bg-panel)",
          border: "1px solid var(--border)",
          borderRadius: 4,
          fontSize: 11,
          color: "var(--text-secondary)",
          pointerEvents: "none"
        }}
      >
        <span>
          {cursorCoords
            ? `Курсор: ${formatDeg(cursorCoords.lat, "N", "S")}, ${formatDeg(cursorCoords.lon, "E", "W")}`
            : detail
              ? `Центр: ${formatDeg(detail.coords[1], "N", "S")}, ${formatDeg(detail.coords[0], "E", "W")}`
              : "Курсор: —"}
        </span>
        {detail && (
          <>
            <span style={{ color: "var(--border-strong)" }}>|</span>
            <span style={{ color: "var(--text-muted)" }}>bbox: [{detail.bbox.join(", ")}]</span>
          </>
        )}
      </div>

      {/* Нижній правий HUD (радарна шкала + масштаб) */}
      <div
        className="mono"
        style={{
          position: "absolute",
          right: 12,
          bottom: 24,
          zIndex: 440,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "4px 10px",
          background: "var(--bg-panel)",
          border: "1px solid var(--border)",
          borderRadius: 4,
          fontSize: 10,
          color: "var(--text-secondary)",
          pointerEvents: "none"
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span>-25 dB</span>
          <svg width="50" height="6" viewBox="0 0 50 6" aria-hidden="true">
            <rect x="0" y="0" width="10" height="6" fill="#09090b" />
            <rect x="10" y="0" width="10" height="6" fill="#1e293b" />
            <rect x="20" y="0" width="10" height="6" fill="#475569" />
            <rect x="30" y="0" width="10" height="6" fill="#94a3b8" />
            <rect x="40" y="0" width="10" height="6" fill="#e2e8f0" />
          </svg>
          <span>0 dB</span>
        </div>
        <span style={{ color: "var(--border-strong)" }}>|</span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              display: "inline-block",
              width: 44,
              height: 5,
              borderLeft: "1px solid var(--text-secondary)",
              borderRight: "1px solid var(--text-secondary)",
              borderBottom: "1px solid var(--text-secondary)"
            }}
          />
          <span>{scaleLabel}</span>
        </div>
      </div>
    </div>
  );
}
