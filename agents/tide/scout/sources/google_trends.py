"""Google Trends via pytrends (free, no key).

Two jobs:
 1) discover(): expand seed categories into rising product queries (candidates)
 2) momentum(): measure a candidate's 90-day interest slope + freshness

Defensive by design: Trends rate-limits aggressively, so every call is wrapped,
paced, and allowed to fail without killing the run.
"""
import time
import numpy as np

from ... import config

_pytrends = None


def _client():
    global _pytrends
    if _pytrends is None:
        from pytrends.request import TrendReq
        _pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
    return _pytrends


def _pause():
    time.sleep(config.REQUEST_PAUSE_SECONDS)


def discover(seed: str, limit: int = 8) -> list[dict]:
    """Rising related queries for a seed. Returns [{'term', 'growth'}]."""
    out = []
    try:
        pt = _client()
        pt.build_payload([seed], timeframe=config.TRENDS_TIMEFRAME, geo="US")
        _pause()
        related = pt.related_queries() or {}
        rising = (related.get(seed) or {}).get("rising")
        if rising is not None and len(rising):
            for _, row in rising.head(limit).iterrows():
                term = str(row.get("query", "")).strip()
                if 3 <= len(term) <= 60:
                    out.append({"term": term, "growth": float(row.get("value", 0))})
    except Exception as e:  # noqa: BLE001 — sources must never kill the run
        print(f"[trends.discover] '{seed}' failed: {e}")
    return out


def momentum(term: str) -> dict | None:
    """90-day interest series -> slope (per week, normalized) and recency ratio."""
    try:
        pt = _client()
        pt.build_payload([term], timeframe=config.TRENDS_TIMEFRAME, geo="US")
        _pause()
        df = pt.interest_over_time()
        if df is None or df.empty or term not in df.columns:
            return None
        series = df[term].astype(float).values
        if len(series) < 6 or series.max() == 0:
            return None
        y = series / series.max()                       # normalize 0..1
        x = np.arange(len(y))
        slope = float(np.polyfit(x, y, 1)[0])           # per-step trend
        recent = float(y[-4:].mean())
        earlier = float(y[:4].mean()) or 0.01
        return {
            "slope": round(slope, 5),
            "recency_ratio": round(recent / earlier, 3),
            "points": len(y),
            "peak_recent": bool(np.argmax(y) >= len(y) - 4),
        }
    except Exception as e:  # noqa: BLE001
        print(f"[trends.momentum] '{term}' failed: {e}")
        return None
