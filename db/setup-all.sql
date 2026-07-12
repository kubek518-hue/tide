-- TIDE: Trend Intelligence & Decision Engine
-- Shared brain. Run this once in Supabase SQL editor.

create table if not exists products (
  id bigint generated always as identity primary key,
  name text not null unique,
  slug text not null unique,
  category text,
  first_seen timestamptz not null default now(),
  guard_status text not null default 'clear',        -- clear | flagged | excluded
  guard_reasons jsonb not null default '[]'::jsonb,
  status text not null default 'candidate'           -- candidate | picked | archived
);

create table if not exists signals (
  id bigint generated always as identity primary key,
  product_id bigint not null references products(id) on delete cascade,
  source text not null,                               -- google_trends | reddit | meta_ads | ...
  metric text not null,                               -- slope_90d | mentions_30d | ad_count | ...
  value double precision,
  raw jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now()
);
create index if not exists idx_signals_product on signals(product_id, source, captured_at desc);

create table if not exists scores (
  id bigint generated always as identity primary key,
  product_id bigint not null references products(id) on delete cascade,
  run_id bigint,
  momentum double precision not null default 0,       -- 0..40
  confirmation double precision not null default 0,   -- 0..25
  opportunity double precision not null default 0,    -- 0..20 (low saturation = high)
  viability double precision not null default 0,      -- 0..15 (margin/logistics heuristics)
  total double precision not null default 0,          -- 0..100
  verdict text not null,                              -- test | watch | skip | excluded
  confidence text not null default 'low',             -- low | medium | high
  evidence jsonb not null default '{}'::jsonb,        -- honest AI: every score explains itself
  created_at timestamptz not null default now()
);
create index if not exists idx_scores_product on scores(product_id, created_at desc);
create index if not exists idx_scores_verdict on scores(verdict, total desc, created_at desc);

create table if not exists picks (
  id bigint generated always as identity primary key,
  product_id bigint not null references products(id) on delete cascade,
  score_id bigint not null references scores(id),
  week text not null,                                 -- e.g. 2026-W28
  rank int not null,
  published_at timestamptz not null default now(),
  outcome text,                                       -- later: hit | miss | unknown (hit-rate honesty, Charter 8)
  unique (week, product_id)
);

-- Audit trail (Policy C1): every agent run is logged.
create table if not exists runs (
  id bigint generated always as identity primary key,
  agent text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  ok boolean,
  stats jsonb not null default '{}'::jsonb,
  error text
);

-- Waitlist for the landing page (Phase 1b).
create table if not exists waitlist (
  id bigint generated always as identity primary key,
  email text not null unique,
  created_at timestamptz not null default now(),
  source text
);
-- Waitlist security: the landing page uses the public "anon" key, so we lock
-- the table down to insert-only. Nobody can read, change, or delete emails
-- through the public API. Run this in the Supabase SQL editor after schema.sql.

alter table waitlist enable row level security;

drop policy if exists waitlist_public_insert on waitlist;
create policy waitlist_public_insert
  on waitlist for insert
  to anon
  with check (true);

-- No select/update/delete policies are created on purpose:
-- with RLS enabled and no policy, those operations are denied for anon.
-- Phase 2: members, billing status, coach briefings, and read access.
-- Run AFTER schema.sql and waitlist_policy.sql (Supabase SQL editor).

-- ── Members ──────────────────────────────────────────────────────────────
-- Keyed by email so payment (Stripe) and signup (magic link) can arrive in
-- either order. user_id links to Supabase Auth once they log in.

create table if not exists members (
  id bigint generated always as identity primary key,
  email text not null unique,
  user_id uuid unique references auth.users(id),
  active boolean not null default false,        -- flipped by Stripe webhook (or you, manually)
  plan text,                                    -- e.g. 'early-49'
  stripe_customer text,
  created_at timestamptz not null default now()
);

