from aiogram import types, F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tg_bot.config import ADMIN_ID, FILE_JSON, CATEGORIES_JSON, DATA_FOLDER, MESSAGES_FOLDER
from tg_bot.keyboards.main_menu import main_menu_keyboard
from tg_bot.keyboards.channels_menu import get_channels_keyboard, get_categories_keyboard, get_back_button
import json
import os
import shutil
import uuid
import logging
from asgiref.sync import async_to_sync, sync_to_async
from admin_panel import models
from admin_panel.models import Channel, Category

# Налаштування логування
logger = logging.getLogger('admin_operations')

router = Router()

# create a synchronous function, which we will then wrap in async
def _create_category(name):
    from admin_panel.models import Category
    return Category.objects.create(name=name)

def _get_category_id(name):
    from admin_panel.models import Category
    return Category.objects.get(name=name).id

def _get_categories():
    from admin_panel.models import Category
    return list(Category.objects.all().order_by('id'))

def _get_category_by_id(id):
    from admin_panel.models import Category
    return Category.objects.get(id=id)

def _create_channel(name, url, category):
    from admin_panel.models import Channel
    return Channel.objects.create(name=name, url=url, category=category)

def _get_channel_by_name(name):
    from admin_panel.models import Channel
    return Channel.objects.get(name=name)

def _get_channel_by_id(id):
    from admin_panel.models import Channel
    return Channel.objects.get(id=id)

# wrap the synchronous function in async
create_category = sync_to_async(_create_category)
get_category_id = sync_to_async(_get_category_id)
get_categories = sync_to_async(_get_categories)
get_category_by_id = sync_to_async(_get_category_by_id)
create_channel = sync_to_async(_create_channel)
get_channel_by_name = sync_to_async(_get_channel_by_name)
get_channel_by_id = sync_to_async(_get_channel_by_id)
# FSM for adding a channel
class AddChannelStates(StatesGroup):
    waiting_for_channel_link = State() 
    waiting_for_channel_name = State()
    waiting_for_channel_category = State()

# FSM for editing a channel
class EditChannelStates(StatesGroup):
    waiting_for_channel_link = State()
    waiting_for_channel_name = State()
    waiting_for_channel_category = State()

# FSM for removing a channel
class RemoveChannelState(StatesGroup):
    waiting_for_input = State()

# FSM for adding a category
class AddCategoryStates(StatesGroup):
    waiting_for_category_name = State()

# FSM for editing a category
class EditCategoryStates(StatesGroup):
    waiting_for_category_name = State()

# FSM for removing a category
class RemoveCategoryStates(StatesGroup):
    waiting_for_category_id = State()


@router.message(F.text == "📎 List of channels", F.from_user.id == ADMIN_ID)
async def manage_channels(message: types.Message, channels_data: dict):
    """
    View the list of channels and manage them
    """
    # Get channels from the database
    @sync_to_async
    def get_channels():
        return list(Channel.objects.all())
    
    channels = await get_channels()
    
    if not channels:
        await message.answer("The list of channels is empty. Add channels using the buttons below.")
        await message.answer("Select an option:", reply_markup=get_channels_keyboard(channels))
        return
    
    await message.answer("Select a channel:", reply_markup=get_channels_keyboard(channels))

@router.callback_query(F.data.startswith("channel_"), F.from_user.id == ADMIN_ID)
async def channel_callback_handler(call: types.CallbackQuery, channels_data: dict):
    """
    Handler for clicking on the channel button
    """
    channel_id = call.data.split("_")[1]
    
    # Get the channel asynchronously
    @sync_to_async
    def get_and_toggle_channel(channel_id):
        try:
            channel = Channel.objects.get(id=channel_id)
            # Change the status of the channel
            old_status = "Active" if channel.is_active else "Inactive"
            channel.is_active = not channel.is_active
            new_status = "Active" if channel.is_active else "Inactive"
            channel.save()
            logger.info(f"The status of channel #{channel.id} '{channel.name}' has been changed: {old_status} -> {new_status}")
            return channel
        except Channel.DoesNotExist:
            logger.error(f"Attempt to change the status of a non-existent channel #{channel_id}")
            return None
    
    channel = await get_and_toggle_channel(channel_id)
    
    if channel:
        # Get all channels to update the keyboard
        @sync_to_async
        def get_all_channels():
            return list(Channel.objects.all())
        
        channels = await get_all_channels()
        
        # Update the keyboard
        await call.message.edit_reply_markup(reply_markup=get_channels_keyboard(channels))
        await call.answer(f"The status of channel '{channel.name}' has been changed!")
    else:
        await call.answer("Channel not found!")

