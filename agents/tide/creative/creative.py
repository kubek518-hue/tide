"""CREATIVE v1 — ad angles, hooks, scripts, and page copy for TEST picks.

Two modes, chosen automatically:
  template  ($0)   Three honest, pre-vetted frameworks with the product
                   inserted. Always available — the go-around-money mode.
  llm       (paid) One API call per product (cheapest adequate model) for
                   tailored angles. Only runs when ANTHROPIC_API_KEY is set,
                   caps calls per run, and caches: a product with creatives
                   is never regenerated.

Charter enforcement (Policy B4/B15/C3) is code, not vibes:
  - every generated text block runs through guardrails.ad_claims.check()
  - one retry with the flags fed back; still flagged -> the angle is DROPPED,
    never published ("refused" is counted in stats)
  - framing is ad/demonstration; testimonial voice is banned by prompt AND
    caught by the checker as a backstop
"""
import json

import requests

from .. import config
from ..guardrails import ad_claims

MAX_PRODUCTS_PER_RUN = int(__import__("os").environ.get("MAX_CREATIVE_PRODUCTS_PER_RUN", "8"))

PROMPT = """You write short-form video ad concepts for small e-commerce sellers.
Product: "{name}". Evidence about it: {evidence}

Return ONLY a JSON array of exactly 3 objects, no other text:
[{{"angle_name": "...", "hook": "...", "script": "...", "page_copy": "..."}}]

Rules (violations make the output unusable):
- hook: one spoken line under 15 words that earns the next 3 seconds.
- script: a 15-30 second UGC-style ad, visual directions in [brackets],
  spoken lines plain. Frame as a demonstration or an ad. NEVER as a customer
  testimonial or review; never say or imply "I bought this".
- page_copy: 3 short paragraphs: what it is, what it does (specifics), and an
  honest close (shipping/returns placeholder is fine).
- Absolutely no: health/medical claims (cure, treat, pain-free, fat loss),
  income claims, guarantees ("100%", "risk-free", "never fails"),
  fake urgency ("only 3 left", "today only"), before/after framing,
  unproven superlatives ("the best", "#1").
- Plain, specific, honest language sells here. Specifics beat hype."""


# ── Template mode: pre-vetted frameworks (kept boring on purpose) ─────────
def _template_angles(name: str) -> list[dict]:
    n = name.strip().rstrip(".")
    title = n[:1].upper() + n[1:]
    return [
        {
            "angle_name": "Problem, then the fix",
            "hook": f"If this little problem is part of your day, watch this.",
            "script": (f"[Open on the everyday annoyance this solves — 2 seconds, "
                       f"no talking.] That, every single time. [Cut to the {n} in "
                       f"hand.] So this exists. [Show it doing its job, close up, "
                       f"real speed.] One job, done properly. [End on the result.] "
                       f"Link's below if you want a look."),
            "page_copy": (f"{title} does one job and does it properly.\n\n"
                          f"[Two or three concrete specifics: size, material, what "
                          f"it holds/fits/handles, how it attaches or folds.]\n\n"
                          f"Ships with tracking from day one. If it isn't right, "
                          f"our return policy is on this page in plain English."),
        },
        {
            "angle_name": "Three uses in twenty seconds",
            "hook": f"Three ways people actually use the {n} — quick version.",
            "script": (f"[Fast cuts, on-screen counter 1-2-3.] One: [first real "
                       f"use, shown not said]. Two: [second use]. Three: [the "
                       f"unexpected one — this is the cut people rewatch]. "
                       f"[Hold on product.] That's it. No speech needed."),
            "page_copy": (f"One {n}, more than one job.\n\n[List the three uses "
                          f"from the video as short lines with a concrete detail "
                          f"each.]\n\nWhat's in the box, exact dimensions, and our "
                          f"plain-English shipping times are all below."),
        },
        {
            "angle_name": "The honest demo",
            "hook": f"No music, no hype — just the {n} doing its job.",
            "script": (f"[Static shot, natural sound only.] We're not going to "
                       f"yell at you. [Demonstrate the core function once, "
                       f"slowly.] That's what it does. [Show one detail buyers "
                       f"ask about — the seam, the clip, the switch.] If that's "
                       f"useful to you, it's linked below. If not, no hard "
                       f"feelings."),
            "page_copy": (f"Here's exactly what the {title.lower()} is: [one "
                          f"plain sentence].\n\nWhat it's made of, what it "
                          f"measures, and what it works with: [specifics].\n\n"
                          f"Straight answers on shipping and returns below — the "
                          f"same ones we'd want as buyers."),
        },
    ]


