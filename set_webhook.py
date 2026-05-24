import json
import os
import urllib.parse
import urllib.request


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL")
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")


def call_telegram(method, params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


if not TOKEN:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN.")
if not PUBLIC_URL:
    raise SystemExit("Set PUBLIC_URL, for example: https://your-app.onrender.com")

params = {
    "url": f"{PUBLIC_URL.rstrip('/')}/webhook",
    "drop_pending_updates": "true",
}
if WEBHOOK_SECRET:
    params["secret_token"] = WEBHOOK_SECRET

result = call_telegram("setWebhook", params)
print(json.dumps(result, indent=2, ensure_ascii=False))
