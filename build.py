#!/usr/bin/env python3
"""
Builds the Liberty Freedom Gun website.

    python build.py

Reads stories from articles/, writes the finished site to public/.
No extra installs needed. Plain Python 3.9 or newer.
"""

# ============================================================
#  SETTINGS. Change these to whatever you like.
# ============================================================
SITE_NAME = "Liberty Freedom Gun"
TAGLINE = "Reporting the truth since last Tuesday"
DOMAIN = "libertyfreedomgun.com"
DEFAULT_AUTHOR = "Staff Reporter"
DEFAULT_CATEGORY = "News"
SATIRE_NOTE = (
    "Liberty Freedom Gun is a satire site. Every story here is made up. "
    "Any resemblance to actual events is a coincidence, or a joke."
)
# True keeps Google and other search engines from listing the site.
# Link previews in texts and group chats still work either way.
HIDE_FROM_SEARCH_ENGINES = True
# ============================================================

import datetime as dt
import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles"
IMAGES_DIR = ROOT / "images"
STATIC_DIR = ROOT / "static"
OUT = ROOT / "public"

SITE_URL = "https://" + DOMAIN.strip().strip("/")
RESERVED = {"images", "section", "static", "404", "index"}
BUILD_ID = dt.datetime.now().strftime("%Y%m%d%H%M%S")


# ---------- small helpers ----------

def esc(text):
    return html.escape(str(text), quote=True)


def slugify(text):
    text = text.lower().replace("&", " and ").replace("'", "").replace("\u2019", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "story"


def smarten(text):
    """Curly quotes and proper ellipses."""
    text = re.sub(r'(^|[\s(\[{-])"', "\\1\u201c", text)
    text = text.replace('"', "\u201d")
    text = re.sub(r"(^|[\s(\[{-])'", "\\1\u2018", text)
    text = text.replace("'", "\u2019")
    return text.replace("...", "\u2026")


def nice_date(d):
    return f"{d:%B} {d.day}, {d.year}"


def parse_date(value):
    value = (value or "").strip()
    formats = [
        "%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y",
        "%m/%d/%y", "%B %d, %Y", "%b %d, %Y",
    ]
    for f in formats:
        try:
            return dt.datetime.strptime(value, f)
        except ValueError:
            pass
    return None


def image_src(value, root):
    value = value.strip()
    if value.startswith(("http://", "https://", "/")):
        return value
    return f"{root}images/{value}"


def image_abs(value):
    value = value.strip()
    if value.startswith(("http://", "https://")):
        return value
    return f"{SITE_URL}/images/{value.lstrip('/')}"


# ---------- article text formatting ----------

def inline(text):
    # Pull links out first so their web addresses stay untouched.
    links = []

    def stash(m):
        links.append((m.group(1), m.group(2)))
        return f"\x00{len(links) - 1}\x00"

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", stash, text)
    text = esc(smarten(text))
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?![\*\w])", r"<em>\1</em>", text)

    def restore(m):
        label, url = links[int(m.group(1))]
        return f'<a href="{esc(url)}">{esc(smarten(label))}</a>'

    return re.sub(r"\x00(\d+)\x00", restore, text)


