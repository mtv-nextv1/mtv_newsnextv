import html
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

# Public Telegram previews only: no bot, token, account, or external service.
CHANNELS = ("nextv_itv", "mtv_1russia")
CURSOR = Path("telegram-cursor.json")
FEED = Path("news.json")
PAGES_PER_CHANNEL_PER_RUN = 8
MAX_FEED_ITEMS = 300
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def plain_text(fragment):
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"(?i)</(p|div|li)>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(fragment)).strip()


def fetch_page(username, before=None):
    url = "https://t.me/s/" + username
    if before:
        url += "?before=" + str(before)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", "replace")


def parse_posts(page, username):
    # Telegram's preview HTML wraps each message in a tgme_widget_message_wrap.
    starts = list(re.finditer(r'<div\b[^>]*class="[^"]*tgme_widget_message_wrap[^"]*"[^>]*>', page))
    posts = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(page)
        block = page[start.start():end]
        match = re.search(r'data-post="' + re.escape(username) + r'/(\d+)"', block)
        if not match:
            continue
        message_id = int(match.group(1))
        text_match = re.search(
            r'<div\b[^>]*class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            block,
            flags=re.S,
        )
        text = plain_text(text_match.group(1)) if text_match else ""
        # Media-only Telegram posts still get a usable card and direct link.
        if not text:
            text = "Публикация с фото или видео в Telegram — открыть оригинал."
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        time_match = re.search(r'<time\b[^>]*datetime="([^"]+)"', block)
        date = time_match.group(1)[:10] if time_match else "TELEGRAM"
        posts.append({
            "id": f"{username}:{message_id}",
            "category": "TELEGRAM · " + username.upper(),
            "date": date,
            "title": lines[0][:180],
            "body": (" ".join(lines[1:]) if len(lines) > 1 else text)[:900],
            "art": "TG",
            "color": "blue",
            "url": f"https://t.me/{username}/{message_id}",
            "source": username,
        })
    return posts


def fetch_history(username, before=None, max_pages=PAGES_PER_CHANNEL_PER_RUN):
    collected = []
    cursor = before
    for _ in range(max_pages):
        try:
            page = fetch_page(username, cursor)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"[{username}] preview request failed: {type(exc).__name__}")
            break
        posts = parse_posts(page, username)
        if not posts:
            if not collected:
                print(f"[{username}] Telegram returned no public preview posts.")
            break
        collected.extend(posts)
        oldest = min(int(post["id"].rsplit(":", 1)[1]) for post in posts)
        if oldest <= 1 or oldest == cursor:
            break
        cursor = oldest
    oldest_found = min(
        (int(post["id"].rsplit(":", 1)[1]) for post in collected),
        default=None,
    )
    return collected, oldest_found


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


cursor_data = load_json(CURSOR, {})
if not isinstance(cursor_data, dict):
    cursor_data = {}
history_before = cursor_data.get("history_before", {})
if not isinstance(history_before, dict):
    history_before = {}
items = load_json(FEED, [])
if not isinstance(items, list):
    items = []

# Each scheduled run refreshes the newest posts and walks backwards through
# public history. Older posts are imported progressively, without any bot.
new_count = 0
for channel in CHANNELS:
    recent, _ = fetch_history(channel, max_pages=2)
    older, oldest_id = fetch_history(
        channel,
        before=history_before.get(channel),
        max_pages=PAGES_PER_CHANNEL_PER_RUN,
    )
    existing_keys = {
        str(post.get("id") or post.get("url"))
        for post in items
        if isinstance(post, dict)
    }
    for post in recent + older:
        key = str(post.get("id") or post.get("url"))
        if key and key not in existing_keys:
            items.append(post)
            existing_keys.add(key)
            new_count += 1
    if oldest_id is not None:
        history_before[channel] = oldest_id

# Deduplicate and sort by date then message id, newest first.
unique = []
seen = set()
for post in items:
    if not isinstance(post, dict):
        continue
    key = str(post.get("id") or post.get("url") or post.get("title") or "")
    if not key or key in seen:
        continue
    seen.add(key)
    unique.append(post)
unique.sort(
    key=lambda post: (
        str(post.get("date", "")),
        int(str(post.get("id", "")).rsplit(":", 1)[-1])
        if str(post.get("id", "")).rsplit(":", 1)[-1].isdigit()
        else 0,
    ),
    reverse=True,
)
FEED.write_text(
    json.dumps(unique[:MAX_FEED_ITEMS], ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
CURSOR.write_text(
    json.dumps({"history_before": history_before}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(
    f"Public Telegram sync complete: {new_count} new posts; "
    f"{min(len(unique), MAX_FEED_ITEMS)} posts in feed; "
    f"channels: {', '.join(CHANNELS)}. No bot token used."
)
