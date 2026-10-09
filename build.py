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
STATS = DATA.get("stats", {})

MD = markdown.Markdown(extensions=["extra", "smarty", "toc"], output_format="html5")


def frontmatter(text):
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
    """Tiny mustache: {{key}} substitution, {{#key}}...{{/key}} and {{^key}}...{{/key}} blocks."""
    def block(m):
        neg, key, inner = m.group(1) == "^", m.group(2), m.group(3)
        has = bool(ctx.get(key))
        return inner if (has != neg) else ""
    out = re.sub(r"{{([#^])(\w+)}}(.*?){{/\2}}", block, template, flags=re.S)
    def sub(m):
        key = m.group(1)
        if key.startswith("stats_"):
            return str(STATS.get(key[6:], ""))
        return str(ctx.get(key, SITE.get(key, "")))
    return re.sub(r"{{(\w+)}}", sub, out)


def expand_data(body):
    def sub(m):
        name = m.group(1)
        fn = globals().get(f"partial_{name}")
        return fn(DATA[name]) if fn else ""
    return re.sub(r"{{data:(\w+)}}", sub, body)


def reel_id(url):
    m = re.search(r"/reel/([^/]+)/|/video/(\d+)", url)
    return (m.group(1) or m.group(2)) if m else ""


def thumb_for(item):
    """Thumbnail path: explicit `thumb`, else docs/assets/img/reels/<reel id>.jpg if present."""
    if item.get("thumb"):
        return item["thumb"]
    rid = reel_id(item.get("url", ""))
    if rid and (OUT / "assets/img/reels" / f"{rid}.jpg").exists():
        return f"/assets/img/reels/{rid}.jpg"
    return ""


def tile(item, brand_tag=None, note=None):
    t = thumb_for(item)
    img = f'<img src="{t}" alt="{html.escape(item["title"])}" loading="lazy" width="360" height="640">' if t else ""
    cls = "tile" + ("" if t else " no-thumb") + (" has-tag" if brand_tag else "")
    tag = f'<span class="brand-tag">{html.escape(brand_tag)}</span>' if brand_tag else ""
    note_html = f'<span class="note">{html.escape(note)}</span>' if note else ""
    return f"""
      <a class="{cls}" href="{html.escape(item['url'])}" target="_blank" rel="noopener" aria-label="watch: {html.escape(item['title'])}">
        {img}
        <span class="views">{html.escape(item['views'])}</span>{tag}
        <span class="play"></span>
        <span class="cap"><b>{html.escape(item['title'])}</b><span>{html.escape(item.get('sub',''))}</span>{note_html}</span>
      </a>"""


# ---------- partials ----------

def partial_deals(items):
    return "\n".join(tile({"url": d["url"], "title": d["title"], "views": d["views"] + " views", "sub": d["meta"], "thumb": d.get("thumb", "")},
                          brand_tag=d["brand"], note=d["note"]) for d in items)


def partial_reels(groups):
    out = []
    for g in groups:
        tiles = "".join(tile(r) for r in g["reels"])
        out.append(f"""
      <div class="lane">
        <h3>{html.escape(g['lane'])} <span class="lane-note">{html.escape(g['note'])}</span></h3>
        <div class="tiles five">{tiles}</div>
      </div>""")
    return "\n".join(out)


