import Link from "next/link";
import type { ReactNode } from "react";
import { getStatus, type GateCheck, type RuleRow } from "@/lib/data";
import { dateTime, integer, month, percent } from "@/lib/format";
import { getDictionary, localeOf, type Dictionary } from "@/lib/i18n";
import { requireUser } from "@/lib/supabase/server";
import { fill } from "@/lib/text";

// A tela de entrada: quanto do cadastro já tem fornecedor, como cada par foi decidido, o controle do zero, as listas
// com o portão e a auditoria.
export default async function StatusPage({ params }: PageProps<"/[lang]">) {
  const lang = localeOf((await params).lang);
  const d = getDictionary(lang);
  const db = await requireUser(lang);
  const { status: s, lists, rules: unordered } = await getStatus(db);
  const rules = unordered.toSorted((a, b) => RULE_ORDER.indexOf(a.code) - RULE_ORDER.indexOf(b.code));
  const n = (v: number) => integer(v, lang);
  const share = (v: number) => `${(100 * v) / Math.max(s.products, 1)}%`;

  const how: { value: number; label: string; href?: string }[] = [
    { value: s.by_barcode, label: d.status.how.barcode },
    { value: s.by_supplier_code, label: d.status.how.supplierCode },
    { value: s.by_reviewer, label: d.status.how.reviewer },
    { value: s.by_attributes, label: d.status.how.attributes },
    ...(s.by_similarity ? [{ value: s.by_similarity, label: d.status.how.similarity }] : []),
    { value: s.in_review, label: d.status.how.review, href: `/${lang}/review` },
  ];

  return (
    <div className="flex flex-col gap-14">
      <section>
        <p className="eyebrow">{d.status.eyebrow}</p>
        <h1 className="mt-3 text-5xl font-semibold tracking-tight">{d.status.title}</h1>
        <p className="mt-3 text-ink-2">
          {fill(d.status.updated, { date: dateTime(s.updated_at, lang) })} · {d.priceNote}
        </p>
      </section>

      <section className="rounded-2xl border border-line bg-surface p-10">
        <p className="text-lg text-ink-2">{fill(d.status.ofProducts, { n: <strong className="text-ink">{n(s.products)}</strong> })}</p>
        <p className="mt-2 text-5xl font-semibold tracking-tight">
          {fill(d.status.withSupplier, { n: <span className="text-accent">{n(s.with_supplier)}</span> })}{" "}
          <span className="text-ink-3">({percent(s.with_supplier / Math.max(s.products, 1), lang, 0)})</span>
        </p>
        <div className="mt-8 flex h-4 overflow-hidden rounded-md bg-surface-2">
          <div className="bg-accent/35" style={{ width: share(s.one_supplier) }} />
          <div className="border-l-2 border-surface bg-accent/65" style={{ width: share(s.two_suppliers) }} />
          <div className="border-l-2 border-surface bg-accent" style={{ width: share(s.three_or_more) }} />
        </div>
        <div className="mt-4 flex flex-wrap gap-7 text-ink-2">
          <Legend tone="bg-accent/35" label={d.status.suppliers1} value={n(s.one_supplier)} />
          <Legend tone="bg-accent/65" label={d.status.suppliers2} value={n(s.two_suppliers)} />
          <Legend tone="bg-accent" label={d.status.suppliers3} value={n(s.three_or_more)} />
        </div>
        <p className="mt-6 text-ink-2">{fill(d.status.compared, { n: <strong className="text-ink">{n(s.compared)}</strong> })}</p>
      </section>

      <section>
        <h2 className="text-3xl font-semibold tracking-tight">{d.status.howTitle}</h2>
        <p className="mt-2 text-ink-2">{d.status.howLead}</p>
        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-5">
          {how.map((item) => {
            const card = (
              <div
                className={`h-full rounded-2xl border bg-surface p-6 ${
                  item.href ? "border-accent/60 hover:border-accent" : "border-line"
                }`}
              >
                <p className={`text-4xl font-semibold ${item.href ? "text-accent" : ""}`}>{n(item.value)}</p>
                <p className="mt-3 leading-snug text-ink-2">{item.label}</p>
              </div>
            );
            return item.href ? (
              <Link key={item.label} href={item.href}>
                {card}
              </Link>
            ) : (
              <div key={item.label}>{card}</div>
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="text-3xl font-semibold tracking-tight">{d.status.controlTitle}</h2>
        <div className="mt-6 flex flex-col gap-3">
          <Row>
            {fill(d.status.contradictions, {
              n: <strong className={s.contradictions ? "text-bad" : "text-good"}>{n(s.contradictions)}</strong>,
              total: <strong>{n(s.auto_confirmed)}</strong>,
            })}
            <span className="text-ink-3"> ({d.status.contradictionsHint})</span>
          </Row>
          <Row>{fill(d.status.notCarried, { n: <strong>{n(s.not_carried)}</strong> })}</Row>
          <Row>{fill(d.status.disagreements, { n: <strong>{n(s.open_disagreements)}</strong> })}</Row>
          <Row>{d.status.traceable}</Row>
        </div>
      </section>

      <section>
        <h2 className="text-3xl font-semibold tracking-tight">{d.status.listsTitle}</h2>
        <p className="mt-2 text-ink-2">{d.status.listsLead}</p>
        <div className="mt-6 overflow-hidden rounded-2xl border border-line">
          <table className="w-full text-left">
            <thead className="bg-surface-2 text-sm text-ink-3">
              <tr>
                <Th>{d.status.columns.supplier}</Th>
                <Th>{d.status.columns.month}</Th>
                <Th>{d.status.columns.status}</Th>
                <Th right>{d.status.columns.lines}</Th>
                <Th right>{d.status.columns.confirmed}</Th>
                <Th right>{d.status.columns.review}</Th>
                <Th right wrap>
                  {d.status.columns.notCarried}
                </Th>
                <Th>{d.status.columns.gate}</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {lists.map((l) => (
                <tr key={l.price_list_id} className={l.status === "active" ? "" : "text-ink-3"}>
                  <Td>
                    <p className={l.status === "active" ? "font-semibold" : ""}>{l.supplier_name}</p>
                    <p className="text-sm whitespace-nowrap text-ink-3">
                      {d.formats[l.file_format]} · {l.file_name}
                    </p>
                  </Td>
                  <Td nowrap>{month(l.period, lang)}</Td>
                  <Td nowrap>
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                        l.status === "active"
                          ? "bg-good-soft text-good"
                          : l.status === "held"
                            ? "bg-bad-soft text-bad"
                            : "bg-surface-2 text-ink-3"
                      }`}
                    >
                      {d.listStatus[l.status]}
                    </span>
                  </Td>
                  <Td right>{n(l.lines)}</Td>
                  <Td right>{n(l.confirmed)}</Td>
                  <Td right>{n(l.in_review + l.unmatched)}</Td>
                  <Td right>{n(l.not_carried)}</Td>
                  <Td>
                    <Gate checks={l.gate} d={d} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-ink-3">
          {[1, 2, 3, 4, 5, 6, 7]
            .map((i) => `${i} ${d.gate[GATE_CODES[i - 1] as keyof typeof d.gate]}`)
            .join(" · ")}
        </p>
        <p className="mt-1 text-sm text-ink-3">{d.status.gateLegend}</p>
      </section>

      <section>
        <h2 className="text-3xl font-semibold tracking-tight">{d.status.auditTitle}</h2>
        <p className="mt-2 max-w-4xl text-ink-2">{d.status.auditLead}</p>
        <div className="mt-6 overflow-hidden rounded-2xl border border-line">
          <table className="w-full text-left">
            <thead className="bg-surface-2 text-sm text-ink-3">
              <tr>
                <Th>{d.status.auditColumns.rule}</Th>
                <Th>{d.status.auditColumns.mode}</Th>
                <Th right>{d.status.auditColumns.sample}</Th>
                <Th right>{d.status.auditColumns.errors}</Th>
                <Th right>{d.status.auditColumns.upper}</Th>
                <Th>{d.status.auditColumns.decision}</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {rules.map((r) => (
                <tr key={r.code}>
                  <Td>{d.rules[r.code] ?? r.code}</Td>
                  <Td>
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                        r.mode === "on" ? "bg-good-soft text-good" : r.mode === "off" ? "bg-bad-soft text-bad" : "bg-note-soft text-note"
                      }`}
                    >
                      {d.modes[r.mode]}
                    </span>
                  </Td>
                  <Td right nowrap>
                    {r.sample === null ? "—" : fill(d.status.sampleOf, { n: n(r.sample), total: n(r.population ?? 0) })}
                  </Td>
                  <Td right>
                    {r.errors === null ? "—" : <span className={r.errors ? "font-semibold text-bad" : ""}>{n(r.errors)}</span>}
                  </Td>
                  <Td right>
                    {r.upper_95 === null ? "—" : fill(d.status.upTo, { pct: percent(r.upper_95, lang, 1) })}
                  </Td>
                  <Td>{ruleDecision(r, d)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

// as regras na ordem da cascata
const RULE_ORDER = ["barcode", "supplier_code", "attributes", "price_doubt_identity", "high_similarity"];

const GATE_CODES = ["count", "fidelity", "structure", "price_vs_cost", "price_change", "continuity", "zero_check"];

function ruleDecision(r: RuleRow, d: Dictionary): string {
  if (r.sample === null) return d.status.notAudited;
  if (r.mode_before !== r.mode) return r.mode === "off" ? d.ruleDecision.switchedOff : d.ruleDecision.promoted;
  return r.mode === "on" ? d.ruleDecision.keptOn : r.mode === "trial" ? d.ruleDecision.keptTrial : d.ruleDecision.keptOff;
}

function Gate({ checks, d }: { checks: GateCheck[] | null; d: Dictionary }) {
  if (!checks) return <span className="text-ink-3">—</span>;
  return (
    <div className="flex gap-[3px] whitespace-nowrap">
      {[...checks]
        .sort((a, b) => a.number - b.number)
        .map((c) => {
          const name = d.gate[c.code as keyof typeof d.gate] as string;
          const detail = c.detail ? `: ${d.gate.details[c.detail] ?? c.detail}` : "";
          return (
            <span
              key={c.number}
              title={`${c.number}. ${name}${detail}`}
              className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded text-xs font-bold ${
                c.passed === true ? "bg-good-soft text-good" : c.passed === false ? "bg-bad-soft text-bad" : "bg-surface-2 text-ink-3"
              }`}
            >
              {c.passed === true ? "✓" : c.passed === false ? "✗" : "–"}
            </span>
          );
        })}
    </div>
  );
}

function Legend({ tone, label, value }: { tone: string; label: string; value: string }) {
  return (
    <span className="flex items-center gap-2">
      <span className={`h-2.5 w-2.5 rounded-full ${tone}`} />
      {label} <strong className="text-ink">{value}</strong>
    </span>
  );
}

function Row({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-line bg-surface px-6 py-4 text-lg">{children}</div>;
}

// o cabeçalho fica numa linha; o longo (wrap) quebra em duas, no máximo
function Th({ children, right, wrap }: { children: ReactNode; right?: boolean; wrap?: boolean }) {
  return (
    <th className={`px-3 py-3 font-medium ${right ? "text-right" : ""} ${wrap ? "max-w-28" : "whitespace-nowrap"}`}>
      {children}
    </th>
  );
}

function Td({ children, right, nowrap }: { children: ReactNode; right?: boolean; nowrap?: boolean }) {
  return (
    <td className={`px-3 py-4 align-middle ${right ? "text-right tabular-nums" : ""} ${nowrap ? "whitespace-nowrap" : ""}`}>
      {children}
    </td>
  );
}
