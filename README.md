# World Cup 2026 Standings Widget (Dakboard)

A self-updating Dakboard widget for FIFA World Cup 2026 group standings.
No paid APIs, no CORS problems, nothing always-on to maintain.

## How it works

1. A **GitHub Action** runs every hour (`.github/workflows/update-standings.yml`)
2. It runs `scripts/fetch_standings.py`, which calls the **free** football-data.org
   API and writes `data/standings.json`
3. The Action commits that file back to the repo
4. `index.html` (the widget itself) fetches that JSON from
   `raw.githubusercontent.com` — a plain static file with proper CORS headers,
   so it loads fine in Dakboard's browser view
5. Your Anthropic API key / any paid service is never involved

## One-time setup

### 1. Get a free football-data.org API key
Register at https://www.football-data.org/client/register — free, no credit
card, takes about a minute. You'll get an API token by email.

### 2. Create a GitHub repo and push this folder
```bash
cd worldcup-widget
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 3. Add your API key as a GitHub Secret
In your repo on GitHub: **Settings → Secrets and variables → Actions → New
repository secret**
- Name: `FOOTBALL_DATA_API_KEY`
- Value: (the token you got from football-data.org)

### 4. Update `index.html` with your repo path
Open `index.html`, find this line near the top of the `<script>` block:
```js
const DATA_URL = "https://raw.githubusercontent.com/OWNER/REPO/main/data/standings.json";
```
Replace `OWNER/REPO` with your actual GitHub username and repo name, e.g.:
```js
const DATA_URL = "https://raw.githubusercontent.com/janedoe/worldcup-widget/main/data/standings.json";
```
Commit and push that change.

### 5. Trigger the Action once manually
In your repo: **Actions tab → Update World Cup Standings → Run workflow**.
This populates `data/standings.json` for the first time instead of waiting
up to an hour for the cron to fire.

### 6. Point Dakboard at `index.html`
Host `index.html` somewhere Dakboard can reach it as a URL — easiest options:
- **GitHub Pages**: Settings → Pages → deploy from `main` branch. Your widget
  URL becomes `https://YOUR_USERNAME.github.io/YOUR_REPO/index.html`
- Or any static host (Netlify, Vercel, S3, etc.)

In Dakboard, add a **"Web Page" / custom HTML widget** pointing at that URL.

## Adjusting the schedule

Edit the cron line in `.github/workflows/update-standings.yml`:
```yaml
- cron: '5 * * * *'   # every hour at :05
```
football-data.org's free tier allows 10 requests/minute, so even running
every 15 minutes (`*/15 * * * *`) is nowhere close to the limit.

## Troubleshooting

- **Widget shows "Update failed"**: check the Actions tab for a failed run —
  usually a missing/invalid `FOOTBALL_DATA_API_KEY` secret.
- **Standings look stale**: the script keeps the last good data and marks
  `status: "stale"` if a fetch fails, rather than wiping the board. Check
  Actions logs for the underlying error.
- **A team's flag shows 🏳**: football-data.org's short name didn't match
  anything in `GROUP_SEEDS` in `index.html`. Open the file and adjust the
  name in `GROUP_SEEDS` to match, or extend `resolveFlag()`.
