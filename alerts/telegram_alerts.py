import os
import requests


def send_alert(message: str):
    """
    Send a Telegram message using Bot API
    """

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠️ Telegram credentials not set")
        print(message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print("❌ Telegram send failed:", r.text)
    except Exception as e:
        print("❌ Telegram error:", e)
