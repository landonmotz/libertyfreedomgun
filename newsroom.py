#!/usr/bin/env python3
"""
The Liberty Freedom Gun newsroom robot.

GitHub runs this for you when you open an issue or reply to one.
It asks Google's free Gemini AI to write the story, saves it in articles/,
publishes the site, and replies on the issue with the link.
You never need to run it yourself.
"""

# ============================================================
#  SETTINGS. Change these to whatever you like.
# ============================================================
# Backup Google Gemini models. The robot finds the newest free "Flash"
# model on its own and tries that first, so you rarely need to touch this.
MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest"]

# Used for story dates and front page order.
TIME_ZONE = "America/New_York"

# Extra house style rules for the AI. Add your own lines.
STYLE_NOTES = """
- Favor small, specific, relatable details over big wacky ones.
- Running jokes are welcome if the request mentions them.
"""

# Reply with one of these to take a story down.
DELETE_WORDS = {"delete", "/delete", "delete it", "delete this", "take it down", "remove it"}
# ============================================================

import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import build  # site name, domain, and helpers

ROOT = Path(__file__).resolve().parent
ARTICLES = ROOT / "articles"
IMAGES = ROOT / "images"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
AI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI = "https://generativelanguage.googleapis.com/v1beta"
MARKER = re.compile(r"<!-- lfg-story: ([a-z0-9-]+) -->")

SYSTEM = f"""You are the entire newsroom of {build.SITE_NAME}, a satirical news site in the deadpan style of The Onion. A group of friends sends you story ideas, often about each other.

How to write:
- Play it completely straight. Serious newspaper voice. The joke is treating something absurd or petty as real news.
- 200 to 350 words. Short paragraphs, usually one to three sentences.
- Open with a first sentence that states the "news" plainly.
- Invent quotes, experts, institutions, and very specific statistics.
- Use the names from the request. Friendly roasting is the goal. Nothing sexual, hateful, or genuinely hurtful.
- Never feature celebrities, politicians, or other real public figures. Swap in an invented person instead.
- You may use one "## " subheading and one "> " pull quote that repeats a line from the story.
- Finish with a line that begins "At press time,".
- Do not use em dashes.
{STYLE_NOTES}
Reply with only a JSON object with these keys:
"title": headline in title case
"slug": 3 to 6 lowercase words joined by hyphens
"category": one word, such as Local, Nation, Science, Culture, Sports, Business, Tech
"author": an invented reporter name
"dateline": a US city and state abbreviation in capitals, like "DAYTON, OH"
"summary": one funny sentence for link previews
"caption": a short news-style photo caption if there is a photo, otherwise ""
"body": the story as paragraphs separated by blank lines. Do not repeat the headline or dateline."""


class Problem(Exception):
    """A plain-English problem to report back on the issue."""

    def __init__(self, message, details=""):
        super().__init__(message)
        self.details = details


# ---------- GitHub helpers ----------

def api(method, path, data=None):
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def say(number, text):
    api("POST", f"/repos/{REPO}/issues/{number}/comments", {"body": text})


def close(number):
    try:
        api("PATCH", f"/repos/{REPO}/issues/{number}", {"state": "closed", "state_reason": "completed"})
    except Exception:
        pass


def react(number, comment):
    """Thumbs-up style 'on it' signal so you know the robot saw you."""
    path = (f"/repos/{REPO}/issues/comments/{comment['id']}/reactions" if comment
            else f"/repos/{REPO}/issues/{number}/reactions")
    try:
        api("POST", path, {"content": "eyes"})
    except Exception:
        pass


def find_story(number):
    """The story this issue already made, if any."""
    try:
        comments = api("GET", f"/repos/{REPO}/issues/{number}/comments?per_page=100") or []
    except Exception:
        return None
    for c in reversed(comments):
        m = MARKER.search(c.get("body") or "")
        if m and (ARTICLES / f"{m.group(1)}.md").exists():
            return m.group(1)
    return None


def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def publish(message):
    git("config", "user.name", "LFG Newsroom")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    paths = [p for p in ("articles", "images") if (ROOT / p).exists()]
    git("add", "-A", *paths)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return
    git("commit", "-m", message)
    for attempt in range(3):
        try:
            git("pull", "--rebase", "--autostash", "origin", "main")
            git("push", "origin", "HEAD:main")
            break
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise Problem("Couldn't save the story to GitHub.")
            time.sleep(4)
    # Pushes made by the robot don't start other workflows, so start the
    # site build directly.
    api("POST", f"/repos/{REPO}/actions/workflows/deploy.yml/dispatches", {"ref": "main"})


