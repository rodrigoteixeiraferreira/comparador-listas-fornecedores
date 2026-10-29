import Link from "next/link";
import type { ReactNode } from "react";
import { OriginalTag, Pill } from "@/components/Tags";
import { getQueue, type OptionRow, type ProductRow, type QueueRow } from "@/lib/data";
import { decimal, integer, money, month, productName, size, typeName, varietyName } from "@/lib/format";
import { getDictionary, localeOf, type Dictionary, type Locale } from "@/lib/i18n";
import { requireUser } from "@/lib/supabase/server";
import { fill } from "@/lib/text";
import { DecisionButton } from "./DecisionButton";

// Só o que a máquina não pôde decidir. Para cada linha: o que o extrator leu, por que ela está aqui e os candidatos,
// com o que difere de cada um. A resposta («é este», «não é», «a loja não tem») vale para o texto do fornecedor.
export default async function ReviewPage({ params, searchParams }: PageProps<"/[lang]/review">) {
  const lang = localeOf((await params).lang);
  const d = getDictionary(lang);
  const db = await requireUser(lang);
  const supplier = (await searchParams).supplier;
  const { queue, options, products } = await getQueue(db);
  const bySupplier = Map.groupBy(queue, (q) => q.supplier_code);
  const shown = typeof supplier === "string" && bySupplier.has(supplier) ? bySupplier.get(supplier)! : queue;
  const optionsByLine = Map.groupBy(options, (o) => o.list_line_id);
  const product = new Map(products.map((p) => [p.product_id, p]));

  return (
    <div className="flex flex-col gap-10">
      <section>
        <p className="eyebrow">{d.review.eyebrow}</p>
        <h1 className="mt-3 text-5xl font-semibold tracking-tight">
          {queue.length ? fill(d.review.title, { n: integer(queue.length, lang) }) : d.review.titleEmpty}
        </h1>
        <p className="mt-3 max-w-3xl text-lg text-ink-2">{d.review.lead}</p>
      </section>

      {queue.length > 0 && (
        <nav className="flex flex-wrap gap-2">
          <Chip href={`/${lang}/review`} active={shown === queue}>
            {d.review.all} ({queue.length})
          </Chip>
          {[...bySupplier].map(([code, lines]) => (
            <Chip key={code} href={`/${lang}/review?supplier=${code}`} active={shown !== queue && supplier === code}>
              {lines[0].supplier_name} ({lines.length})
            </Chip>
          ))}
        </nav>
      )}

      {shown.map((q) => (
        <LineCard
          key={q.list_line_id}
          line={q}
          options={optionsByLine.get(q.list_line_id) ?? []}
          product={product}
          d={d}
          lang={lang}
        />
      ))}
    </div>
  );
}

