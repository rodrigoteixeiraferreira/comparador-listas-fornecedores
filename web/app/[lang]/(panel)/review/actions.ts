"use server";

import { refresh } from "next/cache";
import { createClient } from "@/lib/supabase/server";

export type Decision = "confirm" | "reject" | "not_carried";

// Os três botões da revisão. Quem grava é o banco, pelas três funções da migração 0600, e só para quem fez login;
// a conferência daqui é a primeira, não a única.
export async function decide(kind: Decision, line: number, product: number | null): Promise<{ error?: string }> {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims) return { error: "login required" };
  if (!Number.isInteger(line) || (kind !== "not_carried" && !Number.isInteger(product))) return { error: "invalid" };
  const { error } =
    kind === "confirm"
      ? await supabase.rpc("review_confirm", { p_list_line_id: line, p_product_id: product })
      : kind === "reject"
        ? await supabase.rpc("review_reject", { p_list_line_id: line, p_product_id: product })
        : await supabase.rpc("review_not_carried", { p_list_line_id: line });
  if (error) return { error: error.message };
  refresh();
  return {};
}
