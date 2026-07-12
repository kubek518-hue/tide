# Extra Help (Windows) — the traps, in one page
Primary guide: express-assembly.md (5 parts). These are the only tricky spots:
1. **The database password is shown ONCE.** The moment Supabase generates it,
   copy it into Notepad. Lost it? Supabase → Project Settings → Database →
   Reset database password (then use the new one everywhere after).
2. **Hidden .github folder.** Before uploading to GitHub: in the tide folder,
   View → Show → tick "Hidden items". The grayed-out .github folder MUST be
   uploaded — the robots live in it.
3. **The DATABASE_URL secret.** Take the URI connection string, delete
   [YOUR-PASSWORD] INCLUDING the brackets, type the real password there.
   Secret name exactly: DATABASE_URL
4. **Old folders lie.** Only a folder containing VERSION.txt is the real
   v1.0. No VERSION.txt = delete it.
5. **Supabase naps.** Free projects pause after ~1 week idle. Dashboard →
   Restore button → one minute → everything's back, nothing lost.
6. **Worried? Press the button.** GitHub → Actions → "HEALTH CHECK — is
   everything OK?" → Run → read "ALL GOOD" or exactly what to fix.
7. **Stuck?** New chat + attach tide-handoff-brief.md + "Stuck at Part X,
   step Y — my screen shows ___."