@router.callback_query(F.data.startswith("edit_channel_"), F.from_user.id == ADMIN_ID)
async def edit_channel_start(call: types.CallbackQuery, state: FSMContext, channels_data: dict):
    """
    Start the process of editing a channel
    """
    channel_id = call.data.split("_")[2]
    
    @sync_to_async
    def get_channel_by_id_with_data(channel_id):
        try:
            channel = Channel.objects.get(id=channel_id)
            return {
                "id": channel.id,
                "name": channel.name,
                "url": channel.url,
                "category_id": channel.category_id,
                "is_active": channel.is_active
            }
        except Channel.DoesNotExist:
            return None
    
    channel_data = await get_channel_by_id_with_data(channel_id)
    
    if channel_data:
        # Save the channel ID in the state
        await state.update_data(channel_id=channel_id)
        await state.update_data(current_data=channel_data)
        
        await call.message.answer(f"Editing the channel: {channel_data['name']}")
        await call.message.answer(f"Current link: {channel_data['url']}\nEnter a new link or click /skip to leave the current link:")
        await state.set_state(EditChannelStates.waiting_for_channel_link)
        await call.answer()
    else:
        await call.answer("Channel not found!")

@router.message(EditChannelStates.waiting_for_channel_link, F.text, F.from_user.id == ADMIN_ID)
async def process_edit_channel_link(message: types.Message, state: FSMContext):
    """
    get a new channel link
    """
    if message.text == "/skip":
        user_data = await state.get_data()
        await state.update_data(new_channel_link=user_data['current_data']['url'])
    else:
        channel_link = message.text.strip()
        if channel_link.startswith("https://t.me/"):
            await state.update_data(new_channel_link=channel_link)
        else:
            await message.answer("Incorrect channel link. Enter a link in the format 'https://t.me/username':")
            return

    await message.answer("Enter a new channel name or click /skip to leave the current name:")
    await state.set_state(EditChannelStates.waiting_for_channel_name)

@router.message(EditChannelStates.waiting_for_channel_name, F.text, F.from_user.id == ADMIN_ID)
async def process_edit_channel_name(message: types.Message, state: FSMContext):
    """
    get a new channel name
    """
    if message.text == "/skip":
        user_data = await state.get_data()
        await state.update_data(new_channel_name=user_data['current_data']['name'])
    else:
        await state.update_data(new_channel_name=message.text)
    
    # Get categories asynchronously
    @sync_to_async
    def get_all_categories():
        return list(Category.objects.all().order_by('id'))
    
    categories = await get_all_categories()
    user_data = await state.get_data()
    current_category_id = user_data['current_data']['category_id']
    
    category_text = "Select the number of the category from the list or click /skip to leave the current one:\n"
    for category in categories:
        marker = "➡️ " if category.id == current_category_id else ""
        category_text += f"{marker}{category.id} ({category.name})\n"
    
    await message.answer(category_text)
    await state.set_state(EditChannelStates.waiting_for_channel_category)

