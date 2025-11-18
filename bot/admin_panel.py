"""
Упрощённая Admin панель через APIClient (без прямых импортов из api/)

Функционал:
- /admin → Панель управления
- Список пользователей
- Базовая статистика

Использует: bot.api_client.APIClient для всех операций с данными
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import logging
from typing import Optional

from bot.config import is_admin, API_BASE_URL, INTERNAL_API_TOKEN
from bot.api_client import APIClient

logger = logging.getLogger(__name__)
router = Router()


def get_api() -> APIClient:
    """Получить экземпляр API клиента."""
    return APIClient(base_url=API_BASE_URL, token=INTERNAL_API_TOKEN)


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Главная панель администратора."""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
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
    
    # Получаем статистику через API
    try:
        api = get_api()
        users = await api.get_users()
        
        # Подсчитываем статистику
        total_users = len(users)
        active_users = sum(1 for u in users if u.get('active', 0) == 1)
        admins = sum(1 for u in users if u.get('role') == 'admin')
        foremen = sum(1 for u in users if u.get('role') == 'foreman')
        workers = sum(1 for u in users if u.get('role') == 'worker')
        
        # Формируем сообщение
        text = f"""🔧 **Панель администратора**

👥 **Пользователи:**
├─ Всего: {total_users}
├─ Активных: {active_users}
└─ Неактивных: {total_users - active_users}

👔 **По ролям:**
├─ Администраторы: {admins}
├─ Бригадиры: {foremen}
└─ Рабочие: {workers}

Выберите действие:"""
        
        # Кнопки управления (restored from backup — 6 sections)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users:page:0"),
                InlineKeyboardButton(text="📊 Детальная статистика", callback_data="admin:stats")
            ],
            [
                InlineKeyboardButton(text="👔 Заказчики", callback_data="admin:clients"),
                InlineKeyboardButton(text="📅 Расписание", callback_data="admin:schedule:view")
            ],
            [
                InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="adm:add:start")
            ],
            [
                InlineKeyboardButton(text="👷 Только рабочие", callback_data="admin:filter:worker"),
                InlineKeyboardButton(text="👨‍💼 Только бригадиры", callback_data="admin:filter:foreman")
            ],
            [
                InlineKeyboardButton(text="🔧 Только админы", callback_data="admin:filter:admin"),
                InlineKeyboardButton(text="❌ Неактивные", callback_data="admin:filter:inactive")
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:refresh")
            ]
        ])
        
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Admin panel error: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при загрузке панели: {e}")


@router.callback_query(F.data == "admin:refresh")
async def admin_refresh(callback: CallbackQuery):
    """Обновить главную панель."""
    await callback.answer("🔄 Обновляю...")
    await admin_panel(callback.message)
    await callback.message.delete()


@router.callback_query(F.data.startswith("admin:users:page:"))
async def admin_users_list(callback: CallbackQuery):
    """Список пользователей с пагинацией."""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    # Извлекаем номер страницы
    page = int(callback.data.split(":")[-1])
    page_size = 10
    
    try:
        api = get_api()
        users = await api.get_users()
        
        # Пагинация
        total_users = len(users)
        total_pages = (total_users + page_size - 1) // page_size
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total_users)
        page_users = users[start_idx:end_idx]
        
        # Формируем список
        text = f"👥 Пользователи (страница {page + 1}/{total_pages})\n\n"
        
        for idx, user in enumerate(page_users, start=start_idx + 1):
            role_emoji = {
                'admin': '👑',
                'foreman': '👔',
                'worker': '👷'
            }.get(user.get('role', 'worker'), '👤')
            
            active_mark = '✅' if user.get('active', 0) == 1 else '❌'
            name = user.get('name', 'Unknown')
            username = user.get('telegram_username', '')
            username_str = f"(@{username})" if username else ""
            
            text += f"{idx}. {role_emoji} {name} {username_str} {active_mark}\n"
        
        # Кнопки навигации
        buttons = []
        nav_row = []
        
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:users:page:{page-1}"))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"admin:users:page:{page+1}"))
        
        if nav_row:
            buttons.append(nav_row)
        
        buttons.append([InlineKeyboardButton(text="🔙 Главная панель", callback_data="admin:main")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Users list error: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    """Детальная статистика системы."""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    try:
        api = get_api()
        users = await api.get_users()
        
        # Собираем детальную статистику
        total_salary = 0
        active_workers = []
        
        for user in users:
            if user.get('role') == 'worker' and user.get('active', 0) == 1:
                active_workers.append(user)
                salary = user.get('daily_salary', 0)
                if salary:
                    total_salary += salary
        
        avg_salary = total_salary / len(active_workers) if active_workers else 0
        
        text = f"""📊 **Детальная статистика**

👷 **Активные рабочие:** {len(active_workers)}
💰 **Общая дневная зарплата:** {total_salary:,.0f} ₽
📈 **Средняя зарплата:** {avg_salary:,.0f} ₽

🔧 **Системная информация:**
├─ API: ✅ Доступен
└─ База данных: ✅ Подключена
"""
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Главная панель", callback_data="admin:main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin:main")
async def admin_main(callback: CallbackQuery):
    """Вернуться на главную панель."""
    await callback.answer("🏠 Главная панель")
    await callback.message.delete()
    
    # Создаём новое сообщение с панелью
    message = callback.message
    # Подменяем message для вызова admin_panel
    class FakeMessage:
        def __init__(self, original):
            self.from_user = original.from_user
            self.chat = original.chat
            self._original = original
        
        async def answer(self, text, **kwargs):
            await self._original.answer(text, **kwargs)
    
    fake_msg = FakeMessage(message)
    await admin_panel(fake_msg)
