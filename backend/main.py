import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

print("Loading .env from:", ENV_PATH)  # debug
load_dotenv(ENV_PATH)

print("TG_SESSION_NAME:", os.getenv("TG_SESSION_NAME"))  # debug
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.scraper import scrape_historical_messages
from core.orchestrator import KattalanOrchestrator
from data.fyers_provider import FyersDataProvider

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_orchestrator: KattalanOrchestrator = None
_TIMEFRAME_MAP = {"1_month": 1, "3_months": 3, "6_months": 6}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator
    provider = FyersDataProvider()
    _orchestrator = KattalanOrchestrator(provider)
    log.info("Kattalan Quant Engine ready.")
    yield
    log.info("Shutting down.")


app = FastAPI(title="Kattalan Quant Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.websocket("/api/ws/audit")
async def ws_audit(websocket: WebSocket):
    await websocket.accept()

    async def ws_send(data: str):
        await websocket.send_text(data)

    try:
        payload = await websocket.receive_json()
        channel_input: str = payload.get("channel_input", "").strip()
        timeframe_str: str = payload.get("timeframe", "1_month")
        timeframe_months: int = _TIMEFRAME_MAP.get(timeframe_str, 1)

        if not channel_input:
            await ws_send(json.dumps({"progress": 100, "status": "FATAL ERROR: No channel provided."}))
            return

        await ws_send(json.dumps({"progress": 5, "status": "Connecting to Telegram..."}))

        start_date = datetime.now(timezone.utc) - timedelta(days=30 * timeframe_months)
        raw_messages, resolved_id, resolved_name = await scrape_historical_messages(
            channel_input, start_date
        )

        if resolved_id is None:
            await ws_send(json.dumps({
                "progress": 100,
                "status": f"FATAL ERROR: Channel '{channel_input}' not found.",
            }))
            return

        await ws_send(json.dumps({"progress": 15, "status": f"Connected to {resolved_name}."}))

        await _orchestrator.audit_channel(
            channel_input=channel_input,
            timeframe_months=timeframe_months,
            raw_messages=raw_messages,
            resolved_id=resolved_id,
            resolved_name=resolved_name,
            ws_send=ws_send,
        )

    except WebSocketDisconnect:
        log.info("Client disconnected mid-audit — pipeline continues saving to DB.")
    except RuntimeError as e:
        # Telegram session expired etc.
        err = str(e)
        log.error("Runtime error: %s", err)
        try:
            await ws_send(json.dumps({"progress": 100, "status": f"FATAL ERROR: {err}"}))
        except Exception:
            pass
    except Exception as e:
        log.exception("Unhandled error in ws_audit")
        try:
            await ws_send(json.dumps({"progress": 100, "status": f"FATAL ERROR: {e}"}))
        except Exception:
            pass