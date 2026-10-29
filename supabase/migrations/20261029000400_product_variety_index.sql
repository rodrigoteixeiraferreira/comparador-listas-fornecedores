-- O alerta do Supabase depois da 0100: a chave estrangeira produto -> variedade sem índice que a cubra.
-- A 0100 já estava aplicada e migração não se edita: a correção vem aqui.

create index product_type_variety_idx on public.product (type_code, variety_code);