# ── LLM mode ──────────────────────────────────────────────────────────────
def _llm_angles(name: str, evidence: dict) -> list[dict] | None:
    key = __import__("os").environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    model = __import__("os").environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1500,
                "messages": [{
                    "role": "user",
                    "content": PROMPT.format(
                        name=name,
                        evidence=json.dumps(evidence, default=str)[:800]),
                }],
            },
            timeout=60,
        )
        if r.status_code != 200:
            print(f"[creative] LLM HTTP {r.status_code}: {r.text[:150]}")
            return None
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        angles = json.loads(text)
        good = []
        for a in angles[:3]:
            if all(isinstance(a.get(k), str) and a[k].strip()
                   for k in ("angle_name", "hook", "script", "page_copy")):
                good.append({k: a[k].strip() for k in
                             ("angle_name", "hook", "script", "page_copy")})
        return good or None
    except Exception as e:  # noqa: BLE001
        print(f"[creative] LLM failed for '{name}': {e}")
        return None


def _passes_guardrails(angle: dict) -> tuple[bool, list]:
    blob = " ".join([angle["hook"], angle["script"], angle["page_copy"]])
    flags = ad_claims.check(blob)
    return (len(flags) == 0), flags


def _retry_with_flags(name: str, evidence: dict, angle: dict, flags: list) -> dict | None:
    """One corrective pass through the LLM; template mode never needs this."""
    key = __import__("os").environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    problems = "; ".join(f"{f['kind']}: remove '{f['matched']}'" for f in flags)
    fixed = _llm_angles(
        name, {**evidence, "REWRITE_THIS_ANGLE": angle,
               "PROBLEMS_TO_FIX": problems})
    if fixed:
        ok, _ = _passes_guardrails(fixed[0])
        if ok:
            return fixed[0]
    return None


def run(run_id: int | None = None) -> dict:
    from .. import db
    stats = {"products": 0, "angles": 0, "refused": 0, "mode_llm": 0, "mode_template": 0}

    with db.cursor() as cur:
        # Recent TEST picks with no creatives yet (cache-by-existence)
        cur.execute(
            """
            select distinct p.id, p.name, s.evidence
            from picks k
            join products p on p.id = k.product_id
            join scores s on s.id = k.score_id
            where s.verdict = 'test'
              and k.published_at > now() - interval '14 days'
              and not exists (select 1 from creatives c where c.product_id = p.id)
            order by p.id
            limit %s
            """,
            (MAX_PRODUCTS_PER_RUN,),
        )
        targets = cur.fetchall()

        for t in targets:
            evidence = t["evidence"] if isinstance(t["evidence"], dict) \
                else json.loads(t["evidence"] or "{}")
            angles = _llm_angles(t["name"], evidence)
            mode = "llm" if angles else "template"
            if not angles:
                angles = _template_angles(t["name"])

            kept = 0
            for a in angles:
                ok, flags = _passes_guardrails(a)
                if not ok and mode == "llm":
                    fixed = _retry_with_flags(t["name"], evidence, a, flags)
                    if fixed:
                        a, ok = fixed, True
                if not ok:
                    stats["refused"] += 1
                    print(f"[creative] REFUSED angle for '{t['name']}': "
                          f"{[f['kind'] for f in flags]}")
                    continue
                cur.execute(
                    """insert into creatives (product_id, mode, angle_name, hook,
                         script, page_copy, checked)
                       values (%s,%s,%s,%s,%s,%s,true)""",
                    (t["id"], mode, a["angle_name"], a["hook"],
                     a["script"], a["page_copy"]),
                )
                kept += 1

            if kept:
                stats["products"] += 1
                stats["angles"] += kept
                stats[f"mode_{mode}"] += 1

    print(f"[creative] done: {stats}")
    return stats
