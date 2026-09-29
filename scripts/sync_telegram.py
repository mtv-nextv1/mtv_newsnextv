import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = "https://api.telegram.org/bot" + TOKEN + "/"
ALLOWED = {"nextv_itv", "mtv_1russia"}
CURSOR = Path("telegram-cursor.json")
FEED = Path("news.json")

def telegram(method, params):
    body = urllib.parse.urlencode(params).encode()
    request = urllib.request.Request(API + method, data=body)
    with urllib.request.urlopen(request, timeout=25) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram API request failed: " + method)
    return result["result"]

cursor = json.loads(CURSOR.read_text()) if CURSOR.exists() else {"offset": 0, "seen": []}
seen = set(cursor.get("seen", []))
items = json.loads(FEED.read_text()) if FEED.exists() else []
updates = telegram("getUpdates", {
    "offset": int(cursor.get("offset", 0)),
    "timeout": 0,
    "allowed_updates": json.dumps(["channel_post"])
})
offset = int(cursor.get("offset", 0))
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
    key = str(chat.get("id")) + ":" + str(message_id)
    if key in seen:
        continue
    text = (post.get("text") or post.get("caption") or "").strip()
    if not text:
        continue
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items.insert(0, {
        "id": key,
        "category": "TELEGRAM · " + username.upper(),
        "date": "TELEGRAM",
        "title": lines[0][:180],
        "body": (" ".join(lines[1:]) if len(lines) > 1 else text)[:700],
        "art": "TG",
        "color": "blue",
        "url": "https://t.me/" + username + "/" + str(message_id),
        "source": username
    })
    seen.add(key)
FEED.write_text(json.dumps(items[:100], ensure_ascii=False, indent=2) + "\n")
CURSOR.write_text(json.dumps({"offset": offset, "seen": list(seen)[-500:]}, ensure_ascii=False, indent=2) + "\n")
print("Processed", len(updates), "Telegram updates; feed has", min(len(items), 100), "posts.")
