"use client";

import { useActionState } from "react";
import { signIn } from "./actions";

type Labels = { email: string; password: string; submit: string; pending: string; error: string };

export function LoginForm({ lang, labels }: { lang: string; labels: Labels }) {
  const [state, action, pending] = useActionState(signIn.bind(null, lang), { failed: false });
  const field =
    "mt-1.5 w-full rounded-xl border border-line-strong bg-surface-2 px-4 py-3 focus:border-accent focus:outline-none";
  return (
    <form action={action} className="flex flex-col gap-5">
      <label className="text-sm text-ink-2">
        {labels.email}
        <input name="email" type="email" autoComplete="username" required className={field} />
      </label>
      <label className="text-sm text-ink-2">
        {labels.password}
        <input name="password" type="password" autoComplete="current-password" required className={field} />
      </label>
      {state.failed && <p className="text-sm text-bad">{labels.error}</p>}
      <button
        disabled={pending}
        className="rounded-xl bg-accent py-3 font-semibold text-accent-ink hover:brightness-110 disabled:opacity-60"
      >
        {pending ? labels.pending : labels.submit}
      </button>
    </form>
  );
}
