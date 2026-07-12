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
