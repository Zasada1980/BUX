"""Sprint D Bot - Main entry point."""
import asyncio
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot.config import TELEGRAM_BOT_TOKEN, BOT_ADMINS, API_BASE_URL, AGENT_URL, record_bot_metric, is_foreman, is_worker, is_admin
from bot.handlers import router as inbox_router
from bot.agent_handlers import register_agent_handlers
from bot.wizards import router as wizard_router  # H-BOT-2: FSM wizards
from bot.bulk_approve import router as bulk_router  # H-BOT-1: Bulk approve
from bot.channel import router as channel_router  # H-CHAN-1: Channel preview cards
from bot.admin_handlers.admin_users import router as admin_users_router  # UI-3: User management (RESTORED)
from bot.admin_handlers.admin_user_card import router as admin_card_router  # UI-3: User card UI (RESTORED)
from bot.admin_handlers.admin_add_user import router as admin_add_router  # UI-3: Add user wizard (RESTORED)
from bot.admin_handlers.admin_clients import router as admin_clients_router  # Client management (RESTORED)
from bot.admin_panel import router as admin_panel_router  # Admin panel with /admin command
from bot.schedule_parser import router as schedule_router  # Schedule parsing from channel
from bot.worker_handlers import router as worker_router  # Worker panel with buttons
from bot.foreman_handlers import foreman_router  # Foreman panel (RESTORED)
from bot.test_api_handler import router as test_api_router  # APIClient test handler

