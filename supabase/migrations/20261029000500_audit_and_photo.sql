-- O M2: cada tipo de decisão automática vira uma regra com modo (ligada, em teste, desligada); a auditoria por amostra
-- liga, deixa em teste ou desliga; e a fila das linhas da foto em que as duas leituras da IA discordaram.

-- === As regras de decisão ===========================================================================================

-- «on»: decide sozinha, no nível da regra; «trial»: a decisão fica registrada no nível 4 (revisão) até a amostra
-- mostrar que acerta; «off»: não decide (o tipo que errou acima do limite)
create table public.decision_rule (
  code text primary key,
  mode text not null check (mode in ('on', 'trial', 'off')),
  level smallint not null check (level between 2 and 3),  -- o nível do par quando a regra está ligada
  changed_at timestamptz not null default now(),
  evidence jsonb  -- a amostra que decidiu o modo: tamanho, erros, taxa e limite superior
);

insert into public.decision_rule (code, mode, level) values
  ('barcode', 'on', 2),
  ('supplier_code', 'on', 3),
  ('attributes', 'on', 3),
  -- em teste: atributos idênticos e candidato único, com o preço longe do custo (a identidade sem o preço)
  ('price_doubt_identity', 'trial', 3),
  -- em teste: o melhor candidato por semelhança de texto, quando a nota passa de 0,5
  ('high_similarity', 'trial', 3);

alter table public.match add column rule_code text references public.decision_rule (code);
create index match_rule_idx on public.match (rule_code);

alter table public.match drop constraint match_reason_check;
alter table public.match add constraint match_reason_check
  check (reason in ('same_barcode', 'learned_code', 'human_decision', 'unique_candidate', 'price_far_from_cost',
                    'several_candidates', 'text_similarity', 'high_similarity'));

-- === A auditoria por amostra ========================================================================================

-- a amostra se sorteia e se congela antes da primeira resposta; quem responde não vê o que a máquina decidiu ganhar
create table public.audit_round (
  id bigint generated always as identity primary key,
  seed integer not null,
  sample_per_rule integer not null,
  error_limit numeric not null default 0.02,
  created_at timestamptz not null default now(),
  finished_at timestamptz,
  result jsonb  -- por regra: amostra, erros, taxa observada, limite superior de 95% e a decisão
);

create table public.audit_item (
  round_id bigint not null references public.audit_round (id) on delete cascade,
  list_line_id bigint not null references public.list_line (id) on delete cascade,
  product_id bigint not null references public.product (id),
  rule_code text not null references public.decision_rule (code),
  answer text check (answer in ('right', 'wrong')),
  answered_by text,
  answered_at timestamptz,
  primary key (round_id, list_line_id)
);
create index audit_item_line_idx on public.audit_item (list_line_id);
create index audit_item_product_idx on public.audit_item (product_id);
create index audit_item_rule_idx on public.audit_item (rule_code);

-- === A fila de suporte da foto =======================================================================================

create table public.reading_disagreement (
  id bigint generated always as identity primary key,
  price_list_id bigint not null references public.price_list (id) on delete cascade,
  item_code text not null,
  reason text not null check (reason in ('only_one_reading', 'description', 'price', 'doubt')),
  reading_a jsonb,
  reading_b jsonb,
  resolved_at timestamptz
);
create index reading_disagreement_list_idx on public.reading_disagreement (price_list_id);

do $$
declare
  t text;
begin
  foreach t in array array['decision_rule', 'audit_round', 'audit_item', 'reading_disagreement']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy %I on public.%I for select to authenticated using (true)', t || '_read', t);
  end loop;
end;
$$;

-- === A cascata, agora obedecendo o modo de cada regra =================================================================

create or replace function public.run_cascade(p_list_id bigint)
returns table (cascade_step text, matched integer)
language plpgsql
set search_path = ''
as $$
declare
  v_supplier text;
  v_vat boolean;
  v_count integer;
  v_mode jsonb;  -- código da regra -> modo