def partial_codes(items):
    rows = []
    for c in items:
        code = f'<span class="code">{html.escape(c["code"])}</span>' if c.get("code") else '<span class="muted" style="font-size:.85rem">link only</span>'
        rows.append(f"""
      <a class="code-row" href="{html.escape(c['url'])}" target="_blank" rel="noopener">
        <span class="code-brand">{html.escape(c['brand'])}</span>
        <span class="code-what">{html.escape(c['what'])}</span>
        {code}
        <span class="code-deal">{html.escape(c.get('deal',''))}</span>
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
        <span class="meta">{p['date_nice']}{' · ' + html.escape(p['tags']) if p.get('tags') else ''}</span>
        <h3>{html.escape(p['title'])}</h3>
        <p>{html.escape(p.get('description',''))}</p>
        <span class="more">read →</span>
      </a>"""


IMG_RE = re.compile(r'<img src="(/assets/img/([\w-]+)\.jpg)"([^>]*)>')

def responsive(html_text):
    """Add srcset for images that have a -m.jpg variant; full-bleed photos load eagerly."""
    def sub(m):
        src, name, rest = m.group(1), m.group(2), m.group(3)
        if (OUT / "assets/img" / f"{name}-m.jpg").exists() and "srcset" not in rest:
            rest = f' srcset="/assets/img/{name}-m.jpg 1000w, {src} 2000w" sizes="100vw"' + rest
        return f'<img src="{src}"{rest}>'
    out = IMG_RE.sub(sub, html_text)
    out = re.sub(r'(<div class="media">|<figure>)(<img [^>]*?) loading="lazy"', r'\1\2 decoding="async"', out)
    return out


def write(path, content):
    if path.endswith(".html"):
        content = responsive(content)
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
        "jobTitle": "Lifestyle surf creator, founder, mentor",
        "description": SITE["description"],
        "email": SITE["email"],
        "address": {"@type": "PostalAddress", "addressLocality": "Boca Raton", "addressRegion": "FL", "addressCountry": "US"},
        "worksFor": {"@type": "Organization", "name": "Out The Back", "url": SITE["brand_url"]},
        "alumniOf": [{"@type": "CollegeOrUniversity", "name": "USC Marshall School of Business"}],
        "sameAs": [SITE["instagram"], SITE["tiktok"], SITE["youtube"], SITE["linkedin"], SITE["brand_url"]],
        "knowsAbout": ["surfing", "social media marketing", "short-form video", "brand partnerships", "influencer marketing", "apparel", "entrepreneurship"],
    })


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
    for p in OUT.rglob("*.html"):
        p.unlink()
    shutil.rmtree(OUT / "blog", ignore_errors=True)

    posts = load_posts()
    urls = []

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
        ctx["full_title"] = f"{SITE['name']} · lifestyle surf creator, founder, mentor" if slug == "index" else f"{ctx['title']} · {SITE['name']}"
        write(path, render(TPL, ctx))
        urls.append((url, SITE["updated"]))

    for p in posts:
        body = f"""
<article class="post">
  <header class="post-header">
    <p class="meta">{p['date_nice']}{' · ' + html.escape(p['tags']) if p.get('tags') else ''}</p>
    <h1>{html.escape(p['title'])}</h1>
    <p class="lede">{html.escape(p.get('description',''))}</p>
  </header>
  <div class="prose">{p['html']}</div>
  <footer class="post-footer">
    <p class="muted">written by dalen michaels · boca raton, florida</p>
    <p class="cta-row"><a class="btn" href="/brands/">work with me</a> <a class="btn btn-ghost" href="/mentorship/">get mentored</a></p>
  </footer>
</article>"""
        ctx = dict(SITE)
        ctx.update(dict(title=p["title"], description=p.get("description", ""), body=body,
                        canonical=SITE["base_url"] + p["url"], nav="blog", jsonld=article_jsonld(p),
                        page_class="page-post", og_image=SITE["base_url"] + p.get("cover", "/assets/img/og.jpg"),
                        og_type="article", full_title=f"{p['title']} · {SITE['name']}"))
        write(f"blog/{p['slug']}/index.html", render(TPL, ctx))
        urls.append((p["url"], p.get("updated", p["date"])))

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
                    body='<section class="section"><h1>that page paddled out.</h1><p><a class="btn" href="/">back home</a></p></section>'))
    write("404.html", render(TPL, ctx))
    print(f"built {len(urls)} urls → docs/")


if __name__ == "__main__":
    main()
