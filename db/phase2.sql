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
