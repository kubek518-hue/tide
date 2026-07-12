"""SCOUT — finds candidates and collects raw signals into the shared brain.

Flow per run:
  seeds.yaml -> Google Trends rising queries -> candidate terms
  each candidate -> guardrail check -> product row
  each non-excluded product -> momentum + reddit + meta signals -> signals table

Excluded products ARE recorded (with reasons) so the audit trail shows what we
refused and why — but they get no signals and can never be scored or picked.
"""
import pathlib
import random
import yaml

from .. import config, db
from ..guardrails import category_filters
from .sources import google_trends, reddit, meta_ad_library

SEEDS_FILE = pathlib.Path(__file__).parent / "seeds.yaml"


def _load_seeds() -> list[str]:
    with open(SEEDS_FILE) as f:
        return yaml.safe_load(f)["seeds"]


def run() -> dict:
    seeds = _load_seeds()
    random.shuffle(seeds)  # spread rate-limit pressure across runs

    candidates: dict[str, dict] = {}
    for seed in seeds:
        for c in google_trends.discover(seed):
            term = c["term"].lower()
            if term not in candidates:
                candidates[term] = {"seed": seed, "growth": c["growth"]}
        if len(candidates) >= config.MAX_CANDIDATES_PER_RUN:
            break

    stats = {"seeds_used": 0, "candidates": len(candidates),
             "excluded": 0, "flagged": 0, "signals": 0}
    stats["seeds_used"] = len({v["seed"] for v in candidates.values()})

    with db.cursor() as cur:
        for term, meta in candidates.items():
            status, reasons = category_filters.check(term)
            pid = db.upsert_product(cur, term, meta["seed"], status, reasons)
            if status == "excluded":
                stats["excluded"] += 1
                continue
            if status == "flagged":
                stats["flagged"] += 1

            db.insert_signal(cur, pid, "google_trends", "rising_growth",
                             meta["growth"], {"seed": meta["seed"]})
            stats["signals"] += 1

            m = google_trends.momentum(term)
            if m:
                db.insert_signal(cur, pid, "google_trends", "momentum",
                                 m["slope"], m)
                stats["signals"] += 1

            r = reddit.mentions(term)
            if r:
                db.insert_signal(cur, pid, "reddit", "mentions_30d",
                                 r["mentions_30d"], r)
                stats["signals"] += 1

            a = meta_ad_library.ad_count(term)
            if a:
                db.insert_signal(cur, pid, "meta_ads", "active_ads",
                                 a["active_ads"], a)
                stats["signals"] += 1

    print(f"[scout] done: {stats}")
    return stats
