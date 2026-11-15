import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { pluralUk } from "./utils/format";

export type Lang = "en" | "uk";

const STORAGE_KEY = "dancing_with_sars_lang";

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  toggleLang: () => void;
}

const I18nContext = createContext<I18nContextValue>({
  lang: "en",
  setLang: () => {},
  toggleLang: () => {},
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "en" || saved === "uk") return saved;
    } catch {
      // ignore storage errors
    }
    return "en";
  });

  const setLang = (next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore storage errors
    }
  };

  useEffect(() => {
    document.documentElement.lang = lang === "uk" ? "uk" : "en";
    document.title =
      lang === "uk"
        ? "Dancing with the SARs — NISAR L2 GCOV Моніторинг розливів"
        : "Dancing with the SARs — NISAR L2 GCOV Oil Spill Monitor";
  }, [lang]);

  const toggleLang = () => setLang(lang === "en" ? "uk" : "en");

  return (
    <I18nContext.Provider value={{ lang, setLang, toggleLang }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}

const EN_LOCATION_TITLES: Record<string, string> = {
  "oman-caroline-bezengi-2026": "Al Hallaniyat Islands, Oman",
  "green-canyon-600-seeps-2026": "Green Canyon 600, Gulf of Mexico",
  "eugene-island-316-2026": "Eugene Island 316, Gulf of Mexico",
  "wreck-1487-nantucket-2026": "Wreck 1487, South of Nantucket (USA)",
  "neft-dashlari-caspian-2026": "Neft Dashlari, Caspian Sea",
  "coal-oil-point-seeps-2026": "Coal Oil Point, Santa Barbara Channel",
  "canary-lee-twin-2026": "Tenerife – La Gomera (non-oil lookalike)",
  "baltic-bloom-twin-2026": "Gotland Basin, Baltic Sea (non-oil lookalike)",
  "uae-gem2-umm-al-quwain-2026": "Umm Al Quwain, UAE",
};

const EN_LOCATION_DESCRIPTIONS: Record<string, string> = {
  "oman-caroline-bezengi-2026":
    "Grounding of the tanker Caroline Bezengi triggered a major oil spill in the Arabian Sea. Multi-pass NISAR L-band SAR imagery captures the dark slick expanding near Al-Qibliyah Island.",
  "green-canyon-600-seeps-2026":
    "Natural hydrocarbon seeps in the northern Gulf of Mexico producing recurring surface slicks tracked across NISAR L2 GCOV acquisitions.",
  "eugene-island-316-2026":
    "Offshore infrastructure and surface slick monitoring in the Eugene Island 316 block, Gulf of Mexico, using calibrated NISAR L-band backscatter.",
  "wreck-1487-nantucket-2026":
    "Submerged wreck (Wreck 1487) ~90 NM south of Nantucket producing chronic small oil slicks (0.02–6.5 km²). NISAR L-band VV 5 MHz imagery tests detection limits near small point sources.",
  "neft-dashlari-caspian-2026":
    "Neft Dashlari offshore pile-mounted oilfield in the Caspian Sea (operating since 1949). NISAR L-band (HH, 20/40 MHz) captures recurring slicks from platforms, pipelines, and natural seeps.",
  "coal-oil-point-seeps-2026":
    "One of the world's largest natural marine oil seep fields off California (100–150 bbl/day). NISAR L-band tracks surface slicks near the seeps and offshore platforms.",
  "canary-lee-twin-2026":
    "Non-oil control site: wind shadow behind Tenerife in the channel toward La Gomera. Calm lee zones create dark radar lookalikes—demonstrating false-positive behavior with zero oil production.",
  "baltic-bloom-twin-2026":
    "Non-oil control site: summer 2026 cyanobacteria bloom in the Baltic Sea (SMHI report #8). Surface algae dampen capillary waves and appear dark on SAR—testing false-alarm rates.",
  "uae-gem2-umm-al-quwain-2026":
    "Supertanker GEM No. 2 incident ~25 km off Umm Al Quwain (Oct 2026), with shoreline impact on Oct 22 and leak stoppage on Oct 30. Pre-Oct 9 passes serve as clean baselines.",
};

export function localizeTitle(id: string, rawTitle: string, lang: Lang): string {
  if (lang === "en" && EN_LOCATION_TITLES[id]) {
    return EN_LOCATION_TITLES[id];
  }
  return rawTitle;
}

export function localizeDescription(id: string, rawDesc: string, lang: Lang): string {
  if (lang === "en" && EN_LOCATION_DESCRIPTIONS[id]) {
    return EN_LOCATION_DESCRIPTIONS[id];
  }
  return rawDesc;
}

const EN_SNAPSHOT_LABELS: Record<string, string> = {
  "День посадки на мілину": "Tanker grounding day",
  "Напередодні виходу нафти на берег": "Eve of shoreline landfall",
  "Широкий шлейф на північний схід": "Wide plume drifting NE",
  "Найбільша площа плями": "Peak slick area",
  "Останній знімок серії": "Latest pass in series",
  "Слід від точки ще до першого повідомлення NOAA": "Pre-NOAA trace near source",
  "Без незалежного підтвердження": "No independent confirmation",
  "Пляму біля вента видно на знімку": "Slick visible near vent",
  "Пляму біля судна видно на знімку": "Slick visible near wreck",
  "Пляму біля сипів видно на знімку": "Slick visible near seeps",
  "Пляму біля промислу видно на знімку": "Slick visible near oilfield",
  "Аналітики NOAA бачили пляму цього дня": "NOAA analysts observed slick",
  "Sentinel-1 бачив пляму цього дня": "Sentinel-1 observed slick",
  "Цвітіння ціанобактерій: нафти немає": "Cyanobacteria bloom: no oil",
  "Вітрова тінь: нафти немає": "Wind shadow: no oil",
  "Виток триває": "Leak ongoing",
  "Виток: Sentinel-1 бачив пляму цього дня": "Leak: Sentinel-1 observed slick",
  "До ураження танкера (контроль)": "Pre-incident (control)",
  "Після зупинки витоку (30.10): залишки плями": "Post-stoppage (30.10): residual slick",
  "Після ураження танкера, до помітного витоку": "Post-strike, before visible leak",
};

export function localizeSnapshotLabel(rawLabel: string, lang: Lang): string {
  if (lang !== "en") return rawLabel;
  if (EN_SNAPSHOT_LABELS[rawLabel]) return EN_SNAPSHOT_LABELS[rawLabel];

  let m = rawLabel.match(/^(\d+)-й день після першого повідомлення$/);
  if (m) return `Day ${m[1]} after first report`;

  m = rawLabel.match(/^(\d+)-й день після посадки$/);
  if (m) return `Day ${m[1]} after grounding`;

  m = rawLabel.match(/^(\d+) днів після виходу на берег$/);
  if (m) return `${m[1]} d after landfall`;

  m = rawLabel.match(/^До першого повідомлення NOAA \((.+)\)$/);
  if (m) return `Before first NOAA report (${m[1]})`;

  m = rawLabel.match(/^Після останнього звіту NOAA \((.+)\)$/);
  if (m) return `After last NOAA report (${m[1]})`;

  return rawLabel;
}

const NOTE_REPLACEMENTS: [string, string][] = [
  [
    "Пляму біля танкера взято з еталонної розмітки відомої події (батарея методів, origin = reference): автоматичний конвеєр на ранній стадії хронічного витоку її не виділяє",
    "Slick near the tanker is taken from reference annotation (origin = reference); the automated pipeline does not isolate early-stage chronic seepage.",
  ],
  [
    "На цю дату пляму біля танкера не виділяє ні автоматичний конвеєр, ні еталонна розмітка (слабкий контраст у VV)",
    "On this date, neither the automated pipeline nor reference annotation isolates the slick near the tanker (weak VV contrast).",
  ],
  [
    "Місце виходу нафти на берег (Рас-Мадрака, південь Масіри) — за межами кадру",
    "Shoreline landfall site (Ras Madrakah, southern Masirah) is outside the scene frame.",
  ],
  ["Вітер біля точки витоку", "Wind near source"],
  ["Вітер біля вента", "Wind near vent"],
  ["Вітер біля судна", "Wind near wreck"],
  ["Вітер біля сипів", "Wind near seeps"],
  ["Вітер біля промислу", "Wind near oilfield"],
  ["Вітер", "Wind"],
  ["(ERA5)", "(ERA5)"],
  ["м/с", "m/s"],
  ["майже штиль: темні ділянки можуть бути не нафтою.", "near-calm: dark patches may be non-oil lookalikes."],
  ["сильний вітер: тонкі плями погано видно.", "strong wind: thin slicks are poorly visible."],
  ["Аналітики NOAA бачили пляму в цей день на знімках інших супутників.", "NOAA analysts observed the slick on other satellite imagery this day."],
  ["Візуально на знімку видно пляму біля точки витоку.", "Slick is visually discernible near the source."],
  ["Візуально на знімку видно пляму біля вента.", "Slick is visually discernible near the vent."],
  ["Візуально на знімку видно пляму біля судна.", "Slick is visually discernible near the wreck."],
  ["Конвеєр пляму біля точки витоку не виділяє.", "Pipeline does not segment the slick near the source."],
  ["Конвеєр пляму біля вента не виділяє.", "Pipeline does not segment the slick near the vent."],
  ["Конвеєр пляму біля судна не виділяє.", "Pipeline does not segment the slick near the wreck."],
  ["Конвеєр виділяє пляму біля точки витоку", "Pipeline segments the slick near the source"],
  ["Конвеєр виділяє пляму біля вента", "Pipeline segments the slick near the vent"],
  ["Конвеєр виділяє пляму біля судна", "Pipeline segments the slick near the wreck"],
  ["«схоже на нафту»", '"probable oil"'],
  ["«можливо нафта»", '"possible oil"'],
  ["оцінка", "score"],
  ["ділянка", "region"],
  ["км² — це переважно штиль, вона більша за саму пляму.", "km² — mostly calm-wind lookalike, larger than the actual slick."],
  ["Sentinel-1 цього дня, на ~", "Sentinel-1 same day, ~"],
  ["год раніше: пляма", "h earlier: slick"],
  ["біля вента (Cerulean, машинна детекція).", "near vent (Cerulean ML detection)."],
];

export function localizeSnapshotNote(rawNote: string, lang: Lang): string {
  if (lang !== "en" || !rawNote) return rawNote;
  let out = rawNote;
  for (const [uk, en] of NOTE_REPLACEMENTS) {
    if (out.includes(uk)) {
      out = out.split(uk).join(en);
    }
  }
  return out;
}

export function formatArea(km2: number, lang: Lang): string {
  return `${km2.toFixed(1)} ${lang === "uk" ? "км²" : "km²"}`;
}

export function formatEventsCount(count: number, lang: Lang): string {
  if (lang === "uk") {
    return `${count} ${pluralUk(count, ["подія", "події", "подій"])}`;
  }
  return `${count} ${count === 1 ? "event" : "events"}`;
}

export function formatSnapshotsCount(count: number, lang: Lang): string {
  if (lang === "uk") {
    return `${count} ${pluralUk(count, ["знімок", "знімки", "знімків"])}`;
  }
  return `${count} ${count === 1 ? "pass" : "passes"}`;
}
