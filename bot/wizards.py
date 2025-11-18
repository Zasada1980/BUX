"""
H-BOT-2: FSM Wizards для Worker - пошаговое создание task/expense/shift.

Features:
- Task wizard: name → description → confirm
- Expense wizard: amount → category → photo (optional) → confirm
- Shift wizard: улучшенные /shift_in и /shift_out
- Idempotency: wizard_session_id для защиты от дублей
- Validation: OCR policy, amount checks
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import aiohttp
import uuid
from datetime import datetime, timezone

from bot.config import API_BASE_URL, is_worker, record_bot_metric, AI_AGENT_BASE, AI_EXPENSE_CONF

log = logging.getLogger(__name__)
router = Router()

# ============================================================================
# FSM States
# ============================================================================

class TaskWizard(StatesGroup):
    """Task creation wizard states."""
    waiting_for_name = State()
    waiting_for_description = State()
    confirming = State()


class ExpenseWizard(StatesGroup):
    """Expense creation wizard states."""
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_photo = State()  # Optional if amount > threshold
    confirming = State()


# ============================================================================
# Helpers
# ============================================================================

async def api_post(endpoint: str, data: dict) -> tuple[dict, int]:
    """POST request to API with idempotency support."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    # Add Idempotency-Key if session_id present
    if "session_id" in data:
        headers["Idempotency-Key"] = data["session_id"]
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                body = await resp.json()
                return body, resp.status
        except Exception as e:
            log.error(f"API request failed: {e}")
            return {"error": str(e)}, 500


def generate_session_id() -> str:
    """Generate unique session ID for wizard idempotency."""
    return f"WIZ-{uuid.uuid4().hex[:16]}"


def fmt_money(amount: float, currency: str = "ILS") -> str:
    """Format money amount (RTL-safe)."""
    symbol = "₪" if currency == "ILS" else currency
    return f"{symbol}{amount:,.2f}"


