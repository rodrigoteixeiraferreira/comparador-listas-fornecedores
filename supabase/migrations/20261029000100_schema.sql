-- O esquema: dados de referência, cadastro da loja, listas, decisões humanas e pares.
-- Os nomes estão em inglês; os comentários, em português.

create extension if not exists pg_trgm with schema extensions;

-- === Referência: o que o sistema sabe de antemão, nos três idiomas da tela ========================================

create table public.section (
  code text primary key,
  name_es text not null,
  name_pt text not null,
  name_en text not null
);

create table public.product_type (
  code text primary key,
  section_code text not null references public.section (code),
  unit text not null check (unit in ('g', 'ml', 'un')),
  name_es text not null,
  name_pt text not null,
  name_en text not null
);
create index product_type_section_idx on public.product_type (section_code);

create table public.variety (
  type_code text not null references public.product_type (code),
  code text not null,
  is_default boolean not null default false,  -- a variedade subentendida quando a linha não diz nenhuma
  name_es text not null default '',
  name_pt text not null default '',
  name_en text not null default '',
  primary key (type_code, code)
);
create unique index variety_one_default_idx on public.variety (type_code) where is_default;

create table public.brand (
  code text primary key,
  name text not null unique,
  display text not null
);

create table public.supplier (
  code text primary key,
  name text not null unique,
  file_format text not null check (file_format in ('xlsx', 'pdf', 'image')),
  prices_include_vat boolean not null
);

-- o vocabulário: as escritas que o sistema reconhece; o termo errado se desativa, nunca se apaga
create table public.vocabulary_term (
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('type', 'variety', 'brand', 'noise')),
  term text not null,  -- as palavras já normalizadas: maiúsculas, sem acento, sem palavra vazia
  canonical text,  -- o código do tipo, da variedade ou da marca; vazio no ruído
  type_code text references public.product_type (code),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique nulls not distinct (kind, term, canonical, type_code)
);
create index vocabulary_term_type_idx on public.vocabulary_term (type_code);

-- === O cadastro da loja ============================================================================================

create table public.product (
  id bigint primary key,  -- o código interno da loja
  barcode text unique,
  description text not null,
  cost numeric(12, 2) check (cost > 0),  -- o último custo pago, com IVA
  -- o que o extrator leu na descrição
  normalized_text text not null,
  type_code text references public.product_type (code),
  brand_code text references public.brand (code),
  variety_code text,
  size integer check (size > 0),
  unit text check (unit in ('g', 'ml', 'un')),
  pack integer not null default 1 check (pack >= 1),
  leftover text[] not null default '{}',  -- a palavra que sobra, em ordem alfabética
  active boolean not null default true,
  updated_at timestamptz not null default now(),
  foreign key (type_code, variety_code) references public.variety (type_code, code)
);
create index product_attributes_idx on public.product (type_code, brand_code, size, unit, pack);
create index product_brand_idx on public.product (brand_code);
create index product_text_trgm_idx on public.product using gin (normalized_text extensions.gin_trgm_ops);

-- === As listas dos fornecedores ====================================================================================

-- a lista entra «pending»; o portão a deixa «active» (e a anterior vira «replaced») ou «held» (a anterior segue)
create table public.price_list (
  id bigint generated always as identity primary key,
  supplier_code text not null references public.supplier (code),
  period text not null check (period ~ '^\d{4}-\d{2}$'),
  file_name text not null,
  file_sha256 text not null,
  file_format text not null check (file_format in ('xlsx', 'pdf', 'image')),
  vat_included boolean not null,
  status text not null default 'pending' check (status in ('pending', 'active', 'held', 'replaced')),
  gate jsonb,  -- o resultado de cada conferência do portão
  loaded_at timestamptz not null default now(),
  decided_at timestamptz,
  unique (supplier_code, file_sha256)
);
create unique index price_list_one_active_idx on public.price_list (supplier_code) where status = 'active';

create table public.list_line (
  id bigint generated always as identity primary key,
  price_list_id bigint not null references public.price_list (id) on delete cascade,
  source_row integer not null,
  item_code text not null default '',  -- o código do fornecedor
  barcode text,
  description text not null,  -- como o fornecedor escreveu
  normalized_text text not null,
  price numeric(14, 2),  -- como está na lista: com ou sem IVA, da unidade ou da caixa
  case_units integer,  -- unidades da caixa fechada, quando a lista informa à parte
  section text not null default '',
  -- o que o extrator leu
  type_code text,
  brand_code text,
  variety_code text,
  size integer,
  unit text,
  pack integer not null default 1,
  units_per_box integer,  -- «CAJA X 12» na própria linha: o preço é da caixa
  leftover text[] not null default '{}',
  noise text[] not null default '{}',
  ambiguous text[] not null default '{}',
  unique (price_list_id, source_row)
);
create index list_line_barcode_idx on public.list_line (barcode) where barcode is not null;
create index list_line_item_code_idx on public.list_line (item_code);

-- === As decisões humanas: o «é» e o «não é» viram aprendizado ======================================================

-- o «é este»; com product_id vazio, «não é nenhum do cadastro» (a loja não tem): a linha não volta à revisão
create table public.equivalence (
  id bigint generated always as identity primary key,
  supplier_code text not null references public.supplier (code),
  normalized_text text not null,
  product_id bigint references public.product (id),
  decided_by text not null,
  note text,
  decided_at timestamptz not null default now(),
  unique (supplier_code, normalized_text)
);
create index equivalence_product_idx on public.equivalence (product_id);

create table public.rejection (
  id bigint generated always as identity primary key,
  supplier_code text not null references public.supplier (code),
  normalized_text text not null,
  product_id bigint not null references public.product (id),
  reason text,
  decided_by text not null,
  decided_at timestamptz not null default now(),
  unique (supplier_code, normalized_text, product_id)
);
create index rejection_product_idx on public.rejection (product_id);

-- === Os pares: cada linha com o produto, o nível de certeza e o motivo ============================================

-- nível 1: decisão humana; 2: código de barras; 3: regra forte; 4: em revisão (não conta como confirmado)
create table public.match (
  list_line_id bigint primary key references public.list_line (id) on delete cascade,
  product_id bigint not null references public.product (id),
  level smallint not null check (level between 1 and 4),
  step text not null check (step in ('barcode', 'supplier_code', 'equivalence', 'attributes', 'similarity')),
  reason text not null check (reason in ('same_barcode', 'learned_code', 'human_decision', 'unique_candidate',
                                         'price_far_from_cost', 'several_candidates', 'text_similarity')),
  score real,
  confirmed boolean generated always as (level <= 3) stored,
  matched_at timestamptz not null default now()
);
create index match_product_idx on public.match (product_id);

-- os candidatos que a revisão mostra, em ordem
create table public.candidate (
  list_line_id bigint not null references public.list_line (id) on delete cascade,
  product_id bigint not null references public.product (id),
  rank smallint not null,
  score real not null,
  primary key (list_line_id, product_id)
);
create index candidate_product_idx on public.candidate (product_id);
