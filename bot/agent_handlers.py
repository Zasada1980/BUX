"""
Боевые хендлеры для headless agent - интеграция с API REVIZOR
Команды: /in, /task, /expense, /out, /me
"""
import aiohttp
import logging
from aiogram import F
from aiogram.types import Message

log = logging.getLogger(__name__)

API_BASE = "http://127.0.0.1:8088"
INTERNAL_TOKEN = "revizor-internal-secret-2024"

async def api_request(method: str, endpoint: str, data: dict = None):
    """Общий хелпер для запросов к API"""
    url = f"{API_BASE}{endpoint}"
    headers = {"X-Internal-Token": INTERNAL_TOKEN, "Content-Type": "application/json"}
    
    log.info(f"API {method} {endpoint} data={data}")  # DEBUG
    
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                result = await resp.json()
                log.info(f"API response: status={resp.status} body={result}")  # DEBUG
                return result, resp.status
        elif method == "POST":
            async with session.post(url, headers=headers, json=data) as resp:
                result = await resp.json()
                log.info(f"API response: status={resp.status} body={result}")  # DEBUG
                return result, resp.status

async def cmd_in(msg: Message):
    """/in - начать смену"""
    telegram_id = msg.from_user.id
    log.info('cmd_in from %s', telegram_id)
    
    # Use stable /api/v1/shift/start endpoint
    data = {"user_id": str(telegram_id)}
    res, status = await api_request("POST", "/api/v1/shift/start", data)
    
    log.info(f"shift/start response: status={status} res={res}")  # DEBUG
    
    if status in (200, 201):  # Accept both 200 OK and 201 Created
        await msg.answer(f"✅ Смена начата\nID: {res.get('id')}")
    elif status == 409:
        await msg.answer(f"⚠️ У вас уже есть активная смена\nИспользуйте /out для завершения")
    else:
        await msg.answer(f"❌ Ошибка: {res.get('detail', 'Unknown error')}")

async def cmd_task(msg: Message):
    """/task <описание> - добавить задачу"""
    telegram_id = msg.from_user.id
    text = msg.text.replace('/task', '').strip()
    
    if not text:
        await msg.answer("❌ Использование: /task <описание задачи>")
        return
    
    log.info('cmd_task from %s: %s', telegram_id, text)
    
    data = {
        "user_id": str(telegram_id),
        "description": text,
        "category": "general"
    }
    res, status = await api_request("POST", "/api/task/add", data)
    
    if status == 200:
        await msg.answer(f"✅ Задача создана\nID: {res.get('id')}")
    else:
        await msg.answer(f"❌ Ошибка: {res.get('detail', 'Unknown error')}")

async def cmd_expense(msg: Message):
    """/expense <сумма> <описание> - добавить расход"""
    telegram_id = msg.from_user.id
    text = msg.text.replace('/expense', '').strip()
    
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("❌ Использование: /expense <сумма> <описание>\nПример: /expense 500 Такси")
        return
    
    try:
        amount = float(parts[0])
        description = parts[1]
    except ValueError:
        await msg.answer("❌ Неверная сумма")
        return
    
    log.info('cmd_expense from %s: %.2f - %s', telegram_id, amount, description)
    
    data = {
        "user_id": str(telegram_id),
        "amount": amount,
        "currency": "ILS",
        "category": "other",
        "description": description
    }
    res, status = await api_request("POST", "/api/expense/add", data)
    
    if status == 200:
        await msg.answer(f"✅ Расход добавлен\nID: {res.get('id')}\nСумма: ‎₪{amount:.2f}")
    else:
        await msg.answer(f"❌ Ошибка: {res.get('detail', 'Unknown error')}")

async def cmd_out(msg: Message):
    """/out - завершить смену"""
    telegram_id = msg.from_user.id
    log.info('cmd_out from %s', telegram_id)
    
    # Step 1: Find active shift using new endpoint
    user_id = str(telegram_id)
    res_active, status_active = await api_request("GET", f"/api/v1/shift/active?user_id={user_id}")
    
    log.info(f"shift/active response: status={status_active} res={res_active}")
    
    if status_active != 200 or not res_active or not res_active.get('shift_id'):
        await msg.answer("⚠️ Нет активной смены\nИспользуйте /in для начала")
        return
    
    shift_id = res_active['shift_id']
    
    # Step 2: End shift using /api/v1/shift/end
    data = {"shift_id": shift_id}
    res, status = await api_request("POST", "/api/v1/shift/end", data)
    
    log.info(f"shift/end response: status={status} res={res}")
    
    if status == 200:
        duration = res.get('duration', 'N/A')
        await msg.answer(f"✅ Смена завершена\nДлительность: {duration}")
    elif status == 404:
        await msg.answer("⚠️ Нет активной смены\nИспользуйте /in для начала")
    else:
        await msg.answer(f"❌ Ошибка: {res.get('detail', 'Unknown error')}")

async def cmd_me(msg: Message):
    """/me - информация о пользователе"""
    telegram_id = msg.from_user.id
    log.info('cmd_me from %s', telegram_id)
    
    # Get user info from new user management system
    from bot.config import get_db
    from api import crud_users
    
    db = next(get_db())
    user = crud_users.get_user_by_telegram_id(db, telegram_id)
    
    if user:
        role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(user.role, "❓")
        role_name = {"worker": "Рабочий", "foreman": "Бригадир", "admin": "Админ"}.get(user.role, user.role)
        status = "✅ Активен" if user.active else "❌ Неактивен"
        
        report = (
            f"👤 **Ваша информация**\n\n"
            f"🆔 ID: `{user.id}`\n"
            f"📱 Telegram ID: `{telegram_id}`\n"
            f"👤 Username: @{user.telegram_username or 'не указан'}\n"
            f"🎭 Роль: {role_emoji} {role_name}\n"
            f"📊 Статус: {status}\n"
            f"📅 Зарегистрирован: {user.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Try to get work statistics from old API (if exists)
        res, status_code = await api_request("GET", f"/api/worker/{telegram_id}/report")
        if status_code == 200:
            stats = res.get('stats', {})
            if stats:
                report += (
                    f"\n\n📊 **Статистика работы:**\n"
                    f"  • Смен: {stats.get('shifts', 0)}\n"
                    f"  • Задач: {stats.get('tasks', 0)}\n"
                    f"  • Расходы: {stats.get('expenses_sum', 0):.2f} ₪"
                )
        
        await msg.answer(report, parse_mode="Markdown")
    else:
        await msg.answer(
            "❌ Вы не зарегистрированы в системе\n\n"
            "Обратитесь к администратору для получения доступа"
        )

def register_agent_handlers(dp):
    """Регистрация всех боевых хендлеров"""
    # /in (+ alias /shift_in)
    dp.message.register(cmd_in, F.text.in_(['/in', '/shift_in']))
    # /task
    dp.message.register(cmd_task, F.text.startswith('/task'))
    # /expense
    dp.message.register(cmd_expense, F.text.startswith('/expense'))
    # /out (+ alias /shift_out)
    dp.message.register(cmd_out, F.text.in_(['/out', '/shift_out']))
    # /me
    dp.message.register(cmd_me, F.text == '/me')
    log.info('Agent handlers registered: /in /task /expense /out /me (+ aliases /shift_in, /shift_out)')
