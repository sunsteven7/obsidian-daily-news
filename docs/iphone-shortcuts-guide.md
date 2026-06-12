# iPhone Shortcuts Guide

Goal:

```text
iPhone at 08:10
→ download latest-daily-section.md
→ replace the daily-news-digest block in today's Daily Note
→ save back into iCloud Obsidian vault
```

## Before you start

Confirm your vault is visible in the iPhone Files app, for example:

```text
iCloud Drive / Obsidian / Steven's Vault
```

Your exact path may differ.

## URL to download

Use your repo raw URL:

```text
https://raw.githubusercontent.com/YOUR_USERNAME/obsidian-daily-news/main/output/latest-daily-section.md
```

## Shortcut logic

Create a shortcut named:

```text
Import Daily News to Obsidian
```

Actions:

1. **Current Date**
2. **Format Date**
   - Format: Custom
   - Custom format: `yyyy-MM-dd`
   - Save as variable `Today`
3. **URL**
   - Put your raw `latest-daily-section.md` URL
4. **Get Contents of URL**
   - Method: GET
5. **Set Variable**
   - Name: `NewsSection`
6. **Text**
   - `Daily Notes/[Today].md`
   - This is the relative target path inside your vault.
7. **Get File from Folder**
   - Folder: your Obsidian vault folder in iCloud Drive
   - Path: `Daily Notes/[Today].md`
   - Turn off “Show Document Picker” if available
   - If file does not exist, continue with empty text if Shortcuts allows; otherwise use the simpler overwrite setup below first.
8. **Replace Text**
   - Pattern: `(?s)<!-- daily-news-digest:start -->.*?<!-- daily-news-digest:end -->`
   - Replacement: `NewsSection`
   - Input: existing Daily Note text
9. **If** replacement result is same as input / marker not found
   - Append two new lines + `NewsSection`
10. **Save File**
   - Destination: iCloud Drive / Obsidian / Steven's Vault / Daily Notes / `[Today].md`
   - Overwrite if file exists: ON
   - Ask Where to Save: OFF

## Simpler first test

For the first test, do not modify Daily Notes. Just save the downloaded file to:

```text
News/Daily/Test News.md
```

If that appears in Obsidian mobile, then build the full replacement shortcut.

## Automation

In Shortcuts app:

1. Automation
2. New Automation
3. Time of Day
4. 08:10
5. Daily
6. Run Immediately
7. Choose `Import Daily News to Obsidian`

## Important notes

- GitHub Actions runs around 08:00 Asia/Shanghai, but can be delayed.
- 08:10 is usually safer than 08:00.
- If iPhone has no network or iCloud Drive is unavailable, the shortcut may fail that day.
- This does not require your Mac to be on.

