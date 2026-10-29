-- O M3: o que o painel lê e as três decisões que ele grava. O painel só exibe; toda conta continua aqui.
-- A escrita pela API fica restrita aos três botões da revisão («é este», «não é», «a loja não tem»).

-- === Os privilégios ==================================================================================================

-- o Supabase dá todos os privilégios de tabela a anon e authenticated; as políticas já não deixavam escrever, e agora
-- nem o privilégio existe. O visitante sem login não lê nada. Tabela nova numa migração futura repete este bloco.
revoke insert, update, delete, truncate, references, trigger on all tables in schema public from anon, authenticated;
revoke select on all tables in schema public from anon;

-- === O produto, com os nomes nos três idiomas =========================================================================

-- o nome que o painel mostra sai dos atributos (tipo, variedade, marca, tamanho), no idioma de quem lê; a descrição
-- do cadastro fica como a loja escreveu
create view public.product_detail with (security_invoker = true) as
select p.id as product_id,
       p.barcode,
       p.description,
       p.cost,
       p.size,
       p.unit,
       p.pack,
       p.leftover,
       t.section_code,
       s.name_pt as section_pt,
       s.name_es as section_es,
       s.name_en as section_en,
       p.type_code,
       t.name_pt as type_pt,
       t.name_es as type_es,
       t.name_en as type_en,
       p.variety_code,
       v.name_pt as variety_pt,
       v.name_es as variety_es,
       v.name_en as variety_en,
       b.display as brand
  from public.product p
  left join public.product_type t on t.code = p.type_code
  left join public.section s on s.code = t.section_code
  left join public.variety v on v.type_code = p.type_code and v.code = p.variety_code
  left join public.brand b on b.code = p.brand_code
 where p.active;

-- === A comparação ====================================================================================================

-- cada oferta que vale, com a origem (fornecedor, arquivo, mês), como foi identificada e a diferença contra o custo.
-- price_rank ordena só as que competem: a do preço em dúvida aparece, mas não disputa
create view public.comparison_offer with (security_invoker = true) as
select o.product_id,
       o.list_line_id,
       o.supplier_code,
       sp.name as supplier_name,
       pl.file_name,
       pl.file_format,
       o.period,
       l.item_code,
       l.description as line_description,
       l.price as list_price,
       pl.vat_included,
       l.units_per_box,
       o.level,
       o.step,
       m.reason,
       o.unit_price,
       o.cost,
       o.unit_price - o.cost as diff,
       round(o.unit_price / o.cost - 1, 4) as diff_share,
       o.price_ok,
       case when o.price_ok
            then rank() over (partition by o.product_id, o.price_ok order by o.unit_price) end as price_rank
  from public.offer o
  join public.list_line l on l.id = o.list_line_id
  join public.price_list pl on pl.id = l.price_list_id
  join public.match m on m.list_line_id = o.list_line_id
  join public.supplier sp on sp.code = o.supplier_code;

-- produto por produto: quantos fornecedores, quantas ofertas competem, o melhor preço e quanto ele fica do custo
create view public.product_overview with (security_invoker = true) as
select d.*,
       a.suppliers,
       a.competing_offers,
       a.offers_price_in_doubt,
       a.best_price,
       round(a.best_price / d.cost - 1, 4) as best_vs_cost
  from public.product_detail d
  cross join lateral (
    select count(distinct o.supplier_code) as suppliers,
           count(*) filter (where o.price_ok) as competing_offers,
           count(*) filter (where not o.price_ok) as offers_price_in_doubt,
           min(o.unit_price) filter (where o.price_ok) as best_price
      from public.offer o
     where o.product_id = d.product_id
  ) a;

-- === A fila de revisão ==============================================================================================