@router.message(EditChannelStates.waiting_for_channel_category, F.text, F.from_user.id == ADMIN_ID)
async def process_edit_channel_category(message: types.Message, state: FSMContext, channels_data: dict):
    """
    get a new channel category and save the updated data
    """
    user_data = await state.get_data()
    channel_id = user_data['channel_id']
    
    # Determine the new category
    if message.text == "/skip":
        new_category_id = user_data['current_data']['category_id']
    else:
        # Check if the specified category exists
        @sync_to_async
        def check_category_exists(category_id):
            try:
                return Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                return None
        
        try:
            category_id = int(message.text)
        except ValueError:
            await message.answer("Enter a numerical category ID or use /skip")
            return
            
        category = await check_category_exists(category_id)
        if not category:
            await message.answer("Such a category does not exist. Try again or use /skip")
            return
        
        new_category_id = category_id
    
    # Update the channel data
    @sync_to_async
    def update_channel(channel_id, new_name, new_url, new_category_id):
        try:
            channel = Channel.objects.get(id=channel_id)
            old_data = {
                "name": channel.name,
                "url": channel.url,
                "category_id": channel.category_id
            }
            channel.name = new_name
            channel.url = new_url
            channel.category_id = new_category_id
            channel.save()
            
            # Log changes
            logger.info(f"Updated channel #{channel_id}:")
            if old_data['name'] != new_name:
                logger.info(f"- Name: '{old_data['name']}' -> '{new_name}'")
            if old_data['url'] != new_url:
                logger.info(f"- URL: '{old_data['url']}' -> '{new_url}'")
            if old_data['category_id'] != new_category_id:
                logger.info(f"- Category: {old_data['category_id']} -> {new_category_id}")
                
            return True
        except Exception as e:
            logger.error(f"Error updating channel #{channel_id}: {e}")
            return False
    
    success = await update_channel(
        channel_id, 
        user_data['new_channel_name'], 
        user_data['new_channel_link'], 
        new_category_id
    )
    
    if success:
        # Get all channels to update the keyboard
        @sync_to_async
        def get_all_channels():
            return list(Channel.objects.all())
        
        channels = await get_all_channels()
        
        await message.answer(
            "✅ Channel updated successfully!", 
            reply_markup=get_channels_keyboard(channels)
        )
    else:
        await message.answer("❌ Error updating the channel.")
    
    await state.clear()

@router.callback_query(F.data.startswith("category_"), F.from_user.id == ADMIN_ID)
async def category_callback_handler(call: types.CallbackQuery, channels_data: dict):
    """
    Handler for clicking on the category button
    """
    category_id = call.data.split("_")[1]
    
    # Get channels by category
    @sync_to_async
    def get_channels_by_category(category_id):
        return list(Channel.objects.filter(category_id=category_id))
    
    channels = await get_channels_by_category(category_id)
    
    # Get the category name
    @sync_to_async
    def get_category_name(category_id):
        try:
            return Category.objects.get(id=category_id).name
        except Category.DoesNotExist:
            return "Unknown category"
    
    category_name = await get_category_name(category_id)
    
    await call.message.edit_text(
        f"Channels of category '{category_name}':", 
        reply_markup=get_channels_keyboard(channels, category_id)
    )
    await call.answer()

@router.callback_query(F.data == "back", F.from_user.id == ADMIN_ID)
async def back_button_handler(call: types.CallbackQuery, channels_data: dict):
    """
    handler for clicking on the "Back" button
    """
    await call.message.edit_text("Select an action:", reply_markup=get_categories_keyboard(channels_data, await get_categories()))
    await call.answer()

@router.message(F.text == "📍 Categories menu", F.from_user.id == ADMIN_ID)
async def manage_categories(message: types.Message, channels_data: dict):
    """
    manage the list of categories
    """
    await message.answer("Select a category:", reply_markup=get_categories_keyboard(channels_data, await get_categories()))

@router.callback_query(F.data.startswith("edit_category_"), F.from_user.id == ADMIN_ID)
async def edit_category_start(call: types.CallbackQuery, state: FSMContext):
    """
    start the process of editing a category
    """
    category_id = call.data.split("_")[2]
    category = await get_category_by_id(category_id)
    if category:
        await state.update_data(category_id=category.id)
        await state.update_data(current_category_name=category.name)
        
        await call.message.answer(f"Editing the category: {category.name}")
        await call.message.answer("Enter a new category name:")
        await state.set_state(EditCategoryStates.waiting_for_category_name)
        await call.answer()
    else:
        await call.answer("Category not found!")

@router.message(EditCategoryStates.waiting_for_category_name, F.text, F.from_user.id == ADMIN_ID)
async def process_edit_category_name(message: types.Message, state: FSMContext, channels_data: dict):
    """
    get a new category name and save the changes
    """
    category_name = message.text
    user_data = await state.get_data()
    category_id = user_data['category_id']
    
    # update the category name
    category = await get_category_by_id(category_id)
    category.name = category_name
    await category.asave()
    
    # save the changes
    
    await message.answer(f"The category name has been changed to '{category_name}'", reply_markup=get_categories_keyboard(channels_data, await get_categories()))
    await state.clear()

