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
