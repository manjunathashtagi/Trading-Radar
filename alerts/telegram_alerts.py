import requests
import os
import time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_alert(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    for attempt in range(3):

        try:

            r = requests.post(url, json=payload, timeout=30)

            if r.status_code == 200:
                return True

        except Exception as e:

            print(f"Telegram error: {e}")

            time.sleep(3)

    return False