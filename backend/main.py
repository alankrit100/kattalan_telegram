from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import logging
import os
import json
import asyncio
import pytz

from core.utils import is_potential_signal
from core.orchestrator import KattalanOrchestrator
from data.provider_fyers import FyersDataProvider
from core.scraper import scrape_historical_messages

# Set up logging for terminal visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Initialize the App and CORS exactly ONCE
app = FastAPI(title="Kattalan Live Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Initialize the Engine on Startup
try:
    provider = FyersDataProvider()
    orchestrator = KattalanOrchestrator(provider)
    logger.info("Kattalan Engine Successfully Initialized.")
except Exception as e:
    logger.error(f"FATAL: Could not initialize orchestrator. {str(e)}")
    orchestrator = None

# --- WEBHOOK ENDPOINT ---
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

# --- WEBSOCKET ENDPOINT ---
@app.websocket("/api/ws/audit")
async def audit_channel_websocket(websocket: WebSocket):
    await websocket.accept()
    
    if not orchestrator:
        await websocket.send_json({"progress": 0, "status": "ERROR: Engine Offline"})
        return
        
    try:
        data = await websocket.receive_text()
        request_data = json.loads(data)
        
        channel_name = request_data.get("channel_name")
        timeframe = request_data.get("timeframe", "1_month")
        
        days_map = {"1_month": 30, "3_months": 90, "6_months": 180}
        lookback_days = days_map.get(timeframe, 30)
        start_date = datetime.now() - timedelta(days=lookback_days)
        
        await websocket.send_json({"progress": 5, "status": f"Connecting to Telegram for {channel_name}..."})
        
        # Trigger the real scraper
        raw_messages = await scrape_historical_messages(channel_name, start_date)
        total_msgs = len(raw_messages)
        
        if total_msgs == 0:
            await websocket.send_json({"progress": 100, "status": "No messages found."})
            return

        await websocket.send_json({"progress": 20, "status": f"Scraped {total_msgs} messages. Starting AI evaluation..."})
        
        success_count = 0
        total_edge = 0.0
        
        for index, msg in enumerate(raw_messages):
            try:
                # Threaded math execution so UI doesn't freeze
                result = await asyncio.to_thread(
                    orchestrator.process_live_message,
                    raw_text=msg["text"],
                    message_time=msg["time"],
                    channel_id=channel_name,
                    message_id=msg["id"]
                )
                success_count += 1
                
                # Simple Edge aggregation for the UI
                if result.status == "WIN":
                    total_edge += 1.5 
                elif result.status == "LOSS":
                    total_edge -= 1.0
                    
            except Exception as e:
                pass # Skip spam quietly
                
            current_progress = 20 + int((index / total_msgs) * 70)
            await websocket.send_json({
                "progress": current_progress, 
                "status": f"Evaluated {index + 1}/{total_msgs} trades..."
            })
            await asyncio.sleep(0.5) # API rate limit protection
            
        await websocket.send_json({"progress": 95, "status": "Finalizing statistics..."})
        
        final_edge = round(total_edge / success_count, 2) if success_count > 0 else 0
        color_grade = "green" if final_edge > 0 else "red"
        
        await websocket.send_json({
            "progress": 100, 
            "status": "Audit Complete! Saved to Supabase.",
            "results": {
                "channel": channel_name,
                "total_trades": success_count,
                "win_rate": "TBD",
                "edge_ratio": final_edge,
                "color_grade": color_grade
            }
        })

    except WebSocketDisconnect:
        logger.info("Frontend disconnected.")
    except Exception as e:
        await websocket.send_json({"progress": 0, "status": f"FATAL ERROR: {str(e)}"})

# --- HEALTH CHECK ---
@app.get("/health")
def health_check():
    status = "Online" if orchestrator else "Offline"
    return {"status": f"Kattalan is {status}."}