# dalenmichaels.com

Personal site for Dalen Michaels: brand deals, mentorship, speaking, fan codes, SEO blog. Static HTML built by `build.py`, served from `docs/` on GitHub Pages at https://dalenmichaels.com.

## Build & preview

```bash
python3 build.py                       # content/ + templates/ → docs/
python3 -m http.server 8787 --directory docs   # preview at http://localhost:8787
```

Commit the `docs/` output too: GitHub Pages serves it directly, there is no CI build.

## Layout

- `site.json` — name, email, socials, `intro_video_id` (YouTube ID for the home-page video; empty = show the headshot), `clarity_id`, `stats_asof`, `updated`.
- `templates/base.html` — head (SEO/OG/JSON-LD), nav, footer. `{{key}}` from site.json or page front matter, `{{#key}}…{{/key}}` conditional.
- `content/pages/*.html` — one file per page, front matter `slug/title/description`. `{{data:deals}}`, `{{data:reels}}`, `{{data:brands}}`, `{{data:codes}}`, `{{latest_posts}}`, `{{all_posts}}` expand from data/posts.
- `content/data/*.json` — deals, reels, brands list, codes. Edit these, not the HTML, to update numbers/links.
- `content/posts/YYYY-MM-DD-slug.md` — blog posts. Front matter: `title, date, description, tags, slug, cover (optional), draft: true (to hide)`.
- `docs/assets/` — css, img (web-sized, ≤1600px, q82), the two PDFs.

## Voice (non-negotiable)

- lowercase. short sentences. things Dalen would literally say. no "we are pleased", no corporate phrasing, no em-dashes.
- first person. specific numbers over adjectives. one idea per paragraph.
- headlines in Instrument Serif with the italic accent word (`<i>word</i>`) carrying the teal.
- faith, family (mom Alena, dog Dude), surfing, Out The Back, Destination X S2 are the recurring threads. Don't invent facts; if a fact isn't in site.json, the pages, or a post, ask Dalen.

## Blog agent workflow

1. Pick a topic from Dalen's recent reels/TikToks or the backlog below. Target search terms that pair his name with a subject ("dalen michaels destination x", "surf hurricane florida", "out the back surf brand", "creator brand deals rates").
2. Write 500–900 words in the voice above. Include at least one internal link (`/brands/`, `/mentorship/`, `/speaking/`, another post) and one outbound link to the source reel.
3. Save to `content/posts/`, run `python3 build.py`, check `docs/blog/<slug>/index.html` renders, commit with a message like `post: <title>`, push to main.
4. Never change rates, stats, or claims about people without Dalen's say-so.

Backlog: building the OTB van · the warehouse build · how I price brand deals · jiu jitsu and business · my morning routine (the LMNT reel) · florida surf spots guide · what mom-and-son content taught me · van tour 2026 recap · surf expo as a small brand.

## Deploy

GitHub Pages, branch `main`, folder `/docs`, custom domain `dalenmichaels.com` (CNAME file is generated). DNS at the registrar: A records 185.199.108.153 / .109 / .110 / .111 and CNAME `www` → `<user>.github.io`.
