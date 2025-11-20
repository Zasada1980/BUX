"""Seed bot_commands table with default Telegram commands by role."""
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "shifts.db"

# Default commands configuration
COMMANDS = [
    # Admin commands (8 commands)
    {"role": "admin", "command_key": "admin_panel", "telegram_command": "/admin", "label": "🔧 Админ-панель", "description": "Открыть админ-панель", "enabled": True, "is_core": True, "position": 1},
    {"role": "admin", "command_key": "users_mgmt", "telegram_command": "/users", "label": "👥 Управление пользователями", "description": "Список пользователей", "enabled": True, "is_core": False, "position": 2},
    {"role": "admin", "command_key": "add_user", "telegram_command": "/add_user", "label": "➕ Добавить пользователя", "description": "Добавить нового пользователя", "enabled": True, "is_core": False, "position": 3},
    {"role": "admin", "command_key": "salaries_mgmt", "telegram_command": "/salaries", "label": "💰 Управление зарплатами", "description": "Просмотр и корректировка зарплат", "enabled": True, "is_core": False, "position": 4},
    {"role": "admin", "command_key": "clients_mgmt", "telegram_command": "/clients", "label": "🏢 Управление клиентами", "description": "Список клиентов", "enabled": True, "is_core": False, "position": 5},
    {"role": "admin", "command_key": "reports", "telegram_command": "/reports", "label": "📊 Отчёты", "description": "Сгенерировать отчёты", "enabled": True, "is_core": False, "position": 6},
    {"role": "admin", "command_key": "inbox", "telegram_command": "/inbox", "label": "📥 Входящие (модерация)", "description": "Модерация задач и расходов", "enabled": True, "is_core": True, "position": 7},
    {"role": "admin", "command_key": "start", "telegram_command": "/start", "label": "🏠 Начало работы", "description": "Главное меню", "enabled": True, "is_core": True, "position": 8},
    
    # Foreman commands (same as admin for now, can be customized)
    {"role": "foreman", "command_key": "foreman_inbox", "telegram_command": "/inbox", "label": "📥 Входящие", "description": "Модерация задач от рабочих", "enabled": True, "is_core": True, "position": 1},
    {"role": "foreman", "command_key": "foreman_explain", "telegram_command": "/explain", "label": "📖 Разбор задачи", "description": "Подробности расчёта", "enabled": True, "is_core": False, "position": 2},
    {"role": "foreman", "command_key": "foreman_start", "telegram_command": "/start", "label": "🏠 Начало работы", "description": "Главное меню", "enabled": True, "is_core": True, "position": 3},
    
    # Worker commands (2 commands)
    {"role": "worker", "command_key": "worker_panel", "telegram_command": "/worker", "label": "👷 Панель рабочего", "description": "Начать/завершить смену, задачи, расходы", "enabled": True, "is_core": True, "position": 1},
    {"role": "worker", "command_key": "worker_start", "telegram_command": "/start", "label": "🏠 Начало работы", "description": "Главное меню", "enabled": True, "is_core": True, "position": 2},
]


def seed_bot_commands():
    """Seed bot_commands table with default data."""
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        print("ℹ️  Run `docker compose up -d` and `docker compose exec api alembic upgrade head` first")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_commands'")
    if not cursor.fetchone():
        print("❌ Table 'bot_commands' not found. Run migration first:")
        print("   docker compose exec api alembic upgrade head")
        conn.close()
        return
    
    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM bot_commands")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"⚠️  Table 'bot_commands' already has {count} rows. Skipping seed.")
        print("   To reseed, run: DELETE FROM bot_commands; then rerun this script.")
        conn.close()
        return
    
    # Insert commands
    inserted = 0
    for cmd in COMMANDS:
        try:
            cursor.execute("""
                INSERT INTO bot_commands (
                    role, command_key, telegram_command, label, description,
                    enabled, is_core, position, command_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cmd["role"], cmd["command_key"], cmd["telegram_command"],
                cmd["label"], cmd.get("description", ""),
                cmd["enabled"], cmd["is_core"], cmd["position"], "slash"
            ))
            inserted += 1
        except sqlite3.IntegrityError as e:
            print(f"⚠️  Skipping duplicate: {cmd['command_key']} ({e})")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Seeded {inserted} bot commands:")
    print(f"   - admin: 8 commands")
    print(f"   - foreman: 3 commands")
    print(f"   - worker: 2 commands")
    print(f"\nℹ️  To apply to Telegram bot, use Web UI (Settings → Telegram Bot → Apply to Bot)")


if __name__ == "__main__":
    seed_bot_commands()