-- When someone signs in for the first time, attach their auth id to the
-- member row with the same email (creating the row if it doesn't exist).
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into members (email, user_id)
  values (lower(new.email), new.id)
  on conflict (email) do update set user_id = excluded.user_id;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── Coach briefings ──────────────────────────────────────────────────────
create table if not exists briefings (
  id bigint generated always as identity primary key,
  week text not null unique,
  body text not null,                            -- plain-language markdown
  created_at timestamptz not null default now()
);

-- ── Row Level Security: members read the product, nobody writes ──────────
-- Agents connect as the table owner (DATABASE_URL) and bypass RLS, so these
-- policies only govern the public API used by the dashboard.

alter table members   enable row level security;
alter table products  enable row level security;
alter table scores    enable row level security;
alter table picks     enable row level security;
alter table briefings enable row level security;
alter table signals   enable row level security;  -- no policy: not exposed
alter table runs      enable row level security;  -- no policy: not exposed

drop policy if exists members_read_self on members;
create policy members_read_self on members
  for select to authenticated
  using (user_id = auth.uid());

-- Helper: is the calling user an active member?
create or replace function public.is_active_member()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from members where user_id = auth.uid() and active
  );
$$;

drop policy if exists picks_member_read on picks;
create policy picks_member_read on picks
  for select to authenticated using (public.is_active_member());

drop policy if exists scores_member_read on scores;
create policy scores_member_read on scores
  for select to authenticated using (public.is_active_member());

drop policy if exists products_member_read on products;
create policy products_member_read on products
  for select to authenticated using (public.is_active_member());

drop policy if exists briefings_member_read on briefings;
create policy briefings_member_read on briefings
  for select to authenticated using (public.is_active_member());
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
-- Phase 5: Creative agent output + hit-rate receipts (Charter 8).
-- Run AFTER phase4.sql (Supabase SQL editor).

-- ── Creatives: ad angles generated per picked product ────────────────────
create table if not exists creatives (
  id bigint generated always as identity primary key,
  product_id bigint not null references products(id) on delete cascade,
  mode text not null,                    -- 'llm' | 'template'
  angle_name text not null,
  hook text not null,
  script text not null,                  -- 15-30s UGC-style, visual cues in [brackets]
  page_copy text not null,
  checked boolean not null default false, -- passed guardrails/ad_claims at generation
  created_at timestamptz not null default now()
);
create index if not exists idx_creatives_product on creatives(product_id);
alter table creatives enable row level security;
drop policy if exists creatives_member_read on creatives;
create policy creatives_member_read on creatives
  for select to authenticated using (public.is_active_member());

-- ── Pick outcomes: the honesty bookkeeping ────────────────────────────────
alter table picks add column if not exists outcome_note text;
alter table picks add column if not exists outcome_at timestamptz;
-- Founder marks picks.outcome = 'hit' | 'miss' in the Table Editor during
-- validation (+2 and +4 week checkpoints). The auditor turns those marks
-- into the public number below.

-- ── Public hit rate: readable by ANYONE, including the landing page ──────
-- This is Charter 8 as infrastructure: the number goes public, good or bad.
create table if not exists hitrate_public (
  period text primary key,               -- 'all' | 'last_90d'
  picks_scored int not null,
  hits int not null,
  rate numeric,                          -- null until picks_scored > 0
  updated_at timestamptz not null default now()
);
alter table hitrate_public enable row level security;
drop policy if exists hitrate_anyone_read on hitrate_public;
create policy hitrate_anyone_read on hitrate_public
  for select to anon, authenticated using (true);
-- Phase 6: Operations — the action queue (Policy C1/B9 as schema).
-- Run AFTER phase5.sql (Supabase SQL editor).

-- ── Per-store operation settings: kill switch + execution-layer cap ──────
create table if not exists op_settings (
  store_id bigint primary key references stores(id) on delete cascade,
  kill_switch boolean not null default false,      -- true = nothing executes, period
  max_actions_per_day int not null default 5
    check (max_actions_per_day between 0 and 50),
  updated_at timestamptz not null default now()
);
alter table op_settings enable row level security;
drop policy if exists op_settings_owner_all on op_settings;
create policy op_settings_owner_all on op_settings
  for all to authenticated
  using (public.owns_store(store_id))
  with check (public.owns_store(store_id));

