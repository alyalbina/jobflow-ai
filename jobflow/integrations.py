"""Read-only Telegram transport and opt-in notification delivery."""

import asyncio
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from telethon import TelegramClient, errors, events

from .storage import now


class Monitor:
    def __init__(self, store, data_dir, client_factory=TelegramClient):
        self.store, self.data_dir, self.factory = store, Path(data_dir), client_factory
        self.client = None
        self.lock = asyncio.Lock()
        self.state = "Not connected"
        self.stopping = False

    async def connect(self):
        if self.client and self.client.is_connected():
            return True
        api_id = os.getenv("TELEGRAM_API_ID", "")
        api_hash = os.getenv("TELEGRAM_API_HASH", "")
        if not api_id.isdigit() or not api_hash or not (self.data_dir / "telegram.session").exists():
            self.state = "Run Connect-Telegram.cmd locally to authorize your account"
            return False
        self.client = self.factory(
            str(self.data_dir / "telegram"),
            int(api_id),
            api_hash,
            flood_sleep_threshold=60,
            auto_reconnect=True,
            sequential_updates=True,
        )
        await self.client.connect()
        if not await self.client.is_user_authorized():
            await self.client.disconnect()
            self.state = "Authorization required; run Connect-Telegram.cmd locally"
            return False
        self.client.add_event_handler(self.on_new, events.NewMessage())
        self.client.add_event_handler(self.on_edit, events.MessageEdited())
        self.client.add_event_handler(self.on_delete, events.MessageDeleted())
        self.state = "Connected · read-only monitoring"
        return True

    def event_source(self, chat_id):
        return next(
            iter(self.store.rows("SELECT * FROM sources WHERE channel_id=? AND enabled=1", (chat_id,))), None
        )

    async def on_new(self, event):
        source = self.event_source(event.chat_id)
        if source:
            self.persist(source, event.message, advance=False)

    async def on_edit(self, event):
        await self.on_new(event)

    async def on_delete(self, event):
        # Telegram does not always include a chat ID. Never delete by bare message ID.
        source = self.event_source(event.chat_id)
        if source:
            self.store.delete_messages(source["id"], event.deleted_ids)

    def persist(self, source, message, advance=True):
        text = message.raw_text or ""
        return self.store.ingest(
            source["id"],
            message.id,
            text,
            message.date.isoformat(),
            f"https://t.me/{source['username']}/{message.id}",
            advance=advance,
        )

    async def sync_source(self, source):
        if source.get("next_retry") and source["next_retry"] > now():
            return
        try:
            entity = await self.client.get_entity(source["username"])
            if not getattr(entity, "broadcast", False) and not getattr(entity, "megagroup", False):
                self.store.source_update(
                    source["id"], verified="not_channel", error="Source is not a channel/group"
                )
                return
            from telethon.utils import get_peer_id

            channel_id = get_peer_id(entity)
            self.store.source_update(
                source["id"], verified="accessible", channel_id=channel_id, error=None, next_retry=None
            )
            if not source["cursor"]:
                limit = int(self.store.get("preferences")["history_limit"])
                batch = await self.client.get_messages(entity, limit=limit)
                for message in sorted(batch, key=lambda m: m.id):
                    self.persist(source, message)
            else:
                # Oldest-first ensures a bounded poll never jumps over an uncommitted message.
                async for message in self.client.iter_messages(
                    entity, min_id=source["cursor"], reverse=True, limit=200, wait_time=1
                ):
                    self.persist(source, message)
            recent = self.store.rows(
                "SELECT message_id FROM messages WHERE source_id=? AND deleted=0 ORDER BY message_id DESC LIMIT 30",
                (source["id"],),
            )
            if recent:
                ids = [r["message_id"] for r in recent]
                refreshed = await self.client.get_messages(entity, ids=ids)
                if len(refreshed) == len(ids):
                    for mid, message in zip(ids, refreshed, strict=True):
                        if message is None:
                            self.store.delete_messages(source["id"], [mid])
                        else:
                            self.persist(source, message, advance=False)
            self.store.source_update(source["id"], last_sync=now())
        except errors.FloodWaitError as exc:
            until = (datetime.now(UTC) + timedelta(seconds=exc.seconds)).isoformat()
            self.store.source_update(
                source["id"],
                next_retry=until,
                error=f"Telegram rate limit; retry after {exc.seconds} seconds",
            )
        except (
            errors.ChannelPrivateError,
            errors.UsernameInvalidError,
            errors.UsernameNotOccupiedError,
            ValueError,
        ):
            self.store.source_update(
                source["id"], verified="unavailable", error="Unavailable or not accessible to this account"
            )
        except (TimeoutError, OSError, errors.RPCError):
            self.store.source_update(
                source["id"], error="Temporary Telegram/network error; next scheduled poll will retry"
            )

    async def sync(self):
        async with self.lock:
            try:
                if not await self.connect():
                    return {"state": self.state}
                for source in self.store.rows("SELECT * FROM sources WHERE enabled=1"):
                    await self.sync_source(source)
                return {"state": self.state}
            except (TimeoutError, OSError, errors.RPCError):
                self.state = "Temporary connection error; retry scheduled"
                return {"state": self.state}

    async def stop(self):
        self.stopping = True
        if self.client:
            await self.client.disconnect()

    async def loop(self):
        while not self.stopping:
            try:
                await self.sync()
                await notify(self.store)
            except Exception:
                self.state = "Background operation failed; next scheduled poll will retry"
            await asyncio.sleep(max(60, int(self.store.get("preferences")["poll_seconds"])))


