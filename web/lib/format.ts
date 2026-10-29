// Só formatação: toda conta (preço por unidade, diferença, posição) já vem pronta do banco.
import { INTL, type Locale } from "./i18n/locales";

export function money(value: number | string | null, lang: Locale): string {
  if (value === null) return "—";
  return new Intl.NumberFormat(INTL[lang], {
    style: "currency",
    currency: "ARS",
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 2,
  }).format(Number(value));
}

// a diferença contra o custo, sempre com o sinal: −$ 420,00
export function signedMoney(value: number | string, lang: Locale): string {
  const n = Number(value);
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return sign + money(Math.abs(n), lang);
}

export function percent(share: number | string | null, lang: Locale, digits = 1, signed = false): string {
  if (share === null) return "—";
  return new Intl.NumberFormat(INTL[lang], {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: signed ? "exceptZero" : "auto",
  })
    .format(Number(share))
    .replace("-", "−");
}

export function decimal(value: number | string, lang: Locale, digits = 2): string {
  return new Intl.NumberFormat(INTL[lang], { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(
    Number(value),
  );
}

export function integer(value: number | string, lang: Locale): string {
  return new Intl.NumberFormat(INTL[lang]).format(Number(value));
}

// 500 g, 1 kg, 1,5 L, 12 un; o pack na frente: 6 × 1,5 L
export function size(size: number | null, unit: string | null, pack: number | null, lang: Locale): string {
  if (size === null || unit === null) return "";
  const n = (v: number) => new Intl.NumberFormat(INTL[lang], { maximumFractionDigits: 2 }).format(v);
  const text =
    unit === "g" && size >= 1000
      ? `${n(size / 1000)} kg`
      : unit === "ml" && size >= 1000
        ? `${n(size / 1000)} L`
        : `${n(size)} ${unit}`;
  return pack && pack > 1 ? `${pack} × ${text}` : text;
}

export function month(period: string, lang: Locale): string {
  const [year, m] = period.split("-").map(Number);
  return new Intl.DateTimeFormat(INTL[lang], { month: "short", year: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(year, m - 1, 15)),
  );
}

export function dateTime(iso: string | null, lang: Locale): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(INTL[lang], {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date(iso));
}

// os nomes em espanhol vêm do vocabulário do extrator: maiúsculas e sem acento. Para exibir, minúsculas e os
// acentos das palavras que os têm
const SPANISH_ACCENTS: Record<string, string> = {
  almacen: "almacén",
  atun: "atún",
  azucar: "azúcar",
  cafe: "café",
  clasica: "clásica",
  clasicas: "clásicas",
  clasico: "clásico",
  jabon: "jabón",
  limon: "limón",
  pure: "puré",
  tirabuzon: "tirabuzón",
};

function spanish(text: string): string {
  return text
    .toLowerCase()
    .split(" ")
    .map((w) => SPANISH_ACCENTS[w] ?? w)
    .join(" ");
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// a inicial minúscula no meio da frase, menos na sigla (UHT milk)
function midSentence(text: string): string {
  return /^[A-Z][a-z]/.test(text) ? text.charAt(0).toLowerCase() + text.slice(1) : text;
}

export function sectionName(row: { section_pt: string | null; section_es: string | null; section_en: string | null },
                            lang: Locale): string {
  const name = lang === "pt" ? row.section_pt : lang === "es" ? row.section_es : row.section_en;
  if (!name) return "";
  return lang === "es" ? capitalize(spanish(name)) : name;
}

export type Named = {
  type_pt: string | null;
  type_es: string | null;
  type_en: string | null;
  variety_pt: string | null;
  variety_es: string | null;
  variety_en: string | null;
  brand: string | null;
  size: number | null;
  unit: string | null;
  pack: number | null;
};

export function typeName(row: Named, lang: Locale): string {
  const name = lang === "pt" ? row.type_pt : lang === "es" ? row.type_es : row.type_en;
  if (!name) return "";
  return lang === "es" ? capitalize(spanish(name)) : name;
}

export function varietyName(row: Named, lang: Locale): string {
  const name = lang === "pt" ? row.variety_pt : lang === "es" ? row.variety_es : row.variety_en;
  if (!name) return "";
  return lang === "es" ? spanish(name) : name;
}

// o nome que o sistema entendeu, montado pelos atributos, na ordem natural de cada idioma:
// «Erva-mate tradicional Tres Lunas 500 g», «Tres Lunas traditional yerba mate 500 g»
export function productName(row: Named, lang: Locale): string {
  const type = typeName(row, lang);
  const variety = varietyName(row, lang);
  const parts =
    lang === "en"
      ? [row.brand, variety, midSentence(type)]
      : [type, variety, row.brand];
  return [...parts, size(row.size, row.unit, row.pack, lang)].filter(Boolean).join(" ");
}