-- as linhas das listas ativas que ninguém decidiu: o par em revisão (nível 4) ou nenhum par, fora o que a loja não tem.
-- O que o extrator entendeu vem com os nomes nos três idiomas; a palavra que sobra e a ambígua, como foram lidas
create view public.review_queue with (security_invoker = true) as
select l.id as list_line_id,
       pl.id as price_list_id,
       pl.supplier_code,
       sp.name as supplier_name,
       pl.period,
       pl.file_name,
       pl.file_format,
       l.source_row,
       l.item_code,
       l.barcode,
       l.description,
       l.price as list_price,
       pl.vat_included,
       l.units_per_box,
       public.unit_price(l.price, pl.vat_included, l.units_per_box) as unit_price,
       l.type_code,
       t.name_pt as type_pt,
       t.name_es as type_es,
       t.name_en as type_en,
       l.brand_code,
       b.display as brand,
       l.variety_code,
       v.name_pt as variety_pt,
       v.name_es as variety_es,
       v.name_en as variety_en,
       l.size,
       l.unit,
       l.pack,
       l.leftover,
       l.ambiguous,
       m.product_id as proposed_product_id,
       m.step,
       m.reason,
       m.score,
       m.rule_code
  from public.list_line l
  join public.price_list pl on pl.id = l.price_list_id and pl.status = 'active'
  join public.supplier sp on sp.code = pl.supplier_code
  left join public.product_type t on t.code = l.type_code
  left join public.variety v on v.type_code = l.type_code and v.code = l.variety_code
  left join public.brand b on b.code = l.brand_code
  left join public.match m on m.list_line_id = l.id
 where (m.list_line_id is null or m.level = 4)
   and not public.is_not_carried(pl.supplier_code, l.normalized_text);

-- as opções de cada linha da fila: a proposta da cascata primeiro, depois os candidatos na ordem dela. Para cada uma,
-- o que difere do que a linha diz (só conta o atributo que o extrator leu), a palavra que sobra de cada lado e o preço
-- contra o custo
create view public.review_option with (security_invoker = true) as
with opt as (
  select c.list_line_id, c.product_id, c.rank, c.score
    from public.candidate c
  union all
  select m.list_line_id, m.product_id, 0, m.score
    from public.match m
   where m.level = 4
     and not exists (select 1 from public.candidate c
                      where c.list_line_id = m.list_line_id and c.product_id = m.product_id)
)
select q.list_line_id,
       o.product_id,
       row_number() over (partition by q.list_line_id
                          order by o.product_id = q.proposed_product_id desc nulls last, o.rank, o.product_id)
         as position,
       o.score,
       coalesce(o.product_id = q.proposed_product_id, false) as proposed,
       l.type_code is not null and l.type_code is distinct from p.type_code as type_differs,
       l.brand_code is not null and l.brand_code is distinct from p.brand_code as brand_differs,
       l.variety_code is not null and l.variety_code is distinct from p.variety_code as variety_differs,
       l.size is not null and (l.size is distinct from p.size or l.unit is distinct from p.unit) as size_differs,
       l.pack is distinct from p.pack as pack_differs,
       array(select unnest(l.leftover) except select unnest(p.leftover) order by 1) as line_only_words,
       array(select unnest(p.leftover) except select unnest(l.leftover) order by 1) as product_only_words,
       round(q.unit_price / p.cost, 3) as price_to_cost,
       public.contradicts(l, p) as contradicts
  from public.review_queue q
  join opt o on o.list_line_id = q.list_line_id
  join public.list_line l on l.id = q.list_line_id
  join public.product p on p.id = o.product_id and p.active;

-- === As listas e as regras ===========================================================================================

-- cada lista: o arquivo, o resultado das 7 conferências do portão e a conta das linhas
create view public.list_overview with (security_invoker = true) as
select s.price_list_id,
       s.supplier_code,
       sp.name as supplier_name,
       s.period,
       s.status,
       pl.file_name,
       pl.file_format,
       pl.vat_included,
       pl.loaded_at,
       pl.gate,
       s.lines,
       s.confirmed,
       s.in_review,
       s.not_carried,
       s.unmatched
  from public.list_summary s
  join public.price_list pl on pl.id = s.price_list_id
  join public.supplier sp on sp.code = s.supplier_code;

