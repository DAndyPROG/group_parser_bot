from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from asgiref.sync import sync_to_async

from tg_bot.keyboards.session_menu import (
    session_menu_keyboard,
    get_sessions_list_keyboard,
    get_session_actions_keyboard
)
from tg_bot.keyboards.main_menu import main_menu_keyboard
from admin_panel.models import TelegramSession

router = Router()

class AddSessionStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_api_id = State()
    waiting_for_api_hash = State()

# keyboard with the cancel button
cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Cancel")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

@router.message(F.text == "🔑 Add new session")
async def show_session_menu(message: Message):
    """Shows the session management menu"""
    await message.answer(
        "Select an action:",
        reply_markup=session_menu_keyboard
    )

@router.message(F.text == "🔙 Back to main menu")
async def back_to_main_menu(message: Message, state: FSMContext):
    """Returns to the main menu"""
    # clear the FSM state
    await state.clear()
    await message.answer(
        "Main menu:",
        reply_markup=main_menu_keyboard
    )

@router.message(F.text == "❌ Cancel")
async def cancel_action(message: Message, state: FSMContext):
    """Cancelling the action and returning to the session menu"""
    # clear the FSM state
    await state.clear()
    await message.answer(
        "Action cancelled. Select an option:",
        reply_markup=session_menu_keyboard
    )

@router.message(F.text == "➕ Add new session")
async def start_add_session(message: Message, state: FSMContext):
    """Starts the process of adding a new session"""
    await message.answer(
        "Enter the phone number in the format +380XXXXXXXXX:\n"
        "To cancel, click the button below ⬇️",
        reply_markup=cancel_keyboard
    )
    await state.set_state(AddSessionStates.waiting_for_phone)

@router.message(AddSessionStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Processing the entered phone number"""
    # check if this is a cancellation
    if message.text == "❌ Cancel":
        await cancel_action(message, state)
        return
    
    phone = message.text.strip()
    try:
        # phone number validation
        phone_validator = RegexValidator(
            regex=r'^\+380\d{9}$',
            message='The phone number must be in the format +380XXXXXXXXX'
        )
        phone_validator(phone)
        
        # check if such a number already exists
        phone_exists = await sync_to_async(TelegramSession.objects.filter(phone=phone).exists)()
        if phone_exists:
            await message.answer(
                "This phone number is already registered. Try another:",
                reply_markup=cancel_keyboard
            )
            return
        
        await state.update_data(phone=phone)
        await message.answer(
            "Enter the API ID (https://my.telegram.org/apps):",
            reply_markup=cancel_keyboard
        )
        await state.set_state(AddSessionStates.waiting_for_api_id)
    except ValidationError:
        await message.answer(
            "Incorrect phone number format. Try again:",
            reply_markup=cancel_keyboard
        )

@router.message(AddSessionStates.waiting_for_api_id)
async def process_api_id(message: Message, state: FSMContext):
    """Processing the entered API ID"""
    # check if this is a cancellation
    if message.text == "❌ Cancel":
        await cancel_action(message, state)
        return
    
    api_id = message.text.strip()
    await state.update_data(api_id=api_id)
    await message.answer(
        "Enter the API Hash (https://my.telegram.org/apps):",
        reply_markup=cancel_keyboard
    )
    await state.set_state(AddSessionStates.waiting_for_api_hash)

@router.message(AddSessionStates.waiting_for_api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    """Processing the entered API Hash and saving the session"""
    # check if this is a cancellation
    if message.text == "❌ Cancel":
        await cancel_action(message, state)
        return
    
    api_hash = message.text.strip()
    data = await state.get_data()
    
    try:
        # create the session asynchronously
        @sync_to_async
        def create_session():
            return TelegramSession.objects.create(
                phone=data['phone'],
                api_id=data['api_id'],
                api_hash=api_hash
            )
        
        session = await create_session()
        await message.answer(
            f"✅ Session successfully added!\n"
            f"Number: {session.phone}\n"
            f"API ID: {session.api_id}",
            reply_markup=session_menu_keyboard
        )
    except Exception as e:
        await message.answer(
            f"❌ Error adding the session: {str(e)}",
            reply_markup=session_menu_keyboard
        )
    
    await state.clear()

@router.message(F.text == "📋 List of sessions")
async def show_sessions_list(message: Message):
    """Displaying the list of all sessions"""
    # get the sessions asynchronously
    @sync_to_async
    def get_all_sessions():
        return list(TelegramSession.objects.all())
    
    sessions = await get_all_sessions()
    if not sessions:
        await message.answer(
            "The list of sessions is empty",
            reply_markup=session_menu_keyboard
        )
        return
    
    await message.answer(
        "Select a session:",
        reply_markup=get_sessions_list_keyboard(sessions)
    )

@router.callback_query(F.data.startswith("session_"))
async def show_session_actions(callback: CallbackQuery):
    """Displaying the actions for the selected session"""
    session_id = int(callback.data.split("_")[1])
    
    # get the session asynchronously
    @sync_to_async
    def get_session_by_id(session_id):
        return TelegramSession.objects.get(id=session_id)
    
    session = await get_session_by_id(session_id)
    
    await callback.message.edit_text(
        f"Information about the session:\n"
        f"Number: {session.phone}\n"
        f"API ID: {session.api_id}\n"
        f"Status: {'Active' if session.is_active else 'Inactive'}\n"
        f"Created: {session.created_at.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=get_session_actions_keyboard(session_id)
    )

@router.callback_query(F.data.startswith("delete_session_"))
async def delete_session(callback: CallbackQuery):
    """Deleting the session"""
    session_id = int(callback.data.split("_")[2])
    
    # delete the session asynchronously
    @sync_to_async
    def delete_session_by_id(session_id):
        session = TelegramSession.objects.get(id=session_id)
        session.delete()
    
    try:
        await delete_session_by_id(session_id)
        
        # get all sessions after deletion
        @sync_to_async
        def get_all_sessions():
            return list(TelegramSession.objects.all())
        
        sessions = await get_all_sessions()
        
        await callback.message.edit_text(
            "✅ Session successfully deleted!",
            reply_markup=get_sessions_list_keyboard(sessions)
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Error deleting the session: {str(e)}",
            reply_markup=get_session_actions_keyboard(session_id)
        )

@router.callback_query(F.data.startswith("edit_session_"))
async def start_edit_session(callback: CallbackQuery, state: FSMContext):
    """Starting the process of editing the session"""
    session_id = int(callback.data.split("_")[2])
    
    # get the session asynchronously
    @sync_to_async
    def get_session_by_id(session_id):
        return TelegramSession.objects.get(id=session_id)
    
    session = await get_session_by_id(session_id)
    
    await state.update_data(session_id=session_id)
    await callback.message.edit_text(
        "Enter the new API ID:"
    )
    await state.set_state(AddSessionStates.waiting_for_api_id)

@router.callback_query(F.data == "back_to_session_menu")
async def back_to_session_menu(callback: CallbackQuery):
    """Returning to the session menu"""
    # replace the message with the inline buttons with a new message
    await callback.message.delete()
    await callback.message.answer(
        "Select an action:",
        reply_markup=session_menu_keyboard
    )

@router.callback_query(F.data == "back_to_sessions_list")
async def back_to_sessions_list(callback: CallbackQuery):
    """Returning to the list of sessions"""
    # get all sessions asynchronously
    @sync_to_async
    def get_all_sessions():
        return list(TelegramSession.objects.all())
    
    sessions = await get_all_sessions()
    
    await callback.message.edit_text(
        "Select a session:",
        reply_markup=get_sessions_list_keyboard(sessions)
    ) 