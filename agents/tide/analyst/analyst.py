"""ANALYST — turns raw signals into a 0–100 score, a verdict, and evidence.

Scoring model v0.1 (every weight is documented; Charter 8 requires the score
to explain itself, so evidence JSON always states what was seen and missing):

  momentum      0–40  Google Trends slope + recency (is interest accelerating?)
  confirmation  0–25  Reddit chatter volume x organic ratio (are humans talking?)
  opportunity   0–20  Meta ad count inverted (few ads while rising = early)
                      -> without a Meta token this axis maxes at 10 (uncertainty
                         is expressed, never hidden)
  viability     0–15  Logistics heuristics from the product name (small/light
                      goods score higher; oversized/freight items score lower)

Verdicts: total >= 68 -> test | 45–67 -> watch | < 45 -> skip
Confidence: how many independent sources reported FRESH data (1 low, 2 med, 3+ high)

Model v0.2 additions (FRESHNESS LAW + multi-source agreement):
  - Every signal is weighed by age: full weight to 7 days, decaying to 40% at
    30 days, DISCARDED past 45 — and the evidence says so, always.
  - A source only counts toward confidence if it reported within 14 days.
  - Agreement rule: a lone fresh source can never produce a "test" verdict —
    it is downgraded to "watch" and the evidence states why. One signal is
    never enough to bet money on.
Weights and thresholds are unchanged from v0.1 — same 0-100 scale, same
verdict lines. v0.2 only distrusts stale data and lone signals.
"""
import datetime as _dt

FRESH_FULL_DAYS = 7          # this young counts in full
FRESH_FLOOR_DAYS = 30        # by now a signal counts 40%
STALE_DISCARD_DAYS = 45      # older than this is treated as missing — and said
FRESH_SOURCE_DAYS = 14       # a source only "agrees" if it reported in 2 weeks


def _age_days(captured_at, now=None) -> float | None:
    if captured_at is None:
        return None
    now = now or _dt.datetime.now(_dt.timezone.utc)
    ca = captured_at if captured_at.tzinfo else captured_at.replace(tzinfo=_dt.timezone.utc)
    return max(0.0, (now - ca).total_seconds() / 86400)


def _freshness_factor(age: float | None) -> float:
    """FRESHNESS LAW: newer weighs more; stale is distrusted, then discarded.
    Unknown age is trusted at full and the evidence admits the date is missing."""
    if age is None:
        return 1.0
    if age > STALE_DISCARD_DAYS:
        return 0.0
    if age <= FRESH_FULL_DAYS:
        return 1.0
    if age >= FRESH_FLOOR_DAYS:
        return 0.4
    return 1.0 - 0.6 * ((age - FRESH_FULL_DAYS) / (FRESH_FLOOR_DAYS - FRESH_FULL_DAYS))


def _fresh_tag(age: float | None) -> str:
    if age is None:
        return "date unknown — trusted, with this caveat on record"
    if age > STALE_DISCARD_DAYS:
        return f"{age:.0f}d old — stale, discarded"
    if age <= FRESH_FULL_DAYS:
        return f"{age:.0f}d old — fresh"
    return f"{age:.0f}d old — discounted for age"


def _verdict_with_agreement(total: float, n_fresh: int) -> tuple[str, str | None]:
    """Multi-source agreement: 'hot' requires several fresh signals agreeing."""
    verdict = ("test" if total >= VERDICT_TEST
               else "watch" if total >= VERDICT_WATCH else "skip")
    if verdict == "test" and n_fresh < 2:
        return "watch", ("downgraded to watch: only one fresh source — "
                         "a single signal is never enough to bet money on")
    if verdict == "test":
        return verdict, f"met — {n_fresh} fresh sources agree"
    return verdict, None

VERDICT_TEST = 68
VERDICT_WATCH = 45

HEAVY_WORDS = ["furniture", "sofa", "treadmill", "mattress", "desk", "cabinet",
               "trampoline", "kayak", "grill"]
LIGHT_WORDS = ["organizer", "holder", "mount", "clip", "strap", "cover", "mat",
               "light", "lamp", "brush", "opener", "peeler", "sticker", "case"]


def _momentum_points(sig: dict) -> tuple[float, dict]:
    m = sig.get("google_trends:momentum")
    ev = {"trend_series": None}
    if not m:
        return 0.0, ev
    raw = m["raw"]
    slope = float(raw.get("slope", 0))
    recency = float(raw.get("recency_ratio", 1))
    pts = max(0.0, min(25.0, slope * 2500))            # slope of .01/step = full marks
    pts += max(0.0, min(10.0, (recency - 1.0) * 10))   # recent > earlier
    if raw.get("peak_recent"):
        pts += 5
    age = _age_days(m.get("captured_at"))
    f = _freshness_factor(age)
    if f == 0.0:
        ev["trend_series"] = {"stale": f"last reading {age:.0f} days old — discarded (freshness law)"}
        return 0.0, ev
    ev["trend_series"] = {"slope": slope, "recency_ratio": recency,
                          "peak_recent": raw.get("peak_recent"),
                          "freshness": _fresh_tag(age), "weight": round(f, 2)}
    return round(min(40.0, pts) * f, 2), ev


