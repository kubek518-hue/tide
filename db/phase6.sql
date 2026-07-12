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
