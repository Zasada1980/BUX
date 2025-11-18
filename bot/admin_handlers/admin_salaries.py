"""
Admin handlers для управления зарплатами.
Импорт из Excel, просмотр, статистика.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date
import logging
import httpx

from bot.config import API_BASE_URL

router = Router()
logger = logging.getLogger(__name__)

API_BASE = API_BASE_URL.replace("/api", "")  # http://127.0.0.1:8088


class SalaryImportStates(StatesGroup):
    """FSM states для импорта зарплат."""
    waiting_for_excel = State()
    confirm_import = State()


# ========== KEYBOARDS ==========

def get_salary_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню зарплат."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Импорт из Excel", callback_data="sal:import")],
        [InlineKeyboardButton(text="📋 Список зарплат", callback_data="sal:list")],
        [InlineKeyboardButton(text="◀️ Назад в админку", callback_data="adm:panel")]
    ])


def get_import_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения импорта."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить импорт", callback_data="sal:apply")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="sal:menu")]
    ])


# ========== HANDLERS ==========

@router.callback_query(F.data == "adm:salaries")
async def show_salary_menu(callback: CallbackQuery, state: FSMContext):
    """Главное меню управления зарплатами."""
    await state.clear()
    
    text = (
        "💰 <b>Управление зарплатами</b>\n\n"
        "Выберите действие:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_salary_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "sal:menu")
async def back_to_salary_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню зарплат."""
    await show_salary_menu(callback, state)


@router.callback_query(F.data == "sal:import")
async def start_salary_import(callback: CallbackQuery, state: FSMContext):
    """Начало импорта зарплат из Excel."""
    text = (
        "📊 <b>Импорт зарплат из Excel</b>\n\n"
        "Скопируйте данные из Excel в формате:\n"
        "<code>Имя\\tСумма</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>Виталик\\t5000\n"
        "Дима\\t4500.50</code>\n\n"
        "Отправьте текст сообщением:"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state(SalaryImportStates.waiting_for_excel)
    await callback.answer()


@router.message(SalaryImportStates.waiting_for_excel)
async def receive_excel_data(message: Message, state: FSMContext):
    """Получение Excel данных и отображение превью."""
    raw_text = message.text.strip()
    
    # Запрос превью к API
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/admin/salaries/import/preview",
                json={"raw_text": raw_text},
                timeout=10.0
            )
            response.raise_for_status()
            preview_data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"API error during salary preview: {e}")
            await message.answer(
                "❌ Ошибка при обработке данных. Попробуйте снова.",
                reply_markup=get_salary_menu_keyboard()
            )
            await state.clear()
            return
    
    # Формирование превью таблицы
    preview_items = preview_data["preview"]
    matched_count = preview_data["matched_count"]
    total_count = preview_data["total_count"]
    
    # Построение таблицы
    table_lines = ["<b>Превью импорта:</b>\n"]
    for item in preview_items[:10]:  # Показываем первые 10
        status_icon = "✅" if item["status"] == "matched" else \
                      "❌" if item["status"] == "no_match" else "⚠️"
        amount_str = f"₪{item['amount']}" if item['amount'] else "—"
        worker_name = item["worker_name"] or "НЕ НАЙДЕН"
        table_lines.append(
            f"{status_icon} {item['name']} → {amount_str} ({worker_name})"
        )
    
    if len(preview_items) > 10:
        table_lines.append(f"\n... и ещё {len(preview_items) - 10} строк")
    
    table_lines.append(f"\n📊 <b>Итого:</b> {matched_count}/{total_count} совпадений")
    
    text = "\n".join(table_lines)
    
    # Сохраняем данные в state для применения
    await state.update_data(raw_text=raw_text, preview=preview_data)
    await state.set_state(SalaryImportStates.confirm_import)
    
    await message.answer(
        text,
        reply_markup=get_import_confirm_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "sal:apply", SalaryImportStates.confirm_import)
async def apply_salary_import(callback: CallbackQuery, state: FSMContext):
    """Применение импорта зарплат в БД."""
    data = await state.get_data()
    raw_text = data.get("raw_text")
    
    if not raw_text:
        await callback.answer("❌ Данные не найдены", show_alert=True)
        return
    
    # Дата выплаты — сегодня
    payment_date = date.today().isoformat()
    
    # Запрос к API для применения
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/admin/salaries/import/apply",
                json={"raw_text": raw_text, "payment_date": payment_date},
                timeout=15.0
            )
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPError as e:
            logger.error(f"API error during salary import: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при сохранении данных.",
                reply_markup=get_salary_menu_keyboard()
            )
            await state.clear()
            await callback.answer()
            return
    
    imported = result["imported"]
    skipped = result["skipped"]
    message_text = result["message"]
    
    text = (
        f"<b>{message_text}</b>\n\n"
        f"✅ Импортировано: {imported}\n"
        f"⏭️ Пропущено: {skipped}\n"
        f"📅 Дата: {payment_date}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_salary_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer("✅ Импорт завершён")


@router.callback_query(F.data == "sal:list")
async def show_salary_list(callback: CallbackQuery):
    """Список последних зарплат."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE}/api/admin/salaries/list",
                params={"limit": 20},
                timeout=10.0
            )
            response.raise_for_status()
            salaries = response.json()
        except httpx.HTTPError as e:
            logger.error(f"API error fetching salaries: {e}")
            await callback.answer("❌ Ошибка загрузки данных", show_alert=True)
            return
    
    if not salaries:
        text = "📋 <b>Список зарплат</b>\n\nЗаписей нет."
    else:
        lines = ["📋 <b>Последние зарплаты:</b>\n"]
        for s in salaries[:15]:
            lines.append(
                f"• {s['worker_name']}: {s['amount']} ({s['date']})"
            )
        if len(salaries) > 15:
            lines.append(f"\n... и ещё {len(salaries) - 15}")
        text = "\n".join(lines)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_salary_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