# ---------- AI ----------

def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start:end + 1])


SKIP_WORDS = ("lite", "image", "tts", "audio", "live", "embed", "exp", "cyber",
              "computer", "robot", "native", "nano", "thinking", "learn")


def version_of(name):
    m = re.search(r"(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


def model_list():
    """Newest free Flash model first, then the backups."""
    stable, previews = [], []
    try:
        req = urllib.request.Request(f"{GEMINI}/models?pageSize=200", headers={"x-goog-api-key": AI_KEY})
        with urllib.request.urlopen(req, timeout=30) as r:
            listing = json.loads(r.read())
        for m in listing.get("models", []):
            name = m.get("name", "").replace("models/", "")
            low = name.lower()
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            if "flash" not in low or "latest" in low or any(w in low for w in SKIP_WORDS):
                continue
            (previews if "preview" in low else stable).append(name)
        stable.sort(key=lambda n: (-version_of(n), len(n)))
        previews.sort(key=lambda n: (-version_of(n), len(n)))
    except Exception as e:
        print(f"Couldn't list models: {e}")
    names = stable[:2] + MODELS[:1] + previews[:1] + stable[2:3] + MODELS[1:]
    ordered = []
    for n in names:
        if n not in ordered:
            ordered.append(n)
    print("Will try:", ", ".join(ordered))
    return ordered


def read_reply(text):
    """Pull the story out of whatever shape the AI replied with."""
    story = parse_json(text)
    if isinstance(story, list) and story:
        story = story[0]
    if not isinstance(story, dict):
        raise ValueError("reply wasn't a story")
    story = {str(k).lower(): v for k, v in story.items()}
    if "title" not in story:
        for v in story.values():
            if isinstance(v, dict) and ("title" in v or "headline" in v):
                story = {str(k).lower(): x for k, x in v.items()}
                break
    story.setdefault("title", story.get("headline", ""))
    for key in ("article", "text", "content", "story"):
        if not story.get("body") and isinstance(story.get(key), str):
            story["body"] = story[key]
    if not story.get("title") or not story.get("body"):
        raise ValueError("reply was missing a title or body")
    return story


def call_native(model, ask, json_mode):
    config = {"responseMimeType": "application/json"} if json_mode else {}
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": ask}]}],
    }
    if config:
        payload["generationConfig"] = config
    req = urllib.request.Request(
        f"{GEMINI}/models/{model}:generateContent",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"x-goog-api-key": AI_KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        data = json.loads(r.read())
    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "no reply")
        raise ValueError(f"blocked: {reason}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        reason = candidates[0].get("finishReason", "empty reply")
        if reason in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION"):
            raise ValueError(f"blocked: {reason}")
        raise ValueError(f"empty reply ({reason})")
    return text


def call_chat(model, ask):
    """Google's OpenAI-style endpoint, as a second route to the same model."""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": ask}],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        f"{GEMINI}/openai/chat/completions",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def ask_ai(ask):
    if not AI_KEY:
        raise Problem("No AI key found. Add a GEMINI_API_KEY secret to the repo. The README shows how.")
    queue = model_list()
    tried, log = set(), []
    rate_limited = blocked = False
    while queue and len(tried) < 7:
        model = queue.pop(0)
        if model in tried:
            continue
        tried.add(model)
        routes = [("json", lambda: call_native(model, ask, True)),
                  ("plain", lambda: call_native(model, ask, False)),
                  ("chat", lambda: call_chat(model, ask))]
        for how, attempt in routes:
            try:
                story = read_reply(attempt())
                print(f"Written by {model} ({how})")
                return story
            except urllib.error.HTTPError as e:
                detail = " ".join(e.read().decode("utf-8", "replace").split())[:260]
                log.append(f"{model} ({how}): HTTP {e.code} {detail}")
                print(log[-1])
                if e.code in (400, 401, 403) and re.search(r"API.?key|API_KEY_INVALID|PERMISSION_DENIED", detail):
                    raise Problem("Google rejected the AI key. Check the GEMINI_API_KEY secret.")
                for hint in re.findall(r"models/(gemini-[\w.\-]*\w)", detail):
                    if hint not in tried:
                        queue.insert(0, hint)  # Google told us which model to use
                        break
                if e.code == 429:
                    rate_limited = True
                    break
                if e.code == 400:
                    continue  # try this model another way
                break  # not found or server trouble: next model
            except (ValueError, KeyError, IndexError, TypeError, urllib.error.URLError, TimeoutError) as e:
                log.append(f"{model} ({how}): {e}")
                print(log[-1])
                if "blocked" in str(e):
                    blocked = True
                    break
    details = "\n".join(log)
    if blocked:
        raise Problem("The AI wouldn't write that one. Try wording it differently.", details)
    if rate_limited:
        raise Problem("The free AI limit is used up for now. Try again later.", details)
    raise Problem("The AI didn't give a usable story.", details)


# ---------- text cleanup ----------

IMAGE_MD = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
IMAGE_HTML = re.compile(r"<img[^>]*?src=[\"'](https?://[^\"']+)[\"'][^>]*>", re.I)


def find_image(text):
    text = text or ""
    for pattern in (IMAGE_HTML, IMAGE_MD):
        m = pattern.search(text)
        if m:
            return m.group(1)
    return None


def clean_request(text):
    text = IMAGE_HTML.sub("", text or "")
    text = IMAGE_MD.sub("", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return text.strip()


def one_line(value):
    return " ".join(str(value or "").split())


def no_em_dashes(text):
    text = re.sub(r"\s*\u2014\s*", ", ", text)
    return re.sub(r",\s*,", ",", text)


def tidy_story(story):
    title = one_line(story.get("title")).strip("\"'")
    dateline = one_line(story.get("dateline")).upper().strip(" -:.,")
    body = str(story.get("body") or "").replace("\r\n", "\n").strip()
    lines = body.split("\n")
    if lines and lines[0].lstrip().startswith("#") and title.lower()[:20] in lines[0].lower():
        body = "\n".join(lines[1:]).strip()
    if dateline:
        body = re.sub(rf"^\**{re.escape(dateline)}\**\s*[\-\u2013\u2014:.,]*\s*", "", body, flags=re.I)
    category = one_line(story.get("category")).split(" ")[0].strip(".,").capitalize()[:20]
    return {
        "title": no_em_dashes(title),
        "slug": one_line(story.get("slug")),
        "category": category or build.DEFAULT_CATEGORY,
        "author": one_line(story.get("author")) or build.DEFAULT_AUTHOR,
        "dateline": dateline,
        "summary": no_em_dashes(one_line(story.get("summary"))),
        "caption": no_em_dashes(one_line(story.get("caption"))),
        "body": no_em_dashes(body),
    }


# ---------- files ----------

def now_stamp():
    try:
        from zoneinfo import ZoneInfo
        moment = dt.datetime.now(ZoneInfo(TIME_ZONE))
    except Exception:
        moment = dt.datetime.now()
    return moment.strftime("%Y-%m-%d %H:%M")


def unique_slug(text):
    words = build.slugify(text).split("-")[:7]
    base = "-".join(words) or "story"
    if base in build.RESERVED:
        base += "-story"
    slug, n = base, 2
    while (ARTICLES / f"{slug}.md").exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def save_photo(url, slug):
    """Download a photo from the issue into images/. Returns the file name, or ''."""
    data = None
    for with_auth in (False, True):
        req = urllib.request.Request(url, headers={"User-Agent": "lfg-newsroom"})
        if with_auth:
            req.add_header("Authorization", f"Bearer {TOKEN}")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read(30_000_000)
            break
        except Exception as e:
            print(f"Photo download failed ({'with' if with_auth else 'without'} token): {e}")
    if not data:
        return ""

    IMAGES.mkdir(exist_ok=True)
    for old in IMAGES.glob(f"{slug}-photo*"):
        old.unlink()
    name = f"{slug}-photo{int(time.time()) % 100000}.jpg"
    try:
        from PIL import Image, ImageOps
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        img = img.convert("RGB")
        img.thumbnail((1600, 1600))
        img.save(IMAGES / name, "JPEG", quality=82, optimize=True, progressive=True)
        return name
    except Exception as e:
        print(f"Couldn't convert photo: {e}")
        return ""


def write_article(slug, story, image, caption, date):
    lines = [
        f"title: {story['title']}",
        f"date: {date}",
        f"category: {story['category']}",
        f"author: {story['author']}",
    ]
    if story["dateline"]:
        lines.append(f"dateline: {story['dateline']}")
    if story["summary"]:
        lines.append(f"summary: {story['summary']}")
    if image:
        lines.append(f"image: {image}")
        if caption:
            lines.append(f"caption: {caption}")
    ARTICLES.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n---\n" + story["body"].strip() + "\n"
    (ARTICLES / f"{slug}.md").write_text(text, encoding="utf-8")


def link(slug):
    return f"{build.SITE_URL}/{slug}/"


def done_message(slug, title, verb, note=""):
    extra = f"\n\n{note}" if note else ""
    return (
        f"**{title}** is {verb}.\n\n{link(slug)}\n\n"
        "Live in about a minute. Refresh if you see the old version."
        f"{extra}\n\n"
        "Want changes? Reply here with what to change, like \"make it shorter\" or "
        "\"add that Dan cried.\" Drag in a photo to add one. Reply **delete** to take it down.\n\n"
        f"<!-- lfg-story: {slug} -->"
    )


# ---------- the three jobs ----------

def new_story(number, issue, comment):
    premise = one_line(clean_request(issue.get("title")))
    details = clean_request(issue.get("body"))
    if comment:
        details = (details + "\n\n" + clean_request(comment.get("body"))).strip()
    photo_url = find_image(comment.get("body") if comment else "") or find_image(issue.get("body"))

    ask = f"Story idea: {premise}"
    if details:
        ask += f"\n\nExtra details from the requester:\n{details}"
    ask += "\n\nThere is a photo, so write a caption." if photo_url else "\n\nNo photo. Leave caption empty."

    story = tidy_story(ask_ai(ask))
    slug = unique_slug(story["slug"] or story["title"])
    image = save_photo(photo_url, slug) if photo_url else ""
    note = "Couldn't use that photo. Try a JPG or PNG." if photo_url and not image else ""
    write_article(slug, story, image, story["caption"], now_stamp())
    publish(f"New story: {story['title']}")
    say(number, done_message(slug, story["title"], "up", note))
    close(number)


def revise_story(number, slug, feedback):
    path = ARTICLES / f"{slug}.md"
    old = build.read_article(path)
    photo_url = find_image(feedback)
    ask = (
        "Here is the current story file:\n\n" + path.read_text(encoding="utf-8") +
        "\n\nRewrite it using this feedback. Keep what already works.\n\nFeedback: " +
        (clean_request(feedback) or "Use the new photo.")
    )
    if photo_url:
        ask += "\n\nThere is a new photo, so write a caption."
    story = tidy_story(ask_ai(ask))

    image, caption, note = old["image"], old["caption"], ""
    if photo_url:
        new_image = save_photo(photo_url, slug)
        if new_image:
            image, caption = new_image, story["caption"] or caption
        else:
            note = "Couldn't use that photo. Try a JPG or PNG."
    elif image and story["caption"]:
        caption = story["caption"]

    write_article(slug, story, image, caption, old["date"].strftime("%Y-%m-%d %H:%M"))
    publish(f"Update story: {story['title']}")
    say(number, done_message(slug, story["title"], "updated", note))


def delete_story(number, slug):
    (ARTICLES / f"{slug}.md").unlink(missing_ok=True)
    for photo in (IMAGES.glob(f"{slug}-photo*") if IMAGES.exists() else []):
        photo.unlink()
    publish(f"Delete story: {slug}")
    say(number, "Taken down. The link will stop working in about a minute.\n\n"
                "Reply here to write a fresh version.")


def main():
    if not TOKEN or not REPO:
        print("This runs on GitHub. Open an issue on your repo to write a story.")
        return 0
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    issue = event["issue"]
    number = issue["number"]
    comment = event.get("comment")
    react(number, comment)

    try:
        slug = find_story(number)
        if comment and slug and one_line(comment.get("body")).lower().strip(".!") in DELETE_WORDS:
            delete_story(number, slug)
        elif comment and slug:
            revise_story(number, slug, comment.get("body") or "")
        else:
            new_story(number, issue, comment)
    except Problem as p:
        extra = ""
        if p.details:
            extra = f"\n\n<details><summary>What the AI said</summary>\n\n```\n{p.details}\n```\n</details>"
        say(number, f"Couldn't finish that one. {p}\n\nReply here to try again.{extra}")
        return 1
    except Exception as e:
        say(number, "Something broke while writing that story. Reply here to try again.\n\n"
                    f"<details><summary>Error details</summary>\n\n```\n{e}\n```\n</details>")
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
