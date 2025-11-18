import sqlite3

conn = sqlite3.connect('data/shifts.db')
c = conn.cursor()

# Recreate shifts table
c.execute('DROP TABLE IF EXISTS shifts')
c.execute('''CREATE TABLE shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)''')

# Recreate tasks table with ALL required columns
c.execute('DROP TABLE IF EXISTS tasks')
c.execute('''CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL,
    rate_code TEXT NOT NULL,
    qty REAL NOT NULL,
    unit TEXT,
    amount REAL NOT NULL,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)''')

# Recreate expenses table
c.execute('DROP TABLE IF EXISTS expenses')
c.execute('''CREATE TABLE expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    photo_ref TEXT NOT NULL,
    description TEXT,
    ocr_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)''')

# Create initial shift
c.execute('INSERT INTO shifts (user_id, status) VALUES (?, ?)', ('gold_user', 'open'))
shift_id = c.lastrowid

conn.commit()
conn.close()

print(f'DB recreated. Shift ID: {shift_id}')
