-- Phase 4: Sentinel — protection radar, alerts, dispute logging.
-- Run AFTER phase3.sql (Supabase SQL editor).

-- Track fulfillment speed: Bookkeeper now records when each order shipped.
alter table orders_cache add column if not exists fulfilled_day date;

-- ── Protection snapshot: one row per store, refreshed daily ──────────────
create table if not exists protection (
  store_id bigint primary key references stores(id) on delete cascade,
  dispute_rate numeric,           -- disputes / orders, 30d (null = no data yet)
  dispute_source text,            -- 'shopify_payments' | 'manual_log' | 'none'
  refund_rate numeric,            -- refunded orders / orders, 30d
  late_rate numeric,              -- orders unshipped after 3 days / shippable orders
  orders_30d int,
  details jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now()
);
alter table protection enable row level security;
drop policy if exists protection_owner_read on protection;
create policy protection_owner_read on protection
  for select to authenticated using (public.owns_store(store_id));

-- ── Alerts: Sentinel writes, members read and resolve ────────────────────
create table if not exists alerts (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  kind text not null,              -- disputes | refunds | shipping
  severity text not null,          -- watch | warning | urgent
  title text not null,
  body text not null,              -- plain language + concrete next steps
  created_at timestamptz not null default now(),
  resolved boolean not null default false
);
create index if not exists idx_alerts_open on alerts(store_id, kind) where not resolved;
alter table alerts enable row level security;
drop policy if exists alerts_owner_read on alerts;
create policy alerts_owner_read on alerts
  for select to authenticated using (public.owns_store(store_id));
drop policy if exists alerts_owner_resolve on alerts;
create policy alerts_owner_resolve on alerts
  for update to authenticated
  using (public.owns_store(store_id))
  with check (public.owns_store(store_id));

-- ── Manual dispute log: fallback for PayPal / non-Shopify-Payments ───────
create table if not exists disputes_log (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  day date not null,
  source text not null default 'other',   -- paypal | stripe | shopify | other
  amount numeric,
  note text,
  created_at timestamptz not null default now()
);
alter table disputes_log enable row level security;
drop policy if exists disputes_owner_all on disputes_log;
create policy disputes_owner_all on disputes_log
  for all to authenticated
  using (public.owns_store(store_id))
  with check (public.owns_store(store_id));
