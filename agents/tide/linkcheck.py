"""LINK HEALTH-CHECK — outbound links rot; this tells you when one dies.

Mirrors the outbound links in docs/app.html (view-the-item links, supplier
finder, marketplace hub) — KEEP THE TWO IN SYNC, same rule as the ad-claims
mirror. Run by the HEALTH CHECK workflow; run any time by hand with
`python -m tide.linkcheck`.

Honesty notes:
  - This never fails the build. Third parties break their own pages; you just
    get told in plain words which button needs a look.
  - Big retailers often refuse robots (403/429) while working fine for humans.
    That is reported as "guarded — open it yourself to confirm", never as dead.
"""
import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; TIDE-linkcheck/1.0; honest health check)"}
ROBOT_GUARDED = {401, 403, 405, 429, 503}

# name -> homepage-level URL proving the destination still exists.
# Mirror of docs/app.html link arrays. If one dies, fix it THERE and HERE.
OUTBOUND = {
    "Google search (photos/price/via-Google links)": "https://www.google.com",
    "Google Trends": "https://trends.google.com/trends/explore",
    "Google Lens": "https://lens.google.com",
    "Amazon Best Sellers": "https://www.amazon.com/gp/bestsellers",
    "Amazon Movers & Shakers": "https://www.amazon.com/gp/movers-and-shakers",
    "TikTok tag pages": "https://www.tiktok.com/tag/tiktokmademebuyit",
    "AliExpress": "https://www.aliexpress.com",
    "CJdropshipping": "https://www.cjdropshipping.com",
    "Zendrop": "https://www.zendrop.com",
    "Spocket": "https://www.spocket.co",
    "DSers": "https://www.dsers.com",
    "Alibaba search": "https://www.alibaba.com",
    "Faire": "https://www.faire.com",
}


def check(url: str, session=None, timeout: int = 12) -> tuple[str, object]:
    """Returns (state, detail): state in {'ok','guarded','dead'}."""
    s = session or requests
    try:
        r = s.head(url, timeout=timeout, allow_redirects=True, headers=UA)
        if r.status_code in (405, 501):  # some sites refuse HEAD; try a real GET
            r = s.get(url, timeout=timeout, allow_redirects=True, headers=UA, stream=True)
        code = r.status_code
    except requests.RequestException as e:
        return "dead", str(e)[:90]
    if code < 400:
        return "ok", code
    if code in ROBOT_GUARDED:
        return "guarded", code
    return "dead", code


def main(session=None) -> int:
    ok = guarded = dead = 0
    for name, url in OUTBOUND.items():
        state, detail = check(url, session=session)
        if state == "ok":
            ok += 1
            print(f"[link] OK      {name}")
        elif state == "guarded":
            guarded += 1
            print(f"[link] GUARDED {name} — refuses robots (HTTP {detail}); "
                  "open it yourself once to confirm it still works")
        else:
            dead += 1
            print(f"[link] DEAD?   {name} — {detail}. The button in Mission Control "
                  "probably needs a new address: fix it in docs/app.html AND here.")
    print(f"[link] summary: {ok} ok · {guarded} guarded · {dead} need a look "
          "(this check never blocks anything — it just tells you)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
