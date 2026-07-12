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
