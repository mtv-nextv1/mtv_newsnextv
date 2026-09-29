import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

# Public channel previews provide recent history; Bot API polling adds new posts.
ALLOWED = {"nextv_itv", "mtv_1russia"}
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
API = "https://api.telegram.org/bot" + TOKEN + "/"
CURSOR = Path("telegram-cursor.json")
FEED = Path("news.json")
MAX_HISTORY_PAGES = 5
USER_AGENT = "Mozilla/5.0 (compatible; MTVNewsSync/1.0)"


def telegram(method, params):
    body = urllib.parse.urlencode(params).encode()
    request = urllib.request.Request(API + method, data=body)
    with urllib.request.urlopen(request, timeout=25) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram API request failed: " + method)
    return result["result"]


def plain_text(fragment):
    fragment = re.sub(r"(?i)<br\\s*/?>", "\\n", fragment)
    fragment = re.sub(r"(?i)</(p|div|li)>", "\\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return re.sub(r"\\n{3,}", "\\n\\n", html.unescape(fragment)).strip()


def fetch_history(username):
    posts = []
    before = None
    visited = set()
    for _ in range(MAX_HISTORY_PAGES):
        url = "https://t.me/s/" + username
        if before:
            url += "?before=" + str(before)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                page = response.read().decode("utf-8", "replace")
        except Exception as exc:
            print("History fetch failed for", username, ":", type(exc).__name__)
            break

        blocks = re.findall(
            r'<div class="tgme_widget_message_wrap[^"]*"[^>]*>.*?(?=<div class="tgme_widget_message_wrap|<div class="tgme_channel_info|$)',
            page,
            flags=re.S,
        )
        if not blocks:
            # Telegram occasionally adds attributes before the class.
            blocks = re.findall(
                r'<div[^>]*class="[^"]*tgme_widget_message_wrap[^"]*"[^>]*>.*?(?=<div[^>]*class="[^"]*tgme_widget_message_wrap|<div[^>]*class="[^"]*tgme_channel_info|$)',
                page,
                flags=re.S,
            )
        if not blocks:
            break

        page_ids = []
        for block in blocks:
            match = re.search(r'data-post="' + re.escape(username) + r'/(\\d+)"', block)
            if not match:
                continue
            message_id = int(match.group(1))
            page_ids.append(message_id)
            key = username + ":" + str(message_id)
            if key in visited:
                continue
            visited.add(key)
            text_match = re.search(
                r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                block,
                flags=re.S,
            )
            text = plain_text(text_match.group(1)) if text_match else ""
            if not text:
                text = "Публикация в Telegram — откройте пост по ссылке."
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            time_match = re.search(r'<time[^>]*datetime="([^"]+)"', block)
            date = time_match.group(1)[:10] if time_match else "TELEGRAM"
            posts.append({
                "id": key,
                "category": "TELEGRAM · " + username.upper(),
                "date": date,
                "title": lines[0][:180],
                "body": (" ".join(lines[1:]) if len(lines) > 1 else text)[:700],
                "art": "TG",
                "color": "blue",
                "url": "https://t.me/" + username + "/" + str(message_id),
                "source": username,
            })
        if not page_ids:
            break
        oldest = min(page_ids)
        if before == oldest or oldest <= 1:
            break
        before = oldest
    return posts


cursor = json.loads(CURSOR.read_text()) if CURSOR.exists() else {"offset": 0, "seen": []}
seen = set(cursor.get("seen", []))
items = json.loads(FEED.read_text()) if FEED.exists() else []
if not isinstance(items, list):
    items = []

# Merge recent public history on every run, so existing channels populate the site.
history_count = 0
for username in sorted(ALLOWED):
    for post in fetch_history(username):
        if not any((old.get("id") == post["id"] or old.get("url") == post["url"]) for old in items):
            items.append(post)
            history_count += 1
        seen.add(post["id"])

# Bot API is optional for historical import; configure a secret to receive new posts.
updates = []
offset = int(cursor.get("offset", 0))
if TOKEN:
    try:
        updates = telegram("getUpdates", {
            "offset": offset,
            "timeout": 0,
            "allowed_updates": json.dumps(["channel_post"]),
        })
        for update in updates:
            offset = max(offset, int(update["update_id"]) + 1)
            post = update.get("channel_post")
            if not post:
                continue
            chat = post.get("chat", {})
            username = (chat.get("username") or "").lower()
            if username not in ALLOWED:
                continue
            message_id = post.get("message_id")
            key = username + ":" + str(message_id)
            if key in seen:
                continue
            text = (post.get("text") or post.get("caption") or "").strip()
            if not text:
                text = "Публикация в Telegram — откройте пост по ссылке."
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            items.append({
                "id": key,
                "category": "TELEGRAM · " + username.upper(),
                "date": post.get("date", ""),
                "title": lines[0][:180],
                "body": (" ".join(lines[1:]) if len(lines) > 1 else text)[:700],
                "art": "TG",
                "color": "blue",
                "url": "https://t.me/" + username + "/" + str(message_id),
                "source": username,
            })
            seen.add(key)
    except Exception as exc:
        print("Bot API polling failed; public history was still collected:", type(exc).__name__)
else:
    print("TELEGRAM_BOT_TOKEN is not set; imported public channel history only.")

# Deduplicate by stable id/url and keep newest items first.
unique = []
keys = set()
for item in sorted(items, key=lambda item: str(item.get("date", "")), reverse=True):
    key = item.get("id") or item.get("url") or item.get("title")
    if not key or key in keys:
        continue
    keys.add(key)
    unique.append(item)
FEED.write_text(json.dumps(unique[:100], ensure_ascii=False, indent=2) + "\\n")
CURSOR.write_text(json.dumps({"offset": offset, "seen": list(seen)[-500:]}, ensure_ascii=False, indent=2) + "\\n")
print("Imported", history_count, "historical posts; processed", len(updates), "updates; feed has", min(len(unique), 100), "posts.")
