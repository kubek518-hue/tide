# FILE-BY-FILE AUDIT CHECKLIST — Build v1.1
*Every file in this project, individually checked. ✓ = verified good.
✎ = a problem was found in this pass and FIXED in v1.1.*

## Root
- ✓ VERSION.txt — build stamp; regenerated for v1.1
- ✓ MANIFEST.sha256 — fingerprint of every file; regenerated for v1.1
- ✎ README.md — FIXED: 7 stale "paste db/phaseX.sql" instructions unified to
  the single setup-all.sql paste; "dormant agents" wording removed (all
  nine are active); repo map updated
- ✎ EXPRESS-ASSEMBLY.md — FIXED: pointed to a helper file that no longer
  existed; now points to EXTRA-HELP-WINDOWS.md (which now ships in the repo)
- ✓ EXTRA-HELP-WINDOWS.md — added to the repo (was download-only before)
- ✓ AUDIT-REPORT.md — current for v1.1
- ✓ .env.example — all 7 variables present and correct (DATABASE_URL,
  META_AD_LIBRARY_TOKEN, tuning knobs, ANTHROPIC_API_KEY, LLM_MODEL, cap)
- ✓ .gitignore — .env, caches, and reports/*.md ignored (intentional:
  weekly digests are delivered as workflow artifacts, not commits)
- ✓ reports/.gitkeep — keeps the folder in git; publisher also creates it

## db/ (database)
- ✓ setup-all.sql — THE one-paste file: verified 24 tables + 24 security
  policies, phase order machine-checked
- ✓ schema.sql — reference copy, phase 1 (products, signals, scores, picks,
  runs, waitlist)
- ✓ waitlist_policy.sql — insert-only public access; emails unreadable
- ✓ phase2.sql — members, briefings, auth trigger, member-read policies
- ✓ phase3.sql — stores (tokens WRITE-ONLY: no select policy, verified),
  store_status mirror trigger, product_costs, ad_spend, orders_cache,
  pnl_daily (NULLS NOT DISTINCT unique index verified)
- ✓ phase4.sql — protection, alerts (read + resolve policies), disputes_log,
  fulfilled_day column
- ✓ phase5.sql — creatives, pick outcome columns, hitrate_public
  (anon-readable by design, Charter §8)
- ✓ phase6.sql — op_settings, actions queue; RLS verified to allow ONLY:
  member inserts pre-approved whitelisted kinds; proposals moved only to
  approved/declined
- ✓ phase7.sql — playbooks, creators, samples with owner policies

## agents/ (the brain)
- ✓ requirements.txt — 6 pinned deps; pandas capped <2.2 (pytrends guard)
- ✓ tide/config.py — env-driven, helpful error if DATABASE_URL missing
- ✓ tide/db.py — connection, slugify, upserts, run audit logging
- ✓ tide/orchestrator.py — all 11 commands registered (9 agents + audit;
  selftest runs standalone); run logging verified
- ✓ tide/selftest.py — 4 checks, plain-language output, safe/read-only
- ✓ tide/auditor.py — hit-rate publisher; correct `from . import db`
- ✓ tide/guardrails/category_filters.py — exclude/flag lists + plain
  warnings; unit-tested (weapons excluded, kids flagged, lamp clear)
- ✓ tide/guardrails/ad_claims.py — 7 claim rules; unit-tested both ways
- ✓ tide/scout/scout.py — seeds→candidates→signals; excluded products
  recorded but never scored; imports verified (`from .sources import ...`)
- ✓ tide/scout/seeds.yaml — 30 categories, parses
- ✓ tide/scout/sources/google_trends.py — discover + momentum, paced,
  crash-proof (every call wrapped)
- ✓ tide/scout/sources/reddit.py — public JSON, organic-ratio math checked
- ✓ tide/scout/sources/meta_ad_library.py — official API, skips gracefully
  without token
- ✓ tide/analyst/analyst.py — weights documented; missing-ad-data honesty
  cap re-tested (10/20); source count cleaned this audit; lazy db import
- ✓ tide/publisher/publisher.py — reports path resolves to repo /reports
  (verified parents[3]); honest-odds disclaimer present
- ✓ tide/coach/coach.py — weekly briefing upsert; Charter §7 language
- ✓ tide/bookkeeper/bookkeeper.py — pagination via Link headers; refunds
  from total vs current; fulfilled_day recorded; NULL-cogs honesty; fee
  estimates labeled; one bad store can't block others
- ✓ tide/sentinel/sentinel.py — thresholds unit-tested; <20-orders noise
  guard; dispute source always recorded; lazy db import
- ✓ tide/creative/creative.py — template mode 15 angles zero flags; refusal
  path tested; LLM capped + cached; lazy db import
- ✓ tide/operations/operations.py — ✎ FIXED in v1.0 audit (fatal import),
  re-verified gone in this pass; payload validation incl. injection test;
  kill switch → cap → whitelist ordering confirmed
- ✓ tide/recruiter/recruiter.py — outreach guardrail-tested; queries builder
  tested; lazy db import
- ✓ all 12 __init__.py files — present, intentionally empty

## .github/workflows/ (the robots)
- ✓ scan.yml — every 6h: scout analyst operations; parses; secret wired
- ✓ digest.yml — Mondays: publisher coach creative audit recruiter;
  ANTHROPIC_API_KEY optional; artifact upload of the digest
- ✓ bookkeeper.yml — daily: bookkeeper sentinel
- ✓ setup.yml — inputs → key injection (sed patterns match the exact
  placeholders in both pages, verified) → commit → Pages enable + deploy →
  address printed → first hunt if secret exists; permissions correct
  (contents/pages/id-token); safe to re-run
- ✓ healthcheck.yml — runs tide.selftest with the secret

## docs/ (the faces)
- ✓ index.html — divs balanced; visible copy passes banned-vocab scan; the
  three PASTE placeholders + contact email present for the SETUP button;
  waitlist posts with honeypot; hit-rate fetch guarded and switches at ≥10
  scored picks
- ✓ app.html — divs balanced; copy scan clean; all six loaders wired
  (dashboard, store, protection, ops, crew + route); both hand-patched
  regions re-inspected this pass (angles block at its definition and its
  single use; queue button correctly inside the TEST-verdict conditional);
  Supabase v2 inserts use minimal returns (no select-policy violations)

## governance/ + supabase/
- ✓ governance/operators-charter.md — 11 commitments, complete
- ✓ governance/internal-policy-attorney-brief.md — Parts A–G complete,
  incl. all 16 Never-Build items and the E1–E10 attorney agenda
- ✓ supabase/functions/stripe-webhook/index.ts — HMAC signature check,
  5-minute replay window, upsert on email conflict, service-role writes

**Total: 61 files. 61 checked. 3 fixed in this pass (all documentation),
0 code defects remaining known.**
