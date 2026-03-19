from fastapi import FastAPI, Request, HTTPException
from datetime import datetime
import logging
import os

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
async def telegram_webhook(payload: dict): # <-- Changed this line to expect a JSON dictionary
    """
    The endpoint Telegram hits when a channel posts a message.
    """
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Engine offline. Data provider missing.")

    try:
        # Since we used `payload: dict`, FastAPI automatically parses the JSON for us!
        
        # Extract message block (channels use 'channel_post', groups/bots use 'message')
        message_block = payload.get("message") or payload.get("channel_post")
        
        if not message_block or "text" not in message_block:
            return {"status": "ignored", "reason": "Not a text message"}

        raw_text = message_block["text"]
        
        # Telegram sends time as a UNIX timestamp
        unix_time = message_block["date"]
        message_time = datetime.fromtimestamp(unix_time)

        logger.info(f"Incoming Signal at {message_time}: {raw_text[:30]}...")

        # Run the Kattalan Pipeline
        result = orchestrator.process_live_message(
            raw_text=raw_text,
            message_time=message_time,
            symbol="BANKNIFTY"
        )
        
        logger.info(f"Signal Processed: {result.status} | Exit: {result.exit_executed_price}")
        
        return {"status": "success", "evaluation": result.model_dump()}

    except Exception as e:
        logger.error(f"Processing Error: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.get("/health")
def health_check():
    """Verify the server is running."""
    status = "Online" if orchestrator else "Offline (Missing CSV)"
    return {"status": f"Kattalan is {status}."}