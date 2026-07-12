# TIDE — Trend Intelligence & Decision Engine

One system, one brain, a roster of agents. Finds rising products **before**
mainstream tools surface them, scores them with evidence, refuses the unsafe
ones, and publishes honest weekly picks.

**Monthly cost: $0.** Supabase free tier + GitHub Actions free tier. The only
thing you ever pay for at this phase is a domain name.

---

## How it works (60-second version)

```
seeds.yaml ──► SCOUT ──► signals ──► ANALYST ──► scores ──► PUBLISHER ──► weekly picks
 (categories)   every 6h   (brain)    guardrails    0–100      Mondays      + evidence
                                      + evidence    verdicts
```

- **Scout** expands seed categories into rising product queries (Google Trends),
  then confirms with Reddit chatter and (optionally) Meta Ad Library saturation.
- **Guardrails** exclude weapons/supplements/counterfeits and flag children's,
  electrical, and skin-applied products with plain-language warnings.
  This is the Operator's Charter written as code — see `agents/tide/guardrails/`.
- **Analyst** scores 0–100 across momentum / confirmation / opportunity /
  viability. Every score carries its evidence. Missing data lowers confidence —
  it is never papered over.
- **Publisher** writes the weekly top-10 with honest-odds framing.
- Dormant agents (coach, sentinel, bookkeeper, creative, recruiter, operations)
  are scaffolded with their contracts — they switch on in later phases.

---

## Setup — 15 minutes, step by step

### 1. Create the free database (5 min)
1. Go to supabase.com → New project (free tier). Pick any region near you.
2. In the left menu: **SQL Editor** → New query → paste the whole contents of
   **`db/setup-all.sql`** (ONE file — it contains every phase) → **Run**.
   You should see "Success". The individual files below (schema, phase2–7)
   are reference copies only; you never need to run them separately.
3. Left menu: **Project Settings → Database → Connection string → URI**.
   Copy it. Replace `[YOUR-PASSWORD]` with your database password.
   This is your `DATABASE_URL`.

### 2. Put this code on GitHub (3 min)
1. Create a new **private** repository on github.com.
2. Upload this folder's contents (drag-and-drop works, or `git push`).

### 3. Give the robots the key (2 min)
1. In your repo: **Settings → Secrets and variables → Actions → New repository secret**.
2. Name: `DATABASE_URL` — Value: the connection string from step 1.
3. (Optional, better scores) Add `META_AD_LIBRARY_TOKEN` — a free token from
   developers.facebook.com (create an app → Graph API → Ad Library access).
   Without it, everything still works; the opportunity axis just stays neutral.

### 4. First run (2 min)
1. Repo → **Actions** tab → enable workflows if asked.
2. Open **scan (scout + analyst)** → **Run workflow**. Watch the log.
3. When it finishes, check Supabase → **Table Editor** → `products`, `signals`,
   `scores`. Your brain is filling up.
4. From now on it runs itself every 6 hours. Mondays, the **weekly digest**
   workflow publishes picks (Actions → the run → Artifacts → `weekly-picks`).

### Run locally instead (optional)
```bash
cd agents
pip install -r requirements.txt
export DATABASE_URL="postgres://..."     # from step 1
python -m tide.orchestrator scout analyst publisher
```

---

## Phase 1b — publish the landing page (10 minutes, still $0)

The landing page lives in `docs/index.html` (that folder name lets GitHub
Pages serve it with zero build steps).

1. **Secure the waitlist table:** Supabase → SQL Editor → paste
   `db/waitlist_policy.sql` → Run. This makes the table insert-only for the
   public key — nobody can read the emails through the page.
2. **Add your keys:** Supabase → Project Settings → **API**. Copy the
   **Project URL** and the **anon public** key into the two `PASTE_...`
   constants at the bottom of `docs/index.html`. (The anon key is designed to
   be public — the policy from step 1 is what protects the data.)
3. **Turn on GitHub Pages:** repo → Settings → Pages → Source: *Deploy from a
   branch* → Branch: `main`, folder `/docs` → Save. Your page is live at
   `https://<username>.github.io/<repo>/` in about a minute.
