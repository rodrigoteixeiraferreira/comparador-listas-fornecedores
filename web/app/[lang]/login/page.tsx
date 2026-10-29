import { Suspense } from "react";
import { DemoBadge } from "@/components/DemoBadge";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { getDictionary, localeOf } from "@/lib/i18n";
import { LoginForm } from "./LoginForm";

export default async function LoginPage({ params }: PageProps<"/[lang]/login">) {
  const lang = localeOf((await params).lang);
  const d = getDictionary(lang);
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-8 px-6">
      <div className="flex items-center justify-between">
        <DemoBadge text={d.badge} />
        <Suspense>
          <LanguageSwitch current={lang} label={d.language} />
        </Suspense>
      </div>
      <div>
        <p className="text-lg font-semibold">
          <span className="text-accent">{d.brand.store}</span>
          <span className="text-ink-3"> · </span>
          {d.brand.product}
        </p>
        <h1 className="mt-6 text-4xl font-semibold tracking-tight">{d.login.title}</h1>
        <p className="mt-3 text-ink-2">{d.login.lead}</p>
      </div>
      <div className="rounded-2xl border border-line bg-surface p-7">
        <LoginForm lang={lang} labels={d.login} />
      </div>
    </main>
  );
}
