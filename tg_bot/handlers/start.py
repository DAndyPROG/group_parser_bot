from aiogram import Router, types, F
from aiogram.filters import CommandStart
from tg_bot.keyboards.main_menu import main_menu_keyboard
from tg_bot.config import WEB_SERVER_PORT, ADMIN_ID
from aiogram.utils.markdown import hlink
import qrcode
from io import BytesIO
from tg_bot.keyboards.channels_menu import get_channels_keyboard, get_categories_keyboard
from asgiref.sync import async_to_sync, sync_to_async
router = Router()

def _get_categories():
    from admin_panel.models import Category
    return list(Category.objects.all())

def _get_channels():
    from admin_panel.models import Channel
    return list(Channel.objects.all())

# Обгортаємо синхронну функцію в асинхронну
get_categories = sync_to_async(_get_categories)
get_channels = sync_to_async(_get_channels)
@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привіт! Я бот для парсингу повідомлень з Telegram каналів.", reply_markup=main_menu_keyboard)

@router.message(F.text == "🌐 Перейти на сайт")
async def website(message: types.Message):
    # Використовуємо зовнішню IP-адресу або доменне ім'я, якщо воно налаштоване
    website_url = f"http://192.168.0.237:{WEB_SERVER_PORT}"  # Змінено на IP, який відображається при запуску Flask
    
    # Створюємо інлайн-клавіатуру з кнопкою для переходу на сайт
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Відкрити сайт", url=website_url)],
        [types.InlineKeyboardButton(text="Отримати QR-код", callback_data="get_qr_code")]
    ])
    
    await message.answer("Сайт доступний за посиланням:", reply_markup=keyboard)

@router.callback_query(F.data == "get_qr_code")
async def send_qr_code(callback: types.CallbackQuery):
    website_url = f"http://192.168.0.237:{WEB_SERVER_PORT}"
    
    try:
        # Створюємо QR-код для веб-сайту
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(website_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Зберігаємо зображення у буфер
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        
        # Відправляємо QR-код
        await callback.message.answer_photo(
            photo=types.BufferedInputFile(
                file=bio.getvalue(), 
                filename="qrcode.png"
            ),
            caption=f"QR-код для доступу до сайту: {website_url}"
        )
        await callback.answer()
    except Exception as e:
        await callback.message.answer(f"Помилка створення QR-коду: {e}")
        await callback.answer("Не вдалося створити QR-код")

@router.message(F.text == "📎Список каналів")
async def list_channels(message: types.Message, channels_data: dict):
    """
    Відображає список підключених каналів
    """
    channels = await get_channels()
    # Якщо повідомлення від адміністратора, надаємо клавіатуру з кнопками керування
    if message.from_user.id == ADMIN_ID:
        await message.answer("Виберіть канал:", reply_markup=get_channels_keyboard(channels))
        return
    
    # Для звичайних користувачів просто показуємо список
    if not channels:
        await message.answer("Список каналів порожній.")
        return
    
    channels_text = "📎 Список підключених каналів:\n\n"
    for channel in channels:
        status = "✅ Активний" if channel.is_active else "❌ Неактивний"
        channels_text += f"• {channel.name} ({status})\n"
    
    await message.answer(channels_text)

@router.message(F.text == "📍Меню категорій")
async def list_categories(message: types.Message, channels_data: dict, categories: dict):
    """
    Відображає список категорій
    """
    categories = await get_categories()
    # Якщо повідомлення від адміністратора, надаємо клавіатуру з кнопками керування
    if message.from_user.id == ADMIN_ID:
        await message.answer("Виберіть категорію:", reply_markup=get_categories_keyboard(channels_data, categories))
        return
    
    # Для звичайних користувачів просто показуємо список
    if not categories:
        await message.answer("Список категорій порожній.")
        return
    
    categories_text = "📍 Список категорій:\n\n"
    for category in categories:
        categories_text += f"• ID {category.id}: {category.name}\n"
    
    await message.answer(categories_text)