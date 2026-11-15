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
};

const EN_LOCATION_DESCRIPTIONS: Record<string, string> = {
  "oman-caroline-bezengi-2026":
    "Grounding of the tanker Caroline Bezengi triggered a major oil spill in the Arabian Sea. Multi-pass NISAR L-band SAR imagery captures the dark slick expanding near Al-Qibliyah Island.",
  "green-canyon-600-seeps-2026":
    "Natural hydrocarbon seeps in the northern Gulf of Mexico producing recurring surface slicks tracked across NISAR L2 GCOV acquisitions.",
  "eugene-island-316-2026":
    "Offshore infrastructure and surface slick monitoring in the Eugene Island 316 block, Gulf of Mexico, using calibrated NISAR L-band backscatter.",
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
