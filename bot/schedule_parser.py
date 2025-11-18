"""Schedule parsing from Telegram channel messages.

Формат сообщения в канале:
📅 Расписание на 15.11.2025

Ваня → ИмяКлиента (или nickname)
Петя → Другой Клиент
...

Примечания: опциональный текст
"""
import re
import logging
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)
router = Router()

engine = create_engine("sqlite:///api/data/workledger.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _parse_schedule_message(text: str):
    """Parse schedule message from channel.
    
    Поддерживаемые форматы:
    1. Простой: "Ваня → NextDoor"
    2. С адресом (3 строки):
       "Виталик, Дима"
       "Офер тель авив"  (адрес)
       Клиент определяется по никнейму "Офер" → NextDoor
    
    Returns:
        dict with keys: 
        - date (str YYYY-MM-DD)
        - assignments (list of tuples (worker_name, client_name, work_address))
        - notes (str)
    """
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    # Find date in first lines (format: DD.MM.YYYY or "завтра")
    date_str = None
    date_obj = None
    date_line_idx = -1
    
    for idx, line in enumerate(lines[:3]):  # Check first 3 lines
        # Match DD.MM.YYYY or D.M.YYYY
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.?(\d{4})?', line)
        if match:
            day, month, year = match.groups()
            year = year or str(datetime.now().year)
            try:
                date_obj = datetime(int(year), int(month), int(day))
                date_str = date_obj.strftime('%Y-%m-%d')
                date_line_idx = idx
                break
            except ValueError:
                continue
        
        # Match "завтра"
        if re.search(r'завтра|tomorrow', line, re.IGNORECASE):
            date_obj = datetime.now() + timedelta(days=1)
            date_str = date_obj.strftime('%Y-%m-%d')
            date_line_idx = idx
            break
    
    if not date_str:
        return None
    
    # Parse assignments
    assignments = []
    notes_lines = []
    in_notes = False
    
    content_lines = lines[date_line_idx + 1:]  # Skip date line
    
    i = 0
    while i < len(content_lines):
        line = content_lines[i]
        
        # Check for notes section
        if re.match(r'примечан|notes|заметк', line, re.IGNORECASE):
            in_notes = True
            i += 1
            continue
        
        if in_notes:
            notes_lines.append(line)
            i += 1
            continue
        
        # Format 1: "WorkerName → ClientName" или "WorkerName -> ClientName"
        match = re.match(r'([А-Яа-яA-Za-z\s]+)\s*[→->]\s*(.+)', line)
        if match:
            worker_names = match.group(1).strip()
            client_name = match.group(2).strip()
            # Split multiple workers by comma
            for worker in re.split(r',\s*', worker_names):
                assignments.append((worker.strip(), client_name, None))
            i += 1
            continue
        
        # Format 2: Multi-line format (workers, address, client inferred)
        # Line 1: "Виталик, Дима" (worker names separated by comma)
        # Line 2: "Офер тель авив" (address with client nickname)
        if ',' in line or (i + 1 < len(content_lines) and not re.search(r'[→->]', content_lines[i + 1])):
            worker_names_line = line
            workers = [w.strip() for w in re.split(r',\s*', worker_names_line)]
            
            # Check if next line is address (doesn't have → and looks like address)
            if i + 1 < len(content_lines):
                next_line = content_lines[i + 1]
                # If next line doesn't have assignment arrow, treat as address
                if not re.search(r'[→->]', next_line):
                    work_address = next_line.strip()
                    # Extract client nickname from address (first word usually)
                    # "Офер тель авив" → client nickname "Офер"
                    address_words = work_address.split()
                    client_nickname = address_words[0] if address_words else None
                    
                    for worker in workers:
                        assignments.append((worker, client_nickname, work_address))
                    
                    i += 2  # Skip both lines
                    continue
        
        i += 1
    
    notes = '\n'.join(notes_lines) if notes_lines else None
    
    return {
        'date': date_str,
        'assignments': assignments,
        'notes': notes
    }


def _find_worker_by_name(name: str):
    """Find worker by name (case-insensitive)."""
    db = SessionLocal()
    try:
        from api.models_users import User
        worker = db.query(User).filter(
            User.name.ilike(f'%{name}%'),
            User.role == 'worker'
        ).first()
        return worker.id if worker else None
    finally:
        db.close()


def _find_client_by_name(name: str):
    """Find client by company name or nickname."""
    db = SessionLocal()
    try:
        from api.models import Client
        # Try exact match first
        client = db.query(Client).filter(
            (Client.company_name.ilike(f'%{name}%')) |
            (Client.nickname1.ilike(f'%{name}%')) |
            (Client.nickname2.ilike(f'%{name}%'))
        ).first()
        return client.id if client else None
    finally:
        db.close()


def _save_schedule(date_str: str, client_id: int, worker_ids: list, work_address: str | None, notes: str | None, created_by: int):
    """Save or update schedule for date and client."""
    db = SessionLocal()
    try:
        from api.models import Schedule
        
        # Check if schedule exists for this date and client
        existing = db.query(Schedule).filter(
            Schedule.date == date_str,
            Schedule.client_id == client_id
        ).first()
        
        worker_ids_str = ','.join(map(str, worker_ids)) if worker_ids else None
        
        if existing:
            # Update
            existing.worker_ids = worker_ids_str  # type: ignore
            existing.work_address = work_address  # type: ignore
            existing.notes = notes  # type: ignore
            existing.created_by = created_by  # type: ignore
        else:
            # Create new
            schedule = Schedule(
                date=date_str,
                client_id=client_id,
                worker_ids=worker_ids_str,
                work_address=work_address,
                notes=notes,
                created_by=created_by
            )
            db.add(schedule)
        
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save schedule: {e}")
        db.rollback()
        return False
    finally:
        db.close()


@router.message(F.text & F.chat.type.in_({"channel", "supergroup"}))
async def parse_channel_schedule(message: Message):
    """Parse schedule messages from channel."""
    text = message.text
    
    if not text:
        return
    
    # Check if message looks like schedule (contains → or ->)
    if '→' not in text and '->' not in text:
        return
    
    # Check if message starts with schedule keyword
    if not re.search(r'расписан|schedule|график', text[:100], re.IGNORECASE):
        return
    
    logger.info(f"Parsing potential schedule message: {text[:50]}...")
    
    parsed = _parse_schedule_message(text)
    if not parsed:
        logger.warning("Failed to parse schedule: no date found")
        return
    
    date_str = parsed['date']
    assignments = parsed['assignments']  # Now: list of (worker_name, client_name, work_address)
    notes = parsed['notes']
    
    if not assignments:
        logger.warning("Failed to parse schedule: no assignments found")
        return
    
    # Get admin user ID for created_by (default to 1)
    created_by = 1  # TODO: get from message.from_user if needed
    
    # Process each assignment
    saved_count = 0
    failed_count = 0
    
    for assignment in assignments:
        worker_name = assignment[0]
        client_name = assignment[1]
        work_address = assignment[2] if len(assignment) > 2 else None
        
        worker_id = _find_worker_by_name(worker_name)
        client_id = _find_client_by_name(client_name)
        
        if not worker_id:
            logger.warning(f"Worker not found: {worker_name}")
            failed_count += 1
            continue
        
        if not client_id:
            logger.warning(f"Client not found: {client_name}")
            failed_count += 1
            continue
        
        # Save schedule
        if _save_schedule(date_str, client_id, [worker_id], work_address, notes, created_by):
            saved_count += 1
        else:
            failed_count += 1
    
    logger.info(f"Schedule parsing complete: {saved_count} saved, {failed_count} failed for {date_str}")


@router.callback_query(F.data == "adm:schedule:view")
async def view_schedule(callback: CallbackQuery, bot: Bot):
    """View schedule for tomorrow (admin command)."""
    db = SessionLocal()
    try:
        from api.models import Schedule, Client
        from api.models_users import User
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        schedules = db.query(Schedule, Client).join(
            Client, Schedule.client_id == Client.id
        ).filter(
            Schedule.date == tomorrow
        ).all()
        
        if not schedules:
            text = f"📅 <b>Расписание на завтра ({tomorrow})</b>\n\n❌ Расписание не найдено"
        else:
            lines = [f"📅 <b>Расписание на завтра ({tomorrow})</b>\n"]
            
            for sched, client in schedules:
                worker_names = []
                if sched.worker_ids:
                    worker_ids = [int(x.strip()) for x in sched.worker_ids.split(',') if x.strip()]
                    for wid in worker_ids:
                        worker = db.query(User).filter(User.id == wid).first()
                        if worker:
                            worker_names.append(worker.name)
                
                workers_str = ', '.join(worker_names) if worker_names else '—'
                lines.append(f"• <b>{client.company_name}</b> ({client.nickname1})")
                lines.append(f"  👷 {workers_str}")
                
                if sched.notes:
                    lines.append(f"  📝 {sched.notes}")
                lines.append("")
            
            text = '\n'.join(lines)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад в админку", callback_data="back_to_admin")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()
