"""OPERATIONS v1 — the hands. Executes ONLY member-approved actions, inside
hard limits, and writes everything down (Policy C1/B9, Charter 6).

Safety model, in order of enforcement:
  1. Kill switch: if op_settings.kill_switch is true, nothing runs. Full stop.
  2. Execution-layer daily cap: the agent counts what it executed in the last
     24h and refuses beyond max_actions_per_day — the cap lives HERE, in the
     code that acts, not in the interface.
  3. Whitelisted kinds only; payloads validated before any network call.
  4. Every action ends as 'executed' (with result) or 'failed' (with a
     plain-language error a beginner can act on). Nothing silent, ever.

v1 kinds are deliberately money-safe and reversible:
  import_product  -> creates a DRAFT product in the member's Shopify store
  pause_product   -> sets an existing product back to draft (off the shelf)

Proposals: after executing, the agent looks at the books and proposes pausing
products that lost more than $20 over the last 7 days — proposals sit in the
queue until the member approves or declines. The agent never approves its own
ideas.
"""
import datetime
import json

import requests

API_VERSION = "2024-04"
LOSS_PROPOSAL_THRESHOLD = -20.0   # 7d profit below this -> propose a pause

SCOPE_HELP = ("Your store token can't write products yet. In Shopify admin: "
              "Settings > Apps and sales channels > Develop apps > your TIDE "
              "app > Configuration > add the write_products scope > save > "
              "reinstall the app, then approve this action again.")


def _validate(kind: str, payload: dict) -> str | None:
    """Return a plain-language problem, or None if the payload is safe."""
    if kind == "import_product":
        title = (payload.get("title") or "").strip()
        if not (3 <= len(title) <= 255):
            return "The product title is missing or too long."
        if len(payload.get("body_html") or "") > 20000:
            return "The product description is unreasonably long."
        return None
    if kind == "pause_product":
        pid = str(payload.get("shopify_product_id") or "")
        if not pid.isdigit():
            return "No valid Shopify product id to pause."
        return None
    return "Unknown action kind."


def _shopify(store: dict, method: str, path: str, body: dict) -> tuple[int, dict]:
    r = requests.request(
        method,
        f"https://{store['shop_domain']}/admin/api/{API_VERSION}/{path}",
        headers={"X-Shopify-Access-Token": store["access_token"],
                 "Content-Type": "application/json"},
        json=body, timeout=30,
    )
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        data = {"raw": r.text[:300]}
    return r.status_code, data


def _execute(store: dict, kind: str, payload: dict) -> tuple[bool, dict | None, str | None]:
    """Returns (ok, result, error). Errors are written for humans."""
    problem = _validate(kind, payload)
    if problem:
        return False, None, problem

    if kind == "import_product":
        code, data = _shopify(store, "POST", "products.json", {
            "product": {
                "title": payload["title"].strip(),
                "body_html": payload.get("body_html") or "",
                "status": "draft",
                "tags": "tide-pick",
            }
        })
        if code in (200, 201):
            p = data.get("product", {})
            return True, {"shopify_product_id": p.get("id"),
                          "admin_note": "Created as a DRAFT — review it, add "
                          "images and price, then publish when ready."}, None
        if code in (401, 403):
            return False, None, SCOPE_HELP
        return False, None, f"Shopify said no (HTTP {code}). Detail: {json.dumps(data)[:200]}"

    if kind == "pause_product":
        pid = payload["shopify_product_id"]
        code, data = _shopify(store, "PUT", f"products/{pid}.json",
                              {"product": {"id": int(pid), "status": "draft"}})
        if code == 200:
            return True, {"shopify_product_id": pid,
                          "admin_note": "Set to draft — it's off the shelf. "
                          "Republish anytime from Shopify admin."}, None
        if code in (401, 403):
            return False, None, SCOPE_HELP
        if code == 404:
            return False, None, "That product wasn't found in the store (maybe already deleted)."
        return False, None, f"Shopify said no (HTTP {code}). Detail: {json.dumps(data)[:200]}"

    return False, None, "Unknown action kind."


