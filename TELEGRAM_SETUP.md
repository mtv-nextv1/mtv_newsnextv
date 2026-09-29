# Telegram news sync setup

The repository contains a scheduled importer and a website feed reader. The importer now attempts to import recent public posts from both Telegram channel previews, then merges newly delivered Bot API updates into the same feed.

## Required setup

1. **Rotate any bot token that was pasted into chat.** Use [@BotFather](https://t.me/BotFather) to revoke it and issue a replacement. Never commit a token to the repository.
2. Add the bot as an administrator to both source channels, `@nextv_itv` and `@mtv_1russia`, so Telegram can deliver new channel-post updates to it.
3. Open **Settings → Secrets and variables → Actions** in this repository and add a repository secret named `TELEGRAM_BOT_TOKEN` with the replacement token as its value.
4. Make sure the bot is not configured with a webhook: Telegram's `getUpdates` polling API does not work while a webhook is set. If a webhook is configured for this bot, remove it or use a dedicated bot for this importer.
5. Open **Actions → Telegram news sync** and choose **Run workflow** to import posts now. The workflow then checks every five minutes.
6. Publish with GitHub Pages from branch `main`, folder `/(root)`, if Pages is not already enabled.

## What it does

- Reads recent public posts from `https://t.me/s/nextv_itv` and `https://t.me/s/mtv_1russia` (up to five preview pages per channel per run, subject to Telegram's public preview availability).
- Polls Bot API updates when `TELEGRAM_BOT_TOKEN` is configured, so new channel posts can be added automatically.
- Merges and deduplicates posts into `news.json`; the static site fetches that file when it loads.
- Public channel previews expose only a limited recent history, not the complete archive. Telegram Bot API polling also cannot browse arbitrary historical posts.
- If public previews are unavailable, the importer logs the fetch error and continues. For dependable ongoing updates, configure the bot secret and channel admin permissions.

## Troubleshooting

- If Actions fails with a missing or invalid token, add/rotate the `TELEGRAM_BOT_TOKEN` secret and confirm the bot is an administrator in both channels.
- If the workflow succeeds but no cards appear, inspect the run log and open `news.json` in the repository. Confirm the channels are public and that their Telegram preview pages are accessible.
- If there are no new cards, publish a test post after the bot has access and inspect the workflow log.
- GitHub Pages is static. Never put the bot token in HTML/JavaScript; the token must remain in Actions secrets.
