# CloudNews: Obsidian Daily News via GitHub Actions + iPhone Shortcuts

This folder is a **standalone cloud version** of the daily news system.

It does **not** upload your Obsidian vault. It only generates Markdown news files from public RSS / Google News RSS sources.

## What it generates

After GitHub Actions runs, these files are created/updated:

```text
output/latest-daily-section.md   # iPhone downloads this and writes into today's Daily Note
output/latest-news.md            # full standalone news note with frontmatter
output/latest-date.txt           # YYYY-MM-DD
output/daily/YYYY-MM-DD News.md  # cloud archive copy
```

## Recommended repo setup

Create a new GitHub repo, for example:

```text
obsidian-daily-news
```

Recommended: make this repo **public only if you are comfortable with generated news being public**. It will not contain your vault, but the generated news list is visible if public.

If you make it private, iPhone Shortcuts cannot easily download the raw files without embedding a GitHub token, which is less secure.

## Upload files

Upload the contents of this `CloudNews/` folder as the root of that repo:

```text
daily_news_digest_cloud.py
.github/workflows/daily-news.yml
README.md
docs/iphone-shortcuts-guide.md
```

## Enable GitHub Actions

1. Go to the repo on GitHub.
2. Open **Actions**.
3. Enable workflows if prompted.
4. Run **Daily Obsidian News** manually once via `workflow_dispatch`.
5. Confirm `output/latest-daily-section.md` exists.

## iPhone download URL

If your repo is public, the raw URL will look like:

```text
https://raw.githubusercontent.com/YOUR_USERNAME/obsidian-daily-news/main/output/latest-daily-section.md
```

Your iPhone Shortcut downloads this file every day at 8:10 and writes it into your iCloud Obsidian vault.
