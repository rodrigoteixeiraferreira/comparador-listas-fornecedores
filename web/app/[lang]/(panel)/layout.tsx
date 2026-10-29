import { Suspense } from "react";
import { DemoBadge } from "@/components/DemoBadge";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { NavLinks } from "@/components/NavLinks";
import { signOut } from "@/lib/actions";
import { getQueueCount } from "@/lib/data";
import { getDictionary, localeOf } from "@/lib/i18n";
import { requireUser } from "@/lib/supabase/server";

export default async function PanelLayout({ children, params }: LayoutProps<"/[lang]">) {
  const lang = localeOf((await params).lang);
  const d = getDictionary(lang);
  const db = await requireUser(lang);
  const inReview = await getQueueCount(db);
  return (
    <>
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-8 pt-7">
          <div className="flex items-center justify-between gap-6">
            <p className="text-lg font-semibold tracking-tight">
              <span className="text-accent">{d.brand.store}</span>
              <span className="text-ink-3"> · </span>
              {d.brand.product}
            </p>
            <div className="flex items-center gap-4">
              <DemoBadge text={d.badge} />
              <Suspense>
                <LanguageSwitch current={lang} label={d.language} />
              </Suspense>
              <form action={signOut.bind(null, lang)}>
                <button className="text-sm text-ink-3 hover:text-ink">{d.logout}</button>
              </form>
            </div>
          </div>
          <NavLinks
            items={[
              { href: `/${lang}`, label: d.nav.status },
              { href: `/${lang}/compare`, label: d.nav.compare },
              { href: `/${lang}/review`, label: d.nav.review, count: inReview },
            ]}
          />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-8 pt-12 pb-24">{children}</main>
    </>
  );
}