begin
  select pl.supplier_code, pl.vat_included into v_supplier, v_vat
    from public.price_list pl
   where pl.id = p_list_id;
  if not found then
    raise exception 'price list % not found', p_list_id;
  end if;
  select jsonb_object_agg(r.code, r.mode) into v_mode from public.decision_rule r;

  delete from public.match m using public.list_line l
   where m.list_line_id = l.id and l.price_list_id = p_list_id;
  delete from public.candidate c using public.list_line l
   where c.list_line_id = l.id and l.price_list_id = p_list_id;

  -- 1. o mesmo código de barras, sem nenhuma contradição (o código velho de outro tamanho não passa)
  if v_mode ->> 'barcode' <> 'off' then
    insert into public.match (list_line_id, product_id, level, step, reason, rule_code)
    select l.id, p.id, case when v_mode ->> 'barcode' = 'on' then 2 else 4 end, 'barcode', 'same_barcode', 'barcode'
      from public.list_line l
      join public.product p on p.barcode = l.barcode and p.active
     where l.price_list_id = p_list_id
       and not public.contradicts(l, p)
       and not public.is_rejected(v_supplier, l.normalized_text, p.id);
    get diagnostics v_count = row_count;
  else
    v_count := 0;
  end if;
  cascade_step := 'barcode'; matched := v_count; return next;

  -- 2. o código do fornecedor, aprendido num par confirmado de uma lista anterior dele; o tipo, a marca e o
  --    tamanho precisam estar lidos e iguais (o código reaproveitado para outro produto não passa)
  if v_mode ->> 'supplier_code' <> 'off' then
    insert into public.match (list_line_id, product_id, level, step, reason, rule_code)
    select l.id, p.id, case when v_mode ->> 'supplier_code' = 'on' then 3 else 4 end, 'supplier_code',
           'learned_code', 'supplier_code'
      from public.list_line l
      join lateral (
        select m2.product_id
          from public.list_line l2
          join public.price_list pl2 on pl2.id = l2.price_list_id
          join public.match m2 on m2.list_line_id = l2.id and m2.confirmed
         where pl2.supplier_code = v_supplier
           and pl2.status in ('active', 'replaced')
           and pl2.id <> p_list_id
           and l2.item_code = l.item_code
         order by pl2.loaded_at desc, pl2.id desc
         limit 1
      ) learned on true
      join public.product p on p.id = learned.product_id and p.active
     where l.price_list_id = p_list_id
       and l.item_code <> ''
       and not exists (select 1 from public.match m where m.list_line_id = l.id)
       and l.type_code = p.type_code and l.brand_code = p.brand_code and l.size = p.size and l.unit = p.unit
       and not public.contradicts(l, p)
       and not public.is_rejected(v_supplier, l.normalized_text, p.id);
    get diagnostics v_count = row_count;
  else
    v_count := 0;
  end if;
  cascade_step := 'supplier_code'; matched := v_count; return next;

  -- 3. a equivalência confirmada: o que uma pessoa já respondeu para este texto deste fornecedor (sempre vale)
  insert into public.match (list_line_id, product_id, level, step, reason)
  select l.id, e.product_id, 1, 'equivalence', 'human_decision'
    from public.list_line l
    join public.equivalence e on e.supplier_code = v_supplier and e.normalized_text = l.normalized_text
    join public.product p on p.id = e.product_id and p.active  -- o «não é nenhum» (product_id vazio) não entra
   where l.price_list_id = p_list_id
     and not exists (select 1 from public.match m where m.list_line_id = l.id);
  get diagnostics v_count = row_count;
  cascade_step := 'equivalence'; matched := v_count; return next;

  -- 4. os atributos idênticos, a mesma palavra que sobra dos dois lados e um candidato só. Com o preço coerente com o
  --    custo, decide a regra «attributes»; com o preço longe, decide a «price_doubt_identity» (a identidade sem o
  --    preço). Mais de um candidato vai à revisão
  with cand as (
    select l.id as line_id, p.id as product_id,
           count(*) over (partition by l.id) as n,
           public.unit_price(l.price, v_vat, l.units_per_box) / p.cost as ratio
      from public.list_line l
      join public.product p
        on p.active
       and p.type_code = l.type_code and p.brand_code = l.brand_code and p.variety_code = l.variety_code
       and p.size = l.size and p.unit = l.unit and p.pack = l.pack and p.leftover = l.leftover
     where l.price_list_id = p_list_id
       and cardinality(l.ambiguous) = 0
       and not exists (select 1 from public.match m where m.list_line_id = l.id)
       and not public.is_not_carried(v_supplier, l.normalized_text)
       and not public.is_rejected(v_supplier, l.normalized_text, p.id)
  ), ranked as (
    select *,
           row_number() over (partition by line_id order by abs(coalesce(ratio, 99) - 1), product_id) as rank,
           case when n > 1 then null
                when ratio between 0.5 and 2 then 'attributes'
                else 'price_doubt_identity' end as rule
      from cand
  ), kept as (
    -- com a regra «attributes» desligada, a linha segue para a semelhança de texto, como qualquer outra
    select * from ranked
     where rule is null or rule = 'price_doubt_identity' or v_mode ->> rule <> 'off'
  ), cands as (
    insert into public.candidate (list_line_id, product_id, rank, score)
    select line_id, product_id, rank, 1 from kept
  )
  insert into public.match (list_line_id, product_id, level, step, reason, score, rule_code)
  select line_id, product_id,
         case when rule is not null and v_mode ->> rule = 'on' then 3 else 4 end,
         'attributes',
         case when n > 1 then 'several_candidates'
              when rule = 'attributes' then 'unique_candidate'
              else 'price_far_from_cost' end,
         ratio,
         case when rule is not null and v_mode ->> rule <> 'off' then rule end
    from kept
   where rank = 1;
  get diagnostics v_count = row_count;
  cascade_step := 'attributes'; matched := v_count; return next;

  -- 5. a semelhança de texto: só ordena os candidatos para a revisão (nível 4). Acima de 0,5, a regra em teste
  --    «high_similarity» registra a decisão que tomaria, para a amostra julgar
  insert into public.candidate (list_line_id, product_id, rank, score)
  select l.id, s.product_id, s.rank, s.score
    from public.list_line l
    cross join lateral (
      select x.product_id, x.score, row_number() over (order by x.score desc, x.product_id) as rank
        from (
          select p.id as product_id, extensions.similarity(p.normalized_text, l.normalized_text) as score
            from public.product p
           where p.active
             and not public.is_rejected(v_supplier, l.normalized_text, p.id)
        ) x
       where x.score >= 0.3
       order by x.score desc, x.product_id
       limit 3
    ) s
   where l.price_list_id = p_list_id
     and not exists (select 1 from public.match m where m.list_line_id = l.id)
     and not public.is_not_carried(v_supplier, l.normalized_text);

  insert into public.match (list_line_id, product_id, level, step, reason, score, rule_code)
  select c.list_line_id, c.product_id,
         case when c.score > 0.5 and v_mode ->> 'high_similarity' = 'on' then 3 else 4 end,
         'similarity',
         case when c.score > 0.5 and v_mode ->> 'high_similarity' <> 'off' then 'high_similarity'
              else 'text_similarity' end,
         c.score,
         case when c.score > 0.5 and v_mode ->> 'high_similarity' <> 'off' then 'high_similarity' end
    from public.candidate c
    join public.list_line l on l.id = c.list_line_id
   where l.price_list_id = p_list_id
     and c.rank = 1
     and not exists (select 1 from public.match m where m.list_line_id = c.list_line_id);
  get diagnostics v_count = row_count;
  cascade_step := 'similarity'; matched := v_count; return next;
end;
$$;

revoke execute on function public.run_cascade(bigint) from public, anon, authenticated;
