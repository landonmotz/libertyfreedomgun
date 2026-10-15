# Liberty Freedom Gun

A fake news site for you and your friends. Free to host.

## What's in here

| Folder or file | What it does |
| --- | --- |
| `articles/` | Your stories. One `.md` file per story. |
| `images/` | Photos for stories. Optional. |
| `static/` | Look of the site, icons, link preview image. |
| `build.py` | Turns your stories into the website. |
| `newsroom.py` | The AI robot that writes stories from issues. |
| `.github/workflows/` | Publishes the site, and runs the AI newsroom. |

## One-time setup (GitHub Pages, free)

1. Make a free account at github.com.
2. Click **New repository**. Name it anything. Make it **Public** (free Pages needs public).
3. On the new repo page, click **uploading an existing file**. Unzip this project and drag everything inside it into the browser. Click **Commit changes**.
4. Check that the `.github` folder uploaded. Some computers hide it.
   - Missing? Click **Add file > Create new file**. Type `.github/workflows/deploy.yml` as the name. Paste in that file's contents. Commit.
   - On a Mac, press Cmd + Shift + . in Finder to see hidden folders.
5. Go to **Settings > Pages**. Under **Source**, pick **GitHub Actions**.
6. Go to the **Actions** tab. Click **Build and publish site**, then **Run workflow**. Wait for the green check.
7. Back in **Settings > Pages**, type `libertyfreedomgun.com` under **Custom domain**. Save.
8. At your domain company (GoDaddy, Namecheap, etc.), add these DNS records:

   | Type | Name | Value |
   | --- | --- | --- |
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |
   | CNAME | www | YOUR-GITHUB-USERNAME.github.io |

   Delete any old A records for `@` first.
9. Wait. Can take a few hours. Then tick **Enforce HTTPS** in Settings > Pages.

## AI newsroom (easiest way to post)

**One-time setup:**

1. Go to aistudio.google.com and sign in with Google.
2. Click **Get API key**, then **Create API key**. Copy it.
3. On GitHub: **Settings > Secrets and variables > Actions > New repository secret**.
4. Name: `GEMINI_API_KEY`. Secret: paste the key. Click **Add secret**.

**Posting a story:**

1. Open the **Issues** tab. Click **New issue**.
2. Title: the story idea. Like `Dan got banned from Costco`.
3. Optional: add details in the box. Drag in a photo.
4. Click **Create**.

About a minute later, the robot replies with the link. Works in the GitHub phone app too.

- **Change it:** reply on the issue. Like "make it shorter" or "add that Dan cried."
- **New photo:** reply with a photo dragged in.
- **Take it down:** reply `delete`.
- **Let friends post:** Settings > Collaborators > Add people. Strangers can't trigger it.

Uses Google's free Gemini AI. The free tier allows plenty of stories a day for a friend group. Google may use free-tier requests to improve its products. Tweak the writing style at the top of `newsroom.py`.

## Post a new story by hand

1. Open the `articles` folder on GitHub.
2. Click **Add file > Create new file**.
3. Name it something like `dan-banned-from-costco.md`. The name becomes the link.
4. Copy the layout from `_TEMPLATE.md` and fill it in.
5. Click **Commit changes**. Wait about a minute.
6. Send the link: `https://libertyfreedomgun.com/dan-banned-from-costco/`

Works from your phone's browser too.

## Story format

```
title: Area Man Banned From Costco After Sample Incident
date: 2026-10-05
category: Local
author: Staff Reporter
dateline: DAYTON, OH
summary: One funny line. Shows up in text message link previews.
image: costco.jpg
caption: The scene of the incident.
---
First paragraph. Blank line between paragraphs.

## A subheading

> A big pull quote.

**bold**, *italics*, [a link](https://example.com)

![A caption](another-photo.jpg)
```

Only `title` is required. Newest `date` goes on top of the front page.

- **Hide a story:** rename it to start with `_`, like `_draft.md`.
- **Delete a story:** delete the file.
- **Fix a typo:** click the file, click the pencil, commit.

## Photos

Upload them into `images/` (Add file > Upload files). Then add `image: yourphoto.jpg` to the story. That photo also shows in link previews. Wide photos look best. Keep each under 2 MB.

## Write stories with AI

Paste this into Claude or any chatbot:

```
Write a short satirical news article about this premise: [YOUR PREMISE HERE]

Style: deadpan and serious, like a real newspaper. Invent every quote. No celebrities or real public figures. 200 to 350 words. Short paragraphs. End with an "At press time," line.

Reply with only this format, nothing before or after:

title: (headline in title case)
date: (today's date as YYYY-MM-DD)
category: (one word, like Local, Science, Nation, Culture, Sports)
author: (a made-up reporter name)
dateline: (CITY, ST in capitals)
summary: (one funny sentence)
---
(article body, blank line between paragraphs, can use ## subheadings and one > pull quote)
```

Copy the answer into a new file in `articles/`. Done.

## Settings

Open `build.py`. The top section has the site name, tagline, domain, footer note, and a search engine switch. Search engines are blocked by default, so strangers won't find your fake stories on Google. Link previews still work.

## Preview on your own computer (optional)

Install Python 3, then in this folder run:

```
python build.py
python -m http.server 8000 -d public
```

Open http://localhost:8000

## Other free hosts

**Netlify Drop:** Run `python build.py`, then drag the `public` folder onto app.netlify.com/drop. You'd redo this for each new story, so GitHub Pages is easier long term.

**Cloudflare Pages:** Connect your GitHub repo. Build command `python build.py`. Output folder `public`.