# File logging for background process
log_dir = Path(__file__).parent.parent / "logs" / "bot"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "bot.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler(log_file, encoding='utf-8')  # File output
    ]
)
logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    
    # Extract deep link parameter if present
    command_args = message.text.split(maxsplit=1)
    deep_link_param = command_args[1] if len(command_args) > 1 else None
    
    logger.info(f"🔍 /start from user_id={user_id}, username={username}, deep_link={deep_link_param}, is_worker={is_worker(user_id)}")
    
    # STEP 0: Handle invite deep link
    if deep_link_param and deep_link_param.startswith("invite_"):
        try:
            import base64
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from api.models_users import User
            from bot.config import DB_PATH
            
            # Decode invite token
            invite_token = deep_link_param.replace("invite_", "")
            # Add padding if needed
            padding = 4 - (len(invite_token) % 4)
            if padding != 4:
                invite_token += "=" * padding
            
            decoded = base64.urlsafe_b64decode(invite_token).decode()
            worker_id = int(decoded.split(":")[0])
            
            logger.info(f"🔗 Processing invite for worker_id={worker_id}, telegram_id={user_id}")
            
            # Direct DB connection
            engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            db = SessionLocal()
            
            try:
                # Find worker by ID
                worker = db.query(User).filter(
                    User.id == worker_id,
                    User.active == True
                ).first()
                
                if worker:
                    # Check if already registered
                    if worker.telegram_id and worker.telegram_id != user_id:
                        await message.answer(
                            "⚠️ <b>Эта приглашение уже использовано</b>\n\n"
                            "Аккаунт привязан к другому Telegram.\n"
                            "Обратитесь к администратору.",
                            parse_mode="HTML"
                        )
                        return
                    
                    # Link telegram_id
                    worker.telegram_id = user_id
                    db.commit()
                    db.refresh(worker)
                    
                    logger.info(f"✅ Invite processed: worker {worker.id} linked to telegram_id {user_id}")
                    
                    # Send welcome message
                    salary_info = f"💰 Ваша дневная зарплата: ₪{worker.daily_salary:.2f}" if worker.daily_salary else ""
                    
                    welcome_msg = (
                        f"✅ <b>Добро пожаловать на работу, {worker.name}!</b>\n\n"
                        f"{salary_info}\n"
                        f"📱 Ваш Telegram успешно привязан к системе учёта.\n\n"
                        f"<b>Доступные команды:</b>\n"
                        f"• /shift_in - начать смену\n"
                        f"• /new_task - создать задачу\n"
                        f"• /new_expense - добавить расход\n"
                        f"• /shift_out - завершить смену\n"
                        f"• /me - моя карточка\n\n"
                        f"Удачной работы! 👷"
                    )
                    await message.answer(welcome_msg, parse_mode="HTML")
                    return
                else:
                    await message.answer(
                        "❌ <b>Приглашение недействительно</b>\n\n"
                        "Пользователь не найден или деактивирован.\n"
                        "Обратитесь к администратору.",
                        parse_mode="HTML"
                    )
                    return
            finally:
                db.close()
        except Exception as e:
            logger.error(f"❌ Invite link processing failed: {e}")
            await message.answer(
                "❌ <b>Ошибка обработки приглашения</b>\n\n"
                "Неверный формат ссылки или истекший токен.\n"
                "Запросите новую ссылку у администратора.",
                parse_mode="HTML"
            )
            return
    
    # STEP 1: Sync users from web interface via Ollama agent
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{AGENT_URL}/v1/agent/sync-users")
            if response.status_code == 200:
                sync_result = response.json()
                logger.info(f"✅ Agent sync: {sync_result.get('synced', 0)} users, {sync_result.get('created', 0)} created")
            else:
                logger.warning(f"⚠️ Agent sync failed: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Agent sync error: {e}")
    
    # STEP 2: AUTO-LINK: Check if user is already registered by telegram_id OR auto-link by username
    if not is_worker(user_id):
        logger.info(f"🔄 Checking worker registration for user_id={user_id}, username={username}")
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from api.models_users import User
            from bot.config import DB_PATH
            
            # Direct DB connection (use unified DB_PATH)
            engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            db = SessionLocal()
            
            try:
                worker = None
                
                # VARIANT 1: Check if worker already registered by telegram_id (admin added by phone)
                worker = db.query(User).filter(
                    User.telegram_id == user_id,
                    User.active == True
                ).first()
                
                if worker:
                    logger.info(f"✅ Found worker {worker.id} by telegram_id={user_id}")
                    # Send welcome message
                    welcome_msg = (
                        f"✅ <b>Добро пожаловать на работу, {worker.name}!</b>\n\n"
                        f"💰 Ваша дневная зарплата: ₪{worker.daily_salary:.2f}\n"
                        f"📱 Ваш Telegram успешно привязан\n\n"
                        f"<b>Доступные команды:</b>\n"
                        f"• /shift_in - начать смену\n"
                        f"• /new_task - создать задачу\n"
                        f"• /new_expense - добавить расход\n"
                        f"• /shift_out - завершить смену\n"
                        f"• /me - моя карточка\n\n"
                        f"Удачной работы! 👷"
                    )
                    await message.answer(welcome_msg, parse_mode="HTML")
                    return
                
                # VARIANT 2: Auto-link by telegram_username if not found by ID
                if username:
                    worker = db.query(User).filter(
                        User.telegram_username == username,
                        User.telegram_id == None,
                        User.active == True
                    ).first()
                    
                    if worker:
                        # Auto-link telegram_id
                        worker.telegram_id = user_id
                        db.commit()
                        db.refresh(worker)
                        
                        logger.info(f"✅ Auto-linked telegram_id {user_id} to worker {worker.id} (@{username})")
                        
                        # Send welcome message
                        welcome_msg = (
                            f"✅ <b>Добро пожаловать на работу, {worker.name}!</b>\n\n"
                            f"💰 Ваша дневная зарплата: ₪{worker.daily_salary:.2f}\n"
                            f"📱 Ваш Telegram успешно привязан\n\n"
                            f"<b>Доступные команды:</b>\n"
                            f"• /shift_in - начать смену\n"
                            f"• /new_task - создать задачу\n"
                            f"• /new_expense - добавить расход\n"
                            f"• /shift_out - завершить смену\n"
                            f"• /me - моя карточка\n\n"
                            f"Удачной работы! 👷"
                        )
                        await message.answer(welcome_msg, parse_mode="HTML")
                        return
            finally:
                db.close()
        except Exception as e:
            logger.error(f"❌ Auto-link check failed: {e}")
    
    # Standard role-based welcome
    if is_foreman(user_id):
        await message.answer(
            "🔧 Бригадир-бот\n\n"
            "<b>Команды:</b>\n"
            "• /inbox - входящие задачи\n"
            "  → Используйте кнопку '☑ Массовый выбор' для bulk approve\n"
            "• /explain - разбор задачи"
        )
    elif is_worker(user_id):
        # Send to worker panel instead of old message
        await message.answer(
            "👷 <b>Панель рабочего</b>\n\n"
            "Используйте команду /worker для доступа к панели управления",
            parse_mode="HTML"
        )
    else:
        await message.answer("👋 Привет! Используйте /start для начала.")

