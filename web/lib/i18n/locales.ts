// os três idiomas do painel; o português abre quando o navegador não pede outro
export const LOCALES = ["pt", "es", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "pt";

// a formatação de número e data de cada um; o preço é sempre em pesos argentinos
export const INTL: Record<Locale, string> = { pt: "pt-BR", es: "es-AR", en: "en-US" };

export function isLocale(value: string | undefined): value is Locale {
  return (LOCALES as readonly string[]).includes(value ?? "");
}

// o primeiro idioma do Accept-Language que o painel tem
export function pickLocale(acceptLanguage: string | null): Locale {
  for (const part of (acceptLanguage ?? "").split(",")) {
    const code = part.split(";")[0].trim().slice(0, 2).toLowerCase();
    if (isLocale(code)) return code;
  }
  return DEFAULT_LOCALE;
}