def _confirmation_points(sig: dict) -> tuple[float, dict]:
    r = sig.get("reddit:mentions_30d")
    ev = {"reddit": None}
    if not r:
        return 0.0, ev
    raw = r["raw"]
    mentions = int(raw.get("mentions_30d", 0))
    organic = float(raw.get("organic_ratio", 0))
    pts = min(15.0, mentions * 0.5) * (0.5 + 0.5 * organic)
    if mentions >= 10 and organic >= 0.8:
        pts += 5
    age = _age_days(r.get("captured_at"))
    f = _freshness_factor(age)
    if f == 0.0:
        ev["reddit"] = {"stale": f"last reading {age:.0f} days old — discarded (freshness law)"}
        return 0.0, ev
    ev["reddit"] = {"mentions_30d": mentions, "organic_ratio": organic,
                    "freshness": _fresh_tag(age), "weight": round(f, 2)}
    return round(min(25.0, pts) * f, 2), ev


def _opportunity_points(sig: dict) -> tuple[float, dict]:
    a = sig.get("meta_ads:active_ads")
    ev = {"meta_ads": None}
    if not a:
        # No ad data -> cap at neutral 10/20 and say so. Never fake certainty.
        ev["meta_ads"] = "no data (token not configured) — capped at 10/20"
        return 10.0, ev
    age = _age_days(a.get("captured_at"))
    if _freshness_factor(age) == 0.0:
        ev["meta_ads"] = f"last ad reading {age:.0f} days old — discarded, capped at 10/20 (freshness law)"
        return 10.0, ev
    count = int(a["raw"].get("active_ads", 0))
    ev["meta_ads"] = {"active_ads": count, "freshness": _fresh_tag(age)}
    if count <= 5:
        return 20.0, ev
    if count <= 25:
        return 14.0, ev
    if count <= 100:
        return 7.0, ev
    return 2.0, ev


def _viability_points(name: str) -> tuple[float, dict]:
    n = name.lower()
    if any(w in n for w in HEAVY_WORDS):
        return 4.0, {"logistics": "heavy/oversized — freight risk"}
    if any(w in n for w in LIGHT_WORDS):
        return 13.0, {"logistics": "small & light — cheap to ship, low return pain"}
    return 9.0, {"logistics": "unknown size class — neutral"}


def run(run_id: int | None = None) -> dict:
    from .. import db
    stats = {"scored": 0, "test": 0, "watch": 0, "skip": 0}
    with db.cursor() as cur:
        cur.execute(
            """select id, name, guard_status, guard_reasons from products
               where guard_status <> 'excluded' and status <> 'archived'"""
        )
        products = cur.fetchall()

        for p in products:
            sig = db.latest_signals(cur, p["id"])
            if not sig:
                continue

            momentum, ev1 = _momentum_points(sig)
            confirmation, ev2 = _confirmation_points(sig)
            opportunity, ev3 = _opportunity_points(sig)
            viability, ev4 = _viability_points(p["name"])
            total = round(momentum + confirmation + opportunity + viability, 1)

            sources = len({k.split(":")[0] for k in sig})
            fresh = {k.split(":")[0] for k, v in sig.items()
                     if (_age_days(v.get("captured_at")) or 0) <= FRESH_SOURCE_DAYS}
            n_fresh = len(fresh)
            confidence = "high" if n_fresh >= 3 else "medium" if n_fresh == 2 else "low"
            verdict, agreement = _verdict_with_agreement(total, n_fresh)

            evidence = {**ev1, **ev2, **ev3, **ev4,
                        "sources_reporting": sources,
                        "sources_fresh": n_fresh,
                        **({"agreement_rule": agreement} if agreement else {}),
                        "guard_status": p["guard_status"],
                        "guard_reasons": p["guard_reasons"],
                        "model_version": "0.2"}

            cur.execute(
                """insert into scores (product_id, run_id, momentum, confirmation,
                     opportunity, viability, total, verdict, confidence, evidence)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (p["id"], run_id, momentum, confirmation, opportunity,
                 viability, total, verdict, confidence,
                 __import__("json").dumps(evidence)),
            )
            stats["scored"] += 1
            stats[verdict] += 1

    print(f"[analyst] done: {stats}")
    return stats
