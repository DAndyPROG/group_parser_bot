import asyncio
import json
import os
import signal
import re
import logging
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

# configuration of logging
logging.basicConfig(    
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('telegram_parser')

# config Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# import models
from admin_panel import models

def _save_message_to_db(message_data):
    """
    save message to db
    """
    try:
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
        logger.info(f"Saved message: channel '{channel.name}', message ID {message_data['message_id']}")
        return message
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        return None

def _get_channels():
    channels = list(models.Channel.objects.all().order_by('id'))
    return channels

def _get_category_id(channel):
    """
    getting the category ID for the channel
    """
    try:
        if hasattr(channel, 'category_id') and channel.category_id:
            return channel.category_id
        elif hasattr(channel, 'category') and channel.category:
            return channel.category.id
        else:
            logger.warning(f"Channel '{channel.name}' has no associated category")
            return None
    except Exception as e:
        logger.error(f"Error getting category for channel '{channel.name}': {e}")
        return None

save_message_to_db = sync_to_async(_save_message_to_db)
get_channels = sync_to_async(_get_channels)
get_category_id = sync_to_async(_get_category_id)

last_processed_message_ids = {}

# flag for stop bot
stop_event = False

async def get_channel_messages(client, channel_identifier):
    """
    getting messages from the specified channel
    """
    try:
        await client.get_dialogs()  # update the dialog cache
        channel = await client.get_entity(channel_identifier)
        messages = await client.get_messages(channel, 10)  # get the last 10 messages
        logger.debug(f"Received {len(messages)} messages from channel {getattr(channel, 'title', channel_identifier)}")
        return messages, channel
    except errors.ChannelInvalidError:
        logger.warning(f"Channel {channel_identifier} not found or unavailable")
        return [], None
    except Exception as e:
        logger.error(f"Error getting messages from channel {channel_identifier}: {e}")
        return [], None

async def download_media(client, message, media_dir):
    """
    downloading media from the message and returning the path to the file
    """
    try:
        if message.media:
            os.makedirs(media_dir, exist_ok=True)
            timestamp = message.date.strftime("%Y%m%d_%H%M%S")
            file_path = await message.download_media(
                file=os.path.join(media_dir, f"{message.id}_{timestamp}")
            )
            if file_path:
                logger.debug(f"Downloaded media: {os.path.basename(file_path)}")
                return os.path.basename(file_path)
            else:
                logger.warning(f"Unable to download media for message {message.id}")
                return None
        return None
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
        return None

async def save_message_to_data(message, channel, queue, category_id=None, client=None):
    """
    saving the message and sending information to the queue
    """
    try:        
        # data about media
        media_type = None
        media_file = None
        
        # determine the type of media and download it
        if message.media and client:
            if isinstance(message.media, MessageMediaPhoto):
                media_type = "photo"
                media_file = await download_media(client, message, "media/messages")
                logger.debug(f"Media type: photo, file: {media_file}")
            elif isinstance(message.media, MessageMediaDocument):
                if message.media.document.mime_type.startswith('video'):
                    media_type = "video"
                elif message.media.document.mime_type.startswith('image'):
                    media_type = "gif" if message.media.document.mime_type == 'image/gif' else "image"
                else:
                    media_type = "document"
                media_file = await download_media(client, message, "media/messages")
                logger.debug(f"Media type: {media_type}, file: {media_file}")
            elif isinstance(message.media, MessageMediaWebPage):
                media_type = "webpage"
                logger.debug(f"Media type: webpage")
        
        # get the channel name
        channel_name = getattr(channel, 'title', None) or getattr(channel, 'name', 'Unknown channel')
        
        # save the message
        message_info = {
            'text': message.text,
            'media': "media/messages/" + media_file if media_file else "",
            'media_type': media_type if media_type else None,
            'message_id': message.id,
            'channel_id': message.peer_id.channel_id,
            'channel_name': channel_name,
            'link': f"https://t.me/c/{message.peer_id.channel_id}/{message.id}",
            'date': message.date.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # save to DB
        await save_message_to_db(message_info)
        
        # send to queue
        queue.put({
            'message_info': message_info, 
            'category_id': category_id
        })
        
        logger.info(f"Saved message {message.id} from channel '{channel_name}'")

    except Exception as e:
        logger.error(f"Error saving message: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Error traceback: {error_traceback}")

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
    
    logger.info("====== Telethon Parser started ======")
    logger.info(f"API ID: {API_ID}")
    logger.info(f"Session: telethon_session")
    
    try:
        me = await client.get_me()
        logger.info(f"Authorized as: {me.first_name} (@{me.username}) [ID: {me.id}]")
    except Exception as e:
        logger.error(f"Error getting account information: {e}")

    while not stop_event:
        try:
            channels = await get_channels()
            logger.info(f"Found {len(channels)} channels for parsing")
            
            active_channels = sum(1 for channel in channels if channel.is_active)
            logger.info(f"Active channels: {active_channels}/{len(channels)}")
            
            for channel in channels:
                if channel.is_active:
                    try:
                        # use channel link
                        channel_link = channel.url
                        
                        if not channel_link or not channel_link.startswith('https://t.me/'):
                            logger.warning(f"Channel '{channel.name}' has no valid link")
                            continue
                            
                        # first try to join channel
                        try:
                            # extract username from link
                            username = extract_username_from_link(channel_link)
                            if username:
                                entity = await client.get_entity(username)
                                await client(JoinChannelRequest(entity))
                                logger.info(f"Successfully joined channel: @{username}")
                            else:
                                logger.warning(f"Unable to get identifier from link: {channel_link}")
                        except Exception as e:
                            logger.error(f"Error joining channel {channel_link}: {e}")

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
                                logger.info(f"New message in channel '{channel.name}' [ID: {latest_message.id}]")
                                await save_message_to_data(latest_message, channel, queue, category_id, client)
                                last_processed_message_ids[channel_identifier] = latest_message.id
                            else:
                                logger.debug(f"Message from channel '{channel.name}' already processed")
                        else:
                            logger.warning(f"Unable to get messages from channel: '{channel.name}'")

                    except errors.FloodError as e:
                        logger.warning(f"Exceeded the request limit. Waiting {e.seconds} seconds")
                        await asyncio.sleep(e.seconds)

                    except Exception as e:
                        logger.error(f"Error in telethon_task for channel '{channel.name}': {e}")
                else:
                    logger.debug(f"Channel '{channel.name}' is not active for parsing")

                await asyncio.sleep(5)  # pause between channels
        except Exception as e:
            logger.error(f"Error reading or processing channels: {e}")
            
        logger.info("Parsing cycle completed. Waiting 30 seconds for the next cycle...")
        await asyncio.sleep(30)  # pause between checks

def handle_interrupt(signum, frame):
    global stop_event
    logger.info("Received signal to stop Telethon...")
    stop_event = True

def telethon_worker_process(queue):
    """
    start background task Telethon in separate process.
    """
    logger.info("Starting Telethon parser process...")
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(telethon_task(queue))
    except KeyboardInterrupt:
        logger.info("Parser process completed by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Error in parser process: {e}")
    finally:
        loop.close()
        logger.info("Parser process completed")