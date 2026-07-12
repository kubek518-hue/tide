"""AUDITOR — Charter 8 as a weekly job.

Reads picks the founder has scored (picks.outcome = 'hit' | 'miss', marked in
the Table Editor at the +2/+4 week checkpoints of the validation protocol) and
publishes the aggregate to hitrate_public — the table the landing page reads.

The number goes out whatever it is. That's the point.
"""


def run(run_id: int | None = None) -> dict:
    from . import db
    stats = {}
    with db.cursor() as cur:
        for period, where in (
            ("all", "true"),
            ("last_90d", "published_at > now() - interval '90 days'"),
        ):
            cur.execute(
                f"""select count(*) filter (where outcome in ('hit','miss')) as scored,
                           count(*) filter (where outcome = 'hit') as hits
                    from picks where {where}"""
            )
            row = cur.fetchone()
            scored, hits = row["scored"] or 0, row["hits"] or 0
            rate = round(hits / scored, 4) if scored else None
            cur.execute(
                """insert into hitrate_public (period, picks_scored, hits, rate, updated_at)
                   values (%s,%s,%s,%s,now())
                   on conflict (period) do update set
                     picks_scored = excluded.picks_scored, hits = excluded.hits,
                     rate = excluded.rate, updated_at = now()""",
                (period, scored, hits, rate),
            )
            stats[period] = {"scored": scored, "hits": hits, "rate": rate}
    print(f"[audit] published: {stats}")
    return stats
