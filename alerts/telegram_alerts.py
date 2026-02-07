import os
import requests

BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send_alert(msg):
    if not BOT or not CHAT:
        return
    requests.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        data={"chat_id": CHAT, "text": msg, "parse_mode": "HTML"},
        timeout=10
    )
