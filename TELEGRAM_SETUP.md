# Telegram news importer
This importer accepts channel_post updates delivered to the bot and writes them to news.json.
Required GitHub Actions secret: TELEGRAM_BOT_TOKEN (never commit the token itself).
Important: add the bot as an administrator to each source channel and configure Telegram updates/webhook so channel_post updates reach the bot. Telegram bots cannot read arbitrary channel history.
