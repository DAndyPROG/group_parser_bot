from telethon import TelegramClient
from tg_bot.config import API_ID, API_HASH

async def authorize_telethon():
    """
    authorize Telethon, requesting required data.
    """
    client = TelegramClient('telethon_session', API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("Telethon authorization required.")
        await client.start()
    await client.disconnect()
    print("Telethon authorization completed successfully.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(authorize_telethon())


