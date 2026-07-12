"""PUBLISHER — turns this week's best verdicts into the picks table and a
markdown digest (reports/picks-<week>.md), written in Charter voice: plain
language, evidence shown, warnings shown, odds stated honestly.
"""
import datetime
import json
import pathlib

from .. import db
from ..guardrails import category_filters

REPORTS_DIR = pathlib.Path(__file__).resolve().parents[3] / "reports"
TOP_N = 10

DISCLAIMER = (
    "> **Honest odds:** These are research leads, not guarantees. Most product "
    "tests fail — that's normal and expected. Test small, use money you can "
    "afford to lose, and kill losers fast. Every score below shows its evidence."
)


def _week() -> str:
    y, w, _ = datetime.date.today().isocalendar()
    return f"{y}-W{w:02d}"


def run() -> dict:
    week = _week()
    with db.cursor() as cur:
        cur.execute(
            """
            select distinct on (s.product_id)
                   s.id as score_id, s.product_id, s.total, s.verdict,
                   s.confidence, s.evidence, p.name, p.guard_status, p.guard_reasons
            from scores s join products p on p.id = s.product_id
            where s.created_at > now() - interval '7 days'
              and s.verdict in ('test', 'watch')
              and p.guard_status <> 'excluded'
            order by s.product_id, s.created_at desc
            """
        )
        rows = sorted(cur.fetchall(), key=lambda r: -r["total"])[:TOP_N]

        lines = [f"# Weekly picks — {week}", "", DISCLAIMER, ""]
        rank = 0
        for r in rows:
            rank += 1
            cur.execute(
                """insert into picks (product_id, score_id, week, rank)
                   values (%s,%s,%s,%s)
                   on conflict (week, product_id) do nothing""",
                (r["product_id"], r["score_id"], week, rank),
            )
            ev = r["evidence"] if isinstance(r["evidence"], dict) else json.loads(r["evidence"])
            badge = "TEST" if r["verdict"] == "test" else "WATCH"
            lines += [
                f"## {rank}. {r['name'].title()}  —  {r['total']}/100  ({badge}, "
                f"{r['confidence']} confidence)",
            ]
            reasons = r["guard_reasons"] if isinstance(r["guard_reasons"], list) \
                else json.loads(r["guard_reasons"])
            if r["guard_status"] == "flagged" and reasons:
                lines.append(f"**Heads up:** {category_filters.human_warning(reasons)}")
            lines.append("```json")
            lines.append(json.dumps(ev, indent=2, default=str))
            lines.append("```")
            lines.append("")

        if rank == 0:
            lines.append("_No products cleared the bar this week. A quiet week "
                         "beats a bad recommendation._")

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"picks-{week}.md"
    out.write_text("\n".join(lines))
    print(f"[publisher] wrote {out} with {rank} picks")
    return {"week": week, "picks": rank, "file": str(out)}