-- cada regra de decisão automática: o modo de agora e a última amostra que a julgou
create view public.rule_status with (security_invoker = true) as
select r.code,
       r.mode,
       r.level,
       r.changed_at,
       a.item ->> 'mode_before' as mode_before,
       (a.item ->> 'population')::integer as population,
       (a.item ->> 'sample')::integer as sample,
       (a.item ->> 'errors')::integer as errors,
       (a.item ->> 'upper_95')::numeric as upper_95,
       a.error_limit,
       a.audited_at
  from public.decision_rule r
  left join lateral (
    select x.item, ar.error_limit, ar.finished_at as audited_at
      from public.audit_round ar
      cross join lateral jsonb_array_elements(ar.result) as x(item)
     where x.item ->> 'rule' = r.code
     order by ar.id desc
     limit 1
  ) a on true;

-- === O estado da base ================================================================================================

-- uma linha só: a cobertura do cadastro, como cada par foi decidido nas listas ativas, as contradições e as filas
create view public.base_status with (security_invoker = true) as
with pairs as (
  select lp.*
    from public.line_pair lp
    join public.price_list pl on pl.id = lp.price_list_id
   where pl.status = 'active'
)
select (select count(*) from public.product_overview) as products,
       (select count(*) from public.product_overview where suppliers >= 1) as with_supplier,
       (select count(*) from public.product_overview where suppliers = 1) as one_supplier,
       (select count(*) from public.product_overview where suppliers = 2) as two_suppliers,
       (select count(*) from public.product_overview where suppliers >= 3) as three_or_more,
       (select count(*) from public.product_overview where competing_offers >= 2) as compared,
       (select count(*) from pairs where level = 1) as by_reviewer,
       (select count(*) from pairs where level = 2) as by_barcode,
       (select count(*) from pairs where level = 3 and step = 'supplier_code') as by_supplier_code,
       (select count(*) from pairs where level = 3 and step = 'attributes') as by_attributes,
       (select count(*) from pairs where level = 3 and step = 'similarity') as by_similarity,
       (select count(*) from pairs where confirmed) as confirmed,
       -- o critério de aceite vale para o que a máquina confirmou sozinha (níveis 2 e 3), como a conferência 7 do
       -- portão: a decisão humana pode contrariar uma leitura errada do extrator, e vale
       (select count(*) from pairs where level in (2, 3)) as auto_confirmed,
       (select count(*) from pairs where level in (2, 3) and compatible = false) as contradictions,
       (select count(*) from public.review_queue) as in_review,
       (select coalesce(sum(not_carried), 0) from public.list_summary where status = 'active') as not_carried,
       (select count(*)
          from public.reading_disagreement r
          join public.price_list pl on pl.id = r.price_list_id
         where pl.status = 'active' and r.resolved_at is null) as open_disagreements,
       (select max(loaded_at) from public.price_list where status = 'active') as updated_at;

-- === Os três botões da revisão =======================================================================================

-- O trabalho fica num esquema que a API não expõe, com os privilégios do dono (as tabelas não aceitam escrita de
-- quem entra pelo painel). A API vê só as três funções finas do público, e só para quem fez login.
create schema private;
revoke all on schema private from public;

-- quem decide: o usuário logado, pelo e-mail. Sem login (ou com login anônimo), nada se grava
create function private.reviewer()
returns text
language plpgsql
stable
set search_path = ''
as $$
begin
  if auth.uid() is null or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) then
    raise exception 'login required' using errcode = '42501';
  end if;
  return coalesce(auth.jwt() ->> 'email', auth.uid()::text);
end;
$$;

-- a linha precisa estar numa lista ativa; devolve o fornecedor, o texto e a proposta da cascata
create function private.review_line(p_list_line_id bigint, out supplier text, out normalized_text text,
                                    out proposed bigint)
language plpgsql
stable
set search_path = ''
as $$
begin
  select pl.supplier_code, l.normalized_text, m.product_id
    into supplier, normalized_text, proposed
    from public.list_line l
    join public.price_list pl on pl.id = l.price_list_id and pl.status = 'active'
    left join public.match m on m.list_line_id = l.id
   where l.id = p_list_line_id;
  if not found then
    raise exception 'line % is not in an active list', p_list_line_id;
  end if;
end;
$$;

-- a decisão vale para o texto do fornecedor: a cascata roda de novo na lista ativa dele
create function private.rerun_supplier(p_supplier text)
returns void
language plpgsql
set search_path = ''
as $$
declare
  v_list bigint;