4. **Custom domain (the ~$12/year, optional):** buy a domain, add it in the
   same Pages screen, follow the DNS instructions shown.
5. **Test it:** submit your own email, then check Supabase → Table Editor →
   `waitlist`. Submitting twice should say "already on the list."

Before publishing, replace `hello@example.com` in the footer with a real
contact address.

## Phase 2 — Mission Control: login, briefings, billing (30 minutes, ~$0)

Members sign in at `docs/app.html` (magic links, no passwords), see the coach's
weekly briefing and the picks with evidence. Stripe handles money; a tiny
serverless function flips paid members to active.

1. **Database:** already included in `db/setup-all.sql` (reference copy: `db/phase2.sql`).
   This creates `members` + `briefings` and locks all product tables to
   *active members only* (the agents are unaffected).
2. **Auth:** Supabase → Authentication → Providers → make sure **Email** is on
   (magic links are the default). Under URL Configuration, add your Pages URL
   (e.g. `https://<username>.github.io/<repo>/app.html`) to the redirect list.
3. **Dashboard keys:** open `docs/app.html`, paste the same `SUPABASE_URL` and
   `SUPABASE_ANON_KEY` as the landing page.
4. **Stripe (only when you're ready to charge):**
   a. stripe.com → create account → Payment Links → New: a subscription price
      (suggested: $29–49/mo, 14-day trial optional). Copy the link into
      `STRIPE_PAYMENT_LINK` in `docs/app.html`.
   b. Install the Supabase CLI, then from the repo root:
      `supabase functions deploy stripe-webhook --no-verify-jwt`
   c. Stripe → Developers → Webhooks → Add endpoint:
      `https://<project-ref>.functions.supabase.co/stripe-webhook`,
      event: `checkout.session.completed`. Copy the signing secret.
   d. Set the function's secrets:
      `supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_... SB_URL=https://xxxx.supabase.co SB_SERVICE_ROLE_KEY=eyJ...`
5. **Before Stripe exists** (validation weeks): activate early users by hand —
   Supabase → Table Editor → `members` → set `active` to true. Honest and free.
6. **Test the flow:** sign in with your email → you land on the "Almost there"
   screen → flip yourself active (or pay through your own link) → "check again"
   → Mission Control loads.

The **Coach** now runs every Monday after the Publisher and writes the weekly
briefing the dashboard shows. v1 is template-based (costs nothing); its file
marks exactly where an LLM upgrade plugs in later.

## Phase 3 — profit truth: connect a store, see real P&L (15 minutes)

The Bookkeeper is live. Members connect a Shopify store and Mission Control
shows **money actually made**: revenue minus their entered product costs,
estimated payment fees (2.9% + $0.30/order, labeled as estimates), refunds,
and their logged ad spend. Products with no entered cost show "needs cost" —
the system never guesses margins.

1. **Database:** already included in `db/setup-all.sql` (reference copy: `db/phase3.sql`).
   Design note: store tokens are **write-only** through the public API — the
   dashboard can save a token but no client can ever read one back. Agents
   read via `DATABASE_URL` only.
2. **Nothing else to configure.** The `daily books` workflow runs every
   morning (05:45 UTC); run it manually from the Actions tab for an instant
   first sync after connecting a store.
3. **Member flow (what your users do):** dashboard → "Your store" → follow the
   2-minute custom-app instructions shown inline (Shopify admin → Develop
   apps → scopes `read_orders`, `read_products` → install → copy token) →
   paste domain + token → enter per-unit costs when prompted → log ad spend
   daily. Traffic lights do the rest: green = profitable, amber = needs cost,
   red = losing with a plain suggestion to stop its ads.

Current honest limitations (stated in-product too): fees are estimates until
processor sync exists; ad spend is manual until the Meta API integration
(Phase 4); revenue is order-line based and refunds are applied at store level.

## Phase 4 — Sentinel: the protection radar (5 minutes)

Sentinel runs daily right after the Bookkeeper and watches the three numbers
that end dropshipping businesses — before they become account bans:

- **Dispute rate (30d):** from Shopify Payments when the store's token has the
  disputes scope, otherwise from the member's manual dispute log — the source
  is always displayed. Alerts start at 0.30% (processors act around 0.75–1%).
- **Refund rate (30d):** the early supplier-drift signal. Alerts from 5%.
- **Shipping speed:** % of orders older than 3 days with no fulfillment.
  Late delivery is the #1 cause of disputes; alerts from 5%.

Every alert is plain language with concrete next steps, one open alert per
topic (no alarm spam), and under 20 orders/30d the radar says "not enough data
yet" instead of shouting noise. Policy B7 note: Sentinel helps members *comply*
— it contains nothing that dodges or games detection, and never will.

Setup:
1. **Database:** already included in `db/setup-all.sql` (reference copy: `db/phase4.sql`).
2. That's it — the `daily books + protection` workflow already runs
   `bookkeeper` then `sentinel`. Run it manually once from Actions to see the
   first snapshot.
3. Optional, better dispute data: members can add the Shopify Payments
   disputes read scope to their custom app; without it, the manual dispute
   log keeps the radar honest.

The dashboard's Protection panel also includes **"Check my ad"** — an instant
pre-flight scan for the seven claim types that get ads rejected or sellers in
legal trouble (health claims, income promises, fake urgency, testimonial
framing, and so on), each flag explained with a fix. The canonical rule list
lives in `agents/tide/guardrails/ad_claims.py`; the dashboard mirrors it and
the Creative agent (Phase 5) will refuse to generate any of it.

## Phase 5 — Creative + the hit-rate receipts (5 minutes)

Every Monday after the picks publish, the **Creative** agent writes 3 ad
angles per TEST pick — hook, 15–30s UGC-style script with visual directions,
and page copy — shown on each pick card in Mission Control.

Two modes, picked automatically:
- **Template mode ($0, default):** three honest, pre-vetted frameworks with
  the product inserted ("Problem then the fix", "Three uses in twenty
  seconds", "The honest demo"). Zero API cost.
- **LLM mode (optional):** add an `ANTHROPIC_API_KEY` repo secret and angles
  become product-tailored. Cheapest adequate model, one call per product,
  hard cap per run (`MAX_CREATIVE_PRODUCTS_PER_RUN`, default 8), and cached —
  a product is never generated twice. At default settings this costs cents
  per week, funded by revenue per house rules.

**Guardrails are enforced at generation, not suggested:** every angle runs
through `guardrails/ad_claims.py`; flagged LLM output gets one corrective
retry; anything still flagged is refused and counted — it never reaches a
member. Testimonial framing, health claims, income claims, fake urgency:
structurally impossible to ship.

**The hit-rate pipeline (Charter §8) is now live infrastructure:**
1. During validation you mark `picks.outcome` = `hit` or `miss` in the
   Table Editor at the +2/+4 week checkpoints (use `outcome_note` for why).
2. The weekly **audit** job aggregates those into `hitrate_public` —
   a table readable by anyone, including logged-out visitors.
3. The landing page's Receipts section reads it automatically and switches
   from "VALIDATING" to the real percentage once ≥10 picks are scored.
   The number ships good or bad. That's the product.

Setup: already included in `db/setup-all.sql` (reference copy: `db/phase5.sql`). Optionally add
the `ANTHROPIC_API_KEY` secret. Everything else is already wired into the
Monday workflow (`publisher → coach → creative → audit`).

## Phase 6 — Operations: one-tap actions with hard limits (5 minutes)

The action layer is live, built to Policy C1/B9: **nothing runs without a
member's tap, everything is capped, logged, and reversible.**

v1 actions (deliberately money-safe):
- **Send a pick to your store** — one tap on any TEST pick creates the product
  in the member's Shopify store as an unpublished **draft** (title + the
  Creative agent's page copy), ready for images and pricing. Requires the
  `write_products` scope on their custom app; without it the action fails
  with step-by-step instructions instead of a cryptic error.
- **Pause a losing product** — the system watches the books and, when a
  product loses more than $20 over 7 days, files a *proposal* with the reason
  in plain language. It sits in "Waiting for your decision" until the member
  taps Approve or Decline. Approved = the product goes back to draft
  (reversible in one click from Shopify admin). **The agent never approves
  its own ideas.**

The safety machinery (all live now, ready for money-touching actions later):
- **Kill switch** — one button freezes all execution instantly.
- **Daily action cap** (default 5, member-set 0–50, with a confirm step) —
  enforced *in the executor's code*, which counts the last 24 hours and
  refuses beyond the cap. The interface merely displays it.
- **Approval flow enforced by the database:** members can only insert
  pre-approved whitelisted actions for their own store, and can only move
  system proposals to approved/declined — the RLS policies make other
  transitions impossible, not just hidden.
- **Full audit:** every action ends as executed (with result) or failed
  (with a plain-language fix); the queue shows recent activity with
  traffic-light dots.

Setup: already included in `db/setup-all.sql` (reference copy: `db/phase6.sql`). Operations
executes on the existing 6-hour heartbeat (`scan` workflow) — no new
workflow, no new cost.

## Phase 7 — Recruiter: the creator engine, done honestly (5 minutes)

The ninth and final agent. No scraping, no gray areas (Policy B13) — the
Recruiter generates a **playbook per TEST pick** every Monday: the exact
TikTok searches that surface fitting creators, two outreach messages that
pass the same guardrails as our ads (no income promises to creators either,
one follow-up maximum by design), and the disclosure rule stated plainly:
posts need #ad — it's the law, and disclosed posts still convert.

The dashboard's Creators section adds the discipline layer:
- **Vetting scorecard** — add a candidate's handle, followers, and average
  views; the watch-rate math gives a plain verdict (invite / worth a try /
  skip). Big follower counts with tiny views get called what they are.
- **Sample ROI tracker** — log every sample sent (cost + date), mark when the
  creator posts, attribute sales as they come. Traffic lights enforce the
  rule that makes this channel work: green = earning, amber = waiting (30-day
  window shown), red = no post after 30 days, stop sending samples there.

Setup: already included in `db/setup-all.sql` (reference copy: `db/phase7.sql`). The Monday
workflow already ends with `recruiter`.

**All nine agents are now active.** The build is complete; what remains is
deployment, the validation run, the attorney session, and launch.

## The validation protocol (do this before selling anything)

The product's promise is *finding winners early*. Prove it, with receipts:

1. Let the engine run for **2–3 weeks** untouched.
2. Each Monday, save the digest and write down that week's TEST picks.
3. For each pick, log two checkpoints at +2 and +4 weeks:
   - Did it appear in mainstream tools' trending lists *after* we flagged it?
   - Did its Google Trends curve keep rising?
4. Hit rate = picks that confirmed / total picks. This number goes on the
   landing page (Charter §8) — whatever it is.

`picks.outcome` exists in the schema for exactly this bookkeeping.

---

## Roadmap (built as one piece — modules switch on)

| Phase | What activates | Funded by |
|---|---|---|
| **1 (now)** | Scout, Analyst, Publisher, guardrails, audit log | $0 |
| **1b** | Landing page + waitlist (`waitlist` table is ready) | $0 |
| **2** | Dashboard (Mission Control UI), Coach, Stripe billing | first users |
| **3** | Operations (store actions w/ caps), Bookkeeper (real P&L), Creative | subscribers |
| **4** | Sentinel (dispute/ad-ban radar), Recruiter (TikTok creators), compliance autopilot | revenue |

## Repo map

```
db/setup-all.sql                 the shared brain (ONE paste; others are references)
agents/tide/orchestrator.py      CLI + run audit log
agents/tide/scout/               discovery + sources (trends, reddit, meta)
agents/tide/analyst/             scoring model v0.1 (documented weights)
agents/tide/publisher/           weekly digest, honest-odds framing
agents/tide/guardrails/          charter-as-code category filters
agents/tide/...                  all nine agents — every one active
.github/workflows/               the free-tier heartbeat
reports/                         weekly digests land here
```

## House rules (non-negotiable)

- No feature ships that violates `internal-policy-attorney-brief.md` Parts A–D.
- Every agent run is logged to `runs` (audit trail).
- Scores must explain themselves. Uncertainty is stated, never hidden.
- Guardrail lists only loosen with a written founder exception.
