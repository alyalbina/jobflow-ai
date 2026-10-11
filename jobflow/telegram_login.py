"""Owner-operated official Telethon account login. Credentials never enter source or logs."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient


async def main():
    load_dotenv()
    api_id = os.getenv("TELEGRAM_API_ID", "")
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    if not api_id.isdigit() or not api_hash:
        print("Create .env from .env.example and fill TELEGRAM_API_ID / TELEGRAM_API_HASH locally.")
        return
    data = Path(os.getenv("JOBFLOW_DATA_DIR", "private")).resolve()
    data.mkdir(parents=True, exist_ok=True)
    print("Stop JobFlow first. Enter your phone, login code and 2FA password only in this local console.")
    print("The official Telegram service authorizes your account. The session stays in private/.")
    async with TelegramClient(str(data / "telegram"), int(api_id), api_hash) as client:
        await client.get_me()
        print("Telegram authorized. Restart JobFlow and enable the channels you want to read.")


if __name__ == "__main__":
    asyncio.run(main())