@router.callback_query(F.data == "add_channel", F.from_user.id == ADMIN_ID)
async def add_channel_start(call: types.CallbackQuery, state: FSMContext):
    """
    start the process of adding a channel
    """
    await call.message.answer("Enter a channel link in the format 'https://t.me/username':")
    await state.set_state(AddChannelStates.waiting_for_channel_link)
    await call.answer()

@router.message(AddChannelStates.waiting_for_channel_link, F.text, F.from_user.id == ADMIN_ID)
async def process_channel_link(message: types.Message, state: FSMContext, channels_data: dict):
    """
    get a channel link from the user
    """
    channel_link = message.text.strip()
    # check if the entered string is a link
    if channel_link.startswith("https://t.me/"):
        # check if the channel already exists
        for channel_id, data in channels_data.items():
            if data.get('Invite_link') == channel_link:
                await message.answer("A channel with this link already exists. Enter another link:")
                return
                
        await state.update_data(channel_link=channel_link)
        await message.answer("Enter a channel name:")
        await state.set_state(AddChannelStates.waiting_for_channel_name)
    else:
        await message.answer("Incorrect channel link. Enter a link in the format 'https://t.me/username':")

@router.message(AddChannelStates.waiting_for_channel_name, F.text, F.from_user.id == ADMIN_ID)
async def process_channel_name(message: types.Message, state: FSMContext, channels_data: dict):
    """
    get a channel name from the user
    """
    channel_name = message.text
    await state.update_data(channel_name=channel_name)
    categories = await get_categories()
    
    # if there are no categories, create a category "By default"

    
    categories_text = "Select a category from the list:\n"
    for category in categories:
        categories_text += f"{category.id} ({category.name})\n"
    
    await message.answer(categories_text)
    await state.set_state(AddChannelStates.waiting_for_channel_category)

@router.message(AddChannelStates.waiting_for_channel_category, F.text, F.from_user.id == ADMIN_ID)
async def process_channel_category(message: types.Message, state: FSMContext, channels_data: dict):
    """
    get the channel category and save the data
    """
    try:
        category_id = int(message.text)
    except ValueError:
        await message.answer("The category ID must be a number. Try again.")
        return
        
    # check if the category exists
    @sync_to_async
    def check_category_exists(category_id):
        try:
            return Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return None
            
    category = await check_category_exists(category_id)
    if not category:
        await message.answer("Such a category does not exist. Try again.")
        return

    # get the data from the state
    user_data = await state.get_data()
    channel_link = user_data.get('channel_link')
    channel_name = user_data['channel_name']

    # save the channel in the database
    @sync_to_async
    def create_channel_in_db(name, url, category_id):
        try:
            channel = Channel.objects.create(
                name=name, 
                url=url, 
                category_id=category_id, 
                is_active=True
            )
            logger.info(f"Created a new channel: ID {channel.id}, name '{name}', category '{category.name}'")
            return channel
        except Exception as e:
            logger.error(f"Error creating the channel '{name}': {e}")
            return None

    channel = await create_channel_in_db(channel_name, channel_link, category_id)
    
    if channel:
        # get all channels to update the keyboard
        @sync_to_async
        def get_all_channels():
            return list(Channel.objects.all())
        
        channels = await get_all_channels()
        
        await message.answer(
            f"✅ Channel '{channel_name}' has been added to category '{category.name}'", 
            reply_markup=get_channels_keyboard(channels)
        )
    else:
        await message.answer("❌ Error adding the channel.")
    
    await state.clear()

@router.callback_query(F.data == "remove_channel", F.from_user.id == ADMIN_ID)
async def remove_channel_start(call: types.CallbackQuery, state: FSMContext):
    """
    start the process of deleting a channel
    """
    await call.message.answer("Enter the name of the channel to delete:")
    await state.set_state(RemoveChannelState.waiting_for_input)
    await call.answer()

