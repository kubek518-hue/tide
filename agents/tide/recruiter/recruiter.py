"""RECRUITER v1 — the creator intelligence layer, done honestly (Policy B13).

No scraping, no gray areas: the agent generates a *playbook* per TEST pick —
exactly where to search on TikTok for fitting creators, plus outreach messages
that pass the same guardrails as our ads (no income promises to creators
either), plus the disclosure rule stated plainly. Members do the human part;
the CRM and sample-ROI math in the dashboard keep them disciplined.

Why this design: our research showed sellers who proactively search and vet
creators (instead of waiting for applicants) roughly double their acceptance
rates — the edge is the workflow, not a scraper.
"""
import datetime
import json
import re

from ..guardrails import ad_claims

DISCLOSURE = ("The boring-but-mandatory part: any creator post about your "
              "product must carry the paid-partnership disclosure (#ad). "
              "It's the law, platforms require it, and disclosed posts still "
              "convert — never ask a creator to skip it.")


def _compact(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())[:30]


def _search_queries(name: str, category: str | None) -> list[str]:
    n = name.strip().lower()
    q = [
        f"{n}",
        f"#{_compact(n)}",
        f"{n} review",
        f"{n} unboxing",
        "tiktok made me buy it " + (category or n),
    ]
    if category:
        q.append(f"best {category} finds")
    return q


def _outreach(name: str) -> list[dict]:
    title = name.strip()
    return [
        {
            "name": "First invite",
            "message": (
                f"Hi — I run a small store and we're testing a product I think "
                f"fits your content: {title}. Can I send you one, free, no "
                f"strings attached? If you like it and want to post, we'll set "
                f"you up with a commission link so you're paid on what you "
                f"drive. If you don't like it, keep it anyway. One rule we "
                f"never bend: posts need the paid-partnership disclosure "
                f"(#ad) — we play it straight."
            ),
        },
        {
            "name": "One follow-up (only one)",
            "message": (
                f"Hi — following up once, and only once, on the {title} sample "
                f"offer. If it's not for you, no problem at all — one word and "
                f"I'm gone. If it is: what address should I ship it to?"
            ),
        },
    ]


def run(run_id: int | None = None) -> dict:
    from .. import db
    stats = {"playbooks": 0, "refused_messages": 0}
    y, w, _ = datetime.date.today().isocalendar()
    week = f"{y}-W{w:02d}"

    with db.cursor() as cur:
        cur.execute(
            """
            select distinct p.id, p.name, p.category
            from picks k
            join products p on p.id = k.product_id
            join scores s on s.id = k.score_id
            where s.verdict = 'test'
              and k.published_at > now() - interval '14 days'
              and not exists (select 1 from playbooks b where b.product_id = p.id)
            order by p.id
            """
        )
        for t in cur.fetchall():
            outreach = []
            for m in _outreach(t["name"]):
                flags = ad_claims.check(m["message"])
                if flags:  # belt and suspenders — templates are written clean
                    stats["refused_messages"] += 1
                    print(f"[recruiter] REFUSED outreach for '{t['name']}': "
                          f"{[f['kind'] for f in flags]}")
                    continue
                outreach.append(m)
            cur.execute(
                """insert into playbooks (product_id, week, search_queries,
                     outreach, disclosure_note)
                   values (%s,%s,%s,%s,%s)
                   on conflict (product_id) do nothing""",
                (t["id"], week,
                 json.dumps(_search_queries(t["name"], t["category"])),
                 json.dumps(outreach), DISCLOSURE),
            )
            stats["playbooks"] += 1

    print(f"[recruiter] done: {stats}")
    return stats
