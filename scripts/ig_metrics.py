#!/usr/bin/env python3
"""Pull the WHOLE Instagram account through the Instagram Graph API and compute the
metrics brands screen for. Writes content/data/stats.json (headline numbers used across
the site) and content/data/metrics.json (the full table on /brands/).

Setup (one time):
  1. @dalenmichaels must be a Professional (Creator/Business) account linked to a Facebook Page.
  2. Meta developer app with the Instagram product; generate a user token in Graph API Explorer
     with scopes: instagram_basic, instagram_manage_insights, pages_show_list, pages_read_engagement.
  3. Put it in ~/.config/dalenmichaels/ig.env (NOT in the repo):
        IG_TOKEN=EAAB...        # short- or long-lived user token
        IG_APP_ID=...           # only needed to exchange a short-lived token
        IG_APP_SECRET=...       # only needed to exchange a short-lived token
     The script upgrades it to a long-lived PAGE token (does not expire) and saves it back.

Run:  python3 scripts/ig_metrics.py && python3 build.py
"""
import json, os, sys, pathlib, statistics, datetime, urllib.request, urllib.parse, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = pathlib.Path.home() / ".config" / "dalenmichaels" / "ig.env"
API = "https://graph.facebook.com/v21.0"
STATS = ROOT / "content/data/stats.json"
METRICS = ROOT / "content/data/metrics.json"


def load_env():
    env = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1); env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("IG_")})
    return env


def save_env(env):
    ENV.parent.mkdir(parents=True, exist_ok=True)
    ENV.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n")
    os.chmod(ENV, 0o600)


def get(path, token, **params):
    params["access_token"] = token
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:400]
            if e.code in (4, 17, 32, 613) or "rate" in body.lower():
                time.sleep(30 * (attempt + 1)); continue
            raise SystemExit(f"API error {e.code} on {path}: {body}")
    raise SystemExit("rate limited repeatedly")


def ensure_page_token(env):
    """Turn whatever token we have into a non-expiring page token + the IG user id."""
    token = env.get("IG_TOKEN")
    if not token:
        sys.exit(f"no IG_TOKEN. create {ENV} (see docstring).")
    if env.get("IG_PAGE_TOKEN") and env.get("IG_USER_ID"):
        return env["IG_PAGE_TOKEN"], env["IG_USER_ID"]
    # exchange short-lived -> long-lived user token if we have app creds
    if env.get("IG_APP_ID") and env.get("IG_APP_SECRET"):
        d = get("oauth/access_token", token, grant_type="fb_exchange_token",
                client_id=env["IG_APP_ID"], client_secret=env["IG_APP_SECRET"], fb_exchange_token=token)
        token = d["access_token"]
    pages = get("me/accounts", token, fields="id,name,access_token,instagram_business_account{id,username}")["data"]
    pages = [p for p in pages if p.get("instagram_business_account")]
    if not pages:
        sys.exit("no facebook page with a linked instagram professional account on this token.")
    page = next((p for p in pages if p["instagram_business_account"].get("username", "").lower() == "dalenmichaels"), pages[0])
    env["IG_PAGE_TOKEN"] = page["access_token"]
    env["IG_USER_ID"] = page["instagram_business_account"]["id"]
    env["IG_USERNAME"] = page["instagram_business_account"].get("username", "")
    save_env(env)
    return env["IG_PAGE_TOKEN"], env["IG_USER_ID"]


def human(n):
    n = float(n or 0)
    if n >= 1e6: return f"{n/1e6:.1f}M".replace(".0M", "M")
    if n >= 1e3: return f"{n/1e3:.1f}K".replace(".0K", "K")
    return str(int(n))


def pct(x, d=1):
    return f"{x*100:.{d}f}%"


