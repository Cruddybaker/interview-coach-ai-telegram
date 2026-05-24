import json
import os
import urllib.parse
import urllib.request


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


if not TOKEN:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN.")

data = urllib.parse.urlencode({"drop_pending_updates": "true"}).encode()
with urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook", data=data, timeout=30) as response:
    print(json.dumps(json.loads(response.read().decode("utf-8")), indent=2, ensure_ascii=False))
