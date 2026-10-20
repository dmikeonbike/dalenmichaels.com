#!/usr/bin/env python3
"""Compute whole-account Instagram metrics from a Meta Business Suite content export
(Insights → Content → Export data → Instagram → Post, lifetime). Writes
content/data/metrics.json + updates content/data/stats.json.

usage: python3 scripts/ig_metrics_from_export.py data/exports/<file>.csv [--followers 66500] [--username dalenmichaels]
"""
import csv, io, json, sys, statistics, pathlib, datetime, argparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("csv"); ap.add_argument("--followers", type=int); ap.add_argument("--username", default="dalenmichaels"); ap.add_argument("--rate", type=int, default=1500)
a = ap.parse_args()

stats_p = ROOT / "content/data/stats.json"; stats = json.loads(stats_p.read_text())
def parse_h(s):
    s = str(s).strip(); m = {"K": 1e3, "M": 1e6}
    return float(s[:-1]) * m[s[-1]] if s and s[-1] in m else float(s or 0)
followers = a.followers or int(parse_h(stats.get("ig_followers", "0")))

raw = open(a.csv, "rb").read().decode("utf-8-sig", "ignore")
rows = list(csv.DictReader(io.StringIO(raw)))
excl = set(json.loads((ROOT / "content/data/exclude_media.json").read_text()))
def num(x):
    try: return float(str(x).replace(",", "") or 0)
    except: return 0.0

posts = []
for r in rows:
    if r.get("Account username", "").lower() != a.username: continue
    if any(x and x in (r.get("Permalink") or "") for x in excl) or r.get("Post ID") in excl: continue
    posts.append({
        "id": r["Post ID"], "type": r.get("Post type", ""), "date": datetime.datetime.strptime(r["Publish time"], "%m/%d/%Y %H:%M").date().isoformat(),
        "permalink": r.get("Permalink", ""), "caption": (r.get("Description") or "").strip().split("\n")[0][:70],
        "views": num(r.get("Views")), "reach": num(r.get("Reach")), "likes": num(r.get("Likes")), "shares": num(r.get("Shares")),
        "comments": num(r.get("Comments")), "saves": num(r.get("Saves")), "follows": num(r.get("Follows")),
    })
reels = [p for p in posts if "reel" in p["type"].lower() and p["views"] > 0]
reels.sort(key=lambda p: p["date"])
if not reels: sys.exit("no reels found for " + a.username)

views = [p["views"] for p in reels]; reach = [p["reach"] for p in reels]
eng = [p["likes"] + p["comments"] + p["saves"] + p["shares"] for p in reels]
tv, te = sum(views), sum(eng)
saves, shares, comments, likes, follows = (sum(p[k] for p in reels) for k in ("saves", "shares", "comments", "likes", "follows"))
days = max(1, (datetime.date.fromisoformat(reels[-1]["date"]) - datetime.date.fromisoformat(reels[0]["date"])).days)
avg_v, med_v = statistics.mean(views), statistics.median(views)
hits = sum(1 for v in views if v >= 100_000); hits1m = sum(1 for v in views if v >= 1_000_000)
def human(n):
    n = float(n)
    if n >= 1e6: return f"{n/1e6:.1f}M".replace(".0M", "M")
    if n >= 1e3: return f"{n/1e3:.1f}K".replace(".0K", "K")
    return f"{int(n)}"
def pct(x, d=1): return f"{x*100:.{d}f}%"
top = sorted(reels, key=lambda p: p["views"], reverse=True)[:6]
window = f"{len(reels)} reels · {datetime.date.fromisoformat(reels[0]['date']).strftime('%b %-d')} to {datetime.date.fromisoformat(reels[-1]['date']).strftime('%b %-d, %Y')}"

metrics = {
    "asof": datetime.date.today().strftime("%B %-d, %Y").lower(), "window": window, "followers": followers, "source": "meta business suite export, lifetime post data",
    "table": [
        {"metric": "total views", "formula": f"sum across {len(reels)} reels", "value": human(tv)},
        {"metric": "average views per reel", "formula": "total views ÷ reels", "value": human(avg_v)},
        {"metric": "median views per reel", "formula": "the middle reel", "value": human(med_v)},
        {"metric": "views-to-follower ratio", "formula": "avg views ÷ followers", "value": f"{avg_v/followers:.1f}x"},
        {"metric": "engagement rate (by followers)", "formula": "(likes + comments + saves + shares) ÷ followers, avg per reel", "value": pct((te/len(reels))/followers)},
        {"metric": "engagement rate (by views)", "formula": "engagements ÷ views", "value": pct(te/tv, 2)},
        {"metric": "like rate", "formula": "likes ÷ views", "value": pct(likes/tv, 2)},
        {"metric": "save rate", "formula": "saves ÷ views", "value": pct(saves/tv, 2)},
        {"metric": "share rate", "formula": "shares ÷ views", "value": pct(shares/tv, 2)},
        {"metric": "comment rate", "formula": "comments ÷ views", "value": pct(comments/tv, 3)},
        {"metric": "new followers from reels", "formula": "follows attributed to posts", "value": human(follows)},
        {"metric": "hit rate", "formula": "reels over 100K ÷ reels", "value": f"{hits} of {len(reels)} ({pct(hits/len(reels),0)})"},
        {"metric": "reels over 1M", "formula": "count", "value": str(hits1m)},
        {"metric": "posting cadence", "formula": "reels ÷ days", "value": f"{len(reels)} in {days} days, one every {days/len(reels):.1f}"},
        {"metric": "cpm on a $1,500 reel", "formula": "rate ÷ avg views × 1,000", "value": f"${a.rate/avg_v*1000:.2f}"},
        {"metric": "cost per engagement", "formula": "rate ÷ avg engagements per reel", "value": f"${a.rate/(te/len(reels)):.2f}"},
    ],
    "top": [{"views": human(p["views"]), "permalink": p["permalink"], "caption": p["caption"] or p["date"], "date": p["date"]} for p in top],
    "totals": {"reels": len(reels), "views": tv, "reach": sum(reach), "engagements": te, "likes": likes, "comments": comments, "saves": saves, "shares": shares, "follows": follows},
}
(ROOT / "content/data/metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
stats.update({"avg_views": human(avg_v), "median_views": human(med_v), "ig_followers": human(followers), "metrics_window": window})
stats_p.write_text(json.dumps(stats, indent=2) + "\n")
print(json.dumps({"reels": len(reels), "total_views": human(tv), "avg": human(avg_v), "median": human(med_v), "er_followers": pct((te/len(reels))/followers), "er_views": pct(te/tv,2), "save_rate": pct(saves/tv,2), "share_rate": pct(shares/tv,2), "hits": hits, "over_1m": hits1m, "follows": int(follows), "cpm": round(a.rate/avg_v*1000,2), "days": days}, indent=1))
