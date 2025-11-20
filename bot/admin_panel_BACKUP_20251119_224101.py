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
        
        # Формируем сообщение (с эффектом свечения через эмодзи)
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
        
        # Кнопки управления (restored from backup — 6 sections)
        kb = InlineKeyboardMarkup(inline_keyboard=[
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
    
    await callback.answer()  # Acknowledge immediately
    
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
        
        # Формируем список с космическим дизайном
        text = f"""```
    ✦   *   ˚   ·   ✧   *   ˚
  ˚   ·   ✦   *   ✧   ·   ˚
```
👨‍🚀 **РЕЕСТР ЭКИПАЖА**
━━━━━━━━━━━━━━━━━━━━━━━━
📄 Страница: `{page + 1}/{total_pages}`
👥 Всего членов экипажа: `{total_users}`
━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        for idx, user in enumerate(page_users, start=start_idx + 1):
            role_emoji = {
                'admin': '👑',
                'foreman': '👔',
                'worker': '👷'
            }.get(user.get('role', 'worker'), '👤')
            
            active_mark = '🟢' if user.get('active', 0) == 1 else '💤'
            name = user.get('name', 'Unknown')
            username = user.get('telegram_username', '')
            username_str = f"@{username}" if username else ""
            
            text += f"**{idx}.** {role_emoji} {active_mark} **{name}** {username_str}\n"
        
        # Кнопки навигации
        buttons = []
        nav_row = []
        
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:users:page:{page-1}"))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"admin:users:page:{page+1}"))
        
        if nav_row:
            buttons.append(nav_row)
        
        buttons.append([InlineKeyboardButton(text="🚀 На мостик", callback_data="admin:main")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        
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
    
    await callback.answer()  # Acknowledge immediately
    
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
        
        text = f"""
✨📊 **ПАНЕЛЬ АНАЛИТИКИ** 📊✨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **ТРУДОВЫЕ РЕСУРСЫ**
│
├─ 👷 Активных инженеров: **{len(active_workers)}** ⚙️
├─ 💰 Общий дневной бюджет: **{total_salary:,.0f} ₽** 💎
└─ 📈 Средняя ставка: **{avg_salary:,.0f} ₽** 📊

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ **СТАТУС СИСТЕМ** ✨
│
├─ 🌐 API: **ОНЛАЙН** ✅
├─ 🗄️ База данных: **ПОДКЛЮЧЕНА** ✅
└─ 🔋 Мощность: **100%** ⚡

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 На мостик", callback_data="admin:main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        
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


@router.callback_query(F.data.startswith("admin:filter:"))
async def admin_filter_users(callback: CallbackQuery):
    """Фильтровать пользователей по роли или статусу."""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    await callback.answer()  # Acknowledge immediately

    filter_type = callback.data.split(":")[-1]

    try:
        api = get_api()
        all_users = await api.get_users()        # Применяем фильтр
        if filter_type == "inactive":
            users = [u for u in all_users if u.get('active', 0) == 0]
            title = "❌ Неактивные пользователи"
        else:
            users = [u for u in all_users if u.get('role') == filter_type and u.get('active', 0) == 1]
            role_names = {
                "worker": "👷 Рабочие",
                "foreman": "👨‍💼 Бригадиры",
                "admin": "🔧 Администраторы"
            }
            title = role_names.get(filter_type, "Пользователи")
        
        if not users:
            await callback.answer(f"Нет пользователей в категории: {filter_type}", show_alert=True)
            return
        
        # Формируем список (первые 10)
        text = f"{title}\n\n"
        text += f"Найдено: {len(users)}\n\n"
        
        for idx, user in enumerate(users[:10], start=1):
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
        
        
        if len(users) > 10:
            text += f"\n... и ещё {len(users) - 10}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Главная панель", callback_data="admin:main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb)
        
    except Exception as e:
        logger.error(f"Filter users error: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "admin:clients")
async def admin_clients(callback: CallbackQuery):
    """Заказчики (клиенты) — заглушка, требует реализации."""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()  # Acknowledge immediately
    
    text = """👔 **Управление заказчиками**

Функция находится в разработке.

Планируемый функционал:
• Список всех заказчиков
• Добавление нового заказчика
• Редактирование информации
• Просмотр истории заказов

Для временного использования обратитесь к веб-интерфейсу."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главная панель", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "admin:schedule:view")
async def admin_schedule_view(callback: CallbackQuery):
    """Расписание на завтра — заглушка."""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()  # Acknowledge immediately
    
    text = """📅 **Расписание на завтра**

Функция находится в разработке.

Планируемый функционал:
• Просмотр расписания смен
• Назначение рабочих на объекты
• Уведомления о смене расписания

Для временного использования обратитесь к веб-интерфейсу."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главная панель", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


