#!/usr/bin/env python3
"""Refresh content/data/stats.json from the Instagram Graph API.

Needs a long-lived Instagram Graph API token for the @dalenmichaels business/creator account
and the IG user id, exported as env vars (never commit them):

    export IG_TOKEN=...        # long-lived token from a Meta developer app
    export IG_USER_ID=...      # numeric instagram business account id
    python3 scripts/update_stats.py && python3 build.py

TikTok has no public stats API for creators, so tiktok numbers stay manual in stats.json.
"""
import json, os, pathlib, sys, urllib.request, urllib.parse, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATS = ROOT / "content" / "data" / "stats.json"
TOKEN = os.environ.get("IG_TOKEN")
USER = os.environ.get("IG_USER_ID")
API = "https://graph.facebook.com/v21.0"


def get(path, **params):
    params["access_token"] = TOKEN
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def human(n):
    n = float(n)
    if n >= 1e6:
        return f"{n/1e6:.1f}M".replace(".0M", "M")
    if n >= 1e3:
        return f"{n/1e3:.1f}K".replace(".0K", "K")
    return str(int(n))


def main():
    if not TOKEN or not USER:
        sys.exit("IG_TOKEN and IG_USER_ID are required (see docstring).")
    data = json.loads(STATS.read_text())

    prof = get(USER, fields="followers_count")
    ig_followers = prof["followers_count"]

    since = int((datetime.datetime.utcnow() - datetime.timedelta(days=30)).timestamp())
    ins = get(f"{USER}/insights", metric="views,reach,total_interactions,profile_views,accounts_engaged",
              period="day", metric_type="total_value", since=since)
    totals = {m["name"]: m["total_value"]["value"] for m in ins["data"]}

    tt = data.get("tt_followers", "0")
    tt_n = float(tt.rstrip("KM")) * (1e3 if tt.endswith("K") else 1e6 if tt.endswith("M") else 1)

    data.update({
        "asof": datetime.date.today().strftime("%B %Y").lower(),
        "views_30d": human(totals.get("views", 0)),
        "reach_30d": human(totals.get("reach", 0)),
        "interactions_30d": human(totals.get("total_interactions", 0)),
        "engaged_30d": human(totals.get("accounts_engaged", 0)),
        "profile_visits_30d": human(totals.get("profile_views", 0)),
        "ig_followers": human(ig_followers),
        "followers_total": human(ig_followers + tt_n),
    })
    STATS.write_text(json.dumps(data, indent=2) + "\n")
    print("stats.json updated:", {k: data[k] for k in ("views_30d", "reach_30d", "followers_total")})


if __name__ == "__main__":
    main()
