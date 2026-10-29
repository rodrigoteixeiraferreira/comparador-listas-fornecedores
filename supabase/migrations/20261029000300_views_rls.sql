-- As views da comparação e a segurança: só quem entra no painel lê; ninguém escreve pela API.

-- cada linha de cada lista com o par, se é confirmado, se contradiz o produto e o preço da unidade (o portão lê daqui)
create view public.line_pair with (security_invoker = true) as
select l.id as list_line_id,
       l.price_list_id,
       l.item_code,
       l.description,
       m.product_id,
       coalesce(m.confirmed, false) as confirmed,
       m.level,
       m.step,
       m.reason,
       case when p.id is null then null else not public.contradicts(l, p) end as compatible,
       public.unit_price(l.price, pl.vat_included, l.units_per_box) as unit_price,
       p.cost
  from public.list_line l
  join public.price_list pl on pl.id = l.price_list_id
  left join public.match m on m.list_line_id = l.id
  left join public.product p on p.id = m.product_id;

-- as ofertas que valem: listas ativas, par confirmado. O preço longe do custo não desfaz a identidade,
-- só tira a linha da competição até alguém conferir (price_ok)
create view public.offer with (security_invoker = true) as
select pl.supplier_code,
       pl.period,
       l.id as list_line_id,
       l.description,
       m.product_id,
       m.level,
       m.step,
       public.unit_price(l.price, pl.vat_included, l.units_per_box) as unit_price,
       p.cost,
       round(public.unit_price(l.price, pl.vat_included, l.units_per_box) / p.cost, 3) as price_to_cost,
       coalesce(public.unit_price(l.price, pl.vat_included, l.units_per_box) / p.cost between 0.5 and 2, false)
         as price_ok
  from public.price_list pl
  join public.list_line l on l.price_list_id = pl.id
  join public.match m on m.list_line_id = l.id and m.confirmed
  join public.product p on p.id = m.product_id
 where pl.status = 'active';

-- produto por produto: quem vende mais barato, entre as ofertas que competem
create view public.product_comparison with (security_invoker = true) as
select p.id as product_id,
       p.description,
       p.type_code,
       p.brand_code,
       p.cost,
       count(o.list_line_id) filter (where o.price_ok) as offers,
       min(o.unit_price) filter (where o.price_ok) as best_price,
       (array_agg(o.supplier_code order by o.unit_price, o.supplier_code) filter (where o.price_ok))[1] as best_supplier,
       count(o.list_line_id) filter (where not o.price_ok) as offers_price_in_doubt
  from public.product p
  left join public.offer o on o.product_id = p.id
 where p.active
 group by p.id;

-- o estado de cada lista: confirmadas, em revisão, as que a loja não tem (decidido) e as sem dono
create view public.list_summary with (security_invoker = true) as
select pl.id as price_list_id,
       pl.supplier_code,
       pl.period,
       pl.status,
       count(l.id) as lines,
       count(m.list_line_id) filter (where m.confirmed) as confirmed,
       count(m.list_line_id) filter (where m.level = 4) as in_review,
       count(l.id) filter (where m.list_line_id is null and public.is_not_carried(pl.supplier_code, l.normalized_text))
         as not_carried,
       count(l.id) filter (where m.list_line_id is null
                             and not public.is_not_carried(pl.supplier_code, l.normalized_text)) as unmatched
  from public.price_list pl
  left join public.list_line l on l.price_list_id = pl.id
  left join public.match m on m.list_line_id = l.id
 group by pl.id;

-- RLS em todas as tabelas: quem entra no painel lê; a escrita é só do processamento (fora da API)
do $$
declare
  t text;
begin
  foreach t in array array['section', 'product_type', 'variety', 'brand', 'supplier', 'vocabulary_term', 'product',
                           'price_list', 'list_line', 'equivalence', 'rejection', 'match', 'candidate']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy %I on public.%I for select to authenticated using (true)', t || '_read', t);
  end loop;
end;
$$;
