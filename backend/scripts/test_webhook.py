import requests
import time

# This is the exact JSON shape Telegram sends to a webhook
mock_telegram_payload = {
    "message": {
        "message_id": 9999,
        "date": int(time.time()),
        "chat": {
            "id": "-1001234567890",
            "title": "Trade With Logic"
        },
        "text": "BUY BANKNIFTY 48000 CE ABOVE 400 SL 350 TGT 450 500"
    }
}

print("🔫 Firing mock Telegram payload at local server...")
try:
    # Target your local FastAPI webhook endpoint
    response = requests.post("http://127.0.0.1:8000/webhook/telegram", json=mock_telegram_payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except requests.exceptions.ConnectionError:
    print("❌ SERVER OFFLINE: You need to start your FastAPI server first.")