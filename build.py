#!/usr/bin/env python3
"""Static site builder for dalenmichaels.com.

Usage:  python3 build.py
Reads   site.json, templates/, content/pages/*.html, content/posts/*.md, content/data/*.json
Writes  docs/  (GitHub Pages serves this folder)

No dependencies beyond `markdown` (pip install --user markdown).
"""
import json, os, re, shutil, html, datetime, pathlib
import markdown

ROOT = pathlib.Path(__file__).parent
SITE = json.loads((ROOT / "site.json").read_text())
OUT = ROOT / "docs"
TPL = (ROOT / "templates" / "base.html").read_text()
DATA = {p.stem: json.loads(p.read_text()) for p in (ROOT / "content" / "data").glob("*.json")}

MD = markdown.Markdown(extensions=["extra", "smarty", "toc"], output_format="html5")


def frontmatter(text):
    """Parse a simple `---\nkey: value\n---` header. Returns (meta, body)."""
    if not text.startswith("---"):
        return {}, text
    _, head, body = text.split("---", 2)
    meta = {}
    for line in head.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, body.lstrip("\n")


def render(template, ctx):
    """Tiny mustache: {{key}} substitution, {{#key}}...{{/key}} conditional blocks."""
    def block(m):
        key, inner = m.group(1), m.group(2)
        return inner if ctx.get(key) else ""
    out = re.sub(r"{{#(\w+)}}(.*?){{/\1}}", block, template, flags=re.S)
    def sub(m):
        key = m.group(1)
        return str(ctx.get(key, SITE.get(key, "")))
    return re.sub(r"{{(\w+)}}", sub, out)


def expand_data(body):
    """Replace {{data:deals}} style tags with rendered partials from content/data."""
    def sub(m):
        name = m.group(1)
        fn = globals().get(f"partial_{name}")
        return fn(DATA[name]) if fn else ""
    return re.sub(r"{{data:(\w+)}}", sub, body)


# ---------- partials rendered from content/data/*.json ----------

def partial_deals(items):
    cards = []
    for d in items:
        stats = " ".join(f"<b>{html.escape(s)}</b>" for s in d.get("stats", []))
        cards.append(f"""
      <article class="deal">
        <div class="deal-head">
          <h3>{html.escape(d['brand'])}</h3>
          <span class="mono">{html.escape(d['meta'])}</span>
        </div>
        <p class="deal-views"><span class="serif">{html.escape(d['views'])}</span> <span class="mono">{html.escape(d.get('views_label','views'))}</span></p>
        <p class="deal-stats mono">{stats}</p>
        <p>{html.escape(d['note'])}</p>
        <a class="watch" href="{html.escape(d['url'])}" target="_blank" rel="noopener">watch ↗</a>
      </article>""")
    return "\n".join(cards)


def partial_reels(groups):
    out = []
    for g in groups:
        tiles = "".join(f"""
        <a class="reel" href="{html.escape(r['url'])}" target="_blank" rel="noopener">
          <span class="reel-views mono">{html.escape(r['views'])}</span>
          <span class="reel-title">{html.escape(r['title'])}</span>
          <span class="reel-sub mono">{html.escape(r.get('sub',''))}</span>
        </a>""" for r in g["reels"])
        out.append(f"""
      <div class="lane">
        <h3 class="serif">{html.escape(g['lane'])} <span class="lane-note">{html.escape(g['note'])}</span></h3>
        <div class="reel-row">{tiles}</div>
      </div>""")
    return "\n".join(out)


def partial_codes(items):
    rows = []
    for c in items:
        code = f'<span class="code mono">{html.escape(c["code"])}</span>' if c.get("code") else '<span class="mono muted">link only</span>'
        rows.append(f"""
      <a class="code-row" href="{html.escape(c['url'])}" target="_blank" rel="noopener">
        <span class="code-brand serif">{html.escape(c['brand'])}</span>
        <span class="code-what">{html.escape(c['what'])}</span>
        {code}
        <span class="code-deal mono">{html.escape(c.get('deal',''))}</span>
      </a>""")
    return "\n".join(rows)


def partial_brands(items):
    return " <span class='dot'>·</span> ".join(html.escape(b) for b in items)


# ---------- posts ----------

def load_posts():
    posts = []
    for p in sorted((ROOT / "content" / "posts").glob("*.md")):
        meta, body = frontmatter(p.read_text())
        if meta.get("draft", "false").lower() == "true":
            continue
        MD.reset()
        meta["html"] = MD.convert(body)
        meta["slug"] = meta.get("slug") or p.stem
        meta["url"] = f"/blog/{meta['slug']}/"
        meta["date_obj"] = datetime.date.fromisoformat(meta["date"])
        meta["date_nice"] = meta["date_obj"].strftime("%b %-d, %Y").lower()
        posts.append(meta)
    posts.sort(key=lambda m: m["date_obj"], reverse=True)
    return posts


def post_card(p):
    return f"""
      <a class="post-card" href="{p['url']}">
        <span class="mono">{p['date_nice']}{' · ' + html.escape(p['tags']) if p.get('tags') else ''}</span>
        <h3 class="serif">{html.escape(p['title'])}</h3>
        <p>{html.escape(p.get('description',''))}</p>
        <span class="watch">read ↗</span>
      </a>"""


