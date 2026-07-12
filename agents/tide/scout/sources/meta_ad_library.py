"""Meta Ad Library API (free with a Meta developer token — optional).

Signal: how many active ads already run for this term. Few ads + rising trend
= early opportunity. Many ads = saturated. No token? Source skips gracefully
and the Analyst widens its uncertainty instead of guessing.

Policy note (B13): this is Meta's official public API — no scraping, no logins.
"""
import time
import requests

from ... import config

API = "https://graph.facebook.com/v19.0/ads_archive"


def ad_count(term: str) -> dict | None:
    if not config.META_AD_LIBRARY_TOKEN:
        return None
    try:
        r = requests.get(
            API,
            params={
                "search_terms": term,
                "ad_reached_countries": '["US"]',
                "ad_active_status": "ACTIVE",
                "fields": "id",
                "limit": 250,
                "access_token": config.META_AD_LIBRARY_TOKEN,
            },
            timeout=25,
        )
        time.sleep(config.REQUEST_PAUSE_SECONDS)
        if r.status_code != 200:
            print(f"[meta_ads] '{term}' HTTP {r.status_code}: {r.text[:120]}")
            return None
        data = r.json().get("data") or []
        capped = len(data) >= 250
        return {"active_ads": len(data), "count_capped": capped}
    except Exception as e:  # noqa: BLE001
        print(f"[meta_ads] '{term}' failed: {e}")
        return None