function Chip({ href, active, children }: { href: string; active: boolean; children: ReactNode }) {
  return (
    <Link
      href={href}
      className={`rounded-full border px-4 py-1.5 text-sm ${
        active ? "border-accent bg-accent-soft text-accent" : "border-line-strong text-ink-2 hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}

type CardProps = {
  line: QueueRow;
  options: OptionRow[];
  product: Map<number, ProductRow>;
  d: Dictionary;
  lang: Locale;
};

function LineCard({ line: q, options, product, d, lang }: CardProps) {
  const notRead = <span className="text-ink-3 italic">{d.review.read.notRead}</span>;
  const buttons = { saving: d.review.saving, errorText: d.review.error };
  return (
    <article
      className="overflow-hidden rounded-2xl border border-line bg-surface"
      data-line={q.list_line_id}
      data-reason={q.reason ?? "none"}
    >
      <header className="flex items-start justify-between gap-6 border-b border-line bg-surface-2 px-7 py-5">
        <div>
          <p className="text-xl font-semibold">
            {q.description}
            <OriginalTag text={d.original} hint={d.originalHint} />
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-3">
            <span>
              {q.supplier_name} · {q.file_name} · {month(q.period, lang)} · {fill(d.review.row, { n: q.source_row })}
              {q.item_code && <> · {fill(d.review.code, { code: q.item_code })}</>}
            </span>
            {q.file_format === "image" && <Pill tone="note">{d.compare.fromPhoto}</Pill>}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-lg font-semibold">{fill(d.review.listPrice, { price: money(q.list_price, lang) })}</p>
          <p className="text-sm text-ink-3">{fill(d.review.unitPrice, { price: money(q.unit_price, lang) })}</p>
        </div>
      </header>

      <div className="grid gap-8 px-7 py-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="flex flex-col gap-6">
          <div>
            <Heading>{d.review.readTitle}</Heading>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-5 gap-y-1.5">
              <dt className="text-ink-3">{d.review.read.type}</dt>
              <dd>{typeName(q, lang) || notRead}</dd>
              <dt className="text-ink-3">{d.review.read.brand}</dt>
              <dd>{q.brand ?? notRead}</dd>
              <dt className="text-ink-3">{d.review.read.variety}</dt>
              <dd>{varietyName(q, lang) || notRead}</dd>
              <dt className="text-ink-3">{d.review.read.size}</dt>
              <dd>{size(q.size, q.unit, null, lang) || notRead}</dd>
              <dt className="text-ink-3">{d.review.read.pack}</dt>
              <dd>{q.pack && q.pack > 1 ? fill(d.review.read.packOf, { n: q.pack }) : d.review.read.single}</dd>
            </dl>
            <div className="mt-3 flex flex-wrap gap-2">
              {q.leftover.length > 0 && <Pill tone="note">{fill(d.review.leftover, { words: q.leftover.join(", ") })}</Pill>}
              {q.ambiguous.length > 0 && <Pill tone="note">{fill(d.review.ambiguous, { words: q.ambiguous.join(", ") })}</Pill>}
            </div>
          </div>
          <div>
            <Heading>{d.review.whyTitle}</Heading>
            <p className="mt-2 leading-relaxed text-ink-2">{d.review.why[q.reason ?? "none"] ?? d.review.why.none}</p>
          </div>
        </div>

        <div>
          <Heading>{d.review.optionsTitle}</Heading>
          <ul className="mt-3 flex flex-col gap-3">
            {options.map((o) => {
              const p = product.get(o.product_id);
              if (!p) return null;
              return (
                <li
                  key={o.product_id}
                  data-differs={differing(o).join(" ")}
                  data-description={p.description}
                  className={`flex justify-between gap-5 rounded-xl border p-4 ${o.proposed ? "border-accent/50" : "border-line"}`}
                >
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2">
                      <span className="text-ink-3">{fill(d.review.position, { n: o.position })}</span>
                      {o.proposed && <Pill tone="accent">{d.review.proposal}</Pill>}
                      <strong>{productName(p, lang)}</strong>
                    </p>
                    <p className="mt-1 text-sm text-ink-3">
                      {fill(d.storeDescription, { text: p.description })} ·{" "}
                      {fill(d.review.cost, { price: money(p.cost, lang) })}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">{differences(q, o, p, d, lang)}</div>
                  </div>
                  <div className="flex shrink-0 flex-col gap-2">
                    <DecisionButton kind="confirm" line={q.list_line_id} product={o.product_id} label={d.review.yes} {...buttons} />
                    <DecisionButton kind="reject" line={q.list_line_id} product={o.product_id} label={d.review.no} {...buttons} />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <footer className="flex items-center justify-end gap-4 border-t border-line px-7 py-4">
        <p className="text-sm text-ink-3">{d.review.notCarriedHint}</p>
        <DecisionButton kind="not_carried" line={q.list_line_id} product={null} label={d.review.notCarried} {...buttons} />
      </footer>
    </article>
  );
}

// os marcadores do que difere, para o script dos prints achar o exemplo certo
function differing(o: OptionRow): string[] {
  return [
    o.type_differs && "type",
    o.brand_differs && "brand",
    o.variety_differs && "variety",
    o.size_differs && "size",
    o.pack_differs && "pack",
    o.line_only_words.length > 0 && "line-only",
    o.product_only_words.length > 0 && "product-only",
  ].filter((x): x is string => Boolean(x));
}

// o que separa a linha do candidato: em vermelho o que difere; em neutro o que só informa
function differences(q: QueueRow, o: OptionRow, p: ProductRow, d: Dictionary, lang: Locale) {
  const out: ReactNode[] = [];
  const bad = (key: string, text: ReactNode) => out.push(<Pill key={key} tone="bad">{text}</Pill>);
  if (o.type_differs) bad("type", d.review.differs.type);
  if (o.brand_differs) bad("brand", d.review.differs.brand);
  if (o.variety_differs) bad("variety", d.review.differs.variety);
  if (o.size_differs)
    bad("size", fill(d.review.differs.size, { line: size(q.size, q.unit, null, lang), product: size(p.size, p.unit, null, lang) }));
  if (o.pack_differs) bad("pack", d.review.differs.pack);
  if (o.line_only_words.length) bad("lineOnly", fill(d.review.differs.lineOnly, { words: o.line_only_words.join(", ") }));
  if (o.product_only_words.length)
    bad("productOnly", fill(d.review.differs.productOnly, { words: o.product_only_words.join(", ") }));
  const anyDiff = out.length > 0;
  if (o.score !== null && Number(o.score) < 1)
    out.push(<Pill key="sim">{fill(d.review.similarity, { score: decimal(o.score, lang, 2) })}</Pill>);
  else if (!anyDiff) out.push(<Pill key="same" tone="good">{d.review.sameAttributes}</Pill>);
  if (o.price_to_cost !== null) {
    const ratio = Number(o.price_to_cost);
    out.push(
      <Pill key="price" tone={ratio < 0.5 || ratio > 2 ? "bad" : "plain"}>
        {fill(d.review.priceToCost, { ratio: decimal(ratio, lang, 2) })}
      </Pill>,
    );
  }
  return out;
}

function Heading({ children }: { children: ReactNode }) {
  return <h3 className="text-xs font-semibold tracking-widest text-ink-3 uppercase">{children}</h3>;
}
