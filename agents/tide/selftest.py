"""SELF-TEST — run `python -m tide.selftest` (or the workflow) any time
something feels wrong. It checks the whole pipeline's plumbing and reports
in plain language. Safe to run as often as you like; it changes nothing.
"""
import sys


def main() -> int:
    ok = True

    # 1. Environment
    import os
    if os.environ.get("DATABASE_URL"):
        print("[1/6] Database key ......... found")
    else:
        print("[1/6] Database key ......... MISSING — set the DATABASE_URL "
              "secret (guide Part 3)")
        return 1

    # 2. Connection
    try:
        from . import db
        with db.cursor() as cur:
            cur.execute("select 1 as one")
            assert cur.fetchone()["one"] == 1
        print("[2/6] Database connection .. works")
    except Exception as e:  # noqa: BLE001
        print(f"[2/6] Database connection .. FAILED — {str(e)[:160]}")
        print("      Usual cause: the password inside DATABASE_URL (no [ ] "
              "brackets allowed), or a paused Supabase project (open the "
              "dashboard and click Restore).")
        return 1

    # 3. Tables (one per phase)
    expected = ["products", "signals", "scores", "picks", "runs", "waitlist",
                "members", "briefings", "stores", "pnl_daily", "protection",
                "alerts", "creatives", "hitrate_public", "actions", "playbooks",
                "creators", "samples"]
    try:
        with db.cursor() as cur:
            cur.execute(
                "select table_name from information_schema.tables "
                "where table_schema='public'")
            have = {r["table_name"] for r in cur.fetchall()}
        missing = [t for t in expected if t not in have]
        if missing:
            ok = False
            print(f"[3/6] Tables ............... MISSING: {', '.join(missing)}")
            print("      Fix: run db/setup-all.sql once in the Supabase SQL "
                  "Editor (guide Part 1).")
        else:
            print(f"[3/6] Tables ............... all {len(expected)} present")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"[3/6] Tables ............... check failed — {str(e)[:120]}")

    # 4. Signs of life
    try:
        with db.cursor() as cur:
            cur.execute("select count(*) as c from products")
            n = cur.fetchone()["c"]
            cur.execute("select agent, ok, started_at from runs "
                        "order by id desc limit 1")
            last = cur.fetchone()
        life = f"{n} products known"
        if last:
            life += (f"; last agent run: {last['agent']} "
                     f"({'ok' if last['ok'] else 'FAILED'}) at "
                     f"{last['started_at']:%Y-%m-%d %H:%M} UTC")
        else:
            life += "; no agent runs yet — run the 'scan' workflow once"
        print(f"[4/6] Signs of life ........ {life}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"[4/6] Signs of life ........ check failed — {str(e)[:120]}")

    # 5. Source freshness — the self-monitoring the freshness law requires.
    #    A quiet source is a WARNING, not a failure: scoring already discounts
    #    stale data on its own; this line just tells you why numbers moved.
    try:
        import datetime as dt
        with db.cursor() as cur:
            cur.execute("select source, max(captured_at) as last from signals group by source")
            latest = {r["source"]: r["last"] for r in cur.fetchall()}
        now = dt.datetime.now(dt.timezone.utc)
        parts = []
        for src, label in (("google_trends", "Google Trends"), ("reddit", "Reddit"),
                           ("meta_ads", "Meta Ad Library")):
            last = latest.get(src)
            if last is None:
                parts.append(label + (": never reported (fine — needs a token you haven't added)"
                                      if src == "meta_ads" else
                                      ": never reported — run the scan workflow once"))
                continue
            if last.tzinfo is None:
                last = last.replace(tzinfo=dt.timezone.utc)
            days = (now - last).days
            parts.append(f"{label}: {days}d ago" + ("" if days <= 7 else
                         " — GONE QUIET; scoring is already discounting it (freshness law); check the scan workflow"))
        print("[5/6] Source freshness ..... " + " | ".join(parts))
    except Exception as e:  # noqa: BLE001
        print(f"[5/6] Source freshness ..... check failed — {str(e)[:120]}")

    # 6. v2 pieces present? (warning with the exact fix, never a hard failure)
    try:
        with db.cursor() as cur:
            cur.execute("select table_name from information_schema.tables where table_schema='public'")
            have2 = {r["table_name"] for r in cur.fetchall()}
        v2_missing = [t for t in ("profit_estimates", "ripples") if t not in have2]
        if v2_missing:
            print(f"[6/6] v2 database step ..... NOT RUN YET — missing {', '.join(v2_missing)}. "
                  "Fix: paste v2-migration.sql once in the Supabase SQL Editor (v2 guide Part 2).")
        else:
            print("[6/6] v2 database step ..... installed (profit estimates + Ripple Lab)")
    except Exception as e:  # noqa: BLE001
        print(f"[6/6] v2 database step ..... check failed — {str(e)[:120]}")

    print("\nRESULT:", "ALL GOOD — the pipeline is healthy." if ok
          else "Something needs attention — see the lines above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