async def notify(store, transport=None):
    prefs = store.get("preferences")
    if not prefs.get("notifications"):
        return {"state": "Disabled"}
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not re.fullmatch(r"-?\d+", chat or ""):
        return {"state": "Bot token and personal chat ID required locally"}
    for job in store.jobs():
        if (
            not job["unavailable"]
            and job["matching"]["action"] == "Apply"
            and job["matching"]["score"] >= prefs["minimum_score"]
        ):
            body = (
                f"JobFlow · {job['title']}\nScore {job['matching']['score']}/100 · preference score, not hiring probability\n"
                + "\n".join(job["matching"]["why"][:2])
                + "\n"
                + (job["original_url"] or "Original link unavailable")
            )
            store.enqueue(f"job:{job['id']}", "job", body[:4000])
    for app in store.rows("SELECT a.*,j.data FROM applications a JOIN jobs j ON j.id=a.job_id"):
        for kind in ("followup", "interview"):
            due = app[kind + "_at"]
            if due and due <= now() and app["status"] not in ("Rejected", "Withdrawn", "Offer"):
                import json

                store.enqueue(
                    f"{kind}:{app['id']}:{due}",
                    kind,
                    f"JobFlow {kind} reminder · {json.loads(app['data']).get('title')} · {due}",
                )
    last = store.get("last_notification")
    if (
        last
        and (datetime.now(UTC) - datetime.fromisoformat(last)).total_seconds() < prefs["notification_seconds"]
    ):
        return {"state": "Frequency limit"}
    candidates = store.rows("SELECT * FROM outbox WHERE status='queued' ORDER BY id LIMIT 5")
    queued = []
    for candidate in candidates:
        if sum(len(r["body"]) + 2 for r in queued) + len(candidate["body"]) <= 4000:
            queued.append(candidate)
        else:
            break
    if not queued:
        return {"state": "Nothing due"}
    # Persist intent before delivery. Ambiguous timeouts are not auto-retried to avoid spam.
    with store.connect() as db:
        db.executemany("UPDATE outbox SET status='sending' WHERE id=?", [(r["id"],) for r in queued])
    try:
        async with httpx.AsyncClient(timeout=20, transport=transport) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat,
                    "text": "\n\n".join(r["body"] for r in queued),
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            if not response.json().get("ok"):
                raise ValueError("Bot delivery rejected")
        state = "sent"
        store.set("last_notification", now())
    except (httpx.HTTPError, ValueError):
        state = "delivery_unknown"
    with store.connect() as db:
        db.executemany(
            "UPDATE outbox SET status=?,sent_at=?,error=? WHERE id=?",
            [
                (
                    state,
                    now() if state == "sent" else None,
                    None if state == "sent" else "Delivery not confirmed; inspect bot before manual retry",
                    r["id"],
                )
                for r in queued
            ],
        )
    return {"state": state, "items": len(queued)}
