"""
Главная панель администратора (ОРБИТАЛЬНЫЙ ЦЕНТР УПРАВЛЕНИЯ)

Обработчики:
- /admin команда
- admin:main callback (возврат на главную)

Логика:
1. Проверка прав доступа (is_admin)
2. Запрос статистики через APIClient
3. Подсчёт метрик (всего, активных, по ролям)
4. Формирование космического интерфейса с emoji glow
5. Отображение кнопок навигации
"""
import logging
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import is_admin, API_BASE_URL, INTERNAL_API_TOKEN
from bot.api_client import APIClient

logger = logging.getLogger(__name__)


def get_api() -> APIClient:
    """Получить экземпляр API клиента."""
    return APIClient(base_url=API_BASE_URL, token=INTERNAL_API_TOKEN)


def get_main_panel_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура главной панели (10 кнопок в 6 рядах)
    
    Кнопки:
    - Ряд 1: 👥 Экипаж, 📊 Аналитика
    - Ряд 2: 👔 Контрагенты, 📅 Полетный план
    - Ряд 3: ➕ Рекрутировать
    - Ряд 4: 👷 Только Инженеры, 👨‍💼 Только Офицеры
    - Ряд 5: 🔧 Только Адмиралы, ❌ В стазисе
    - Ряд 6: 🔄 Перезагрузка систем
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Экипаж", callback_data="admin:users:page:0"),
            InlineKeyboardButton(text="📊 Аналитика", callback_data="admin:stats")
        ],
        [
            InlineKeyboardButton(text="👔 Контрагенты", callback_data="admin:clients"),
            InlineKeyboardButton(text="📅 Полетный план", callback_data="admin:schedule:view")
        ],
        [
            InlineKeyboardButton(text="➕ Рекрутировать", callback_data="admin:add:start")
        ],
        [
            InlineKeyboardButton(text="👷 Только Инженеры", callback_data="admin:filter:worker"),
            InlineKeyboardButton(text="👨‍💼 Только Офицеры", callback_data="admin:filter:foreman")
        ],
        [
            InlineKeyboardButton(text="🔧 Только Адмиралы", callback_data="admin:filter:admin"),
            InlineKeyboardButton(text="❌ В стазисе", callback_data="admin:filter:inactive")
        ],
        [
            InlineKeyboardButton(text="🔄 Перезагрузка систем", callback_data="admin:refresh")
        ]
    ])


async def show_main_panel(message: Message):
    """
    Отобразить главную панель администратора
    
    Шаги:
    1. Проверка прав доступа (is_admin)
    2. GET /api/admin/users через APIClient
    3. Подсчёт метрик:
       - total_users — общее количество
       - active_users — с active=1
       - admins — роль admin
       - foremen — роль foreman
       - workers — роль worker
    4. Формирование текста с космическим дизайном
    5. Отправка сообщения с клавиатурой
    
    Args:
        message: aiogram Message (от /admin команды или callback)
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Проверка доступа
    if not is_admin(user_id):
        logger.warning(f"⚠️ Admin access denied for user_id={user_id}, username=@{username}")
        await message.answer(
            f"❌ **Доступ запрещён**\n\n"
            f"Панель администратора доступна только для авторизованных администраторов.\n\n"
            f"Ваш ID: `{user_id}`\n"
            f"Обратитесь к администратору системы для получения доступа.",
            parse_mode="Markdown"
        )
        return
    
    # Запрос статистики
    try:
        api = get_api()
        users = await api.get_users()
        
        # Подсчёт метрик
        total_users = len(users)
        active_users = sum(1 for u in users if u.get('active', 0) == 1)
        admins = sum(1 for u in users if u.get('role') == 'admin')
        foremen = sum(1 for u in users if u.get('role') == 'foreman')
        workers = sum(1 for u in users if u.get('role') == 'worker')
        
        # Космический интерфейс с emoji glow
        text = f"""
✨🚀 **ОРБИТАЛЬНЫЙ ЦЕНТР УПРАВЛЕНИЯ** 🚀✨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👨‍🚀 Командор: **@{username}**
📡 Статус системы: **🟢 ОНЛАЙН** ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ **📊 МЕТРИКИ ЭКИПАЖА** ✨
│
├─ 🪐 Всего персонала: **{total_users}** 👥
├─ 🟢 В строю: **{active_users}** ⚡
└─ 💤 В стазисе: **{total_users - active_users}** 🧊

✨ **🛡️ СОСТАВ ФЛОТА** ✨
│
├─ 👑 **{admins}** Адмирал(ов) 🌟
├─ 👔 **{foremen}** Офицер(ов) 💫
└─ 👷 **{workers}** Инженер(ов) ⚙️

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👇 **ВЫБЕРИТЕ МОДУЛЬ:** 🎯"""
        
        kb = get_main_panel_keyboard()
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Admin panel error: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при загрузке панели: {e}")
