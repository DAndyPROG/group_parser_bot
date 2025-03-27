import asyncio
import json
import os
import signal
import re
from datetime import datetime
import django

from telethon import TelegramClient, errors, client
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
from asgiref.sync import sync_to_async
from tg_bot.config import (
    API_ID, API_HASH, FILE_JSON, MAX_MESSAGES,
    CATEGORIES_JSON, DATA_FOLDER, MESSAGES_FOLDER
)

# config Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_app.settings')
django.setup()

# import models
from admin_panel import models

def _save_message_to_db(message_data):
    """
    save message to db
    """
    channel = models.Channel.objects.get(name=message_data['channel_name'])
    message = models.Message(
        text=message_data['text'],
        media=message_data['media'],
        media_type=message_data['media_type'],
        telegram_message_id=message_data['message_id'],
        telegram_channel_id=message_data['channel_id'],
        telegram_link=message_data['link'],
        channel=channel,
        created_at=message_data['date'],
    )
    message.save()

def _get_channels():
    channels = list(models.Channel.objects.all().order_by('id'))
    return channels

def _get_category_id(channel):
    category = models.Category.objects.get(channel=channel)
    return category.id 

save_message_to_db = sync_to_async(_save_message_to_db)
get_channels = sync_to_async(_get_channels)
get_category_id = sync_to_async(_get_category_id)

last_processed_message_ids = {}

# flag for stop bot
stop_event = False

async def get_channel_messages(client, channel_identifier):
    """
    get last messages from specified channel.
    """
    try:
        await client.get_dialogs()  # update dialog cache
        channel = await client.get_entity(channel_identifier)
        messages = await client.get_messages(channel, 10)  # get last 10 messages
        return messages, channel
    except errors.ChannelInvalidError:
        print(f"Channel {channel_identifier} not found or unavailable.")
        return [], None
    except Exception as e:
        print(f"Error getting messages from channel {channel_identifier}: {e}")
        return [], None

async def download_media(client, message, media_dir):
    """
    download media from message and return path to file
    """
    try:
        if message.media:
            os.makedirs(media_dir, exist_ok=True)
            timestamp = message.date.strftime("%Y%m%d_%H%M%S")
            file_path = await message.download_media(
                file=os.path.join(media_dir, f"{message.id}_{timestamp}")
            )
            return os.path.basename(file_path) if file_path else None
        return None
    except Exception as e:
        print(f"Error downloading media: {e}")
        return None

async def save_message_to_data(message, channel, queue, category_id=None, client=None):
    """
    save message to data folder, with category, and send message info to main process.
    """
    try:        
        # media info
        media_type = None
        media_file = None
        
        # determine media type and download it
        if message.media and client:  # check if client is passed
            if isinstance(message.media, MessageMediaPhoto):
                media_type = "photo"
                media_file = await download_media(client, message, "media/messages")
            elif isinstance(message.media, MessageMediaDocument):
                if message.media.document.mime_type.startswith('video'):
                    media_type = "video"
                elif message.media.document.mime_type.startswith('image'):
                    media_type = "gif" if message.media.document.mime_type == 'image/gif' else "image"
                else:
                    media_type = "document"
                media_file = await download_media(client, message, "media/messages")
            elif isinstance(message.media, MessageMediaWebPage):
                media_type = "webpage"
                # here we don't download webpage, we just specify the type
        
        # get channel name
        channel_name = getattr(channel, 'title', None) or getattr(channel, 'name', 'Unknown channel')
        
        # save full message without limits
        message_info = {
            'text': message.text,
            'media': "media/messages/" + media_file if media_file else "",
            'media_type': media_type if media_type else None,
            'message_id': message.id,
            'channel_id': message.peer_id.channel_id,
            'channel_name': channel_name,  # add channel name
            'link': f"https://t.me/c/{message.peer_id.channel_id}/{message.id}",
            'date': message.date.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # save to db
        await save_message_to_db(message_info)
        
        # send message info to main process
        # don't send channel object, only necessary data
        queue.put({
            'message_info': message_info, 
            'category_id': category_id
        })

    except Exception as e:
        print(f"Error saving message to file: {e}")
        import traceback
        traceback.print_exc()

def extract_username_from_link(link):
    """extract username/channel from telegram link"""
    username_match = re.search(r'https?://(?:t|telegram)\.me/([^/]+)', link)
    if username_match:
        return username_match.group(1)
    return None

async def telethon_task(queue):
    global stop_event
    """
    background task for parsing messages with Telethon.
    """
    client = TelegramClient('telethon_session', API_ID, API_HASH)
    await client.start()

    while not stop_event:
        try:
            channels = await get_channels()
            for channel in channels:
                if channel.is_active:
                    try:
                        # use channel link
                        channel_link = channel.url
                        
                        if not channel_link or not channel_link.startswith('https://t.me/'):
                            print(f"Channel {channel.name} has no valid link.")
                            continue
                            
                        # first try to join channel
                        try:
                            # extract username from link
                            username = extract_username_from_link(channel_link)
                            if username:
                                entity = await client.get_entity(username)
                                await client(JoinChannelRequest(entity))
                                print(f"Successfully joined channel: {username}")
                            else:
                                print(f"Failed to extract username from link: {channel_link}")
                        except Exception as e:
                            print(f"Error joining channel {channel_link}: {e}")

                        # get messages from channel
                        messages, tg_channel = await get_channel_messages(client, channel_link)
                        
                        if messages and tg_channel:
                            # check if message is new
                            latest_message = messages[0]
                            channel_identifier = channel_link  # use link as identifier
                            last_message_id = last_processed_message_ids.get(channel_identifier)
                            
                            if not last_message_id or latest_message.id > last_message_id:
                                # get category id
                                category_id = None
                                if hasattr(channel, 'category_id'):
                                    category_id = await get_category_id(channel)
                                # send message to save
                                await save_message_to_data(latest_message, channel, queue, category_id, client)
                                last_processed_message_ids[channel_identifier] = latest_message.id
                            else:
                                print(f"Message from channel {channel.name} already processed.")
                        else:
                            print(f"Failed to get messages from channel: {channel.name}")

                    except errors.FloodError as e:
                        print(f"Exceeded request frequency limit. Waiting {e.seconds} seconds.")
                        await asyncio.sleep(e.seconds)

                    except Exception as e:
                        print(f"Error in telethon_task for channel {channel.name}: {e}")
                else:
                    print(f"Channel {channel.name} is not active for parsing.")

                await asyncio.sleep(5)  # pause between channels
        except Exception as e:
            print(f"Error reading or processing channels: {e}")

        await asyncio.sleep(30)  # pause between checks

def handle_interrupt(signum, frame):
    global stop_event
    print("Received signal to stop Telethon...")
    stop_event = True

def telethon_worker_process(queue):
    """
    start background task Telethon in separate process.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # add handling more signals for Windows and Unix systems
    try:
        signal.signal(signal.SIGINT, handle_interrupt)
        signal.signal(signal.SIGTERM, handle_interrupt)
    except (AttributeError, ValueError) as e:
        print(f"Error setting signal handler: {e}")
        # some signals may not be supported in Windows

    try:
        loop.run_until_complete(telethon_task(queue))
    except RuntimeError as e:
        print(f"Error in event loop: {e}")
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt, stopping...")
        stop_event = True
    finally:
        loop.close()
        print("Event loop closed.")