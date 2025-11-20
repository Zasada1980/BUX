
import os
import sys
from sqlalchemy import create_engine

# Mock settings
class Settings:
    DB_PATH = os.getenv("DB_PATH", "/app/db/shifts.db")

settings = Settings()
print(f"DB_PATH: {settings.DB_PATH}")

if settings.DB_PATH.startswith('/'):
    db_url = f"sqlite:///{settings.DB_PATH}"
else:
    db_url = f"sqlite:///./{settings.DB_PATH}"

print(f"URL: {db_url}")

try:
    engine = create_engine(db_url)
    conn = engine.connect()
    print("Connected!")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
