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

const UK_LOCATION_TITLES: Record<string, string> = {
  "oman-caroline-bezengi-2026": "Острови Халланіят, Оман",
  "green-canyon-600-seeps-2026": "Green Canyon 600, Мексиканська затока",
  "eugene-island-316-2026": "Eugene Island 316, Мексиканська затока",
  "wreck-1487-nantucket-2026": "Wreck 1487, південніше Нантакета (США)",
  "neft-dashlari-caspian-2026": "Нафтові Камені, Каспійське море",
  "coal-oil-point-seeps-2026": "Coal Oil Point, протока Санта-Барбара",
  "canary-lee-twin-2026": "Тенерифе – Ла-Гомера (двійник без нафти)",
  "baltic-bloom-twin-2026": "Готландська западина, Балтика (двійник без нафти)",
  "uae-gem2-umm-al-quwain-2026": "Умм-ель-Кайвайн, ОАЕ",
};

const UK_LOCATION_DESCRIPTIONS: Record<string, string> = {
  "oman-caroline-bezengi-2026":
    "Танкер Caroline Bezengi після підозри на вибух (8.06.2026) сів на мілину біля острова Аль-Кіблія (острови Халланіят) 30.06.2026, приблизно за 41 км від Шарбітату. Нафтовий шлейф дрейфує на північний схід; 12.08 нафта вийшла на берег біля Рас-Мадраки та південної Масіри. Плями виділено автоматично за знімками NISAR L-band; оцінка «схоже на нафту» — ранжування для перевірки, а не доказ.",
  "green-canyon-600-seeps-2026":
    "Природні нафтові сипи на глибині ~1180 м (вент Mega Plume). Нафта піднімається з дна постійно; пляма на поверхні з'являється біля вента при вітрі ~2–7 м/с і живе кілька годин. У районі є й інші сипи Green Canyon, тому плями далеко від вента — не обов'язково помилки. Знімки NISAR L-band, VV 5 МГц (грубіша роздільність); оцінка «схоже на нафту» — ранжування для перевірки, а не доказ. Сип діє постійно, тому «До» — знімок того самого треку, на якому плями біля вента не видно (може бути пізнішим за інші дати).",
  "eugene-island-316-2026":
    "Повторювана нафтова пляма в блоці Eugene Island 316 біля узбережжя Луїзіани. З 03.08 до 20.09.2026 аналітики NOAA/NESDIS щоразу бачили її в одній і тій самій точці й пов'язують із трубопроводом; офіційно джерело не встановлене, берегова охорона США та BSEE розслідують. Плями виділено автоматично за знімками NISAR L-band (HH, 40 МГц); оцінка «схоже на нафту» — ранжування для перевірки, а не доказ. На знімках NISAR 07.07 і 19.07 тонкий шлейф від тієї самої точки видно ще до першого повідомлення. «До» — знімок того самого треку без сліду біля точки: для треку 156D це 20.01.2026, для 033A — 10.07.2026.",
  "wreck-1487-nantucket-2026":
    "Затонуле судно (Wreck 1487) приблизно за 90 морських миль на південь від Нантакета. Звідси постійно виходять невеликі плями нафти: аналітики NOAA повідомляли про них у 68 днів з 03.10.2025 до 06.11.2026, площа плям 0,02–6,5 км². Знімки NISAR L-band, VV 5 МГц (груба роздільність): такі малі плями на межі можливостей знімка, і автоматичний конвеєр біля судна їх майже не виділяє. Оцінка «схоже на нафту» — ранжування для перевірки, а не доказ. «До» — знімок того самого треку при сильному вітрі (~12 м/с) без звітів NOAA за ±1 день.",
  "neft-dashlari-caspian-2026":
    "Нафтові Камені (Neft Daşları) — морський промисел на палях у Каспійському морі, видобуток з 1949 року. Біля комплексу регулярно видно плями: витоки з платформ і трубопроводів, а також природні сипи. Плями виділено автоматично за знімками NISAR L-band (HH, 20/40 МГц); оцінка «схоже на нафту» — ранжування для перевірки, а не доказ. «До» — знімок того самого треку без плям біля комплексу.",
  "coal-oil-point-seeps-2026":
    "Одне з найбільших у світі полів природних нафтових сипів біля узбережжя Каліфорнії: 100–150 барелів нафти на добу. Плями добре видно ввечері при слабкому вітрі; ранкові проходи часто в штиль. Поруч є нафтові платформи. Плями виділено автоматично за знімками NISAR L-band; оцінка «схоже на нафту» — ранжування для перевірки, а не доказ. «До» — знімок того самого треку без плям біля поля сипів.",
  "canary-lee-twin-2026":
    "Контрольний район без нафти: вітрова тінь острова Тенерифе в протоці до Ла-Гомери. За пасатом утворюються штильові смуги й фронти, які на радарі темні, як нафта. Нафтовидобутку тут немає. Усе, що конвеєр тут позначає як «схоже на нафту», — хибні тривоги; набір показує, як часто вони трапляються.",
  "baltic-bloom-twin-2026":
    "Контрольний район без нафти: влітку 2026 року тут цвіли ціанобактерії (звіт SMHI № 8, 25.08.2026). Поверхневі скупчення водоростей гасять дрібні хвилі й на радарі темні, як нафта. Усе, що конвеєр тут позначає як «схоже на нафту», — хибні тривоги; набір показує, як часто вони трапляються.",
  "uae-gem2-umm-al-quwain-2026":
    "Супертанкер (за даними аналітиків — GEM No. 2) уражено 09.10.2026; з 19.10 з нього витікала нафта приблизно за 25 км від Умм-ель-Кайвайна, 22.10 нафта дійшла до берега, 30.10 виток зупинено. Точне місце танкера не опубліковано. Під час витоку майже штиль (~2–3 м/с), тому на L-band пляму важко відрізнити від штилю. Плями виділено автоматично за знімками NISAR L-band (HH); оцінка «схоже на нафту» — ранжування для перевірки, а не доказ. Дати до 09.10 — контроль без витоку.",
};

