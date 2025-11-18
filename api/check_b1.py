"""Check B1 migration: closed_reason column + unique index."""
import sqlite3

conn = sqlite3.connect('/data/workledger.db')

# Check column exists
print("=== shifts table columns ===")
for row in conn.execute("PRAGMA table_info(shifts)"):
    if 'closed_reason' in str(row):
        print(f"✅ closed_reason column: {row}")

# Check indexes
print("\n=== shifts table indexes ===")
for row in conn.execute("PRAGMA index_list(shifts)"):
    idx_name = row[1]
    print(f"Index: {idx_name}")
    if idx_name == 'ux_shifts_user_open':
        # Get index details
        print(f"  ✅ FOUND: {idx_name}")
        for detail in conn.execute(f"PRAGMA index_info({idx_name})"):
            print(f"    {detail}")

conn.close()
