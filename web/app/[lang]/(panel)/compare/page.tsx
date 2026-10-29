import { OriginalTag, Pill } from "@/components/Tags";
import { getComparison, getSections, type OfferRow, type ProductRow } from "@/lib/data";
import { decimal, integer, money, month, percent, productName, sectionName, signedMoney } from "@/lib/format";
import { getDictionary, localeOf, type Dictionary, type Locale } from "@/lib/i18n";
import { requireUser } from "@/lib/supabase/server";
import { fill } from "@/lib/text";

// Produto por produto: o custo da loja e a oferta de cada fornecedor, da mais barata para a mais cara. A oferta com o
// preço em dúvida aparece, marcada, e não disputa.
export default async function ComparePage({ params, searchParams }: PageProps<"/[lang]/compare">) {
  const lang = localeOf((await params).lang);
  const d = getDictionary(lang);
  const db = await requireUser(lang);
  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q.slice(0, 60) : "";
  const section = typeof sp.section === "string" ? sp.section : "";
  const min = ([1, 2, 3].includes(Number(sp.min)) ? Number(sp.min) : 2) as 1 | 2 | 3;
  const [{ products, offers }, sections] = await Promise.all([
    getComparison(db, { q, section, min }, lang),
    getSections(db),
  ]);
  const byProduct = Map.groupBy(offers, (o) => o.product_id);

  return (
    <div className="flex flex-col gap-10">
      <section>
        <p className="eyebrow">{d.compare.eyebrow}</p>
        <h1 className="mt-3 text-5xl font-semibold tracking-tight">
          {fill(d.compare.title, { n: integer(products.length, lang), min })}
        </h1>
        <p className="mt-3 max-w-3xl text-lg text-ink-2">{d.compare.lead}</p>
        <p className="mt-1 text-ink-3">{d.priceNote}</p>
      </section>

      <form action={`/${lang}/compare`} className="flex flex-wrap gap-3">
        <input
          name="q"
          defaultValue={q}
          placeholder={d.compare.search}
          className="min-w-72 flex-1 rounded-xl border border-line-strong bg-surface px-4 py-3 placeholder:text-ink-3 focus:border-accent focus:outline-none"
        />
        <select name="min" defaultValue={String(min)} className={SELECT}>
          {([1, 2, 3] as const).map((m) => (
            <option key={m} value={m}>
              {d.compare.minSuppliers[m]}
            </option>
          ))}
        </select>
        <select name="section" defaultValue={section} className={SELECT}>
          <option value="">{d.compare.allSections}</option>
          {sections.map((s) => (
            <option key={s.code} value={s.code}>
              {sectionName({ section_pt: s.name_pt, section_es: s.name_es, section_en: s.name_en }, lang)}
            </option>
          ))}
        </select>
        <button className="rounded-xl bg-accent px-6 py-3 font-semibold text-accent-ink hover:brightness-110">
          {d.compare.filter}
        </button>
      </form>

      {products.length === 0 && <p className="text-lg text-ink-2">{d.compare.empty}</p>}
      {products.map((p) => (
        <ProductCard key={p.product_id} product={p} offers={byProduct.get(p.product_id) ?? []} d={d} lang={lang} />
      ))}
    </div>
  );
}

const SELECT =
  "rounded-xl border border-line-strong bg-surface px-4 py-3 text-ink focus:border-accent focus:outline-none";

function ProductCard({ product: p, offers, d, lang }: { product: ProductRow; offers: OfferRow[]; d: Dictionary; lang: Locale }) {
  return (
    <article className="overflow-hidden rounded-2xl border border-line">
      <header className="flex items-start justify-between gap-6 bg-surface-2 px-7 py-5">
        <div>
          <h2 className="text-xl font-semibold">{productName(p, lang)}</h2>
          <p className="mt-1 text-sm text-ink-3">
            {fill(d.storeDescription, { text: p.description })} · {p.barcode} · {sectionName(p, lang)} ·{" "}
            {fill(d.compare.suppliersCount, { n: p.suppliers })}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-xs font-semibold tracking-widest text-ink-3 uppercase">{d.compare.yourCost}</p>
          <p className="text-2xl font-semibold">{money(p.cost, lang)}</p>
        </div>
      </header>
      <ul className="divide-y divide-line bg-surface">
        {offers.map((o) => (
          <li key={o.list_line_id} className={`flex justify-between gap-8 px-7 py-5 ${o.price_ok ? "" : "opacity-80"}`}>
            <div>
              <p className="text-lg">
                {o.line_description}
                <OriginalTag text={d.original} hint={d.originalHint} />
              </p>
              <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-3">
                <span>
                  {o.supplier_name} · {o.file_name} · {month(o.period, lang)}
                </span>
                {o.file_format === "image" && <Pill tone="note">{d.compare.fromPhoto}</Pill>}
                {o.units_per_box && o.units_per_box > 1 && (
                  <Pill tone="note">{fill(d.compare.perBox, { n: o.units_per_box })}</Pill>
                )}
                {!o.vat_included && <Pill>{d.compare.vatAdded}</Pill>}
              </p>
              <p className="mt-3 text-xs font-semibold tracking-widest text-ink-3 uppercase">{d.compare.howIdentified}</p>
              <p className="text-ink-2">{d.reasons[o.reason as keyof typeof d.reasons] ?? o.reason}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className="flex items-center justify-end gap-2 text-xl font-semibold">
                {o.price_rank === 1 && p.competing_offers >= 2 && <Pill tone="accent">{d.compare.cheapest}</Pill>}
                {money(o.unit_price, lang)}
              </p>
              {o.diff !== null && (
                <p className={`mt-1 tabular-nums ${Number(o.diff) < 0 ? "text-good" : Number(o.diff) > 0 ? "text-bad" : "text-ink-3"}`}>
                  {signedMoney(o.diff, lang)} · {percent(o.diff_share, lang, 1, true)}
                </p>
              )}
              {!o.price_ok && (
                <div className="mt-2 flex max-w-64 flex-col items-end gap-1">
                  <Pill tone="bad">{d.compare.priceInDoubt}</Pill>
                  <p className="text-sm text-ink-3">
                    {fill(d.compare.priceInDoubtHint, { ratio: decimal(1 + Number(o.diff_share ?? 0), lang, 1) })}
                  </p>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </article>
  );
}
