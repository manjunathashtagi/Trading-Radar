import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from alerts.telegram_alerts import send_alert
send_alert("✅ Telegram test successful – Alpha system online")
