"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { LOCALES } from "@/lib/i18n/locales";

// troca só o idioma da rota; a página e os filtros ficam
export function LanguageSwitch({ current, label }: { current: string; label: string }) {
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const rest = pathname.split("/").slice(2).join("/");
  return (
    <div aria-label={label} className="flex overflow-hidden rounded-full border border-line-strong text-xs font-semibold">
      {LOCALES.map((lang) => (
        <Link
          key={lang}
          href={`/${lang}${rest ? `/${rest}` : ""}${search ? `?${search}` : ""}`}
          aria-current={lang === current ? "true" : undefined}
          className={`px-3 py-1.5 uppercase tracking-wider ${
            lang === current ? "bg-accent text-accent-ink" : "text-ink-2 hover:text-ink"
          }`}
        >
          {lang}
        </Link>
      ))}
    </div>
  );
}
