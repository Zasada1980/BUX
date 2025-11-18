from sqlalchemy import create_engine, text

e = create_engine('sqlite:///./telegram_ollama.db')
with e.connect() as c:
    tasks = c.execute(text('SELECT COUNT(*) FROM tasks')).scalar()
    expenses = c.execute(text('SELECT COUNT(*) FROM expenses')).scalar()
    print(f'Tasks: {tasks}')
    print(f'Expenses: {expenses}')
    
    if tasks > 0:
        print('\nFirst task:')
        row = c.execute(text('SELECT id, rate_code, qty, amount FROM tasks LIMIT 1')).fetchone()
        print(f'  ID={row[0]}, rate_code={row[1]}, qty={row[2]}, amount={row[3]}')
    
    if expenses > 0:
        print('\nFirst expense:')
        row = c.execute(text('SELECT id, category, amount FROM expenses LIMIT 1')).fetchone()
        print(f'  ID={row[0]}, category={row[1]}, amount={row[2]}')