async def _ai_suggest_category(text: str, amount: float) -> tuple[str, float]:
    """AI-powered expense category suggestion via Ollama.
    
    Args:
        text: Expense description or OCR text
        amount: Expense amount
    
    Returns:
        Tuple of (category, confidence) where:
        - category: One of transport/food/materials/communication/other
        - confidence: 0.0-1.0 (1.0 = highest confidence)
    """
    if not AI_AGENT_BASE:
        log.debug("AI_AGENT_BASE not configured, skipping AI categorization")
        return "unknown", 0.0
    
    try:
        prompt = (
            f"Categorize this expense:\n"
            f"Description: {text}\n"
            f"Amount: {amount} ILS\n\n"
            f"Available categories: transport, food, materials, communication, other\n"
            f"Return ONLY JSON: {{\"category\": \"...\", \"confidence\": 0.0-1.0}}"
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{AI_AGENT_BASE}/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    log.warning(f"AI categorization failed: HTTP {resp.status}")
                    return "unknown", 0.0
                
                data = await resp.json()
                response_text = data.get("response", "")
                
                # Parse JSON from response
                import json
                try:
                    # Try to extract JSON from response
                    start = response_text.find("{")
                    end = response_text.rfind("}") + 1
                    if start >= 0 and end > start:
                        result = json.loads(response_text[start:end])
                        category = result.get("category", "unknown")
                        confidence = float(result.get("confidence", 0.0))
                        
                        # Validate category
                        valid_categories = {"transport", "food", "materials", "communication", "other"}
                        if category not in valid_categories:
                            category = "other"
                        
                        log.info(f"AI categorization: {category} (conf={confidence:.2f})")
                        record_bot_metric("ai.categorize.success", {
                            "category": category,
                            "confidence": confidence,
                            "amount": amount
                        })
                        return category, confidence
                except (json.JSONDecodeError, ValueError) as e:
                    log.warning(f"Failed to parse AI response: {e}")
        
        return "unknown", 0.0
        
    except Exception as e:
        log.error(f"AI categorization error: {e}")
        record_bot_metric("ai.categorize.error", {"error": str(e)})
        return "unknown", 0.0


# ============================================================================
# Task Wizard
# ============================================================================

@router.message(Command("new_task"))
async def start_task_wizard(message: Message, state: FSMContext):
    """Start task creation wizard."""
    user_id = message.from_user.id if message.from_user else 0
    
    if not is_worker(user_id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    # Initialize wizard session
    session_id = generate_session_id()
    await state.update_data(
        session_id=session_id,
        user_id=str(user_id),
        started_at=datetime.now(timezone.utc).isoformat()
    )
    
    await state.set_state(TaskWizard.waiting_for_name)
    
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
    
    await message.answer(
        "📝 <b>Новая задача</b>\n\n"
        "Шаг 1/3: Название задачи\n"
        "Введите краткое название (до 50 символов):",
        reply_markup=cancel_kb
    )
    
    record_bot_metric("wizard.task.start", {"user_id": user_id, "session_id": session_id})


@router.message(TaskWizard.waiting_for_name)
async def task_wizard_name(message: Message, state: FSMContext):
    """Process task name input."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание задачи отменено", reply_markup=ReplyKeyboardRemove())
        record_bot_metric("wizard.task.cancel", {"step": "name"})
        return
    
    name = message.text.strip()
    
    # Validation
    if len(name) < 3:
        await message.answer("❌ Название слишком короткое (минимум 3 символа)")
        return
    
    if len(name) > 50:
        await message.answer("❌ Название слишком длинное (максимум 50 символов)")
        return
    
    await state.update_data(task_name=name)
    await state.set_state(TaskWizard.waiting_for_description)
    
    await message.answer(
        f"✅ Название: <b>{name}</b>\n\n"
        "Шаг 2/3: Описание задачи\n"
        "Введите подробное описание (до 500 символов):"
    )


@router.message(TaskWizard.waiting_for_description)
async def task_wizard_description(message: Message, state: FSMContext):
    """Process task description input."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание задачи отменено", reply_markup=ReplyKeyboardRemove())
        record_bot_metric("wizard.task.cancel", {"step": "description"})
        return
    
    description = message.text.strip()
    
    # Validation
    if len(description) < 5:
        await message.answer("❌ Описание слишком короткое (минимум 5 символов)")
        return
    
    if len(description) > 500:
        await message.answer("❌ Описание слишком длинное (максимум 500 символов)")
        return
    
    data = await state.get_data()
    await state.update_data(task_description=description)
    await state.set_state(TaskWizard.confirming)
    
    confirm_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Создать"), KeyboardButton(text="✏️ Изменить")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "📋 <b>Проверьте данные:</b>\n\n"
        f"📌 Название: <b>{data['task_name']}</b>\n"
        f"📝 Описание: {description}\n\n"
        "Всё верно?",
        reply_markup=confirm_kb
    )


