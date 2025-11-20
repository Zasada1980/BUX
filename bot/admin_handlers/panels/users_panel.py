"""
Панель списка пользователей (👥 РЕЕСТР ЭКИПАЖА)

Обработчик:
- admin:users:page:<N> callback

Логика:
1. Проверка прав доступа (is_admin)
2. Запрос всех пользователей через APIClient
3. Пагинация (10 пользователей на страницу)
4. Отображение космического списка
5. Кнопки навигации (пред/след страница) + возврат

ВАЖНО: Использует APIClient, НЕ прямые импорты из api/
"""
import logging
from math import ceil
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import is_admin, API_BASE_URL, INTERNAL_API_TOKEN
from bot.api_client import APIClient

logger = logging.getLogger(__name__)

USERS_PER_PAGE = 10


def get_api() -> APIClient:
    """Получить экземпляр API клиента."""
    return APIClient(base_url=API_BASE_URL, token=INTERNAL_API_TOKEN)


async def show_users_list(callback: CallbackQuery):
    """
    Отобразить список пользователей с пагинацией
    
    Формат callback_data: admin:users:page:<N>
    
    Шаги:
    1. Проверка is_admin
    2. Немедленный callback.answer()
    3. Парсинг номера страницы из callback.data
    4. GET /api/admin/users
    5. Расчёт пагинации:
       - total_pages = ceil(len(users) / USERS_PER_PAGE)
       - start_idx = page * USERS_PER_PAGE
       - end_idx = start_idx + USERS_PER_PAGE
    6. Формирование космического списка:
       - Galaxy ASCII art фон
       - Заголовок с номером страницы
       - Список пользователей с emoji по ролям
       - Разделители
    7. Кнопки навигации:
       - [◀️ Пред] если page > 0
       - [След ▶️] если page < total_pages - 1
       - [🚀 На мостик] всегда
    
    Args:
        callback: aiogram CallbackQuery от кнопки "👥 Экипаж"
    """
    user_id = callback.from_user.id
    
    # Проверка доступа
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    # callback.answer() вызывается в роутере admin_panel.py
    
    try:
        # Парсинг страницы
        page = int(callback.data.split(":")[-1])
        
        api = get_api()
        users = await api.get_users()
        
        total_users = len(users)
        total_pages = ceil(total_users / USERS_PER_PAGE)
        
        # Пагинация
        start_idx = page * USERS_PER_PAGE
        end_idx = start_idx + USERS_PER_PAGE
        page_users = users[start_idx:end_idx]
        
        # Роли emoji
        role_emoji_map = {
            'admin': '👑',
            'foreman': '👔',
            'worker': '👷'
        }
        
        # Космический фон (ASCII galaxy)
        galaxy_bg = """```
    ✦   *   ˚   ·   ✧   *   ˚
  ˚   ·   ✦   *   ✧   ·   ˚
```"""
        
        # Заголовок
        lines = [
            galaxy_bg,
            "👨‍🚀 **РЕЕСТР ЭКИПАЖА**",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📄 Страница: `{page + 1}/{total_pages}`",
            f"👥 Всего членов экипажа: `{total_users}`",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            ""
        ]
        
        # Список пользователей
        for idx, user in enumerate(page_users, start=start_idx + 1):
            name = user.get('name', 'Без имени')
            username = user.get('username')
            user_tg_id = user.get('user_id', 0)
            role = user.get('role', 'worker')
            active = user.get('active', 0)
            
            role_emoji = role_emoji_map.get(role, '👤')
            active_mark = "🟢" if active == 1 else "💤"
            username_str = f"@{username}" if username else f"ID:{user_tg_id}"
            
            lines.append(f"**{idx}.** {role_emoji} {active_mark} **{name}** {username_str}")
        
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        
        text = "\n".join(lines)
        
        # Кнопки навигации
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="◀️ Пред", callback_data=f"admin:users:page:{page - 1}")
            )
        
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="След ▶️", callback_data=f"admin:users:page:{page + 1}")
            )
        
        kb_rows = []
        if nav_buttons:
            kb_rows.append(nav_buttons)
        
        kb_rows.append([
            InlineKeyboardButton(text="🚀 На мостик", callback_data="admin:main")
        ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Users list error: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
