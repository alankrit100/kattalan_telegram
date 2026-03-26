from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import logging
import os
from core.utils import is_potential_signal

from core.orchestrator import KattalanOrchestrator
from data.provider_fyers import FyersDataProvider

from fastapi import FastAPI, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
import json
import asyncio


app = FastAPI(title="Kattalan Live Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Set up logging for terminal visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kattalan Live Engine")

# 1. Initialize the Engine on Startup
try:
        provider = FyersDataProvider()
        orchestrator = KattalanOrchestrator(provider)
        logger.info("Kattalan Engine Successfully Initialized.")
except Exception as e:
        logger.error(f"FATAL: Could not initialize orchestrator. {str(e)}")
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
    
@app.websocket("/api/ws/audit")
async def audit_channel_websocket(websocket: WebSocket):
    """
    This is the live pipeline for your Admin Dashboard.
    It streams progress percentages back to the frontend in real-time.
    """
    await websocket.accept()
    try:
        # 1. Wait for the frontend to send the search query
        data = await websocket.receive_text()
        request_data = json.loads(data)
        
        channel_name = request_data.get("channel_name")
        timeframe = request_data.get("timeframe", "1_month")
        
        # 2. Start the Scrape (Simulated progress for now to test the UI connection)
        await websocket.send_json({"progress": 10, "status": f"Connecting to Telegram for {channel_name}..."})
        await asyncio.sleep(2) # We will replace this with your actual Telethon script later
        
        await websocket.send_json({"progress": 30, "status": "Scraped 850 messages. Firing up Gemini AI..."})
        
        # 3. The AI Parsing Loop (Streaming the loading bar)
        for i in range(1, 6):
            await asyncio.sleep(1) # Simulating the AI batch processing time
            await websocket.send_json({
                "progress": 30 + (i * 10), 
                "status": f"AI Parsing Batch {i}/5..."
            })
            
        # 4. The Math Engine
        await websocket.send_json({"progress": 90, "status": "Fetching Fyers Charts & Running Quant Math..."})
        await asyncio.sleep(2)
        
        # 5. Final Result Delivery
        await websocket.send_json({
            "progress": 100, 
            "status": "Audit Complete! Saving to Supabase.",
            "results": {
                "channel": channel_name,
                "total_trades": 142,
                "win_rate": "68%",
                "edge_ratio": 1.85,
                "color_grade": "green" # Your UI will use this to change colors
            }
        })

    except WebSocketDisconnect:
        print("Frontend disconnected from the audit stream.")
    except Exception as e:
        await websocket.send_json({"progress": 0, "status": f"ERROR: {str(e)}"})
    
@app.get("/health")
def health_check():
    """Verify the server is running."""
    status = "Online" if orchestrator else "Offline (Missing CSV)"
    return {"status": f"Kattalan is {status}."}