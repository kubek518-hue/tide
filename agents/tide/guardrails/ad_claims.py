"""Charter-as-code: ad-claim pre-check (Policy B15 / C3, Charter 5 & 10).

One canonical list, two consumers:
  - Sentinel exposes it to members as the "Check my ad" tool (via the JS
    mirror in the dashboard — keep the two lists in sync when editing).
  - Creative (Phase 5) refuses to *generate* any of this.

Categories map to real rejection/legal reasons, and every flag returns a
plain-language explanation with a fix, not just a "no".
"""
import re

RULES = [
    ("health_claim",
     r"\b(cures?|heals?|treats?|prevents?|reverses?|clinically proven|fda[- ]approved|"
     r"pain[- ]?free|anti[- ]?aging|lose \d+ ?(lbs|pounds|kg)|melts? fat|detox(es|ify)?)\b",
     "Health or medical outcome claims get ads rejected and can bring regulator "
     "attention. Describe what the product does physically, not what it fixes "
     "in the body."),
    ("income_claim",
     r"\b(make|earn)\s+\$?\d[\d,]*\s*(a|per|\/)\s*(day|week|month)|passive income|"
     r"financial freedom|get rich|guaranteed (income|profit|results)\b",
     "Income promises are the fastest route to platform bans and FTC trouble. "
     "Cut the promise; show the product."),
    ("absolute_guarantee",
     r"\b(100% (guaranteed|safe|effective)|never fails?|works? every time|"
     r"risk[- ]free|no risk)\b",
     "Absolute guarantees are unprovable and read as deceptive. Use honest "
     "specifics instead: materials, dimensions, what it does."),
    ("fake_urgency",
     r"\b(only \d+ left|selling out (fast|now)|today only|last chance|"
     r"offer ends (tonight|today|soon))\b",
     "Urgency that isn't literally true is deceptive advertising. If a deadline "
     "or stock number is real, say the real one; otherwise remove it."),
    ("before_after",
     r"\b(before and after|before\/after|transformation (photo|pic))\b",
     "Before/after framing is restricted in most ad categories and heavily "
     "penalized. Show the product in use instead."),
    ("superlative_unproven",
     r"\b(the best|world'?s (best|first|only)|#1|number one)\b",
     "Unproven superlatives invite takedowns and erode trust. Swap for a "
     "specific, checkable fact about the product."),
    ("fake_testimonial_frame",
     r"\b(i bought this and|as a (real )?customer|verified buyer says)\b",
     "If this ad is generated content, testimonial framing makes it a fake "
     "review — banned by our charter and by regulators. Frame it as an ad or "
     "a demonstration, never as a customer speaking."),
]

_COMPILED = [(k, re.compile(p, re.IGNORECASE), why) for k, p, why in RULES]


def check(text: str) -> list[dict]:
    """Return [{kind, matched, why}] — empty list means the copy passed."""
    flags = []
    for kind, rx, why in _COMPILED:
        m = rx.search(text or "")
        if m:
            flags.append({"kind": kind, "matched": m.group(0), "why": why})
    return flags
