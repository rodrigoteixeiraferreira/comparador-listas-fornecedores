import type { ReactNode } from "react";

// a etiqueta do que veio de fora como veio: a linha do fornecedor não se traduz
export function OriginalTag({ text, hint }: { text: string; hint: string }) {
  return (
    <span
      title={hint}
      className="ml-2 inline-block rounded border border-line-strong px-1.5 py-0.5 align-middle text-[0.7rem] font-semibold tracking-wider text-ink-3 uppercase"
    >
      {text}
    </span>
  );
}

const TONES = {
  accent: "bg-accent text-accent-ink",
  note: "bg-note-soft text-note",
  good: "bg-good-soft text-good",
  bad: "bg-bad-soft text-bad",
  plain: "bg-surface-2 text-ink-2",
};

export function Pill({ tone = "plain", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${TONES[tone]}`}>
      {children}
    </span>
  );
}
