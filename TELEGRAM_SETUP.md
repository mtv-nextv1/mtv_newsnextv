# Telegram news sync setup

The repository now contains a scheduled importer and a website feed reader.

## Required setup

1. **Rotate the token that was pasted into chat.** Use [@BotFather](https://t.me/BotFather) to revoke it and issue a replacement. Do not commit any token to the repository.
2. Add the bot as an administrator to both source channels, `@nextv_itv` and `@mtv_1russia`, so Telegram can deliver channel-post updates to it.
3. Open **Settings → Secrets and variables → Actions** in this repository and add a repository secret named `TELEGRAM_BOT_TOKEN` with the replacement token as its value.
4. Make sure the bot is not configured with a webhook: Telegram's `getUpdates` polling API does not work while a webhook is set. If a webhook was configured previously, remove it before testing polling.
5. In **Actions → Telegram news sync**, choose **Run workflow** for the first test. The workflow then checks every five minutes.
6. Publish with GitHub Pages from branch `main`, folder `/(root)`, if Pages is not already enabled.

## What it does

The importer accepts new channel-post updates from the two allowlisted channels, writes cards to `news.json`, and commits the feed. The static site fetches that file when it loads. Only new updates delivered after the bot has access can be imported; the Bot API does not provide arbitrary historical channel browsing.

## Troubleshooting

- If Actions fails with a missing secret, add `TELEGRAM_BOT_TOKEN` in repository Actions secrets.
- If there are no new cards, confirm the bot is an administrator in each channel, publish a new test post, and inspect the workflow log.
- If the bot uses a webhook for another integration, do not switch it to polling without planning that change; use a dedicated bot or webhook-based backend instead.
- The site and its demo admin panel are static. Do not put credentials or bot tokens in HTML or JavaScript.