@router.message(TaskWizard.confirming)
async def task_wizard_confirm(message: Message, state: FSMContext):
    """Confirm and create task."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание задачи отменено", reply_markup=ReplyKeyboardRemove())
        record_bot_metric("wizard.task.cancel", {"step": "confirm"})
        return
    
    if message.text == "✏️ Изменить":
        await state.set_state(TaskWizard.waiting_for_name)
        await message.answer("📝 Введите название задачи заново:")
        return
    
    if message.text != "✅ Создать":
        await message.answer("❌ Неверная команда. Выберите кнопку ниже.")
        return
    
    data = await state.get_data()
    
    # API request with idempotency
    payload = {
        "user_id": data["user_id"],
        "name": data["task_name"],
        "description": data["task_description"],
        "category": "general",
        "session_id": data["session_id"]
    }
    
    await message.answer("⏳ Создаю задачу...", reply_markup=ReplyKeyboardRemove())
    
    result, status = await api_post("/task.add", payload)
    
    if status == 200:
        task_id = result.get("task_id")
        await message.answer(
            f"✅ <b>Задача создана!</b>\n\n"
            f"🆔 ID: {task_id}\n"
            f"📌 {data['task_name']}\n"
            f"📝 {data['task_description']}"
        )
        record_bot_metric("wizard.task.complete", {"task_id": task_id, "session_id": data["session_id"]})
    else:
        error = result.get("error", "Unknown error")
        await message.answer(f"❌ Ошибка создания: {error}")
        record_bot_metric("wizard.task.error", {"error": error})
    
    await state.clear()


# ============================================================================
# Expense Wizard
# ============================================================================

@router.message(Command("new_expense"))
async def start_expense_wizard(message: Message, state: FSMContext):
    """Start expense creation wizard."""
    user_id = message.from_user.id if message.from_user else 0
    
    if not is_worker(user_id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    session_id = generate_session_id()
    await state.update_data(
        session_id=session_id,
        user_id=str(user_id),
        started_at=datetime.now(timezone.utc).isoformat()
    )
    
    await state.set_state(ExpenseWizard.waiting_for_amount)
    
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
    
    await message.answer(
        "💰 <b>Новый расход</b>\n\n"
        "Шаг 1/4: Сумма\n"
        "Введите сумму в шекелях (ILS):\n"
        "Пример: 150.50",
        reply_markup=cancel_kb
    )
    
    record_bot_metric("wizard.expense.start", {"user_id": user_id, "session_id": session_id})


@router.message(ExpenseWizard.waiting_for_amount)
async def expense_wizard_amount(message: Message, state: FSMContext):
    """Process expense amount input."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление расхода отменено", reply_markup=ReplyKeyboardRemove())
        record_bot_metric("wizard.expense.cancel", {"step": "amount"})
        return
    
    try:
        amount = float(message.text.replace(",", ".").strip())
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля")
            return
        
        if amount > 100000:
            await message.answer("❌ Сумма слишком большая (максимум 100,000 ILS)")
            return
        
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число, например: 150.50")
        return
    
    await state.update_data(expense_amount=amount)
    
    # AI Categorization (если настроен AI_AGENT_BASE)
    ai_category = None
    ai_confidence = 0.0
    if AI_AGENT_BASE:
        # Try AI categorization with amount + optional previous description
        data = await state.get_data()
        description = data.get("expense_description", "")
        ai_category, ai_confidence = await _ai_suggest_category(description or f"Amount: {amount}", amount)
    
    await state.set_state(ExpenseWizard.waiting_for_category)
    
    category_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚗 Транспорт"), KeyboardButton(text="🍽️ Еда")],
            [KeyboardButton(text="🛠️ Материалы"), KeyboardButton(text="📱 Связь")],
            [KeyboardButton(text="🏢 Другое"), KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    
    # Build response with AI suggestion if confident
    response_lines = [f"✅ Сумма: <b>{fmt_money(amount)}</b>"]
    
    if ai_category and ai_category != "unknown" and ai_confidence >= AI_EXPENSE_CONF:
        # High confidence — suggest category
        category_emoji_map = {
            "transport": "🚗 Транспорт",
            "food": "🍽️ Еда",
            "materials": "🛠️ Материалы",
            "communication": "📱 Связь",
            "other": "🏢 Другое"
        }
        ai_display = category_emoji_map.get(ai_category, "🏢 Другое")
        response_lines.append(f"\n🤖 <b>ИИ предлагает:</b> {ai_display} (уверенность: {ai_confidence*100:.0f}%)")
        response_lines.append("Вы можете выбрать эту категорию или другую ниже.")
        await state.update_data(ai_suggested_category=ai_category, ai_confidence=ai_confidence)
    elif ai_category and ai_category != "unknown":
        # Low/medium confidence — inform but don't push
        response_lines.append(f"\n🤖 ИИ не уверен в категории (уверенность: {ai_confidence*100:.0f}%)")
    
    response_lines.append("\nШаг 2/4: Категория")
    response_lines.append("Выберите категорию расхода:")
    
    await message.answer(
        "\n".join(response_lines),
        reply_markup=category_kb
    )


@router.message(ExpenseWizard.waiting_for_category)
async def expense_wizard_category(message: Message, state: FSMContext):
    """Process expense category input."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление расхода отменено", reply_markup=ReplyKeyboardRemove())
        record_bot_metric("wizard.expense.cancel", {"step": "category"})
        return
    
    # Map user-friendly names to API categories
    category_map = {
        "🚗 Транспорт": "transport",
        "🍽️ Еда": "food",
        "🛠️ Материалы": "materials",
        "📱 Связь": "communication",
        "🏢 Другое": "other"
    }
    
    category = category_map.get(message.text)
    if not category:
        await message.answer("❌ Неверная категория. Выберите кнопку ниже.")
        return
    
    data = await state.get_data()
    amount = data["expense_amount"]
    
    await state.update_data(expense_category=category, expense_category_display=message.text)
    
    # Check OCR policy (if amount > threshold, require photo)
    OCR_THRESHOLD = 1000.0  # ILS
    
    if amount > OCR_THRESHOLD:
        await state.set_state(ExpenseWizard.waiting_for_photo)
        
        photo_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
        
        await message.answer(
            f"✅ Категория: <b>{message.text}</b>\n\n"
            f"⚠️ Сумма {fmt_money(amount)} > {fmt_money(OCR_THRESHOLD)}\n"
            "Шаг 3/4: Фото чека\n"
            "Прикрепите фото чека (обязательно):",
            reply_markup=photo_kb
        )
    else:
        # Skip photo step
        await state.set_state(ExpenseWizard.confirming)
        await show_expense_confirmation(message, state)


@router.message(ExpenseWizard.waiting_for_photo, F.photo)
async def expense_wizard_photo(message: Message, state: FSMContext):
    """Process expense photo (receipt)."""
    if not message.photo:
        await message.answer("❌ Отправьте фото чека")
        return
    
    # Get largest photo
    photo = message.photo[-1]
    photo_file_id = photo.file_id
    
    await state.update_data(expense_photo_ref=photo_file_id)
    await state.set_state(ExpenseWizard.confirming)
    
    await message.answer("✅ Фото получено")
    await show_expense_confirmation(message, state)


@router.message(ExpenseWizard.waiting_for_photo)
async def expense_wizard_photo_text(message: Message, state: FSMContext):
    """Handle text when photo expected."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление расхода отменено", reply_markup=ReplyKeyboardRemove())
        record_bot_metric("wizard.expense.cancel", {"step": "photo"})
        return
    
    await message.answer("❌ Отправьте фото чека или нажмите 'Отмена'")


