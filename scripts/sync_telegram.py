import html
import json
import re
import urllib.request
from pathlib import Path

# Import public Telegram channel previews only; no bot or API token is required.
ALLOWED = {"nextv_itv", "mtv_1russia"}
CURSOR = Path("telegram-cursor.json")
FEED = Path("news.json")
MAX_HISTORY_PAGES = 12
USER_AGENT = "Mozilla/5.0 (compatible; MTVNewsSync/1.0)"


def plain_text(fragment):
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"(?i)</(p|div|li)>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(fragment)).strip()


def fetch_history(username, before=None, max_pages=MAX_HISTORY_PAGES):
    posts = []
    oldest_found = None
    visited = set()
    for _ in range(max_pages):
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
            match = re.search(r'data-post="' + re.escape(username) + r'/(\d+)"', block)
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
        oldest_found = oldest
        if before == oldest or oldest <= 1:
            break
        before = oldest
    return posts, oldest_found


cursor = json.loads(CURSOR.read_text()) if CURSOR.exists() else {"offset": 0, "seen": []}
seen = set(cursor.get("seen", []))
items = json.loads(FEED.read_text()) if FEED.exists() else []
if not isinstance(items, list):
    items = []

# Fetch recent posts and progressively backfill older public history. The cursor advances on each run.
history_count = 0
history_before = cursor.get("history_before", {})
for username in sorted(ALLOWED):
    recent_posts, recent_oldest = fetch_history(username, max_pages=2)
    for post in recent_posts:
        if not any((old.get("id") == post["id"] or old.get("url") == post["url"]) for old in items):
            items.append(post)
            history_count += 1
        seen.add(post["id"])

    if username not in history_before and recent_oldest is not None:
        history_before[username] = recent_oldest
    older_posts, older_oldest = fetch_history(username, before=history_before.get(username), max_pages=MAX_HISTORY_PAGES)
    for post in older_posts:
        if not any((old.get("id") == post["id"] or old.get("url") == post["url"]) for old in items):
            items.append(post)
            history_count += 1
        seen.add(post["id"])
    if older_oldest is not None:
        history_before[username] = older_oldest

# Public channel previews are the only source; no bot token is used.
updates = []
offset = 0

# Deduplicate by stable id/url and keep newest items first.
unique = []
keys = set()
for item in sorted(items, key=lambda item: str(item.get("date", "")), reverse=True):
    key = item.get("id") or item.get("url") or item.get("title")
    if not key or key in keys:
        continue
    keys.add(key)
    unique.append(item)
FEED.write_text(json.dumps(unique[:100], ensure_ascii=False, indent=2) + "\n")
CURSOR.write_text(json.dumps({"offset": offset, "seen": list(seen)[-500:], "history_before": history_before}, ensure_ascii=False, indent=2) + "\n")
print("Imported", history_count, "new public-history posts; feed has", min(len(unique), 100), "posts.")
