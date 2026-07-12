"""Thin database layer. psycopg2 + plain SQL — no ORM, nothing to break."""
import json
import re
import contextlib
import psycopg2
import psycopg2.extras

from . import config


def connect():
    return psycopg2.connect(config.require_db())


@contextlib.contextmanager
def cursor():
    conn = connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:80] or "unnamed"


def upsert_product(cur, name: str, category: str | None,
                   guard_status: str, guard_reasons: list[str]) -> int:
    cur.execute(
        """
        insert into products (name, slug, category, guard_status, guard_reasons)
        values (%s, %s, %s, %s, %s)
        on conflict (name) do update
          set category = coalesce(excluded.category, products.category),
              guard_status = excluded.guard_status,
              guard_reasons = excluded.guard_reasons
        returning id
        """,
        (name, slugify(name), category, guard_status, json.dumps(guard_reasons)),
    )
    return cur.fetchone()["id"]


def insert_signal(cur, product_id: int, source: str, metric: str,
                  value: float | None, raw: dict) -> None:
    cur.execute(
        """insert into signals (product_id, source, metric, value, raw)
           values (%s, %s, %s, %s, %s)""",
        (product_id, source, metric, value, json.dumps(raw, default=str)),
    )


def latest_signals(cur, product_id: int) -> dict:
    """Most recent value per (source, metric) for a product."""
    cur.execute(
        """
        select distinct on (source, metric) source, metric, value, raw, captured_at
        from signals where product_id = %s
        order by source, metric, captured_at desc
        """,
        (product_id,),
    )
    out = {}
    for row in cur.fetchall():
        out[f"{row['source']}:{row['metric']}"] = row
    return out


def start_run(agent: str) -> int:
    with cursor() as cur:
        cur.execute("insert into runs (agent) values (%s) returning id", (agent,))
        return cur.fetchone()["id"]


def finish_run(run_id: int, ok: bool, stats: dict, error: str | None = None) -> None:
    with cursor() as cur:
        cur.execute(
            """update runs set finished_at = now(), ok = %s, stats = %s, error = %s
               where id = %s""",
            (ok, json.dumps(stats, default=str), error, run_id),
        )