export function localizeTitle(id: string, rawTitle: string, lang: Lang): string {
  if (lang === "uk" && UK_LOCATION_TITLES[id]) {
    return UK_LOCATION_TITLES[id];
  }
  return rawTitle;
}

export function localizeDescription(id: string, rawDesc: string, lang: Lang): string {
  if (lang === "uk" && UK_LOCATION_DESCRIPTIONS[id]) {
    return UK_LOCATION_DESCRIPTIONS[id];
  }
  return rawDesc;
}

const UK_SNAPSHOT_LABELS: Record<string, string> = {
  "Grounding day": "День посадки на мілину",
  "Day before the oil reached the shore": "Напередодні виходу нафти на берег",
  "Wide plume to the north-east": "Широкий шлейф на північний схід",
  "Largest slick area": "Найбільша площа плями",
  "Last image of the series": "Останній знімок серії",
  "Trace from the point before the first NOAA report": "Слід від точки ще до першого повідомлення NOAA",
  "No independent confirmation": "Без незалежного підтвердження",
  "Slick near the vent visible on the image": "Пляму біля вента видно на знімку",
  "Slick near the wreck visible on the image": "Пляму біля судна видно на знімку",
  "Slick near the seeps visible on the image": "Пляму біля сипів видно на знімку",
  "Slick near the oil field visible on the image": "Пляму біля промислу видно на знімку",
  "NOAA analysts saw a slick on this day": "Аналітики NOAA бачили пляму цього дня",
  "Sentinel-1 saw a slick on this day": "Sentinel-1 бачив пляму цього дня",
  "Cyanobacteria bloom: no oil": "Цвітіння ціанобактерій: нафти немає",
  "Wind shadow: no oil": "Вітрова тінь: нафти немає",
  "Leak ongoing": "Виток триває",
  "Leak: Sentinel-1 saw a slick on this day": "Виток: Sentinel-1 бачив пляму цього дня",
  "Before the tanker was struck (control)": "До ураження танкера (контроль)",
  "After the leak was stopped (30.10): remains of the slick": "Після зупинки витоку (30.10): залишки плями",
  "After the tanker was struck, before a visible leak": "Після ураження танкера, до помітного витоку",
};

export function localizeSnapshotLabel(rawLabel: string, lang: Lang): string {
  if (lang !== "uk") return rawLabel;
  if (UK_SNAPSHOT_LABELS[rawLabel]) return UK_SNAPSHOT_LABELS[rawLabel];

  let m = rawLabel.match(/^Day (\d+) after the first report$/);
  if (m) return `${m[1]}-й день після першого повідомлення`;

  m = rawLabel.match(/^Day (\d+) after grounding$/);
  if (m) return `${m[1]}-й день після посадки`;

  m = rawLabel.match(/^(\d+) days after the oil reached the shore$/);
  if (m) return `${m[1]} днів після виходу на берег`;

  m = rawLabel.match(/^Before the first NOAA report \((.+)\)$/);
  if (m) return `До першого повідомлення NOAA (${m[1]})`;

  m = rawLabel.match(/^After the last NOAA report \((.+)\)$/);
  if (m) return `Після останнього звіту NOAA (${m[1]})`;

  return rawLabel;
}