# Catch-all for unknown users (anti-spam) - MUST be LAST
@router.message()
async def catch_unknown(message: Message):
    uid = message.from_user.id if message.from_user else 0
    
    # Check if user is in any ACL
    if not (is_admin(uid) or is_foreman(uid) or is_worker(uid)):
        record_bot_metric("unknown_user", {"user_id": uid, "username": message.from_user.username if message.from_user else None})
        # Silently ignore unknown users (no response)
        return

async def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return
    logger.info("Starting bot")
    record_bot_metric("startup", {})
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Set bot commands menu for admins and workers
    from aiogram.types import BotCommand, BotCommandScopeChat
    admin_commands = [
        BotCommand(command="admin", description="🔧 Админ-панель"),
        BotCommand(command="users", description="👥 Управление пользователями"),
        BotCommand(command="add_user", description="➕ Добавить пользователя"),
        BotCommand(command="salaries", description="💰 Управление зарплатами"),
        BotCommand(command="clients", description="🏢 Управление клиентами"),
        BotCommand(command="reports", description="📊 Отчёты"),
        BotCommand(command="inbox", description="📥 Входящие (модерация)"),
        BotCommand(command="start", description="🏠 Начало работы"),
    ]
    
    foreman_commands = [
        BotCommand(command="foreman", description="🔧 Панель бригадира"),
        BotCommand(command="worker", description="👷 Панель рабочего"),
        BotCommand(command="inbox", description="📥 Входящие (модерация)"),
        BotCommand(command="start", description="🏠 Начало работы"),
    ]
    
    worker_commands = [
        BotCommand(command="worker", description="👷 Панель рабочего"),
        BotCommand(command="start", description="🏠 Начало работы"),
    ]
    
    # Set commands for each admin
    for admin_id in BOT_ADMINS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info(f"✅ Admin menu set for {admin_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to set admin menu for {admin_id}: {e}")
    
    # Set commands for each foreman
    from bot.config import BOT_FOREMEN
    for foreman_id in BOT_FOREMEN:
        try:
            await bot.set_my_commands(foreman_commands, scope=BotCommandScopeChat(chat_id=foreman_id))
            logger.info(f"✅ Foreman menu set for {foreman_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to set foreman menu for {foreman_id}: {e}")
    
    # Worker menu will be set on first /worker command
    logger.info("✅ Bot commands configured")
    
    dp = Dispatcher()
    dp.include_router(test_api_router)  # TEST: APIClient verification (must be early for /test_api)
    dp.include_router(wizard_router)  # H-BOT-2: Must be FIRST for FSM priority
    dp.include_router(admin_add_router)  # UI-3: Add user wizard (FSM states) - RESTORED
    dp.include_router(admin_clients_router)  # Client management (FSM states) - RESTORED
    dp.include_router(admin_panel_router)  # Admin panel with /admin command
    dp.include_router(worker_router)  # Worker panel (FSM states for tasks/expenses)
    dp.include_router(foreman_router)  # Foreman panel - RESTORED
    dp.include_router(schedule_router)  # Schedule parsing and viewing
    dp.include_router(bulk_router)     # H-BOT-1: Bulk approve (before inbox for bulk_* handlers)
    dp.include_router(channel_router)  # H-CHAN-1: Channel callback handlers
    dp.include_router(admin_users_router)  # UI-3: User management (list, filters) - RESTORED
    dp.include_router(admin_card_router)  # UI-3: User card (view, edit, delete) - RESTORED
    dp.include_router(router)
    dp.include_router(inbox_router)
    register_agent_handlers(dp)  # Register worker commands: /in /task /expense /out /me
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
