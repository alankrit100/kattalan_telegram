from fastapi import FastAPI, Request, HTTPException
from datetime import datetime
import logging
import os
from core.utils import is_potential_signal

from core.orchestrator import KattalanOrchestrator
from data.provider_csv import CSVMarketDataProvider

# Set up logging for terminal visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kattalan Live Engine")

# 1. Initialize the Engine on Startup
csv_path = "data/live_data.csv"
if os.path.exists(csv_path):
    try:
        provider = CSVMarketDataProvider(csv_path)
        orchestrator = KattalanOrchestrator(provider)
        logger.info("Kattalan Engine Successfully Initialized.")
    except Exception as e:
        logger.error(f"FATAL: Could not initialize orchestrator. {str(e)}")
        orchestrator = None
else:
    logger.warning(f"WARNING: {csv_path} not found. Engine is offline. Drop a CSV to enable.")
    orchestrator = None

@app.post("/webhook/telegram")
async def telegram_webhook(payload: dict):
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Engine offline.")

    try:
        message_block = (
            payload.get("message") or
            payload.get("channel_post") or
            payload.get("edited_message") or
            payload.get("edited_channel_post")
        )

        if not message_block or "text" not in message_block:
            return {"status": "ignored", "reason": "Not a text message"}

        raw_text = message_block["text"]

        if not is_potential_signal(raw_text):
            return {"status": "ignored", "reason": "Not a trading signal"}

        import pytz
        ist = pytz.timezone("Asia/Kolkata")

        unix_time = message_block["date"]
        message_time = datetime.fromtimestamp(unix_time, tz=ist)

        message_id = str(message_block.get("message_id"))
        channel_id = str(message_block.get("chat", {}).get("id"))

        is_edited = "edit_date" in message_block

        logger.info(f"[{channel_id}] {message_time} | {raw_text[:30]}...")

        result = orchestrator.process_live_message(
            raw_text=raw_text,
            message_time=message_time,
            symbol="BANKNIFTY",
            channel_id=channel_id,
            message_id=message_id
        )

        return {
            "status": "success",
            "edited": is_edited,
            "evaluation": result.model_dump()
        }

    except Exception as e:
        logger.exception("Processing Error")
        return {"status": "error", "message": str(e)}
    
@app.get("/health")
def health_check():
    """Verify the server is running."""
    status = "Online" if orchestrator else "Offline (Missing CSV)"
    return {"status": f"Kattalan is {status}."}