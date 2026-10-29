"use client";

import { useState, useTransition } from "react";
import { fillText } from "@/lib/text";
import { decide, type Decision } from "./actions";

const LOOK: Record<Decision, string> = {
  confirm: "bg-accent text-accent-ink hover:brightness-110",
  reject: "border border-line-strong text-ink hover:border-bad hover:text-bad",
  not_carried: "border border-line-strong text-ink hover:border-accent hover:text-accent",
};

type Props = {
  kind: Decision;
  line: number;
  product: number | null;
  label: string;
  saving: string;
  errorText: string;
};

export function DecisionButton({ kind, line, product, label, saving, errorText }: Props) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        disabled={pending}
        data-decision={kind}
        onClick={() =>
          start(async () => {
            const result = await decide(kind, line, product);
            setError(result.error ?? null);
          })
        }
        className={`rounded-lg px-4 py-2 text-sm font-semibold whitespace-nowrap transition disabled:opacity-50 ${LOOK[kind]}`}
      >
        {pending ? saving : label}
      </button>
      {error && <p className="text-xs text-bad">{fillText(errorText, { message: error })}</p>}
    </div>
  );
}
