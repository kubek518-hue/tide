"""Reddit public search (free, no key — public JSON endpoints, paced politely).

Signal: how much are real people talking about this product in the last month,
and is the conversation organic (many authors) or astroturf (few authors)?
"""
import time
import requests

from ... import config


def mentions(term: str) -> dict | None:
    try:
        r = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": f'"{term}"', "sort": "new", "t": "month", "limit": 100},
            headers={"User-Agent": config.USER_AGENT},
            timeout=20,
        )
        time.sleep(config.REQUEST_PAUSE_SECONDS)
        if r.status_code != 200:
            print(f"[reddit] '{term}' HTTP {r.status_code}")
            return None
        children = (r.json().get("data") or {}).get("children") or []
        authors = {c["data"].get("author") for c in children if c.get("data")}
        score_sum = sum(int(c["data"].get("score", 0)) for c in children)
        return {
            "mentions_30d": len(children),
            "unique_authors": len(authors),
            "score_sum": score_sum,
            "organic_ratio": round(len(authors) / len(children), 2) if children else 0,
        }
    except Exception as e:  # noqa: BLE001
        print(f"[reddit] '{term}' failed: {e}")
        return None