const NOTE_REPLACEMENTS_EN_TO_UK: [string, string][] = [
  [
    "The slick at the tanker is taken from the reference labelling of this known event (method battery, origin = reference): the automatic pipeline does not outline it at this early stage of the chronic leak",
    "Пляму біля танкера взято з еталонної розмітки відомої події (батарея методів, origin = reference): автоматичний конвеєр на ранній стадії хронічного витоку її не виділяє",
  ],
  [
    "On this date neither the automatic pipeline nor the reference labelling outlines the slick at the tanker (weak contrast in VV)",
    "На цю дату пляму біля танкера не виділяє ні автоматичний конвеєр, ні еталонна розмітка (слабкий контраст у VV)",
  ],
  [
    "The place where the oil reached the shore (Ras Madrakah, southern Masirah) is outside the frame",
    "Місце виходу нафти на берег (Рас-Мадрака, південь Масіри) — за межами кадру",
  ],
  [
    "There is no oil in the area: marked slicks are false alarms.",
    "Нафти в цьому районі немає: виділені плями — хибні тривоги.",
  ],
  [
    "Sentinel-1 on this day (almost simultaneously): slick of",
    "Sentinel-1 цього дня (майже одночасно): пляма",
  ],
  ["in the leak area (Cerulean).", "у районі витоку (Cerulean)."],
  [
    "NOAA analysts reported a slick on this day from other satellites.",
    "Аналітики NOAA бачили пляму в цей день на знімках інших супутників.",
  ],
  ["A slick near the seep field is visible on the image.", "Візуально на знімку видно пляму біля поля сипів."],
  ["A slick near the leak point is visible on the image.", "Візуально на знімку видно пляму біля точки витоку."],
  ["A slick near the vent is visible on the image.", "Візуально на знімку видно пляму біля вента."],
  ["A slick near the wreck is visible on the image.", "Візуально на знімку видно пляму біля судна."],
  ["A slick near the oil field is visible on the image.", "Візуально на знімку видно пляму біля промислу."],
  ["The pipeline does not outline a slick near the seep field.", "Конвеєр пляму біля поля сипів не виділяє."],
  ["The pipeline does not outline a slick near the leak point.", "Конвеєр пляму біля точки витоку не виділяє."],
  ["The pipeline does not outline a slick near the vent.", "Конвеєр пляму біля вента не виділяє."],
  ["The pipeline does not outline a slick near the wreck.", "Конвеєр пляму біля судна не виділяє."],
  ["The pipeline does not outline a slick near the oil field.", "Конвеєр пляму біля промислу не виділяє."],
  ["The pipeline outlines a slick near the seep field", "Конвеєр виділяє пляму біля поля сипів"],
  ["The pipeline outlines a slick near the leak point", "Конвеєр виділяє пляму біля точки витоку"],
  ["The pipeline outlines a slick near the vent", "Конвеєр виділяє пляму біля вента"],
  ["The pipeline outlines a slick near the wreck", "Конвеєр виділяє пляму біля судна"],
  ["The pipeline outlines a slick near the oil field", "Конвеєр виділяє пляму біля промислу"],
  [
    "is a dark patch with a bright rim, typical of a rain cell, not oil (checked visually); the current score is wrong here.",
    "— темна пляма зі світлим обідком, характерна для дощової комірки, а не нафти (перевірено візуально); поточна оцінка тут помилкова.",
  ],
  ["A large", "Велика ділянка"],
  ["area in the south-west of the frame scored as probable oil", "на південному заході кадру, оцінена як «схоже на нафту»,"],
  ["area in the north-east of the frame scored as probable oil", "на північному сході кадру, оцінена як «схоже на нафту»,"],
  ["Wind near the seep field", "Вітер біля поля сипів"],
  ["Wind near the leak point", "Вітер біля точки витоку"],
  ["Wind near the vent", "Вітер біля вента"],
  ["Wind near the wreck", "Вітер біля судна"],
  ["Wind near the oil field", "Вітер біля промислу"],
  ["Wind in the area", "Вітер у районі"],
  ["Wind", "Вітер"],
  ["m/s", "м/с"],
  ["km²", "км²"],
  ["near calm: dark areas may not be oil.", "майже штиль: темні ділянки можуть бути не нафтою."],
  ["strong wind: thin slicks are hard to see.", "сильний вітер: тонкі плями погано видно."],
  ["probable oil", "«схоже на нафту»"],
  ["possible oil", "«можливо нафта»"],
  ["score", "оцінка"],
];

export function localizeSnapshotNote(rawNote: string, lang: Lang): string {
  if (lang !== "uk" || !rawNote) return rawNote;
  let out = rawNote;
  for (const [en, uk] of NOTE_REPLACEMENTS_EN_TO_UK) {
    if (out.includes(en)) {
      out = out.split(en).join(uk);
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
