"""COACH v1 — the survival system's first heartbeat.

Writes one plain-language weekly briefing that Mission Control shows at the
top of the dashboard. v1 is template-based ($0). When revenue allows, the
marked section upgrades to an LLM call for personalized coaching — the
contract and Charter rules stay identical.

Charter 7 rules enforced here:
  - honest odds in every briefing
  - failures framed as data, never as shame
  - no upsell language, ever
"""
import datetime

from .. import db


def _week() -> str:
    y, w, _ = datetime.date.today().isocalendar()
    return f"{y}-W{w:02d}"


def _fmt_pick(row) -> str:
    badge = "TEST" if row["verdict"] == "test" else "WATCH"
    return f"- **{row['name'].title()}** — {row['total']}/100 ({badge}, {row['confidence']} confidence)"


def run(run_id: int | None = None) -> dict:
    week = _week()
    with db.cursor() as cur:
        cur.execute(
            """
            select p.name, s.total, s.verdict, s.confidence
            from picks k
            join products p on p.id = k.product_id
            join scores s on s.id = k.score_id
            where k.week = %s
            order by k.rank
            """,
            (week,),
        )
        rows = cur.fetchall()
        tests = [r for r in rows if r["verdict"] == "test"]
        watches = [r for r in rows if r["verdict"] == "watch"]

        # ── v1 template (upgrade point: swap this block for an LLM call) ──
        lines = [f"### Your briefing — week {week}", ""]
        if not rows:
            lines += [
                "No products cleared the bar this week. That's the system doing "
                "its job — a quiet week beats a bad recommendation. Keep any "
                "current tests running and check back Monday.",
            ]
        else:
            if tests:
                lines += [f"**{len(tests)} product(s) look ready to test:**", ""]
                lines += [_fmt_pick(r) for r in tests]
                lines += ["", "If you test one: start small, set a budget you're "
                          "comfortable losing, and give it a full 7 days before judging."]
            if watches:
                lines += ["", f"**{len(watches)} worth watching** (rising, but not "
                          "confirmed yet):", ""]
                lines += [_fmt_pick(r) for r in watches]
            lines += [
                "",
                "**The honest part:** most product tests fail — even for "
                "experienced operators, roughly 3 out of 4. A failed test that "
                "cost you little and taught you something is a win. Kill losers "
                "fast and keep your money for the next attempt.",
            ]
        body = "\n".join(lines)

        cur.execute(
            """insert into briefings (week, body) values (%s, %s)
               on conflict (week) do update set body = excluded.body,
                                               created_at = now()""",
            (week, body),
        )

    print(f"[coach] briefing written for {week} ({len(rows)} picks)")
    return {"week": week, "picks_covered": len(rows)}
