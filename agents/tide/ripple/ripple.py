"""RIPPLE LAB — EXPERIMENT. Predicts demand from upcoming culture & seasons.

HONEST FRAMING (do not remove): this is the shakiest feature in TIDE. Most
cultural moments lift nothing measurable for a small seller. Every prediction
here is a "possible lift" for a product CATEGORY, never a promise. The lab
grades itself: the founder judges each ripple hit/miss after the event, and
the auditor publishes the lab's own accuracy separately from the real picks.
If that number is poor after 4-8 weeks, the honest move is to REMOVE this lab.

Sources (deliberately $0 and key-free):
  1. A deterministic seasonal/retail calendar (the only "medium" confidence
     entries are the two strongest retail moments: Black Friday and Christmas).
  2. events.yaml — culture events (movies, games, sports) the founder adds by
     hand. Always low confidence. Automated culture feeds need API keys or
     scraping; this is the honest key-free v1. UPGRADE POINT: a keyed feed
     (e.g. TMDB) could populate events here later — marked, not built.

Guardrail (Policy B): generic categories only. Never counterfeit, never
fake-licensed. "Inspired-by" is the line, and guard_category() enforces the
label whenever an event name leaks into a category.

Wiring note (kept safe on purpose): each ripple carries watch_terms the
founder can add to scout/seeds.yaml by hand. UPGRADE POINT: auto-feeding
scout was deliberately NOT built — the experiment must not touch the real
pipeline until its own hit rate earns it.
"""
import datetime as _dt
import json
import pathlib

import yaml

EVENTS_FILE = pathlib.Path(__file__).parent / "events.yaml"
HEADS_UP_DAYS = 45          # a ripple appears ~6 weeks before its stock-by date


# ── date math (pure, unit-tested) ──────────────────────────────────────────
def nth_weekday(year: int, month: int, weekday: int, n: int) -> _dt.date:
    """n-th <weekday> of a month. Monday=0 .. Sunday=6."""
    first = _dt.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + _dt.timedelta(days=offset + 7 * (n - 1))


def black_friday(year: int) -> _dt.date:
    """Day after the 4th Thursday of November."""
    return nth_weekday(year, 11, 3, 4) + _dt.timedelta(days=1)


# ── the deterministic calendar ──────────────────────────────────────────────
# confidence policy: 'low' by default; 'medium' ONLY for the two strongest
# deterministic retail moments. Nothing here is ever 'high' — honesty first.
def seasonal_rules(year: int) -> list[dict]:
    return [
        dict(key=f"valentines-{year}", name="Valentine's Day",
             date=_dt.date(year, 2, 14), lead_weeks=6, confidence="low",
             categories=["small giftable accessories", "candles & cozy home decor",
                         "couple-themed kitchenware (generic)"],
             watch_terms=["valentines gift for him", "valentines gift for her"],
             reasoning="Gift-buying spikes reliably, but it is crowded and ad costs rise with it."),
        dict(key=f"mothers-day-{year}", name="Mother's Day (US)",
             date=nth_weekday(year, 5, 6, 2), lead_weeks=5, confidence="low",
             categories=["self-care & spa-style items", "garden accessories",
                         "personalizable keepsakes (generic blanks)"],
             watch_terms=["mothers day gift ideas"],
             reasoning="Strong gifting moment; generic categories only, competition is heavy."),
        dict(key=f"fathers-day-{year}", name="Father's Day (US)",
             date=nth_weekday(year, 6, 6, 3), lead_weeks=5, confidence="low",
             categories=["grilling & outdoor cooking accessories", "desk & tool organizers",
                         "hobby gadgets (generic)"],
             watch_terms=["fathers day gift ideas"],
             reasoning="Smaller than Mother's Day but consistent; watch shipping cutoffs."),
        dict(key=f"summer-outdoors-{year}", name="Summer outdoors season",
             date=_dt.date(year, 6, 21), lead_weeks=8, confidence="low",
             categories=["cooling products", "beach & pool accessories", "garden & patio items"],
             watch_terms=["cooling towel", "portable fan"],
             reasoning="Seasonal, weather-dependent, and regional — real but noisy."),
        dict(key=f"back-to-school-{year}", name="Back to school",
             date=_dt.date(year, 9, 1), lead_weeks=8, confidence="low",
             categories=["desk & locker organizers", "lunch gear", "study accessories"],
             watch_terms=["back to school supplies", "desk organizer"],
             reasoning="Reliable calendar demand; margins are thin because everyone knows it."),
        dict(key=f"halloween-{year}", name="Halloween",
             date=_dt.date(year, 10, 31), lead_weeks=8, confidence="low",
             categories=["home & yard decor (generic spooky)", "party accessories",
                         "costume accessories (generic, no characters)"],
             watch_terms=["halloween decorations"],
             reasoning="Big seasonal spike; strictly generic — character costumes are licensed goods."),
        dict(key=f"black-friday-{year}", name="Black Friday / Cyber Monday",
             date=black_friday(year), lead_weeks=10, confidence="medium",
             categories=["giftable gadgets", "cozy home items", "stocking-stuffer-sized products"],
             watch_terms=["black friday deals"],
             reasoning="The strongest deterministic retail moment of the year — which also means peak ad prices."),
        dict(key=f"christmas-{year}", name="Christmas gifting",
             date=_dt.date(year, 12, 25), lead_weeks=10, confidence="medium",
             categories=["gifts under $30 (generic)", "holiday home decor", "family game-night items"],
             watch_terms=["christmas gift ideas"],
             reasoning="Deterministic and huge; stock and shipping deadlines decide winners."),
        dict(key=f"new-year-fitness-{year}", name="New-year fitness wave",
             date=_dt.date(year, 1, 15), lead_weeks=6, confidence="low",
             categories=["home fitness accessories", "meal-prep & planning items"],
             watch_terms=["home workout equipment"],
             reasoning="Real spike, fast fade — most buyers quit by February and so does the demand."),
    ]


