# White Tiger Constitution — Auto-Synced Static Site

This repo auto-publishes a Google Doc to GitHub Pages, refreshing every 10 minutes.

## Setup (one-time)

### 1. Publish your Google Doc to the web

1. Open your Google Doc
2. Go to **File → Share → Publish to web**
3. Click **Publish** and confirm
4. You don't need to copy the link — the build script already has your Doc ID

### 2. Create the GitHub repo

```bash
# Create a new repo (or use an existing one)
git init white-tiger-constitution
cd white-tiger-constitution

# Copy in the files from this download:
#   index.html          ← the page template
#   build.py            ← the build script
#   .github/workflows/sync-doc.yml  ← the GitHub Action

git add .
git commit -m "Initial setup"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 3. Enable GitHub Pages

1. Go to your repo on GitHub → **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Set the branch to `gh-pages` and folder to `/ (root)`
4. Click **Save**

### 4. First run

The workflow runs automatically on push to `main`, so after you push,
it will build and deploy within a couple of minutes.

You can also trigger it manually:
- Go to **Actions** → **Sync Google Doc to GitHub Pages** → **Run workflow**

## How it works

```
Google Doc (you edit here)
    ↓  "Publish to web" makes content publicly accessible
    ↓
GitHub Actions (runs every 10 min)
    ↓  build.py fetches the published doc HTML
    ↓  Extracts the content, injects it into index.html
    ↓  Deploys to gh-pages branch
    ↓
GitHub Pages (serves the static site)
    → yourname.github.io/your-repo
```

## Customization

- **Change the schedule**: Edit the `cron` line in `.github/workflows/sync-doc.yml`.
  For every 5 minutes: `'*/5 * * * *'`
- **Change the Doc ID**: Update `DOC_ID` in both `index.html` and `build.py`
- **Styling**: Edit the `<style>` section in `index.html`

## Note on GitHub Actions scheduling

GitHub doesn't guarantee cron runs at the exact minute — during high load,
they may be delayed by a few minutes. For most use cases this is fine.
Also, GitHub may disable scheduled workflows on repos with no recent
activity (60+ days). Just push a commit or re-enable them manually.
