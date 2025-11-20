import os
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "api"))
from models import Base

# 1. ORM tables
orm_tables = set(Base.metadata.tables.keys())

# 2. Alembic tables
alembic_dir = Path(__file__).parent.parent / "db" / "alembic" / "versions"
alembic_tables = set()
create_table_re = re.compile(r"op\.create_table\(['\"]([A-Za-z0-9_]+)['\"]")
for file in alembic_dir.glob("*.py"):
    with open(file, encoding="utf-8") as f:
        for line in f:
            m = create_table_re.search(line)
            if m:
                alembic_tables.add(m.group(1))

# 3. Compare
orm_only = sorted(list(orm_tables - alembic_tables))
alembic_only = sorted(list(alembic_tables - orm_tables))

# 4. Output
print("# CI-9 ORM/Alembic Schema Audit\n")
print("## ORM-only tables (models.py, нет миграций):")
for t in orm_only:
    print(f"- {t}")
print("\n## Alembic-only tables (миграции, нет ORM):")
for t in alembic_only:
    print(f"- {t}")

print("\n## Итог:")
if not orm_only and not alembic_only:
    print("Нет расхождений: все таблицы покрыты миграциями и моделями.")
else:
    print("Для каждого объекта требуется объяснение или задача в TECH_DEBT/CI-9.x.")