def _propose_pauses(cur, sid: int) -> int:
    """Losing products (7d) -> 'proposed' pause actions, deduped."""
    start = datetime.date.today() - datetime.timedelta(days=7)
    cur.execute(
        """select product_key, product_title, sum(profit) as p7
           from pnl_daily
           where store_id=%s and day >= %s and product_key is not null
             and profit is not null
           group by product_key, product_title
           having sum(profit) < %s""",
        (sid, start, LOSS_PROPOSAL_THRESHOLD),
    )
    made = 0
    for row in cur.fetchall():
        if not str(row["product_key"]).isdigit():
            continue  # only real Shopify products can be paused
        cur.execute(
            """select 1 from actions
               where store_id=%s and kind='pause_product'
                 and payload->>'shopify_product_id' = %s
                 and status in ('proposed','approved') limit 1""",
            (sid, str(row["product_key"])),
        )
        if cur.fetchone():
            continue
        loss = float(row["p7"])
        cur.execute(
            """insert into actions (store_id, kind, payload, reason, status, proposed_by)
               values (%s,'pause_product',%s,%s,'proposed','system')""",
            (sid,
             json.dumps({"shopify_product_id": str(row["product_key"]),
                         "product_title": row["product_title"]}),
             f"{row['product_title']} lost {abs(loss):.2f} over the last 7 days. "
             f"Pausing takes it off the shelf (reversible) while you decide."),
        )
        made += 1
    return made


def run(run_id: int | None = None) -> dict:
    from .. import db
    stats = {"executed": 0, "failed": 0, "skipped_kill": 0,
             "skipped_cap": 0, "proposed": 0}

    with db.cursor() as cur:
        cur.execute("select id, shop_domain, access_token from stores")
        stores = {s["id"]: s for s in cur.fetchall()}

    for sid, store in stores.items():
        try:
            with db.cursor() as cur:
                cur.execute("select kill_switch, max_actions_per_day from op_settings "
                            "where store_id=%s", (sid,))
                st = cur.fetchone() or {"kill_switch": False, "max_actions_per_day": 5}

                if st["kill_switch"]:
                    cur.execute("select count(*) as c from actions where store_id=%s "
                                "and status='approved'", (sid,))
                    stats["skipped_kill"] += cur.fetchone()["c"]
                else:
                    cur.execute(
                        """select count(*) as c from actions where store_id=%s
                           and status='executed' and executed_at > now() - interval '24 hours'""",
                        (sid,),
                    )
                    remaining = max(0, st["max_actions_per_day"] - cur.fetchone()["c"])

                    cur.execute(
                        """select id, kind, payload from actions
                           where store_id=%s and status='approved'
                           order by created_at limit %s""",
                        (sid, remaining if remaining > 0 else 0),
                    )
                    queue = cur.fetchall()
                    cur.execute(
                        """select count(*) as c from actions
                           where store_id=%s and status='approved'""", (sid,))
                    stats["skipped_cap"] += max(0, cur.fetchone()["c"] - len(queue))

                    for a in queue:
                        payload = a["payload"] if isinstance(a["payload"], dict) \
                            else json.loads(a["payload"] or "{}")
                        ok, result, error = _execute(store, a["kind"], payload)
                        cur.execute(
                            """update actions set status=%s, executed_at=now(),
                                 result=%s, error=%s where id=%s""",
                            ("executed" if ok else "failed",
                             json.dumps(result) if result else None, error, a["id"]),
                        )
                        stats["executed" if ok else "failed"] += 1

                stats["proposed"] += _propose_pauses(cur, sid)
        except Exception as e:  # noqa: BLE001
            print(f"[operations] {store['shop_domain']} FAILED: {e}")

    print(f"[operations] done: {stats}")
    return stats

