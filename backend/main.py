from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import logging
import os
import json
import asyncio
import pytz

from core.utils import is_potential_signal
from core.orchestrator import KattalanOrchestrator, build_fyers_symbol
from data.provider_fyers import FyersDataProvider
from core.scraper import scrape_historical_messages
from core.schemas import Signal # <-- Added for Hashmap Caching

# Set up logging for terminal visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Initialize the App and CORS exactly ONCE
app = FastAPI(title="Quant Live Engine")

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
    logger.info("Engine Successfully Initialized.")
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
        
        await websocket.send_json({"progress": 10, "status": "Checking database for existing trades..."})

        
        # --- THE O(1) HASHMAP CATCHER ---
        # 1. Fetch all existing signals for this channel from Supabase (Limit bumped to 10k to prevent pagination traps)
        db_records = await asyncio.to_thread(
            lambda: orchestrator.db.supabase.table('signals').select('*, evaluations(*)').eq('channel_id', channel_name).limit(10000).execute()
        )
        
        # 2. Build the hashmap: { "message_id": Signal_Object }
        existing_signals_map = {}
        if db_records.data:
            for row in db_records.data:
                try:
                    # 1. Safely extract evaluations (handling None, [], or [{}])
                    evals = row.pop("evaluations", None)
                    eval_data = None
                    if isinstance(evals, list) and len(evals) > 0:
                        eval_data = evals[0]
                    elif isinstance(evals, dict):
                        eval_data = evals
                        
                    # 2. Format the datetime safely
                    if isinstance(row.get('issued_at'), str):
                        row['issued_at'] = datetime.fromisoformat(row['issued_at'])
                        
                    # 3. Build the schema
                    existing_signals_map[str(row['message_id'])] = {
                        "signal": Signal(**row), 
                        "evaluation": eval_data
                    }
                except Exception as row_err:
                    # If ONE row is corrupted in the DB, skip it. Don't crash the whole audit.
                    print(f"⚠️ Skipping corrupted DB row {row.get('message_id')}: {row_err}")

        # --- THE NEGATIVE CACHE (Remember the Spam) ---
        safe_channel_name = channel_name.replace('@', '').replace(' ', '_')
        cache_file = f"{safe_channel_name}_processed_ids.json"
        try:
            with open(cache_file, "r") as f:
                processed_ids = set(json.load(f))
        except FileNotFoundError:
            processed_ids = set()

        # 3. Filter the messages
        messages_to_parse = []
        all_parsed_signals = []
        
        for m in raw_messages:
            msg_id_str = str(m["id"])
            
            # CACHE HIT: Valid Trade already in Supabase
            if msg_id_str in existing_signals_map:
                all_parsed_signals.append({
                    "signal": existing_signals_map[msg_id_str]["signal"],
                    "evaluation": existing_signals_map[msg_id_str]["evaluation"]
                })
                continue # Skip AI
                
            # CACHE HIT: Known Spam (Already looked at it before)
            if msg_id_str in processed_ids:
                continue # Skip AI
                
            # CACHE MISS: Brand new message, needs to go to AI
            messages_to_parse.append(m)

        # --- 1. THE BATCHING FIX (AI Spam Filtering) ---
        total_to_parse = len(messages_to_parse)
        
        if total_to_parse > 0:
            batch_size = 25
            await websocket.send_json({"progress": 20, "status": f"Found {total_to_parse} new messages. Sending to AI..."})
            
            for i in range(0, total_to_parse, batch_size):
                batch = messages_to_parse[i : i + batch_size]
                formatted_batch = [{"message_id": m["id"], "text": m["text"], "time": m["time"]} for m in batch]
                
                # Send 25 messages to the LLM simultaneously (WITH AUTO-RETRY)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        parsed_batch = await asyncio.to_thread(orchestrator.parser.parse_batch, formatted_batch, channel_name)
                        all_parsed_signals.extend(parsed_batch)
                        
                        # Update our negative cache with the IDs we just processed
                        for m in batch:
                            processed_ids.add(str(m["id"]))
                            
                        break # Break the retry loop on success!
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "503" in error_msg or "429" in error_msg or "UNAVAILABLE" in error_msg:
                            if attempt < max_retries - 1:
                                print(f"⚠️ API Busy (503/429). Retrying batch {(i//batch_size)+1} in 5 seconds (Attempt {attempt+1}/{max_retries})...")
                                await asyncio.sleep(5)
                            else:
                                print(f"❌ AI Batch {(i//batch_size)+1} permanently failed after {max_retries} attempts: {error_msg}")
                        else:
                            # If it's a code error (not a server error), fail immediately
                            print(f"❌ AI Batch {(i//batch_size)+1} Failed (Code Error): {error_msg}")
                            break
                    
                current_prog = 20 + int(((i + len(batch)) / total_to_parse) * 30)
                await websocket.send_json({"progress": current_prog, "status": f"AI bulk parsed batch {(i//batch_size)+1}..."})
                
                # Safe API delay between BATCHES
                await asyncio.sleep(4.1) 
                
            # Save the updated negative cache to the disk
            with open(cache_file, "w") as f:
                json.dump(list(processed_ids), f)
                
        else:
            await websocket.send_json({"progress": 50, "status": "All messages loaded from cache. AI skipped."})
            
        total_valid = len(all_parsed_signals)
        
        if total_valid == 0:
            await websocket.send_json({"progress": 100, "status": "No valid trades found.", "results": {
                "channel": channel_name, "total_trades": 0, "win_rate": "0%", "edge_ratio": 0, "color_grade": "red"
            }})
            return
            
        await websocket.send_json({"progress": 55, "status": f"Found {total_valid} real trades. Evaluating..."})
        
        # --- 2. EVALUATE TRADES (WITH INSTANT BYPASS) ---
        success_count = 0
        win_count = 0
        total_edge = 0.0
        
        for index, data in enumerate(all_parsed_signals):
            try:
                signal = data["signal"]

                # --- THE INSTANT BYPASS ---
                if data.get("evaluation"):
                    eval_data = data["evaluation"]
                    success_count += 1
                    
                    if eval_data.get("status") == "WIN":
                        total_edge += 1.5 
                        win_count += 1
                    elif eval_data.get("status") == "LOSS":
                        total_edge -= 1.0
                    elif eval_data.get("status") == "SQUARED_OFF":
                        if signal.direction == "BUY" and (eval_data.get("exit_executed_price") or 0) > eval_data.get("entry_executed_price", 0):
                            total_edge += 0.5
                            win_count += 1
                        elif signal.direction == "SELL" and (eval_data.get("exit_executed_price") or float('inf')) < eval_data.get("entry_executed_price", 0):
                            total_edge += 0.5
                            win_count += 1
                        else:
                            total_edge -= 0.5
                else:
                    # --- NEW TRADES FETCH FYERS DATA ---
                    dynamic_symbol = build_fyers_symbol(signal.underlying, signal.instrument_type)
                    end_time = signal.issued_at.replace(hour=15, minute=30, second=0)
                    
                    market_data = await asyncio.to_thread(orchestrator.provider.fetch_1m_data, dynamic_symbol, signal.issued_at, end_time)
                    
                    if market_data:
                        result = await asyncio.to_thread(orchestrator.engine.evaluate, signal, market_data)
                        
                        await asyncio.to_thread(orchestrator.db.upsert_signal, signal)
                        await asyncio.to_thread(orchestrator.db.upsert_evaluation, result)
                        
                        success_count += 1
                        
                        if result.status == "WIN":
                            total_edge += 1.5 
                            win_count += 1
                        elif result.status == "LOSS":
                            total_edge -= 1.0
                        elif result.status == "SQUARED_OFF":
                            if signal.direction == "BUY" and (result.exit_executed_price or 0) > result.entry_executed_price:
                                total_edge += 0.5
                                win_count += 1
                            elif signal.direction == "SELL" and (result.exit_executed_price or float('inf')) < result.entry_executed_price:
                                total_edge += 0.5
                                win_count += 1
                            else:
                                total_edge -= 0.5
                        
            except Exception as e:
                print(f"❌ Quant Eval Failed for {signal.message_id}: {str(e)}")
                
            status_text = "Loaded cached trade" if data.get("evaluation") else "Backtested new trade"
            await websocket.send_json({
                "progress": 55 + int(((index + 1) / total_valid) * 40),
                "status": f"{status_text} {index + 1}/{total_valid}..."
            })
            
        # --- 3. FINAL RESULTS ---
        await websocket.send_json({"progress": 95, "status": "Finalizing statistics..."})
        
        final_edge = round(total_edge / success_count, 2) if success_count > 0 else 0
        win_rate_val = round((win_count / success_count) * 100, 1) if success_count > 0 else 0
        color_grade = "green" if final_edge > 0 else "red"
        
        await websocket.send_json({
            "progress": 100, 
            "status": "Audit Complete! Saved to Supabase.",
            "results": {
                "channel": channel_name,
                "total_trades": success_count,
                "win_rate": f"{win_rate_val}%",
                "edge_ratio": final_edge,
                "color_grade": color_grade
            }
        })

    except WebSocketDisconnect:
        logger.info("Frontend disconnected.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await websocket.send_json({"progress": 0, "status": f"FATAL ERROR: {str(e)}"})

# --- HEALTH CHECK ---
@app.get("/health")
def health_check():
    status = "Online" if orchestrator else "Offline"
    return {"status": f"Engine is {status}."}