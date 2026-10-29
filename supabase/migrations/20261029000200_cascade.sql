-- A cascata: para cada linha de uma lista, o produto do cadastro, com nível de certeza e motivo.
-- Roda em ordem e para no primeiro passo que decide. O «não é» de uma pessoa vale em todos os passos.

-- o preço da unidade de venda, com IVA: o número que se compara entre fornecedores
create function public.unit_price(p_price numeric, p_vat_included boolean, p_units_per_box integer)
returns numeric
language sql
immutable
set search_path = ''
as $$
  select round(p_price * case when p_vat_included then 1 else 1.21 end / coalesce(nullif(p_units_per_box, 0), 1), 2)
$$;

-- a linha contradiz o produto quando diz alguma coisa (tipo, marca, variedade, tamanho, pack) diferente dele;
-- o que a linha não diz não contradiz nada
create function public.contradicts(l public.list_line, p public.product)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select (l.type_code is not null and l.type_code is distinct from p.type_code)
      or (l.brand_code is not null and l.brand_code is distinct from p.brand_code)
      or (l.variety_code is not null and l.variety_code is distinct from p.variety_code)
      or (l.size is not null and (l.size is distinct from p.size or l.unit is distinct from p.unit))
      or l.pack is distinct from p.pack
$$;

create function public.is_rejected(p_supplier text, p_text text, p_product bigint)
returns boolean
language sql
stable
set search_path = ''
as $$
  select exists (
    select 1 from public.rejection r
     where r.supplier_code = p_supplier and r.normalized_text = p_text and r.product_id = p_product
  )
$$;

-- uma pessoa já disse que este texto deste fornecedor não é nenhum produto do cadastro
create function public.is_not_carried(p_supplier text, p_text text)
returns boolean
language sql
stable
set search_path = ''
as $$
  select exists (
    select 1 from public.equivalence e
     where e.supplier_code = p_supplier and e.normalized_text = p_text and e.product_id is null
  )
$$;

create function public.run_cascade(p_list_id bigint)
returns table (cascade_step text, matched integer)
language plpgsql
set search_path = ''
as $$
declare
  v_supplier text;
  v_vat boolean;
  v_count integer;
begin
  select pl.supplier_code, pl.vat_included into v_supplier, v_vat
    from public.price_list pl
   where pl.id = p_list_id;
  if not found then
    raise exception 'price list % not found', p_list_id;
  end if;

  delete from public.match m using public.list_line l
   where m.list_line_id = l.id and l.price_list_id = p_list_id;
  delete from public.candidate c using public.list_line l
   where c.list_line_id = l.id and l.price_list_id = p_list_id;

  -- 1. o mesmo código de barras, sem nenhuma contradição (o código velho de outro tamanho não passa)
  insert into public.match (list_line_id, product_id, level, step, reason)
  select l.id, p.id, 2, 'barcode', 'same_barcode'
    from public.list_line l
    join public.product p on p.barcode = l.barcode and p.active
   where l.price_list_id = p_list_id
     and not public.contradicts(l, p)
     and not public.is_rejected(v_supplier, l.normalized_text, p.id);
  get diagnostics v_count = row_count;
  cascade_step := 'barcode'; matched := v_count; return next;

  -- 2. o código do fornecedor, aprendido num par confirmado de uma lista anterior dele; o tipo, a marca e o
  --    tamanho precisam estar lidos e iguais (o código reaproveitado para outro produto não passa)
  insert into public.match (list_line_id, product_id, level, step, reason)
  select l.id, p.id, 3, 'supplier_code', 'learned_code'
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
  cascade_step := 'supplier_code'; matched := v_count; return next;

  -- 3. a equivalência confirmada: o que uma pessoa já respondeu para este texto deste fornecedor
  insert into public.match (list_line_id, product_id, level, step, reason)
  select l.id, e.product_id, 1, 'equivalence', 'human_decision'
    from public.list_line l
    join public.equivalence e on e.supplier_code = v_supplier and e.normalized_text = l.normalized_text
    join public.product p on p.id = e.product_id and p.active  -- o «não é nenhum» (product_id vazio) não entra
   where l.price_list_id = p_list_id
     and not exists (select 1 from public.match m where m.list_line_id = l.id);
  get diagnostics v_count = row_count;
  cascade_step := 'equivalence'; matched := v_count; return next;

  -- 4. os atributos idênticos, a mesma palavra que sobra dos dois lados e um candidato só. Confirma (nível 3)
  --    quando o preço é coerente com o custo; senão vai à revisão, com o motivo
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
    select *, row_number() over (partition by line_id order by abs(coalesce(ratio, 99) - 1), product_id) as rank
      from cand
  ), cands as (
    insert into public.candidate (list_line_id, product_id, rank, score)
    select line_id, product_id, rank, 1 from ranked
  )
  insert into public.match (list_line_id, product_id, level, step, reason, score)
  select line_id, product_id,
         case when n = 1 and ratio between 0.5 and 2 then 3 else 4 end,
         'attributes',
         case when n > 1 then 'several_candidates'
              when ratio between 0.5 and 2 then 'unique_candidate'
              else 'price_far_from_cost' end,
         ratio
    from ranked
   where rank = 1;
  get diagnostics v_count = row_count;
  cascade_step := 'attributes'; matched := v_count; return next;

  -- 5. a semelhança de texto: nunca confirma; só ordena os candidatos para a revisão (nível 4)
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

  insert into public.match (list_line_id, product_id, level, step, reason, score)
  select c.list_line_id, c.product_id, 4, 'similarity', 'text_similarity', c.score
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