begin
  for v_list in select pl.id from public.price_list pl where pl.supplier_code = p_supplier and pl.status = 'active'
  loop
    perform public.run_cascade(v_list);
  end loop;
end;
$$;

-- «é este» (p_product_id) ou «a loja não tem» (vazio), como o revisor simulado do pipeline: grava a equivalência;
-- a proposta da cascata que não era a certa vira rejeição, para não voltar por outro passo
create function private.review_record(p_list_line_id bigint, p_product_id bigint)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_by text := private.reviewer();
  v_line record;
begin
  select * into v_line from private.review_line(p_list_line_id);
  if p_product_id is not null
     and not exists (select 1 from public.product p where p.id = p_product_id and p.active) then
    raise exception 'product % not found', p_product_id;
  end if;
  insert into public.equivalence (supplier_code, normalized_text, product_id, decided_by)
  values (v_line.supplier, v_line.normalized_text, p_product_id, v_by)
  on conflict (supplier_code, normalized_text)
  do update set product_id = excluded.product_id, decided_by = excluded.decided_by, decided_at = now();
  if p_product_id is not null then
    delete from public.rejection r
     where r.supplier_code = v_line.supplier and r.normalized_text = v_line.normalized_text
       and r.product_id = p_product_id;
  end if;
  if v_line.proposed is not null and v_line.proposed is distinct from p_product_id then
    insert into public.rejection (supplier_code, normalized_text, product_id, reason, decided_by)
    values (v_line.supplier, v_line.normalized_text, v_line.proposed, 'not_the_same_product', v_by)
    on conflict do nothing;
  end if;
  perform private.rerun_supplier(v_line.supplier);
end;
$$;

-- «não é»: este produto nunca mais aparece para este texto deste fornecedor, em passo nenhum
create function private.review_reject(p_list_line_id bigint, p_product_id bigint)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_by text := private.reviewer();
  v_line record;
begin
  select * into v_line from private.review_line(p_list_line_id);
  insert into public.rejection (supplier_code, normalized_text, product_id, reason, decided_by)
  values (v_line.supplier, v_line.normalized_text, p_product_id, 'not_the_same_product', v_by)
  on conflict do nothing;
  delete from public.equivalence e
   where e.supplier_code = v_line.supplier and e.normalized_text = v_line.normalized_text
     and e.product_id = p_product_id;
  perform private.rerun_supplier(v_line.supplier);
end;
$$;

-- as três que a API expõe: finas, com os privilégios de quem chama
create function public.review_confirm(p_list_line_id bigint, p_product_id bigint)
returns void
language plpgsql
set search_path = ''
as $$
begin
  if p_product_id is null then
    raise exception 'product required';
  end if;
  perform private.review_record(p_list_line_id, p_product_id);
end;
$$;

create function public.review_reject(p_list_line_id bigint, p_product_id bigint)
returns void
language plpgsql
set search_path = ''
as $$
begin
  perform private.review_reject(p_list_line_id, p_product_id);
end;
$$;

create function public.review_not_carried(p_list_line_id bigint)
returns void
language plpgsql
set search_path = ''
as $$
begin
  perform private.review_record(p_list_line_id, null);
end;
$$;

revoke execute on all functions in schema private from public, anon, authenticated;
grant usage on schema private to authenticated;
grant execute on function private.review_record(bigint, bigint), private.review_reject(bigint, bigint)
  to authenticated;
revoke execute on function public.review_confirm(bigint, bigint), public.review_reject(bigint, bigint),
  public.review_not_carried(bigint) from public, anon;
grant execute on function public.review_confirm(bigint, bigint), public.review_reject(bigint, bigint),
  public.review_not_carried(bigint) to authenticated;

-- as views novas: quem entra no painel lê; o visitante sem login, não (o revoke do começo veio antes delas)
revoke all on public.product_detail, public.comparison_offer, public.product_overview, public.review_queue,
  public.review_option, public.list_overview, public.rule_status, public.base_status from anon, authenticated;
grant select on public.product_detail, public.comparison_offer, public.product_overview, public.review_queue,
  public.review_option, public.list_overview, public.rule_status, public.base_status to authenticated;
