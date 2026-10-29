import { notFound } from "next/navigation";
import { en } from "./en";
import { es } from "./es";
import { isLocale, type Locale } from "./locales";
import { pt, type Dictionary } from "./pt";

const dictionaries: Record<Locale, Dictionary> = { pt, es, en };

export type { Dictionary, Locale };

// o idioma da rota: fora dos três, a página não existe
export function localeOf(lang: string): Locale {
  if (!isLocale(lang)) notFound();
  return lang;
}

export function getDictionary(lang: string): Dictionary {
  return dictionaries[localeOf(lang)];
}
