import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError

log = logging.getLogger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))


def _make_client() -> TelegramClient:
    session = os.environ["TG_SESSION_NAME"]
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    return TelegramClient(session, api_id, api_hash)


async def scrape_historical_messages(channel_input: str, start_date: datetime):
    """
    Returns (messages, resolved_channel_id, resolved_channel_name).
    Each message dict: {message_id, text, time}.
    """
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)

    async with _make_client() as client:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram session expired. Run scripts/telegram_auth.py."
            )

        target_entity = None
        resolved_id = None
        resolved_name = None
        clean = str(channel_input).strip()

        # Fast path: direct resolution
        try:
            target_entity = await client.get_entity(clean)
            resolved_id = str(target_entity.id)
            resolved_name = getattr(target_entity, "title", clean)
            log.info("Fast-path resolved: %s (%s)", resolved_name, resolved_id)
        except ChannelPrivateError:
            raise
        except Exception as e:
            log.warning("Direct entity fetch failed (%s). Falling back to dialogs.", e)
            no_at = clean.lstrip("@")
            async for dialog in client.iter_dialogs(limit=50):
                has_un = hasattr(dialog.entity, "username") and dialog.entity.username
                if (
                    str(dialog.id) == no_at
                    or dialog.name.strip() == clean.strip()
                    or (has_un and dialog.entity.username.lower() == no_at.lower())
                ):
                    target_entity = dialog.entity
                    resolved_id = str(dialog.id)
                    resolved_name = dialog.name
                    break

        if not target_entity:
            log.error("Could not resolve channel: %s", channel_input)
            return [], None, None

        raw_messages = []
        attempt = 0
        while attempt < 2:
            try:
                async for message in client.iter_messages(target_entity):
                    if message.date < start_date:
                        break
                    if message.text:
                        raw_messages.append({
                            "message_id": str(message.id),
                            "text": message.text,
                            "time": message.date.astimezone(_IST),
                        })
                break
            except FloodWaitError as e:
                wait = e.seconds + 5
                log.warning("FloodWait: sleeping %ds", wait)
                await asyncio.sleep(wait)
                attempt += 1
                if attempt >= 2:
                    raise

        raw_messages.reverse()
        return raw_messages, resolved_id, resolved_name