async def show_expense_confirmation(message: Message, state: FSMContext):
    """Show expense confirmation screen."""
    data = await state.get_data()
    
    confirm_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Создать"), KeyboardButton(text="✏️ Изменить")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    
    photo_status = "✅ Прикреплено" if data.get("expense_photo_ref") else "❌ Нет фото"
    
    await message.answer(
        "📋 <b>Проверьте данные:</b>\n\n"
        f"💰 Сумма: <b>{fmt_money(data['expense_amount'])}</b>\n"
        f"📁 Категория: {data['expense_category_display']}\n"
        f"📸 Фото: {photo_status}\n\n"
        "Всё верно?",
        reply_markup=confirm_kb
    )


@router.message(ExpenseWizard.confirming)
async def expense_wizard_confirm(message: Message, state: FSMContext):
    """Confirm and create expense."""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление расхода отменено", reply_markup=ReplyKeyboardRemove())
        record_bot_metric("wizard.expense.cancel", {"step": "confirm"})
        return
    
    if message.text == "✏️ Изменить":
        await state.set_state(ExpenseWizard.waiting_for_amount)
        await message.answer("💰 Введите сумму заново:")
        return
    
    if message.text != "✅ Создать":
        await message.answer("❌ Неверная команда. Выберите кнопку ниже.")
        return
    
    data = await state.get_data()
    
    # API request with idempotency
    payload = {
        "user_id": data["user_id"],
        "amount": data["expense_amount"],
        "currency": "ILS",
        "category": data["expense_category"],
        "photo_ref": data.get("expense_photo_ref"),
        "session_id": data["session_id"]
    }
    
    await message.answer("⏳ Создаю расход...", reply_markup=ReplyKeyboardRemove())
    
    result, status = await api_post("/expense.add", payload)
    
    if status == 200:
        expense_id = result.get("expense_id")
        await message.answer(
            f"✅ <b>Расход добавлен!</b>\n\n"
            f"🆔 ID: {expense_id}\n"
            f"💰 Сумма: {fmt_money(data['expense_amount'])}\n"
            f"📁 Категория: {data['expense_category_display']}"
        )
        record_bot_metric("wizard.expense.complete", {"expense_id": expense_id, "amount": data['expense_amount']})
    elif status == 422:
        # OCR policy violation
        error = result.get("detail", {}).get("error", "OCR required")
        await message.answer(
            f"❌ <b>Ошибка OCR Policy</b>\n\n"
            f"{error}\n\n"
            "Прикрепите фото чека и попробуйте снова."
        )
        record_bot_metric("wizard.expense.ocr_error", {"error": error})
    else:
        error = result.get("error", "Unknown error")
        await message.answer(f"❌ Ошибка создания: {error}")
        record_bot_metric("wizard.expense.error", {"error": error})
    
    await state.clear()


