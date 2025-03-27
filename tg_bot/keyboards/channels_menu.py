from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_channels_keyboard(channels, category_id=None):
    """
    create a keyboard with a list of channels.
    if category_id is passed, filter channels by category.
    """
    keyboard = []
    
    # add channel buttons
    if channels:
        for channel in channels:
            channel_category_id = getattr(channel, 'category_id', None)
            if channel_category_id is not None or channel_category_id != category_id:
                status = "✅" if channel.is_active else "❌"
                button_text = f"{status} {channel.name}"
                keyboard.append([
                    InlineKeyboardButton(text=button_text, callback_data=f"channel_{channel.id}"),
                    InlineKeyboardButton(text="✏️", callback_data=f"edit_channel_{channel.id}")
                ])

    # add "Add channel" button
    keyboard.append([InlineKeyboardButton(text="➕ Add channel", callback_data="add_channel")])
    # add "Remove channel" button
    keyboard.append([InlineKeyboardButton(text="➖ Remove channel", callback_data="remove_channel")])

    if category_id:
        # add "Back" button to return to the list of categories
        keyboard.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_categories_keyboard(channels_data, categories):
    """
    create a keyboard with a list of categories based on data from categories.json
    """
    keyboard = []
    
    # add category buttons
    categories = sorted(categories, key=lambda x: x.id)
    if categories:
        for category in categories:
            keyboard.append([
                InlineKeyboardButton(text=f"{category.name}", callback_data=f"category_{category.id}"),
                InlineKeyboardButton(text="✏️", callback_data=f"edit_category_{category.id}")
            ])
    
    # add buttons for adding and removing categories
    keyboard.append([InlineKeyboardButton(text="➕ Add category", callback_data="add_category")])
    keyboard.append([InlineKeyboardButton(text="➖ Remove category", callback_data="remove_category")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_button():
    """
    create a "Back" button
    """
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back")]])