"""
Обработчики фильтров пользователей по роли/статусу

Обработчики:
- admin:filter:worker — только роль worker
- admin:filter:foreman — только роль foreman
- admin:filter:admin — только роль admin
- admin:filter:inactive — только неактивные (active=0)

Логика:
1. Проверка прав доступа (is_admin)
2. Немедленный callback.answer()
3. Парсинг фильтра из callback_data
4. GET /api/admin/users
5. Фильтрация по условию
6. Отображение списка с космическим дизайном
7. Кнопка "🚀 На мостик" для возврата
"""
import logging
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import is_admin, API_BASE_URL, INTERNAL_API_TOKEN
from bot.api_client import APIClient

logger = logging.getLogger(__name__)


def get_api() -> APIClient:
    """Получить экземпляр API клиента."""
    return APIClient(base_url=API_BASE_URL, token=INTERNAL_API_TOKEN)


async def handle_filter(callback: CallbackQuery):
    """
    Фильтровать пользователей по роли или статусу
    
    Формат callback_data: admin:filter:<filter_type>
    где filter_type = worker | foreman | admin | inactive
    
    Шаги:
    1. Проверка is_admin
    2. callback.answer() немедленно
    3. Парсинг filter_type из callback.data.split(":")[-1]
    4. GET /api/admin/users
    5. Применение фильтра:
       - worker → role == 'worker'
       - foreman → role == 'foreman'
       - admin → role == 'admin'
       - inactive → active == 0
    6. Формирование текста с результатами
    7. Кнопка возврата
    
    Args:
        callback: aiogram CallbackQuery от кнопок фильтрации
    """
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    # callback.answer() вызывается в роутере admin_panel.py

    try:
        # Парсинг типа фильтра
        filter_type = callback.data.split(":")[-1]
        
        api = get_api()
        users = await api.get_users()
        
        # Применение фильтра
        if filter_type == "worker":
            filtered = [u for u in users if u.get('role') == 'worker']
            title = "👷 ИНЖЕНЕРЫ"
            emoji = "⚙️"
        elif filter_type == "foreman":
            filtered = [u for u in users if u.get('role') == 'foreman']
            title = "👨‍💼 ОФИЦЕРЫ"
            emoji = "💫"
        elif filter_type == "admin":
            filtered = [u for u in users if u.get('role') == 'admin']
            title = "🔧 АДМИРАЛЫ"
            emoji = "🌟"
        elif filter_type == "inactive":
            filtered = [u for u in users if u.get('active', 0) == 0]
            title = "❌ В СТАЗИСЕ"
            emoji = "🧊"
        else:
            await callback.answer("❌ Неизвестный фильтр", show_alert=True)
            return
        
        # Формирование списка
        if not filtered:
            text = f"""
✨{title}✨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Никого не найдено

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        else:
            lines = [f"✨{title}✨", "", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", ""]
            
            for idx, user in enumerate(filtered, start=1):
                name = user.get('name', 'Без имени')
                username = user.get('username')
                user_tg_id = user.get('user_id', 0)
                active = user.get('active', 0)
                
                username_str = f"@{username}" if username else f"ID:{user_tg_id}"
                active_mark = "🟢" if active == 1 else "💤"
                
                lines.append(f"**{idx}.** {emoji} {active_mark} **{name}** {username_str}")
            
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"📊 Всего: **{len(filtered)}** человек")
            
            text = "\n".join(lines)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 На мостик", callback_data="admin:main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Filter error: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