# ============================================================================
# Shift Helpers (улучшенные /shift_in и /shift_out)
# ============================================================================

@router.message(Command("shift_in"))
async def cmd_shift_in(message: Message):
    """Start shift with confirmation."""
    user_id = message.from_user.id if message.from_user else 0
    
    if not is_worker(user_id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    session_id = generate_session_id()
    payload = {
        "user_id": str(user_id),
        "session_id": session_id
    }
    
    result, status = await api_post("/v1/shift/start", payload)
    
    if status == 200:
        shift_id = result.get("shift_id")
        started_at = result.get("started_at", "")
        await message.answer(
            f"✅ <b>Смена начата</b>\n\n"
            f"🆔 ID: {shift_id}\n"
            f"🕐 Начало: {started_at}\n\n"
            "Используйте /new_task и /new_expense для добавления задач и расходов."
        )
        record_bot_metric("shift.start", {"shift_id": shift_id, "user_id": user_id})
    else:
        error = result.get("error", "Unknown error")
        await message.answer(f"❌ Ошибка: {error}")


@router.message(Command("shift_out"))
async def cmd_shift_out(message: Message):
    """End shift with summary."""
    user_id = message.from_user.id if message.from_user else 0
    
    if not is_worker(user_id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    session_id = generate_session_id()
    payload = {
        "user_id": str(user_id),
        "session_id": session_id
    }
    
    result, status = await api_post("/v1/shift/end", payload)
    
    if status == 200:
        shift_id = result.get("shift_id")
        duration_hours = result.get("duration_hours", 0)
        tasks_count = result.get("tasks_count", 0)
        expenses_sum = result.get("expenses_sum", 0)
        
        await message.answer(
            f"✅ <b>Смена завершена</b>\n\n"
            f"🆔 ID: {shift_id}\n"
            f"⏱️ Длительность: {duration_hours:.1f}ч\n"
            f"📋 Задач: {tasks_count}\n"
            f"💰 Расходы: {fmt_money(expenses_sum)}"
        )
        record_bot_metric("shift.end", {"shift_id": shift_id, "duration_hours": duration_hours})
    else:
        error = result.get("error", "Unknown error")
        await message.answer(f"❌ Ошибка: {error}")