def main():
    env = load_env()
    token, uid = ensure_page_token(env)

    acct = get(uid, token, fields="followers_count,media_count,username")
    followers = acct["followers_count"]

    # ---- account insights, last 30 days
    since = int((datetime.datetime.utcnow() - datetime.timedelta(days=30)).timestamp())
    ins = get(f"{uid}/insights", token, metric="views,reach,total_interactions,accounts_engaged,profile_views",
              period="day", metric_type="total_value", since=since)
    a30 = {m["name"]: m["total_value"]["value"] for m in ins["data"]}

    # ---- every post
    media, after = [], None
    while True:
        d = get(f"{uid}/media", token, limit=100,
                fields="id,media_type,media_product_type,timestamp,like_count,comments_count,permalink,caption,is_shared_to_feed",
                **({"after": after} if after else {}))
        media += d["data"]
        after = d.get("paging", {}).get("cursors", {}).get("after")
        if not after or "next" not in d.get("paging", {}): break

    # drop trial reels (not shared to the profile grid) + anything on the manual exclude list
    excl_path = ROOT / "content/data/exclude_media.json"
    excluded = set(json.loads(excl_path.read_text())) if excl_path.exists() else set()
    before = len(media)
    media = [m for m in media if m.get("is_shared_to_feed", True) is not False and m["id"] not in excluded
             and not any(x and x in (m.get("permalink") or "") for x in excluded)]
    print(f"filtered {before-len(media)} trial/excluded posts")

    rows = []
    for m in media:
        try:
            if m.get("media_product_type") == "REELS" or m.get("media_type") == "VIDEO":
                mi = get(f"{m['id']}/insights", token, metric="views,reach,saved,shares,likes,comments,total_interactions")
            else:
                mi = get(f"{m['id']}/insights", token, metric="views,reach,saved,shares,likes,comments,total_interactions")
            v = {x["name"]: x["values"][0]["value"] for x in mi["data"]}
        except SystemExit:
            v = {}
        rows.append({
            "id": m["id"], "type": m.get("media_product_type") or m.get("media_type"), "date": m["timestamp"][:10],
            "permalink": m.get("permalink"), "caption": (m.get("caption") or "")[:80],
            "views": v.get("views", 0), "reach": v.get("reach", 0), "likes": v.get("likes", m.get("like_count", 0)),
            "comments": v.get("comments", m.get("comments_count", 0)), "saves": v.get("saved", 0), "shares": v.get("shares", 0),
            "interactions": v.get("total_interactions", 0),
        })

    reels = [r for r in rows if r["type"] == "REELS" and r["views"]]
    reels.sort(key=lambda r: r["date"], reverse=True)
    last90 = [r for r in reels if r["date"] >= (datetime.date.today() - datetime.timedelta(days=90)).isoformat()]
    base = last90 if len(last90) >= 10 else reels[:30]
    views = [r["views"] for r in base]
    eng = [r["likes"] + r["comments"] + r["saves"] + r["shares"] for r in base]
    days = max(1, (datetime.date.fromisoformat(base[0]["date"]) - datetime.date.fromisoformat(base[-1]["date"])).days) if base else 1

    avg_v = statistics.mean(views) if views else 0
    med_v = statistics.median(views) if views else 0
    tot_v = sum(views); tot_e = sum(eng)
    tot_saves = sum(r["saves"] for r in base); tot_shares = sum(r["shares"] for r in base); tot_comments = sum(r["comments"] for r in base)
    hits = sum(1 for v in views if v >= 100_000)
    top = sorted(reels, key=lambda r: r["views"], reverse=True)[:10]

    window = f"last {len(base)} reels · {base[-1]['date']} to {base[0]['date']}" if base else "n/a"
    rate_reel = 1500
    metrics = {
        "asof": datetime.date.today().isoformat(),
        "window": window,
        "followers": followers,
        "posts_total": acct["media_count"],
        "table": [
            {"metric": "average views per reel", "formula": "total views ÷ reels", "value": human(avg_v)},
            {"metric": "median views per reel", "formula": "middle reel", "value": human(med_v)},
            {"metric": "views-to-follower ratio", "formula": "avg views ÷ followers", "value": f"{avg_v/followers:.1f}x"},
            {"metric": "engagement rate (by followers)", "formula": "(likes+comments+saves+shares) ÷ followers, avg per reel", "value": pct((tot_e/len(base))/followers) if base else "n/a"},
            {"metric": "engagement rate (by views)", "formula": "engagements ÷ views", "value": pct(tot_e/tot_v if tot_v else 0, 2)},
            {"metric": "save rate", "formula": "saves ÷ views", "value": pct(tot_saves/tot_v if tot_v else 0, 2)},
            {"metric": "share rate", "formula": "shares ÷ views", "value": pct(tot_shares/tot_v if tot_v else 0, 2)},
            {"metric": "comment rate", "formula": "comments ÷ views", "value": pct(tot_comments/tot_v if tot_v else 0, 3)},
            {"metric": "hit rate", "formula": "reels over 100K ÷ reels", "value": f"{hits} of {len(base)} ({pct(hits/len(base) if base else 0,0)})"},
            {"metric": "posting cadence", "formula": "reels ÷ days", "value": f"{len(base)} in {days} days"},
            {"metric": "30-day views", "formula": "instagram insights", "value": human(a30.get("views", 0))},
            {"metric": "30-day reach", "formula": "unique accounts", "value": human(a30.get("reach", 0))},
            {"metric": "30-day interactions", "formula": "likes+comments+saves+shares", "value": human(a30.get("total_interactions", 0))},
            {"metric": "30-day engaged accounts", "formula": "unique people who interacted", "value": human(a30.get("accounts_engaged", 0))},
            {"metric": "30-day profile visits", "formula": "instagram insights", "value": human(a30.get("profile_views", 0))},
            {"metric": "cpm on a $1,500 reel", "formula": "rate ÷ avg views × 1,000", "value": f"${rate_reel/avg_v*1000:.2f}" if avg_v else "n/a"},
            {"metric": "cost per engagement", "formula": "rate ÷ avg engagements", "value": f"${rate_reel/(tot_e/len(base)):.2f}" if base and tot_e else "n/a"},
        ],
        "top": [{"views": human(r["views"]), "permalink": r["permalink"], "caption": r["caption"], "date": r["date"]} for r in top],
    }
    METRICS.write_text(json.dumps(metrics, indent=2) + "\n")

    stats = json.loads(STATS.read_text()) if STATS.exists() else {}
    tt = stats.get("tt_followers", "0"); tt_n = float(tt.rstrip("KM")) * (1e3 if tt.endswith("K") else 1e6 if tt.endswith("M") else 1)
    stats.update({
        "asof": datetime.date.today().strftime("%B %Y").lower(),
        "views_30d": human(a30.get("views", 0)), "reach_30d": human(a30.get("reach", 0)),
        "interactions_30d": human(a30.get("total_interactions", 0)), "engaged_30d": human(a30.get("accounts_engaged", 0)),
        "profile_visits_30d": human(a30.get("profile_views", 0)), "ig_followers": human(followers),
        "followers_total": human(followers + tt_n), "avg_views": human(avg_v), "median_views": human(med_v),
    })
    STATS.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"ok: {len(rows)} posts, {len(reels)} reels, followers {followers}, avg {human(avg_v)}, median {human(med_v)}")


if __name__ == "__main__":
    main()
