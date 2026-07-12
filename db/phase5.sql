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