-- ── The action queue ──────────────────────────────────────────────────────
-- Lifecycle: proposed (by system) -> approved | declined (by the member)
--            approved -> executed | failed (by the Operations agent)
-- Members can also create actions directly — those start life as 'approved'
-- because the human click IS the approval.
create table if not exists actions (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  kind text not null check (kind in ('import_product','pause_product')),
  payload jsonb not null default '{}'::jsonb,
  reason text,                                     -- plain language: why this exists
  status text not null default 'proposed'
    check (status in ('proposed','approved','declined','executed','failed')),
  proposed_by text not null default 'system',      -- 'system' | 'member'
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  executed_at timestamptz,
  result jsonb,
  error text
);
create index if not exists idx_actions_queue on actions(store_id, status, created_at);
alter table actions enable row level security;

drop policy if exists actions_owner_read on actions;
create policy actions_owner_read on actions
  for select to authenticated using (public.owns_store(store_id));

-- Members may INSERT only pre-approved actions of whitelisted kinds for
-- their own store (their click is the approval).
drop policy if exists actions_owner_insert on actions;
create policy actions_owner_insert on actions
  for insert to authenticated
  with check (
    public.owns_store(store_id)
    and status = 'approved'
    and proposed_by = 'member'
    and kind in ('import_product','pause_product')
  );

-- Members may UPDATE only system proposals, and only to approve/decline them.
drop policy if exists actions_owner_decide on actions;
create policy actions_owner_decide on actions
  for update to authenticated
  using (public.owns_store(store_id) and status = 'proposed')
  with check (public.owns_store(store_id) and status in ('approved','declined'));
-- Phase 7: Recruiter — creator playbooks, vetting CRM, sample ROI.
-- Run AFTER phase6.sql (Supabase SQL editor).

-- ── Playbooks: generated per TEST pick by the Recruiter agent ─────────────
create table if not exists playbooks (
  id bigint generated always as identity primary key,
  product_id bigint not null unique references products(id) on delete cascade,
  week text not null,
  search_queries jsonb not null default '[]'::jsonb,   -- where to find creators
  outreach jsonb not null default '[]'::jsonb,         -- [{name, message}] guardrail-checked
  disclosure_note text not null,
  created_at timestamptz not null default now()
);
alter table playbooks enable row level security;
drop policy if exists playbooks_member_read on playbooks;
create policy playbooks_member_read on playbooks
  for select to authenticated using (public.is_active_member());

-- ── Creator CRM: the member's own candidate list ──────────────────────────
create table if not exists creators (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  handle text not null,
  followers int check (followers >= 0),
  avg_views int check (avg_views >= 0),
  posts_per_week numeric check (posts_per_week >= 0),
  niche text,
  notes text,
  created_at timestamptz not null default now(),
  unique (store_id, handle)
);
alter table creators enable row level security;
drop policy if exists creators_owner_all on creators;
create policy creators_owner_all on creators
  for all to authenticated
  using (public.owns_store(store_id))
  with check (public.owns_store(store_id));

-- ── Samples: what was sent, what it earned — commission math, honestly ────
create table if not exists samples (
  id bigint generated always as identity primary key,
  store_id bigint not null references stores(id) on delete cascade,
  creator_id bigint not null references creators(id) on delete cascade,
  product_title text not null,
  cost numeric not null default 0 check (cost >= 0),
  sent_day date not null,
  posted boolean not null default false,
  attributed_revenue numeric not null default 0 check (attributed_revenue >= 0),
  note text,
  created_at timestamptz not null default now()
);
alter table samples enable row level security;
drop policy if exists samples_owner_all on samples;
create policy samples_owner_all on samples
  for all to authenticated
  using (public.owns_store(store_id))
  with check (public.owns_store(store_id));
