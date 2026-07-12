# TIDE — Express Assembly (the short version)
*Build: FINAL v1.1 — matches TIDE-FINAL-v1.1.zip only. If your folder has no VERSION.txt file inside, it's an old copy: delete it.*
*Five parts, ~40 minutes, $0. The robot does the fiddly work now. Each part
ends with a "✅ done when" check — don't move on until it's true.*
*(Hit a snag? `EXTRA-HELP-WINDOWS.md` — one page, just the seven traps.)*

**Prepare (2 min):** unzip `TIDE-FINAL-v1.1.zip` → you get a folder `tide`.
Open a notes app — you'll save 4 things in it as you go.

---

## PART 1 — Database: one paste (10 min)

1. Go to **supabase.com** → **"Start your project"** → sign up → confirm email.
2. **"New project"** → Name: `tide` → click **"Generate a password"** →
   ⚠️ **copy the password into your notes NOW (shown only once)** → pick the
   nearest region → **"Create new project"** → wait ~2 minutes.
3. Left sidebar → **SQL Editor** (the `>_` icon).
4. On your computer: `tide` folder → `db` folder → open **`setup-all.sql`**
   with Notepad (Windows) or TextEdit (Mac). Select all, copy.
5. Paste into the SQL Editor's big box → click the green **"Run"**.

✅ Done when it says **"Success"**. (One paste. That's the whole database.)

## PART 2 — Code online (10 min)

1. **github.com** → **Sign up** (free).
2. Make hidden files visible in your `tide` folder (it contains an invisible
   `.github` folder — the robots live there):
   - Windows: folder's **View** menu → **Show** → tick **Hidden items**
   - Mac: in the folder, press **Cmd + Shift + .** (period)
3. On GitHub: **+** (top right) → **"New repository"** → Name: `tide` →
   choose **Private** → **"Create repository"**.
4. Click the link "…or **uploading an existing file**".
5. Select **everything inside** your `tide` folder (Ctrl+A / Cmd+A, including
   `.github`) → drag it onto the dashed box → wait for the list → green
   **"Commit changes"**.

✅ Done when your repo shows `agents`, `db`, `docs`, **and `.github`**.
(Missing `.github`? Redo step 2, then drag just that folder in.)

## PART 3 — The key (5 min)

1. Supabase → **gear icon** (Project Settings) → **Database** →
   **Connection string** → **URI** tab → copy the long
   `postgresql://postgres...` line into your notes.
2. In your notes, replace `[YOUR-PASSWORD]` with your saved password —
   **brackets deleted too.**
3. GitHub repo → **Settings** → **Secrets and variables** → **Actions** →
   **"New repository secret"** → Name: exactly `DATABASE_URL` → Secret:
   paste the finished line → **"Add secret"**.

✅ Done when `DATABASE_URL` is listed.

## PART 4 — Press the one button (10 min)

First grab two more things for your notes: Supabase → gear icon → **API** →
copy the **Project URL** and the long **anon public** key (starts `eyJ`).

1. GitHub repo → **Actions** tab → if asked, click the green button to
   enable workflows.
2. In the left list, click **"SETUP — one button does the rest"**.
3. Click **"Run workflow"** (right side). Three boxes appear — fill them:
   - the Project URL
   - the anon public key
   - your real email
4. Click the green **"Run workflow"** button. Wait 3–6 minutes for the ✓.
5. Click the finished run → the **"Show your website address"** step prints
   your live links. (They also work like this:
   `https://YOURNAME.github.io/tide/` and `.../tide/app.html`.)

The button just did all of this for you: wrote your keys into both pages,
replaced the contact email, switched your website on, published it, and ran
the engine's first hunt.

**Prove it:** open your website and join the waitlist with your own email →
Supabase → **Table Editor** → `waitlist` shows it. Then peek at the
`products` table — the first hunt already filled it.

9. Final proof, one more button: **Actions** tab → **"HEALTH CHECK — is
   everything OK?"** → **Run workflow** → wait ~2 min for the ✓ → click the
   run → the self-test step ends with **"ALL GOOD — the pipeline is
   healthy."** If it doesn't, it tells you exactly what to fix and where.

✅ Done when your email is in `waitlist`, `products` has rows, and HEALTH
CHECK says ALL GOOD.

## PART 5 — Let yourself in (5 min)

1. One-time setting: Supabase → **Authentication** → **URL Configuration** →
   **Add URL** → paste your `.../tide/app.html` address → Save.
2. Visit that app.html address → enter your email → **"Email me a sign-in
   link"** → click the link from your inbox → you'll see **"Almost there"**.
3. Supabase → Table Editor → **`members`** → your row → double-click the
   **`active`** cell → change `false` to `true` → save.
4. Back on the page → **"I already paid — check again"**.

✅ **ASSEMBLED.** You're standing in Mission Control. Picks arrive with the
Monday run; everything else is live now. Total cost: $0.

---

**Afterwards, your only recurring job (15 min every Monday):** read the new
picks; for picks 2–4 weeks old, mark `hit` or `miss` in the `picks` table
(column `outcome`). At 10 scored picks your website starts showing your
track record automatically — that's your launch ticket.

**If anything breaks:**
- SQL "already exists" → harmless, continue.
- Setup run red ✗ → click it, read the failed step. If it's the first-hunt
  step, it's almost always Part 3 (name exactly `DATABASE_URL`, no `[ ]`
  left in the password). Fix and run the button again — it's safe to re-run.
- Changed something in `docs/` later? Just press the SETUP button again —
  it republishes.
- Sign-in email missing → check spam; confirm Part 5 step 1 was saved.
- Stuck → new chat, attach `tide-handoff-brief.md`, say: *"Stuck at Part X,
  step Y — my screen shows ___."*
