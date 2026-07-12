"""BOOKKEEPER v1 — profit truth. No vanity GMV, ever.

For every connected store, every run:
  1. Pull the last 30 days of orders from the Shopify Admin API
  2. Rebuild pnl_daily:
       - one row per (day, product): units, revenue, cogs, gross profit
       - one store-level row per day: payment fees (estimated), ad spend
         (user-logged), refunds — the costs that don't belong to one product
  3. Update store_status so the dashboard can say when numbers were last fresh

Honesty rules baked in:
  - A product with no user-entered cost gets profit = NULL, shown as
    "needs cost" — we never guess margins.
  - Payment fees are an ESTIMATE (2.9% + $0.30/order) and labeled as such.
  - Every store-level row carries a note explaining what it contains.
"""
import datetime
import json

import requests

from .. import db

API_VERSION = "2024-04"
LOOKBACK_DAYS = 30
MAX_PAGES = 8
FEE_RATE = 0.029
FEE_FIXED = 0.30


def _fetch_orders(domain: str, token: str) -> list[dict]:
    since = (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    url = (f"https://{domain}/admin/api/{API_VERSION}/orders.json")
    params = {
        "status": "any",
        "created_at_min": f"{since}T00:00:00Z",
        "limit": 250,
        "fields": "id,created_at,current_total_price,total_price,line_items,refunds,financial_status,fulfillments",
    }
    headers = {"X-Shopify-Access-Token": token}
    orders, pages = [], 0
    while url and pages < MAX_PAGES:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Shopify API {r.status_code}: {r.text[:200]}")
        orders += r.json().get("orders", [])
        url = (r.links.get("next") or {}).get("url")
        params = None  # next-page URL already carries the cursor
        pages += 1
    return orders


def _sync_store(cur, store: dict) -> dict:
    sid = store["id"]
    orders = _fetch_orders(store["shop_domain"], store["access_token"])
    start = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)

    # Cache orders + aggregate
    per_product: dict[tuple, dict] = {}      # (day, product_key) -> agg
    per_day: dict[str, dict] = {}            # day -> {fees, refunds}
    for o in orders:
        day = o["created_at"][:10]
        total = float(o.get("total_price") or 0)
        current = float(o.get("current_total_price") or total)
        refunded = round(max(0.0, total - current), 2)
        fulfilled_day = None
        for f in (o.get("fulfillments") or []):
            fd = (f.get("created_at") or "")[:10]
            if fd and (fulfilled_day is None or fd < fulfilled_day):
                fulfilled_day = fd
        cur.execute(
            """insert into orders_cache (store_id, order_id, created_day, total,
                 refunded, line_items, fulfilled_day)
               values (%s,%s,%s,%s,%s,%s,%s)
               on conflict (store_id, order_id) do update
                 set total = excluded.total, refunded = excluded.refunded,
                     line_items = excluded.line_items,
                     fulfilled_day = excluded.fulfilled_day""",
            (sid, str(o["id"]), day, total, refunded,
             json.dumps(o.get("line_items", [])), fulfilled_day),
        )
        d = per_day.setdefault(day, {"fees": 0.0, "refunds": 0.0, "orders": 0})
        d["fees"] += current * FEE_RATE + FEE_FIXED
        d["refunds"] += refunded
        d["orders"] += 1
        for li in o.get("line_items", []):
            key = str(li.get("product_id") or f"custom:{li.get('title','?')}")
            qty = int(li.get("quantity") or 0)
            price = float(li.get("price") or 0)
            agg = per_product.setdefault((day, key), {
                "title": li.get("title") or "Untitled product",
                "units": 0, "revenue": 0.0,
            })
            agg["units"] += qty
            agg["revenue"] += qty * price

    # Cost map the user has entered
    cur.execute("select product_key, unit_cost from product_costs where store_id=%s", (sid,))
    costs = {r["product_key"]: float(r["unit_cost"]) for r in cur.fetchall()}

    # User-logged ad spend by day
    cur.execute(
        """select day, sum(amount) as amt from ad_spend
           where store_id=%s and day >= %s group by day""",
        (sid, start),
    )
    ads = {str(r["day"]): float(r["amt"]) for r in cur.fetchall()}

    # Rebuild the window
    cur.execute("delete from pnl_daily where store_id=%s and day >= %s", (sid, start))

    for (day, key), agg in per_product.items():
        unit_cost = costs.get(key)
        cogs = round(unit_cost * agg["units"], 2) if unit_cost is not None else None
        profit = round(agg["revenue"] - cogs, 2) if cogs is not None else None
        cur.execute(
            """insert into pnl_daily (store_id, day, product_key, product_title,
                 units, revenue, cogs, fees, ad_spend, profit)
               values (%s,%s,%s,%s,%s,%s,%s,0,0,%s)""",
            (sid, day, key, agg["title"], agg["units"],
             round(agg["revenue"], 2), cogs, profit),
        )

    days = set(per_day) | set(ads)
    for day in days:
        fees = round(per_day.get(day, {}).get("fees", 0.0), 2)
        refunds = round(per_day.get(day, {}).get("refunds", 0.0), 2)
        spend = round(ads.get(day, 0.0), 2)
        cur.execute(
            """insert into pnl_daily (store_id, day, product_key, product_title,
                 units, revenue, cogs, fees, ad_spend, profit)
               values (%s,%s,null,%s,0,%s,0,%s,%s,%s)""",
            (sid, day,
             "Store costs (est. payment fees + your logged ad spend + refunds)",
             -refunds, fees, spend, round(-(fees + spend + refunds), 2)),
        )

    n_orders = sum(d["orders"] for d in per_day.values())
    cur.execute(
        """insert into store_status (store_id, shop_domain, last_sync, orders_30d, note)
           values (%s,%s,now(),%s,%s)
           on conflict (store_id) do update
             set last_sync = now(), orders_30d = excluded.orders_30d,
                 note = excluded.note""",
        (sid, store["shop_domain"], n_orders,
         "Fees are estimated at 2.9% + $0.30 per order until processor sync exists."),
    )
    return {"orders": n_orders, "products": len({k for _, k in per_product})}


def run(run_id: int | None = None) -> dict:
    stats = {"stores": 0, "orders": 0, "errors": 0}
    with db.cursor() as cur:
        cur.execute("select id, shop_domain, access_token from stores")
        stores = cur.fetchall()

    for store in stores:
        try:
            with db.cursor() as cur:
                s = _sync_store(cur, store)
            stats["stores"] += 1
            stats["orders"] += s["orders"]
            print(f"[bookkeeper] {store['shop_domain']}: {s}")
        except Exception as e:  # noqa: BLE001 — one bad store must not block the rest
            stats["errors"] += 1
            print(f"[bookkeeper] {store['shop_domain']} FAILED: {e}")
            with db.cursor() as cur:
                cur.execute(
                    """update store_status set note = %s where store_id = %s""",
                    (f"Sync problem: {str(e)[:140]} — check the token and try again.",
                     store["id"]),
                )

    print(f"[bookkeeper] done: {stats}")
    return stats