@router.message(RemoveChannelState.waiting_for_input, F.text, F.from_user.id == ADMIN_ID)
async def process_remove_channel_input(message: types.Message, state: FSMContext):
    """
    process the user's input for deleting a channel
    """
    channel_name = message.text.strip()
    
    # find and delete the channel
    @sync_to_async
    def find_and_delete_channel(name):
        try:
            channel = Channel.objects.get(name=name)
            channel_id = channel.id
            channel_name = channel.name
            channel.delete()
            logger.info(f"Deleted channel #{channel_id} '{channel_name}'")
            return channel_name
        except Channel.DoesNotExist:
            logger.warning(f"Tried to delete a non-existent channel with the name '{name}'")
            return None
        except Exception as e:
            logger.error(f"Error deleting the channel '{name}': {e}")
            return False
    
    result = await find_and_delete_channel(channel_name)
    
    if result is None:
        await message.answer("❌ Channel not found. Enter the correct channel name.")
    elif result is False:
        await message.answer("❌ Error deleting the channel.")
    else:
        # get the updated list of channels
        @sync_to_async
        def get_all_channels():
            return list(Channel.objects.all())
        
        channels = await get_all_channels()
        
        await message.answer(
            f"✅ Channel '{result}' has been deleted!",
            reply_markup=get_channels_keyboard(channels)
        )
    
    await state.clear()

@router.callback_query(F.data == "add_category", F.from_user.id == ADMIN_ID)
async def add_category_start(call: types.CallbackQuery, state: FSMContext):
    """
    start the process of adding a category
    """
    await call.message.answer("Enter the name of the new category:")
    await state.set_state(AddCategoryStates.waiting_for_category_name)
    await call.answer()

@router.message(AddCategoryStates.waiting_for_category_name, F.text, F.from_user.id == ADMIN_ID)
async def process_category_name(message: types.Message, state: FSMContext, channels_data: dict, bot: Bot):
    """
    get a category name from the user and save the data in categories.json
    """
    category_name = message.text
    await create_category(category_name)
    new_category_id = await get_category_id(category_name)
    
    logger.info(f"Created a new category: ID {new_category_id}, name '{category_name}'")

    await message.answer(f"The category '{category_name}' (ID: {new_category_id}) has been added.", reply_markup=get_categories_keyboard(channels_data, await get_categories()))
    await state.clear()

    # notify about changes
    await message.answer("The category has been added successfully, changes saved.", reply_markup=main_menu_keyboard)

@router.callback_query(F.data == "remove_category", F.from_user.id == ADMIN_ID)
async def remove_category_start(call: types.CallbackQuery, state: FSMContext, channels_data: dict):
    """
    start the process of deleting a category
    """
    categories = await get_categories()
    categories_text = "Select the ID of the category to delete:\n"
    for category in categories:
        categories_text += f"{category.id} ({category.name})\n"
    
    await call.message.answer(categories_text)
    await state.set_state(RemoveCategoryStates.waiting_for_category_id)
    await call.answer()

@router.message(RemoveCategoryStates.waiting_for_category_id, F.text, F.from_user.id == ADMIN_ID)
async def process_remove_category_id(message: types.Message, state: FSMContext, channels_data: dict, bot: Bot):
    """
    get a category ID from the user and delete it
    """
    category_id = message.text
    category = await get_category_by_id(category_id)
    if not category:
        logger.warning(f"Tried to delete a non-existent category with ID {category_id}")
        await message.answer("There is no category with this ID.")
        return

    # save the category name before deleting for logging
    category_name = category.name
    
    # delete the category
    await category.adelete()
    logger.info(f"Deleted category: ID {category_id}, name '{category_name}'")

    categories = await get_categories()
    # update the categories in the channel data
    for channel_id, data in channels_data.items():
        if data['category'] == category_id:
            data['category'] = "0"  # set the category "0" (not defined)

    await message.answer(f"The category with ID '{category_id}' has been deleted.", reply_markup=get_categories_keyboard(channels_data, categories))
    await state.clear()

    # notify about changes
    await message.answer("The category has been deleted successfully, changes saved.", reply_markup=main_menu_keyboard)

# example of a simple admin command (for checking the bot's functionality)
@router.message(Command("ping"), F.from_user.id == ADMIN_ID)
async def admin_ping(message: types.Message):
    await message.answer("Pong!")

# add the /stop command for stopping the bot
@router.message(Command("stop"), F.from_user.id == ADMIN_ID)
async def cmd_stop(message: types.Message, bot: Bot):
    await message.answer("Stopping the bot...")
    # use gradual shutdown
    from main import stop_event, dp
    stop_event.set()
    await message.answer("The bot has been stopped successfully!")
    await bot.session.close()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID