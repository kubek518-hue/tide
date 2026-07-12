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
Confidence: how many independent sources actually reported (1 low, 2 med, 3+ high)
"""

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
    ev["trend_series"] = {"slope": slope, "recency_ratio": recency,
                          "peak_recent": raw.get("peak_recent")}
    return min(40.0, pts), ev


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
    ev["reddit"] = {"mentions_30d": mentions, "organic_ratio": organic}
    return min(25.0, pts), ev


def _opportunity_points(sig: dict) -> tuple[float, dict]:
    a = sig.get("meta_ads:active_ads")
    ev = {"meta_ads": None}
    if not a:
        # No ad data -> cap at neutral 10/20 and say so. Never fake certainty.
        ev["meta_ads"] = "no data (token not configured) — capped at 10/20"
        return 10.0, ev
    count = int(a["raw"].get("active_ads", 0))
    ev["meta_ads"] = {"active_ads": count}
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
            confidence = "high" if sources >= 3 else "medium" if sources == 2 else "low"
            verdict = ("test" if total >= VERDICT_TEST
                       else "watch" if total >= VERDICT_WATCH else "skip")

            evidence = {**ev1, **ev2, **ev3, **ev4,
                        "sources_reporting": sources,
                        "guard_status": p["guard_status"],
                        "guard_reasons": p["guard_reasons"],
                        "model_version": "0.1"}

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