# ── guardrails & windows (pure, unit-tested) ────────────────────────────────
def guard_category(event_name: str, category: str) -> str:
    """Policy B: if an event's name leaks into a category, force the
    inspired-by label so nobody reads it as license to sell fakes."""
    if event_name.lower() in category.lower() and "inspired-by" not in category.lower():
        return f"{category} (inspired-by only — never fake-licensed)"
    return category


def stock_by(event_date: _dt.date, lead_weeks: int) -> _dt.date:
    return event_date - _dt.timedelta(weeks=lead_weeks)


def in_window(today: _dt.date, stock_by_date: _dt.date, event_date: _dt.date,
              heads_up_days: int = HEADS_UP_DAYS) -> bool:
    """A ripple is worth showing from ~6 weeks before its stock-by date
    until the event itself. Earlier is noise; later is too late to act."""
    return (stock_by_date - _dt.timedelta(days=heads_up_days)) <= today <= event_date


def load_founder_events() -> list[dict]:
    """Founder-added culture events (movies/games/sports). ALWAYS low
    confidence — a human hunch is a hunch, and the lab must say so."""
    if not EVENTS_FILE.exists():
        return []
    with open(EVENTS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out = []
    for e in data.get("events") or []:
        try:
            date = e["date"] if isinstance(e["date"], _dt.date) else _dt.date.fromisoformat(str(e["date"]))
            name = str(e["name"]).strip()
            if not name:
                continue
            out.append(dict(
                key=f"founder-{_slug(name)}-{date.isoformat()}",
                name=name, date=date,
                lead_weeks=int(e.get("lead_weeks", 6)),
                confidence="low",                      # forced, on purpose
                categories=[str(c) for c in (e.get("categories") or [])][:6],
                watch_terms=[str(t) for t in (e.get("watch_terms") or [])][:6],
                reasoning=str(e.get("note", "Founder-added culture event. A hunch, labeled as one.")),
            ))
        except (KeyError, ValueError, TypeError) as bad:
            print(f"[ripple] skipping malformed event {e!r}: {bad}")
    return out


def _slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "event"


def build_ripples(today: _dt.date) -> list[dict]:
    """All ripples currently worth showing (pure — testable without a DB)."""
    candidates = []
    for year in (today.year, today.year + 1):
        candidates.extend(seasonal_rules(year))
    candidates.extend(load_founder_events())

    out = []
    for c in candidates:
        sb = stock_by(c["date"], c["lead_weeks"])
        if not in_window(today, sb, c["date"]):
            continue
        out.append(dict(
            event_key=c["key"], event_name=c["name"], event_date=c["date"],
            stock_by=sb, confidence=c["confidence"],
            categories=[guard_category(c["name"], cat) for cat in c["categories"]],
            watch_terms=c["watch_terms"],
            reasoning=c["reasoning"],
        ))
    return out


# ── the agent ───────────────────────────────────────────────────────────────
def run(run_id: int | None = None) -> dict:
    from .. import db  # lazy on purpose — keeps the pure logic testable

    today = _dt.date.today()
    ripples = build_ripples(today)
    written = 0
    with db.cursor() as cur:
        for r in ripples:
            cur.execute(
                """insert into ripples
                     (event_key, event_name, event_date, stock_by, confidence,
                      categories, watch_terms, reasoning)
                   values (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                   on conflict (event_key) do update set
                     event_name = excluded.event_name,
                     event_date = excluded.event_date,
                     stock_by   = excluded.stock_by,
                     confidence = excluded.confidence,
                     categories = excluded.categories,
                     watch_terms = excluded.watch_terms,
                     reasoning  = excluded.reasoning""",
                (r["event_key"], r["event_name"], r["event_date"], r["stock_by"],
                 r["confidence"], json.dumps(r["categories"]),
                 json.dumps(r["watch_terms"]), r["reasoning"]),
            )
            written += 1
    stats = {"in_window": written,
             "note": "experiment — outcomes are founder-judged after each event; "
                     "the auditor publishes the lab's own accuracy"}
    print(f"[ripple] {stats}")
    return stats
