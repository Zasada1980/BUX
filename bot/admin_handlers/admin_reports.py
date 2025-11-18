"""Admin handlers for monthly reports (Phase 2)."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from datetime import datetime
import httpx
import os
import tempfile

from bot.config import API_BASE_URL

router = Router()


def get_last_6_months():
    """Генерирует список последних 6 месяцев в формате YYYY-MM."""
    from datetime import date
    
    today = date.today()
    months = []
    year, month = today.year, today.month
    
    for i in range(6):
        months.append(f"{year}-{month:02d}")
        # Перейти к предыдущему месяцу
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    
    return months


@router.callback_query(F.data == "adm:reports")
async def show_reports_menu(callback_query: CallbackQuery):
    """Показать меню отчётов."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Месячный отчёт", callback_data="rep:monthly")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="adm:panel")]
    ])
    
    await callback_query.message.edit_text(
        "📊 <b>Отчёты</b>\n\n"
        "Выберите тип отчёта:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "rep:monthly")
async def select_month_for_report(callback_query: CallbackQuery):
    """Выбор месяца для отчёта."""
    months = get_last_6_months()
    
    # Создаём клавиатуру с последними 6 месяцами
    keyboard_rows = []
    month_names = {
        "01": "Январь", "02": "Февраль", "03": "Март",
        "04": "Апрель", "05": "Май", "06": "Июнь",
        "07": "Июль", "08": "Август", "09": "Сентябрь",
        "10": "Октябрь", "11": "Ноябрь", "12": "Декабрь"
    }
    
    for month in months:
        year, m = month.split('-')
        month_name = month_names.get(m, m)
        label = f"{month_name} {year}"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"rep:download:{month}"
            )
        ])
    
    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="adm:reports")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback_query.message.edit_text(
        "📅 <b>Выберите месяц</b>\n\n"
        "Для какого месяца сформировать отчёт?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rep:download:"))
async def download_monthly_report(callback_query: CallbackQuery):
    """Скачать месячный отчёт в CSV."""
    month = callback_query.data.split(":")[-1]  # Извлекаем YYYY-MM
    
    # Показываем индикатор загрузки
    await callback_query.answer("⌛ Формирую отчёт...", show_alert=False)
    
    try:
        # Запрос к API для генерации CSV
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/api/admin/reports/monthly.csv",
                params={"month": month}
            )
            
            if response.status_code != 200:
                await callback_query.message.answer(
                    f"❌ Ошибка при формировании отчёта: {response.status_code}"
                )
                return
            
            # Сохраняем CSV во временный файл
            csv_content = response.content
            
            # Создаём временный файл для отправки
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv') as tmp_file:
                tmp_file.write(csv_content)
                tmp_path = tmp_file.name
            
            # Отправляем файл пользователю
            csv_file = FSInputFile(tmp_path, filename=f"monthly_report_{month}.csv")
            
            await callback_query.message.answer_document(
                document=csv_file,
                caption=f"📄 Месячный отчёт за {month}\n\n"
                        f"✅ Файл готов для загрузки"
            )
            
            # Удаляем временный файл
            os.unlink(tmp_path)
            
            # Возвращаемся к меню месяцев
            await select_month_for_report(callback_query)
            
    except httpx.TimeoutException:
        await callback_query.message.answer(
            "⏱️ Превышено время ожидания. Попробуйте позже."
        )
    except Exception as e:
        await callback_query.message.answer(
            f"❌ Ошибка при формировании отчёта: {str(e)}"
        )