def write(path, content):
    path = OUT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def person_jsonld():
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Person",
        "name": SITE["name"],
        "url": SITE["base_url"],
        "image": SITE["base_url"] + "/assets/img/og.jpg",
        "jobTitle": "Surf creator, founder, mentor",
        "description": SITE["description"],
        "email": SITE["email"],
        "address": {"@type": "PostalAddress", "addressLocality": "Boca Raton", "addressRegion": "FL", "addressCountry": "US"},
        "worksFor": {"@type": "Organization", "name": "Out The Back", "url": SITE["brand_url"]},
        "alumniOf": [{"@type": "CollegeOrUniversity", "name": "USC Marshall School of Business"}],
        "sameAs": [SITE["instagram"], SITE["tiktok"], SITE["youtube"], SITE["linkedin"], SITE["brand_url"]],
        "knowsAbout": ["surfing", "social media marketing", "short-form video", "brand partnerships", "apparel", "entrepreneurship"],
    }, indent=None)


def article_jsonld(p):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": p["title"],
        "description": p.get("description", ""),
        "datePublished": p["date"],
        "dateModified": p.get("updated", p["date"]),
        "author": {"@type": "Person", "name": SITE["name"], "url": SITE["base_url"]},
        "publisher": {"@type": "Person", "name": SITE["name"]},
        "mainEntityOfPage": SITE["base_url"] + p["url"],
        "image": SITE["base_url"] + p.get("cover", "/assets/img/og.jpg"),
    })


def main():
    # clean generated html (keep assets)
    for p in OUT.rglob("*.html"):
        p.unlink()
    for d in ("blog",):
        shutil.rmtree(OUT / d, ignore_errors=True)

    posts = load_posts()
    urls = []

    # pages
    for p in sorted((ROOT / "content" / "pages").glob("*.html")):
        meta, body = frontmatter(p.read_text())
        slug = meta.get("slug", p.stem)
        path = "index.html" if slug == "index" else f"{slug}/index.html"
        url = "/" if slug == "index" else f"/{slug}/"
        body = expand_data(body)
        body = body.replace("{{latest_posts}}", "".join(post_card(x) for x in posts[:3]))
        body = body.replace("{{all_posts}}", "".join(post_card(x) for x in posts))
        ctx = dict(SITE)
        ctx.update(meta)
        ctx.update(dict(body=render(body, ctx), canonical=SITE["base_url"] + url, nav=slug,
                        jsonld=person_jsonld() if slug == "index" else "", page_class=f"page-{slug}",
                        og_image=SITE["base_url"] + meta.get("og_image", "/assets/img/og.jpg"),
                        og_type="website"))
        ctx.setdefault("title", SITE["name"])
        ctx["full_title"] = SITE["name"] if slug == "index" else f"{ctx['title']} · {SITE['name']}"
        write(path, render(TPL, ctx))
        urls.append((url, SITE["updated"]))

    # posts
    for p in posts:
        body = f"""
<article class="post">
  <header class="post-header">
    <p class="mono">{p['date_nice']}{' · ' + html.escape(p['tags']) if p.get('tags') else ''}</p>
    <h1 class="serif">{html.escape(p['title'])}</h1>
    <p class="lede">{html.escape(p.get('description',''))}</p>
  </header>
  <div class="prose">{p['html']}</div>
  <footer class="post-footer">
    <p class="mono">written by dalen michaels · boca raton, fl</p>
    <p><a class="btn" href="/brands/">work with me</a> <a class="btn btn-ghost" href="/mentorship/">get mentored</a></p>
  </footer>
</article>"""
        ctx = dict(SITE)
        ctx.update(dict(title=p["title"], description=p.get("description", ""), body=body,
                        canonical=SITE["base_url"] + p["url"], nav="blog", jsonld=article_jsonld(p),
                        page_class="page-post", og_image=SITE["base_url"] + p.get("cover", "/assets/img/og.jpg"),
                        og_type="article", full_title=f"{p['title']} · {SITE['name']}"))
        write(f"blog/{p['slug']}/index.html", render(TPL, ctx))
        urls.append((p["url"], p.get("updated", p["date"])))

    # sitemap, robots, feed, CNAME, 404
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, d in urls:
        sm.append(f"  <url><loc>{SITE['base_url']}{u}</loc><lastmod>{d}</lastmod></url>")
    sm.append("</urlset>")
    write("sitemap.xml", "\n".join(sm))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE['base_url']}/sitemap.xml\n")
    write("CNAME", SITE["domain"] + "\n")

    feed = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
            f"<title>{SITE['name']}</title><link>{SITE['base_url']}</link><description>{html.escape(SITE['description'])}</description>"]
    for p in posts:
        feed.append(f"<item><title>{html.escape(p['title'])}</title><link>{SITE['base_url']}{p['url']}</link>"
                    f"<guid>{SITE['base_url']}{p['url']}</guid><pubDate>{p['date_obj'].strftime('%a, %d %b %Y 00:00:00 GMT')}</pubDate>"
                    f"<description>{html.escape(p.get('description',''))}</description></item>")
    feed.append("</channel></rss>")
    write("feed.xml", "\n".join(feed))

    ctx = dict(SITE)
    ctx.update(dict(title="not found", description="", canonical=SITE["base_url"] + "/404.html", nav="", jsonld="",
                    page_class="page-404", og_image=SITE["base_url"] + "/assets/img/og.jpg", og_type="website",
                    full_title=f"not found · {SITE['name']}",
                    body='<section class="section"><h1 class="serif">that page paddled out.</h1><p><a class="btn" href="/">back home</a></p></section>'))
    write("404.html", render(TPL, ctx))
    print(f"built {len(urls)} urls → docs/")


if __name__ == "__main__":
    main()
