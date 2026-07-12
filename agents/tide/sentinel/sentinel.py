"""SENTINEL v1 — the protection radar. Compliance-improvement only (Policy B7):
it exists to keep members inside the rules, never to dodge detection.

Daily, per connected store:
  1. Dispute rate (30d): Shopify Payments disputes API when the token has the
     scope; otherwise the member's manual dispute log. Source is always shown.
  2. Refund rate (30d) from cached orders — early quality/supplier-drift signal.
  3. Shipping speed: % of orders older than 3 days with no fulfillment.
  4. Writes one protection snapshot + plain-language alerts with concrete next
     steps. One open alert per topic — no alarm spam.

Thresholds (documented, conservative — processors act around 0.75–1%):
  disputes:  watch >=0.30%   warning >=0.50%   urgent >=0.65%
  refunds:   watch >=5%      warning >=10%     urgent >=15%
  shipping:  watch >=5%      warning >=10%     urgent >=20%   (late after 3 days)
"""
import datetime
import json

import requests

API_VERSION = "2024-04"

LEVELS = {
    "disputes": [(0.0065, "urgent"), (0.0050, "warning"), (0.0030, "watch")],
    "refunds":  [(0.15, "urgent"), (0.10, "warning"), (0.05, "watch")],
    "shipping": [(0.20, "urgent"), (0.10, "warning"), (0.05, "watch")],
}

NEXT_STEPS = {
    "disputes": ("Do these today: reply to every open dispute with tracking and "
                 "delivery proof; check that product pages promise realistic "
                 "delivery dates; make sure tracking emails go out the day of "
                 "purchase; slow down ad scaling until the rate falls."),
    "refunds": ("A rising refund rate usually means the supplier changed "
                "something or the listing over-promises. Order a fresh sample, "
                "compare it to your photos, and tighten the product description."),
    "shipping": ("Orders are sitting unshipped. Contact the supplier today, and "
                 "pause ads on anything they can't ship within 3 days — late "
                 "delivery is the #1 cause of disputes."),
}


def _severity(kind: str, rate: float) -> str | None:
    for threshold, level in LEVELS[kind]:
        if rate >= threshold:
            return level
    return None


def _shopify_disputes_30d(domain: str, token: str) -> int | None:
    """Count Shopify Payments disputes initiated in the last 30 days.
    Returns None when the API/scope isn't available (we then fall back)."""
    try:
        r = requests.get(
            f"https://{domain}/admin/api/{API_VERSION}/shopify_payments/disputes.json",
            headers={"X-Shopify-Access-Token": token},
            params={"initiated_at_min":
                    (datetime.date.today() - datetime.timedelta(days=30)).isoformat()},
            timeout=25,
        )
        if r.status_code != 200:
            return None
        return len(r.json().get("disputes", []))
    except Exception:  # noqa: BLE001
        return None


def _raise_alert(cur, store_id: int, kind: str, severity: str,
                 rate: float, detail: str) -> bool:
    """Insert an alert unless an unresolved one for this topic already exists."""
    cur.execute(
        "select 1 from alerts where store_id=%s and kind=%s and not resolved limit 1",
        (store_id, kind),
    )
    if cur.fetchone():
        return False
    titles = {
        "disputes": f"Dispute rate is {rate:.2%} — act before processors do",
        "refunds": f"Refund rate is {rate:.0%} — quality may be drifting",
        "shipping": f"{rate:.0%} of recent orders are shipping late",
    }
    body = (f"{detail} Severity: {severity}. Processors and platforms act on "
            f"sustained problems, and early fixes are cheap. "
            f"{NEXT_STEPS[kind]}")
    cur.execute(
        """insert into alerts (store_id, kind, severity, title, body)
           values (%s,%s,%s,%s,%s)""",
        (store_id, kind, severity, titles[kind], body),
    )
    return True


def _check_store(cur, store: dict) -> dict:
    sid = store["id"]
    start = datetime.date.today() - datetime.timedelta(days=30)
    cutoff = datetime.date.today() - datetime.timedelta(days=3)

    cur.execute(
        """select count(*) as n,
                  count(*) filter (where refunded > 0) as refunded_orders,
                  count(*) filter (where created_day <= %s and fulfilled_day is null)
                      as late_orders,
                  count(*) filter (where created_day <= %s) as shippable
           from orders_cache where store_id=%s and created_day >= %s""",
        (cutoff, cutoff, sid, start),
    )
    o = cur.fetchone()
    n = o["n"] or 0

    disputes = _shopify_disputes_30d(store["shop_domain"], store["access_token"])
    if disputes is not None:
        source = "shopify_payments"
    else:
        cur.execute(
            "select count(*) as c from disputes_log where store_id=%s and day >= %s",
            (sid, start),
        )
        disputes = cur.fetchone()["c"]
        source = "manual_log" if disputes else "none"

    dispute_rate = (disputes / n) if n else None
    refund_rate = (o["refunded_orders"] / n) if n else None
    late_rate = (o["late_orders"] / o["shippable"]) if o["shippable"] else None

    alerts_raised = 0
    if n >= 20:  # below this, rates are noise — say so instead of alarming
        checks = [
            ("disputes", dispute_rate,
             f"{disputes} dispute(s) across {n} orders in 30 days "
             f"(source: {source.replace('_', ' ')})."),
            ("refunds", refund_rate,
             f"{o['refunded_orders']} of {n} orders refunded in 30 days."),
            ("shipping", late_rate,
             f"{o['late_orders']} of {o['shippable']} orders are older than 3 "
             f"days with no shipment."),
        ]
        for kind, rate, detail in checks:
            if rate is None:
                continue
            sev = _severity(kind, rate)
            if sev and _raise_alert(cur, sid, kind, sev, rate, detail):
                alerts_raised += 1

    cur.execute(
        """insert into protection (store_id, dispute_rate, dispute_source,
             refund_rate, late_rate, orders_30d, details, checked_at)
           values (%s,%s,%s,%s,%s,%s,%s,now())
           on conflict (store_id) do update set
             dispute_rate=excluded.dispute_rate, dispute_source=excluded.dispute_source,
             refund_rate=excluded.refund_rate, late_rate=excluded.late_rate,
             orders_30d=excluded.orders_30d, details=excluded.details,
             checked_at=now()""",
        (sid, dispute_rate, source, refund_rate, late_rate, n,
         json.dumps({
             "disputes_30d": disputes,
             "min_sample_note": None if n >= 20 else
                 "Under 20 orders in 30 days — rates would be noise, so alerts "
                 "stay off until there's enough data.",
             "thresholds": {k: [[t, l] for t, l in v] for k, v in LEVELS.items()},
         })),
    )
    return {"orders": n, "alerts": alerts_raised}


def run(run_id: int | None = None) -> dict:
    from .. import db
    stats = {"stores": 0, "alerts": 0, "errors": 0}
    with db.cursor() as cur:
        cur.execute("select id, shop_domain, access_token from stores")
        stores = cur.fetchall()

    for store in stores:
        try:
            with db.cursor() as cur:
                s = _check_store(cur, store)
            stats["stores"] += 1
            stats["alerts"] += s["alerts"]
            print(f"[sentinel] {store['shop_domain']}: {s}")
        except Exception as e:  # noqa: BLE001
            stats["errors"] += 1
            print(f"[sentinel] {store['shop_domain']} FAILED: {e}")

    print(f"[sentinel] done: {stats}")
    return stats
