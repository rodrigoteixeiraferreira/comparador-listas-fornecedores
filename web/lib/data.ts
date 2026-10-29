import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Named } from "./format";

// As leituras do painel: uma view por tela (migração 0600). Nenhuma conta aqui; o banco entrega pronta.

export type BaseStatus = {
  products: number;
  with_supplier: number;
  one_supplier: number;
  two_suppliers: number;
  three_or_more: number;
  compared: number;
  by_reviewer: number;
  by_barcode: number;
  by_supplier_code: number;
  by_attributes: number;
  by_similarity: number;
  confirmed: number;
  auto_confirmed: number;
  contradictions: number;
  in_review: number;
  not_carried: number;
  open_disagreements: number;
  updated_at: string | null;
};

export type GateCheck = {
  number: number;
  code: string;
  passed: boolean | null;
  measured: Record<string, number>;
  detail: string;
};

export type ListRow = {
  price_list_id: number;
  supplier_code: string;
  supplier_name: string;
  period: string;
  status: "active" | "replaced" | "held" | "pending";
  file_name: string;
  file_format: "xlsx" | "pdf" | "image";
  gate: GateCheck[] | null;
  lines: number;
  confirmed: number;
  in_review: number;
  not_carried: number;
  unmatched: number;
};

export type RuleRow = {
  code: string;
  mode: "on" | "trial" | "off";
  mode_before: string | null;
  population: number | null;
  sample: number | null;
  errors: number | null;
  upper_95: number | null;
};

export type ProductRow = Named & {
  product_id: number;
  barcode: string | null;
  description: string;
  cost: number | null;
  section_code: string | null;
  section_pt: string | null;
  section_es: string | null;
  section_en: string | null;
  suppliers: number;
  competing_offers: number;
  offers_price_in_doubt: number;
  best_price: number | null;
  best_vs_cost: number | null;
};

export type OfferRow = {
  product_id: number;
  list_line_id: number;
  supplier_name: string;
  file_name: string;
  file_format: "xlsx" | "pdf" | "image";
  period: string;
  line_description: string;
  vat_included: boolean;
  units_per_box: number | null;
  level: number;
  reason: string;
  unit_price: number;
  diff: number | null;
  diff_share: number | null;
  price_ok: boolean;
  price_rank: number | null;
};

export type QueueRow = Named & {
  list_line_id: number;
  supplier_code: string;
  supplier_name: string;
  period: string;
  file_name: string;
  file_format: "xlsx" | "pdf" | "image";
  source_row: number;
  item_code: string;
  description: string;
  list_price: number | null;
  vat_included: boolean;
  units_per_box: number | null;
  unit_price: number | null;
  type_code: string | null;
  brand_code: string | null;
  variety_code: string | null;
  leftover: string[];
  ambiguous: string[];
  proposed_product_id: number | null;
  reason: string | null;
};

export type OptionRow = {
  list_line_id: number;
  product_id: number;
  position: number;
  score: number | null;
  proposed: boolean;
  type_differs: boolean;
  brand_differs: boolean;
  variety_differs: boolean;
  size_differs: boolean;
  pack_differs: boolean;
  line_only_words: string[];
  product_only_words: string[];
  price_to_cost: number | null;
  contradicts: boolean;
};

function rows<T>(result: { data: unknown; error: { message: string } | null }): T[] {
  if (result.error) throw new Error(result.error.message);
  return (result.data ?? []) as T[];
}

export async function getStatus(db: SupabaseClient) {
  const [status, lists, rules] = await Promise.all([
    db.from("base_status").select("*").single(),
    db.from("list_overview").select("*").order("period", { ascending: false }).order("supplier_name"),
    db.from("rule_status").select("*").order("level").order("code"),
  ]);
  if (status.error) throw new Error(status.error.message);
  return {
    status: status.data as BaseStatus,
    lists: rows<ListRow>(lists),
    rules: rows<RuleRow>(rules),
  };
}

export type CompareFilter = { q: string; section: string; min: 1 | 2 | 3 };

export async function getComparison(db: SupabaseClient, filter: CompareFilter, lang: string) {
  let query = db
    .from("product_overview")
    .select("*")
    .not("suppliers", "lt", filter.min)
    .order("product_id"); // a ordem do cadastro da loja
  if (filter.section) query = query.eq("section_code", filter.section);
  // a busca vale para a descrição da loja, a marca e o tipo no idioma de quem lê; só letras, números e espaço
  const q = filter.q.replace(/[^\p{L}\p{N} ]/gu, " ").trim();
  if (q) query = query.or(`description.ilike.*${q}*,brand.ilike.*${q}*,type_${lang}.ilike.*${q}*`);
  const products = rows<ProductRow>(await query);
  const offers = products.length
    ? rows<OfferRow>(
        await db
          .from("comparison_offer")
          .select("*")
          .in("product_id", products.map((p) => p.product_id))
          .order("price_ok", { ascending: false })
          .order("unit_price"),
      )
    : [];
  return { products, offers };
}

export async function getSections(db: SupabaseClient) {
  return rows<{ code: string; name_pt: string; name_es: string; name_en: string }>(
    await db.from("section").select("code, name_pt, name_es, name_en").order("code"),
  );
}

export async function getQueue(db: SupabaseClient) {
  const queue = rows<QueueRow>(
    await db.from("review_queue").select("*").order("supplier_name").order("source_row"),
  );
  const ids = queue.map((q) => q.list_line_id);
  const options = ids.length
    ? rows<OptionRow>(
        await db.from("review_option").select("*").in("list_line_id", ids).order("position"),
      )
    : [];
  const productIds = [...new Set(options.map((o) => o.product_id))];
  const products = productIds.length
    ? rows<ProductRow>(await db.from("product_overview").select("*").in("product_id", productIds))
    : [];
  return { queue, options, products };
}

export async function getQueueCount(db: SupabaseClient): Promise<number> {
  const { count, error } = await db.from("review_queue").select("list_line_id", { count: "exact", head: true });
  if (error) throw new Error(error.message);
  return count ?? 0;
}
