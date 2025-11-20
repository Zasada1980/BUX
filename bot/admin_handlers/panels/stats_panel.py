"""
Панель аналитики (📊 ПАНЕЛЬ АНАЛИТИКИ)

Обработчик:
- admin:stats callback

Логика:
1. Проверка прав доступа (is_admin)
2. Запрос всех пользователей через APIClient
3. Подсчёт трудовых метрик:
   - Количество активных workers
   - Общая дневная зарплата
   - Средняя зарплата
4. Статус систем (API, БД)
5. Отображение с космическим дизайном
"""
import logging
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import is_admin, API_BASE_URL, INTERNAL_API_TOKEN
from bot.api_client import APIClient

logger = logging.getLogger(__name__)


def get_api() -> APIClient:
    """Получить экземпляр API клиента."""
    return APIClient(base_url=API_BASE_URL, token=INTERNAL_API_TOKEN)


async def show_stats_panel(callback: CallbackQuery):
    """
    Отобразить панель аналитики
    
    Шаги:
    1. Проверка is_admin
    2. Немедленный callback.answer() для снятия "loading clock"
    3. GET /api/admin/users
    4. Фильтрация активных workers
    5. Подсчёт:
       - total_salary = сумма daily_salary активных workers
       - avg_salary = total_salary / количество workers
    6. Формирование текста с разделами:
       - ТРУДОВЫЕ РЕСУРСЫ (workers, бюджет, средняя ставка)
       - СТАТУС СИСТЕМ (API, БД, мощность)
    7. Кнопка "🚀 На мостик" для возврата
    
    Args:
        callback: aiogram CallbackQuery от кнопки "📊 Аналитика"
    """
    user_id = callback.from_user.id
    
    # Проверка доступа
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    # callback.answer() вызывается в роутере admin_panel.py
    
    try:
        api = get_api()
        users = await api.get_users()
        
        # Подсчёт трудовых метрик
        total_salary = 0
        active_workers = []
        
        for user in users:
            if user.get('role') == 'worker' and user.get('active', 0) == 1:
                active_workers.append(user)
                salary = user.get('daily_salary', 0)
                if salary:
                    total_salary += salary
        
        avg_salary = total_salary / len(active_workers) if active_workers else 0
        
        # Космический дизайн с emoji glow
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
