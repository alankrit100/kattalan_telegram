import os
from datetime import datetime, timezone
from telethon import TelegramClient

API_ID = int(os.environ.get("TG_API_ID"))
API_HASH = os.environ.get("TG_API_HASH")

async def scrape_historical_messages(channel_name: str, start_date: datetime):
    """Connects to Telegram, finds the channel, and pulls messages since start_date."""
    
    client = TelegramClient('historical_session', API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("Historical Client not authorized. Run auth script for 'historical_session'.")

    raw_messages = []
    try:
        # 1. Robust Entity Finding (Your trick from run_pipeline)
        target_entity = None
        async for dialog in client.iter_dialogs(limit=150):
            if dialog.name == channel_name:
                target_entity = dialog.entity
                break
                
        if not target_entity:
            print(f"❌ Scraper could not find channel in dialogs: {channel_name}")
            return []

        # 2. Timezone alignment (Telethon uses UTC)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)

        # 3. Fetching the data backwards in time
        async for message in client.iter_messages(target_entity):
            if message.date < start_date:
                break # We've gone past the 1-month lookback, stop fetching!
                
            if message.text: # Only grab text
                raw_messages.append({
                    "text": message.text,
                    "time": message.date,
                    "id": str(message.id)
                })
                
        # 4. Reverse the list so the oldest messages are processed first (chronological order)
        raw_messages.reverse()
        
    except Exception as e:
        print(f"Scraping Error: {e}")
    finally:
        await client.disconnect()
        
    return raw_messages