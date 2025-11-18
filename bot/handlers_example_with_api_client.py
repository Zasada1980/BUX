"""
Пример рефакторинга bot handlers с использованием APIClient.

СТАРЫЙ ПОДХОД (НЕ РАБОТАЕТ В DOCKER):
    from api.crud_users import get_user_by_telegram_id
    from api.models import User
    
НОВЫЙ ПОДХОД (РАБОТАЕТ ВЕЗДЕ):
    from bot.api_client import get_api_client
    
    api = get_api_client(API_BASE_URL, INTERNAL_API_TOKEN)
    user = await api.get_user(telegram_id)
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from decimal import Decimal
import logging

from bot.api_client import get_api_client
from bot.config import API_BASE_URL, INTERNAL_API_TOKEN, is_worker

logger = logging.getLogger(__name__)
router = Router()

# Инициализация API клиента (singleton)
api = get_api_client(API_BASE_URL, INTERNAL_API_TOKEN)


# ============ SHIFT COMMANDS ============

@router.message(Command("in"))
async def shift_start_command(message: Message):
    """
    Начать смену (/in).
    
    СТАРЫЙ КОД:
        from api.crud_shifts import create_shift
        shift = create_shift(db, user_id, ...)
    
    НОВЫЙ КОД:
        shift = await api.start_shift(user_id)
    """
    if not is_worker(message.from_user.id):
        await message.answer("❌ Доступно только для рабочих")
        return
    
    try:
        # Проверяем, нет ли активной смены
        active = await api.get_active_shift(message.from_user.id)
        if active:
            await message.answer(
                f"⚠️ У вас уже есть активная смена #{active['id']}\n"
                f"Начало: {active['start_time']}"
            )
            return
        
        # Начинаем новую смену
        shift = await api.start_shift(message.from_user.id)
        
        await message.answer(
            f"✅ Смена #{shift['id']} начата\n"
            f"Время: {shift['start_time']}"
        )
        
    except Exception as e:
        logger.error(f"Failed to start shift: {e}")
        await message.answer(f"❌ Ошибка при начале смены: {str(e)}")


@router.message(Command("out"))
async def shift_end_command(message: Message):
    """Завершить смену (/out)."""
    if not is_worker(message.from_user.id):
        await message.answer("❌ Доступно только для рабочих")
        return
    
    try:
        shift = await api.end_shift(message.from_user.id)
        
        duration_hours = shift.get('duration_hours', 0)
        total_tasks = shift.get('tasks_count', 0)
        
        await message.answer(
            f"✅ Смена #{shift['id']} завершена\n"
            f"Длительность: {duration_hours:.1f} ч\n"
            f"Задач выполнено: {total_tasks}"
        )
        
    except Exception as e:
        logger.error(f"Failed to end shift: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


# ============ TASK COMMANDS ============

@router.message(Command("task"))
async def create_task_command(message: Message, state: FSMContext):
    """
    Создать задачу (/task).
    
    Можно упростить FSM, используя API для валидации.
    """
    if not is_worker(message.from_user.id):
        await message.answer("❌ Доступно только для рабочих")
        return
    
    # Проверяем активную смену через API
    try:
        active_shift = await api.get_active_shift(message.from_user.id)
        if not active_shift:
            await message.answer("❌ Сначала начните смену: /in")
            return
    except Exception as e:
        logger.error(f"Failed to check active shift: {e}")
        await message.answer("❌ Ошибка проверки смены")
        return
    
    # Запускаем FSM для ввода задачи
    await message.answer(
        "📝 Введите название задачи:"
    )
    # ... FSM states


# ============ EXPENSE COMMANDS ============

@router.message(Command("expense"))
async def create_expense_command(message: Message):
    """
    Добавить расход (/expense).
    
    ПРЕИМУЩЕСТВО: API сам валидирует OCR policy и другие правила.
    """
    if not is_worker(message.from_user.id):
        await message.answer("❌ Доступно только для рабочих")
        return
    
    await message.answer(
        "💰 Введите сумму расхода (например, 150):"
    )
    # ... FSM для ввода суммы, категории, фото


# ============ ADMIN COMMANDS (FOREMAN) ============

@router.message(Command("inbox"))
async def inbox_command(message: Message):
    """
    Inbox для модерации (/inbox).
    
    ПРЕИМУЩЕСТВО: Единая логика модерации в API,
    бот только отображает UI.
    """
    from bot.config import is_foreman
    
    if not is_foreman(message.from_user.id):
        await message.answer("❌ Доступно только для прорабов")
        return
    
    try:
        # Получаем элементы на модерации
        result = await api.get_pending_items(limit=5, offset=0)
        
        items = result.get('items', [])
        total = result.get('total', 0)
        
        if not items:
            await message.answer("✅ Нет элементов на модерации")
            return
        
        # Формируем сообщение с кнопками
        text = f"📥 Inbox ({len(items)}/{total}):\n\n"
        
        for item in items:
            text += f"#{item['id']} {item['type']}: {item['title']}\n"
            text += f"  От: {item['author']}\n"
            text += f"  Сумма: {item.get('amount', 'N/A')}\n\n"
        
        # Inline keyboard с кнопками approve/reject
        # ... (как в текущем коде)
        
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Failed to load inbox: {e}")
        await message.answer("❌ Ошибка загрузки inbox")


@router.callback_query(F.data.startswith("approve_"))
async def approve_item_callback(callback: CallbackQuery):
    """Одобрить элемент (callback)."""
    item_id = int(callback.data.split("_")[1])
    
    try:
        result = await api.approve_item(item_id)
        
        await callback.answer(f"✅ Элемент #{item_id} одобрен")
        
        # Обновляем сообщение (убираем элемент из списка)
        # ...
        
    except Exception as e:
        logger.error(f"Failed to approve item {item_id}: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# ============ OLLAMA CHAT (NEW!) ============

@router.message(Command("ask"))
async def ollama_ask_command(message: Message):
    """
    Задать вопрос Ollama (/ask <вопрос>).
    
    НОВЫЙ ФУНКЦИОНАЛ: Прямой доступ к Ollama из Telegram!
    """
    # Извлекаем текст после команды
    text = message.text.replace("/ask", "").strip()
    
    if not text:
        await message.answer(
            "❓ Использование: /ask <вопрос>\n\n"
            "Примеры:\n"
            "• /ask Сколько у меня задач?\n"
            "• /ask Когда последняя смена?\n"
            "• /ask Сколько потрачено за ноябрь?"
        )
        return
    
    # Показываем typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    try:
        # Отправляем запрос через API → Agent → Ollama
        result = await api.chat_query(
            text=text,
            context={
                "user_id": message.from_user.id,
                "username": message.from_user.username
            }
        )
        
        # Форматируем ответ
        answer = result.get("result", "Нет ответа")
        intent = result.get("intent", "unknown")
        
        response_text = f"🤖 Ollama ({intent}):\n\n{answer}"
        
        await message.answer(response_text)
        
    except Exception as e:
        logger.error(f"Ollama query failed: {e}")
        await message.answer(
            "❌ Не удалось получить ответ от Ollama.\n"
            f"Ошибка: {str(e)}"
        )


# ============ USER INFO ============

@router.message(Command("me"))
async def user_info_command(message: Message):
    """
    Информация о пользователе (/me).
    
    ПРЕИМУЩЕСТВО: Не нужно знать структуру БД,
    API возвращает готовые данные.
    """
    try:
        user = await api.get_user(message.from_user.id)
        
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы в системе.\n"
                "Обратитесь к администратору."
            )
            return
        
        # Получаем статистику (если API предоставляет)
        active_shift = await api.get_active_shift(message.from_user.id)
        tasks = await api.get_user_tasks(message.from_user.id, active_only=True)
        
        text = f"👤 {user['full_name'] or user['username']}\n"
        text += f"Роль: {user['role']}\n\n"
        
        if active_shift:
            text += f"⏱ Активная смена: #{active_shift['id']}\n"
            text += f"Начало: {active_shift['start_time']}\n\n"
        
        text += f"📋 Активных задач: {len(tasks)}\n"
        
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        await message.answer("❌ Ошибка получения данных")


# ============ EXPORT ============

def register_handlers(dp):
    """Регистрация всех handlers в dispatcher."""
    dp.include_router(router)
    logger.info("✅ Example handlers registered (with APIClient)")