def render_body(body, dateline, root):
    out = []
    first_paragraph = True
    blocks = re.split(r"\n\s*\n", body.strip())
    for block in blocks:
        lines = [l.rstrip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        # Headings on their own line, with text possibly right under them.
        while lines and lines[0].lstrip().startswith("#"):
            heading = lines.pop(0).lstrip().lstrip("#").strip()
            out.append(f"<h2>{inline(heading)}</h2>")
        if not lines:
            continue

        first = lines[0].strip()

        # Image: ![caption](photo.jpg)
        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", first)
        if m and len(lines) == 1:
            caption, src = m.group(1).strip(), m.group(2)
            cap = f"<figcaption>{inline(caption)}</figcaption>" if caption else ""
            out.append(
                f'<figure class="story-figure"><img src="{esc(image_src(src, root))}" '
                f'alt="{esc(caption)}" loading="lazy">{cap}</figure>'
            )
            continue

        # Pull quote: > text
        if all(l.lstrip().startswith(">") for l in lines):
            text = " ".join(l.lstrip()[1:].strip() for l in lines)
            out.append(f"<blockquote><p>{inline(text)}</p></blockquote>")
            continue

        # Bulleted list: - item
        if all(re.match(r"\s*[-*+] ", l) for l in lines):
            bullet = re.compile(r"^\s*[-*+] ")
            items = "".join(f"<li>{inline(bullet.sub('', l))}</li>" for l in lines)
            out.append(f"<ul>{items}</ul>")
            continue

        text = inline(" ".join(l.strip() for l in lines))
        if first_paragraph and dateline:
            text = f'<span class="dateline">{esc(dateline)}</span> {text}'
        first_paragraph = False
        out.append(f"<p>{text}</p>")
    return "\n".join(out)


# ---------- reading articles ----------

def read_article(path):
    raw = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    lines = raw.split("\n")
    if lines and lines[0].strip() == "---":
        lines = lines[1:]

    meta, body_lines = {}, lines
    if any(l.strip() == "---" for l in lines):
        cut = next(i for i, l in enumerate(lines) if l.strip() == "---")
        for l in lines[:cut]:
            if ":" in l:
                key, value = l.split(":", 1)
                meta[key.strip().lower()] = value.strip()
        body_lines = lines[cut + 1:]
    else:
        # No settings block: first line is the headline.
        non_empty = [i for i, l in enumerate(lines) if l.strip()]
        if non_empty:
            meta["title"] = lines[non_empty[0]].strip().lstrip("#").strip()
            body_lines = lines[non_empty[0] + 1:]

    title = meta.get("title") or path.stem.replace("-", " ").title()
    date = parse_date(meta.get("date"))
    if date is None:
        if meta.get("date"):
            print(f"  ! {path.name}: could not read date '{meta['date']}', using today")
        date = dt.datetime.now()

    slug = slugify(path.stem)
    if slug in RESERVED:
        slug += "-story"

    image = meta.get("image", "").strip()
    if image and not image.startswith(("http://", "https://")):
        if not (IMAGES_DIR / image.lstrip("/")).exists():
            print(f"  ! {path.name}: image '{image}' not found in images/")

    category = meta.get("category") or DEFAULT_CATEGORY
    return {
        "slug": slug,
        "title": title,
        "date": date,
        "author": meta.get("author") or DEFAULT_AUTHOR,
        "category": category,
        "category_slug": slugify(category),
        "summary": meta.get("summary", ""),
        "image": image,
        "caption": meta.get("caption", ""),
        "dateline": meta.get("dateline", ""),
        "body": "\n".join(body_lines),
        "source": path.name,
    }


def load_articles():
    if not ARTICLES_DIR.exists():
        return []
    stories, seen = [], set()
    for path in sorted(ARTICLES_DIR.iterdir()):
        if path.suffix.lower() not in (".md", ".txt") or path.name.startswith(("_", ".")):
            continue
        a = read_article(path)
        if a["slug"] in seen:
            print(f"  ! {path.name}: another story already uses the link '{a['slug']}', skipped")
            continue
        seen.add(a["slug"])
        stories.append(a)
    stories.sort(key=lambda a: (a["date"], a["title"]), reverse=True)
    return stories


def first_paragraph(a):
    """The opening paragraph of a story, for the front page."""
    for block in re.split(r"\n\s*\n", a["body"].strip()):
        text = " ".join(l.strip() for l in block.split("\n") if l.strip())
        if not text or text[0] in "#>!-*+":
            continue
        html_text = inline(text)
        if a["dateline"]:
            html_text = f'<span class="dateline">{esc(a["dateline"])}</span> {html_text}'
        return html_text
    return ""


# ---------- page pieces ----------

def head(title, description, path, image, og_type, root):
    robots = '<meta name="robots" content="noindex">' if HIDE_FROM_SEARCH_ENGINES else ""
    url = f"{SITE_URL}/{path}"
    if image:
        og_image = image_abs(image)
        size = ""
    else:
        og_image = f"{SITE_URL}/share.png"
        size = ('<meta property="og:image:width" content="1200">'
                '<meta property="og:image:height" content="630">')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{robots}
<link rel="canonical" href="{esc(url)}">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:image" content="{esc(og_image)}">
{size}
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0A3161">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Alfa+Slab+One&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;0,6..72,700;1,6..72,400&family=Public+Sans:wght@400;600;700&display=swap">
<link rel="stylesheet" href="{root}style.css?v={BUILD_ID}">
<script src="{root}site.js?v={BUILD_ID}" defer></script>
</head>"""


def ticker(stories, root):
    if not stories:
        return ""
    latest = stories[:6]
    items = "".join(
        f'<a href="{root}{a["slug"]}/">{esc(smarten(a["title"]))}</a>'
        '<span class="ticker-star" aria-hidden="true">\u2605</span>'
        for a in latest
    )
    hidden = items.replace("<a ", '<a tabindex="-1" ')
    seconds = max(24, len(latest) * 9)
    return f"""<div class="ticker">
  <span class="ticker-label">Breaking</span>
  <div class="ticker-track" style="--ticker-time:{seconds}s">
    <div class="ticker-move">
      <div class="ticker-set">{items}</div>
      <div class="ticker-set" aria-hidden="true">{hidden}</div>
    </div>
  </div>
</div>"""


def masthead(stories, categories, root, big=False, current=""):
    level = "h1" if big else "p"
    wordmark = esc(SITE_NAME)
    if big and " " in SITE_NAME.strip():
        first, rest = SITE_NAME.strip().split(" ", 1)
        wordmark = f'<span class="wm-line">{esc(first)}</span> <span class="wm-line">{esc(rest)}</span>'

    here = ' aria-current="page"'
    nav = [f'<a href="{root}"{here if current == "home" else ""}>Front page</a>']
    for slug, name in categories:
        mark = ' aria-current="page"' if current == slug else ""
        nav.append(f'<a href="{root}section/{slug}/"{mark}>{esc(name)}</a>')
    return f"""<a class="skip" href="#main">Skip to the stories</a>
{ticker(stories, root)}
<header class="masthead{' masthead--big' if big else ''}">
  <div class="wrap masthead-inner">
    <{level} class="wordmark"><a href="{root}">{wordmark}</a></{level}>
    <div class="masthead-meta">
      <p class="tagline">{esc(TAGLINE)}</p>
      <p class="today" data-today>{nice_date(dt.datetime.now())}</p>
    </div>
  </div>
  <div class="stripes" aria-hidden="true"></div>
</header>
<nav class="sections" aria-label="Sections">
  <div class="wrap sections-inner">{"".join(nav)}</div>
</nav>"""


def footer():
    return f"""<footer class="site-footer">
  <div class="wrap">
    <p class="footer-mark">{esc(SITE_NAME)}</p>
    <p class="footer-note">{esc(SATIRE_NOTE)}</p>
    <p class="footer-small">&copy; {dt.datetime.now().year} {esc(SITE_NAME)}</p>
  </div>
</footer>
</body>
</html>"""


def category_link(a, root):
    return (f'<a class="cat" href="{root}section/{a["category_slug"]}/">'
            f'{esc(a["category"])}</a>')


def figure_html(a, root, cls):
    if not a["image"]:
        return ""
    return (f'<a class="{cls}" href="{root}{a["slug"]}/" tabindex="-1" aria-hidden="true">'
            f'<img src="{esc(image_src(a["image"], root))}" alt="" loading="lazy"></a>')


def story_item(a, root, size="small"):
    summary = f'<p class="summary">{esc(smarten(a["summary"]))}</p>' if a["summary"] else ""
    return f"""<article class="item item--{size}">
  {figure_html(a, root, "item-img")}
  {category_link(a, root)}
  <h3 class="item-title"><a href="{root}{a['slug']}/">{esc(smarten(a['title']))}</a></h3>
  {summary}
</article>"""


# ---------- pages ----------

def build_home(stories, categories):
    root = ""
    title = f"{SITE_NAME}: {TAGLINE}"
    parts = [head(title, TAGLINE, "", "", "website", root),
             '<body class="page-home">',
             masthead(stories, categories, root, big=True, current="home"),
             '<main id="main" class="wrap home">']

    if not stories:
        parts.append('<section class="empty"><h2>No stories yet</h2>'
                     '<p>Add a file to the articles folder, then build the site again.</p></section>')
    else:
        lead, side, rest = stories[0], stories[1:4], stories[4:]
        summary = f'<p class="lead-summary">{esc(smarten(lead["summary"]))}</p>' if lead["summary"] else ""
        opener = first_paragraph(lead)
        excerpt = ""
        if opener:
            excerpt = (f'<p class="lead-excerpt">{opener}</p>'
                       f'<p class="read-more"><a href="{lead["slug"]}/">Read the full story</a></p>')
        parts.append(f"""<section class="front">
  <article class="lead">
    {figure_html(lead, root, "lead-img")}
    {category_link(lead, root)}
    <h2 class="lead-title"><a href="{lead['slug']}/">{esc(smarten(lead['title']))}</a></h2>
    {summary}
    <p class="byline">By <span class="author">{esc(lead['author'])}</span>, <time datetime="{lead['date']:%Y-%m-%d}">{nice_date(lead['date'])}</time></p>
    {excerpt}
  </article>""")
        if side:
            parts.append('<div class="side">' + "".join(story_item(a, root) for a in side) + "</div>")
        parts.append("</section>")
        if rest:
            parts.append('<section class="more"><h2 class="section-head">More stories</h2><div class="grid">'
                         + "".join(story_item(a, root, "grid") for a in rest) + "</div></section>")
    parts.append("</main>")
    parts.append(footer())
    (OUT / "index.html").write_text("\n".join(parts), encoding="utf-8")


def build_article(a, stories, categories):
    root = "../"
    page_title = f"{smarten(a['title'])} | {SITE_NAME}"
    description = smarten(a["summary"]) or f"{SITE_NAME}: {TAGLINE}"
    others = [s for s in stories if s["slug"] != a["slug"]][:5]

    figure = ""
    if a["image"]:
        cap = f"<figcaption>{inline(a['caption'])}</figcaption>" if a["caption"] else ""
        figure = (f'<figure class="story-figure story-figure--top">'
                  f'<img src="{esc(image_src(a["image"], root))}" alt="{esc(a["caption"])}">{cap}</figure>')
    deck = f'<p class="deck">{esc(smarten(a["summary"]))}</p>' if a["summary"] else ""

    latest = ""
    if others:
        latest = ('<aside class="latest" aria-labelledby="latest-head"><h2 id="latest-head" class="section-head">Latest</h2>'
                  + "".join(story_item(s, root) for s in others) + "</aside>")

    html_out = f"""{head(smarten(a['title']), description, a['slug'] + '/', a['image'], 'article', root)}
<body class="page-article">
{masthead(stories, categories, root, current=a['category_slug'])}
<main id="main" class="wrap article-layout">
  <article class="story">
    <header class="story-head">
      {category_link(a, root)}
      <h1 class="story-title">{esc(smarten(a['title']))}</h1>
      {deck}
      <p class="byline">By <span class="author">{esc(a['author'])}</span><br>
      <time datetime="{a['date']:%Y-%m-%d}">{nice_date(a['date'])}</time></p>
    </header>
    {figure}
    <div class="story-body">
{render_body(a['body'], a['dateline'], root)}
    </div>
    <div class="share">
      <button type="button" class="share-btn" data-share>Copy link</button>
      <span class="share-status" data-share-status role="status" aria-live="polite"></span>
    </div>
  </article>
  {latest}
</main>
{footer()}"""
    folder = OUT / a["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(html_out, encoding="utf-8")


def build_section(slug, name, stories, categories):
    root = "../../"
    picks = [a for a in stories if a["category_slug"] == slug]
    rows = []
    for a in picks:
        summary = f'<p class="summary">{esc(smarten(a["summary"]))}</p>' if a["summary"] else ""
        rows.append(f"""<article class="row">
  {figure_html(a, root, "row-img")}
  <div class="row-text">
    <h2 class="item-title"><a href="{root}{a['slug']}/">{esc(smarten(a['title']))}</a></h2>
    {summary}
    <p class="byline"><time datetime="{a['date']:%Y-%m-%d}">{nice_date(a['date'])}</time></p>
  </div>
</article>""")
    items = "".join(rows)
    top = head(f"{name} | {SITE_NAME}", f"{name} stories from {SITE_NAME}", f"section/{slug}/", "", "website", root)
    html_out = f"""{top}
<body class="page-section">
{masthead(stories, categories, root, current=slug)}
<main id="main" class="wrap section-page">
  <div class="narrow">
    <h1 class="section-title">{esc(name)}</h1>
    <div class="rows">{items}</div>
  </div>
</main>
{footer()}"""
    folder = OUT / "section" / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(html_out, encoding="utf-8")


def build_404(stories, categories):
    root = "/"
    html_out = f"""{head(f'Page not found | {SITE_NAME}', 'This page does not exist.', '404.html', '', 'website', root)}
<body class="page-404">
{masthead(stories, categories, root)}
<main id="main" class="wrap notfound">
  <div class="narrow">
    <h1 class="story-title">This page does not exist</h1>
    <p class="deck">The link may be mistyped, or the story was taken down. Our reporters checked everywhere, including under the couch.</p>
    <p><a class="share-btn" href="{root}">Go to the front page</a></p>
  </div>
</main>
{footer()}"""
    (OUT / "404.html").write_text(html_out, encoding="utf-8")


# ---------- main ----------

def main():
    print(f"Building {SITE_NAME}...")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUT, dirs_exist_ok=True)
    if IMAGES_DIR.exists():
        shutil.copytree(IMAGES_DIR, OUT / "images", dirs_exist_ok=True)

    stories = load_articles()
    cat_names = {}
    for a in stories:
        cat_names.setdefault(a["category_slug"], a["category"])
    counts = {s: sum(1 for a in stories if a["category_slug"] == s) for s in cat_names}
    categories = sorted(cat_names.items(), key=lambda kv: (-counts[kv[0]], kv[1]))

    build_home(stories, categories)
    for a in stories:
        build_article(a, stories, categories)
    for slug, name in categories:
        build_section(slug, name, stories, categories)
    build_404(stories, categories)

    (OUT / "CNAME").write_text(DOMAIN.strip() + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Done. {len(stories)} stories built into public/")
    for a in stories:
        print(f"  {SITE_URL}/{a['slug']}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
