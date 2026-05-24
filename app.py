import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bot import BOT_VERSION, OPENAI_API_KEY, handle_message, load_question_bank


PORT = int(os.environ.get("PORT", "10000"))
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")


class TelegramWebhookHandler(BaseHTTPRequestHandler):
    server_version = "InterviewCoachAI/0.1"

    def do_GET(self):
        if self.path in {"/", "/health"}:
            self.send_json(
                {
                    "ok": True,
                    "service": "interview-coach-ai-telegram",
                    "version": BOT_VERSION,
                    "openai_enabled": bool(OPENAI_API_KEY),
                    "question_bank_items": len(load_question_bank()),
                }
            )
            return
        self.send_error(404, "Not found")

    def do_POST(self):
        if self.path != "/webhook":
            self.send_error(404, "Not found")
            return

        if WEBHOOK_SECRET:
            incoming_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if incoming_secret != WEBHOOK_SECRET:
                self.send_error(403, "Bad webhook secret")
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = self.rfile.read(length)
            update = json.loads(payload.decode("utf-8"))
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            text = message.get("text")
            if chat.get("id") and text:
                handle_message(chat["id"], text)
            self.send_json({"ok": True})
        except Exception as exc:
            print(f"Webhook error: {exc}")
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


def main():
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        raise SystemExit("Set TELEGRAM_BOT_TOKEN before starting the web app.")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), TelegramWebhookHandler)
    print(f"Interview Coach AI webhook server is running on port {PORT}.")
    server.serve_forever()


if __name__ == "__main__":
    main()
