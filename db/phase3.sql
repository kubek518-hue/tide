-- Phase 3: store connections + profit truth (Bookkeeper).
-- Run AFTER phase2.sql (Supabase SQL editor).

-- ── Helper functions (security definer so policies stay simple) ──────────
create or replace function public.current_member_id()
returns bigint language sql stable security definer set search_path = public as $$
  select id from members where user_id = auth.uid() and active limit 1;
$$;

-- ── Stores: WRITE-ONLY from the client ────────────────────────────────────
-- The dashboard can connect a store (insert) but can NEVER read tokens back.
-- Agents read via DATABASE_URL (table owner bypasses RLS).
create table if not exists stores (
  id bigint generated always as identity primary key,
  member_id bigint not null references members(id) default public.current_member_id(),
  shop_domain text not null unique
    check (shop_domain ~ '^[a-z0-9][a-z0-9-]*\.myshopify\.com$'),
  access_token text not null,
  created_at timestamptz not null default now()
);
alter table stores enable row level security;

drop policy if exists stores_owner_insert on stores;
create policy stores_owner_insert on stores
  for insert to authenticated
  with check (member_id = public.current_member_id()
              and public.current_member_id() is not null);
-- No select/update/delete policies on purpose: tokens are write-only.

create or replace function public.owns_store(sid bigint)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from stores s join members m on m.id = s.member_id
    where s.id = sid and m.user_id = auth.uid()
  );
$$;

-- ── Store status: the readable mirror (no secrets) ───────────────────────
create table if not exists store_status (
  store_id bigint primary key references stores(id) on delete cascade,
  shop_domain text not null,
  last_sync timestamptz,
  orders_30d int,
  note text
);
alter table store_status enable row level security;
drop policy if exists store_status_owner_read on store_status;
create policy store_status_owner_read on store_status
  for select to authenticated using (public.owns_store(store_id));

-- Create the status row the moment a store connects, so the dashboard can
-- confirm the connection without ever touching the stores table.
create or replace function public.handle_new_store()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into store_status (store_id, shop_domain, note)
  values (new.id, new.shop_domain, 'Connected — first sync within 24h.')
  on conflict (store_id) do nothing;
  return new;
end $$;
drop trigger if exists on_store_created on stores;
create trigger on_store_created
  after insert on stores for each row execute function public.handle_new_store();

-- ── Product costs: the user tells us what each unit costs them ───────────
create table if not exists product_costs (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  product_key text not null,              -- Shopify product_id as text
  product_title text,
  unit_cost numeric not null check (unit_cost >= 0),
  updated_at timestamptz not null default now(),
  unique (store_id, product_key)
);
alter table product_costs enable row level security;
drop policy if exists product_costs_owner_all on product_costs;
create policy product_costs_owner_all on product_costs
  for all to authenticated
  using (public.owns_store(store_id))
  with check (public.owns_store(store_id));

-- ── Ad spend: manual log v1 (Meta API integration comes later) ───────────
create table if not exists ad_spend (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  day date not null,
  amount numeric not null check (amount >= 0),
  note text,
  created_at timestamptz not null default now()
);
alter table ad_spend enable row level security;
drop policy if exists ad_spend_owner_all on ad_spend;
create policy ad_spend_owner_all on ad_spend
  for all to authenticated
  using (public.owns_store(store_id))
  with check (public.owns_store(store_id));

-- ── Orders cache: agents-only (no client policies) ───────────────────────
create table if not exists orders_cache (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  order_id text not null,
  created_day date not null,
  total numeric not null default 0,
  refunded numeric not null default 0,
  line_items jsonb not null default '[]'::jsonb,
  unique (store_id, order_id)
);
alter table orders_cache enable row level security;

-- ── The truth table: daily P&L per product (+ one store-level row/day) ────
create table if not exists pnl_daily (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  day date not null,
  product_key text,                        -- NULL = store-level row (fees, ads, refunds)
  product_title text,
  units int not null default 0,
  revenue numeric not null default 0,
  cogs numeric,                            -- NULL = user hasn't entered a cost yet
  fees numeric not null default 0,
  ad_spend numeric not null default 0,
  profit numeric,                          -- NULL when cogs missing (honesty > guessing)
  computed_at timestamptz not null default now()
);
create unique index if not exists pnl_daily_key
  on pnl_daily (store_id, day, product_key) nulls not distinct;
alter table pnl_daily enable row level security;
drop policy if exists pnl_owner_read on pnl_daily;
create policy pnl_owner_read on pnl_daily
  for select to authenticated using (public.owns_store(store_id));
