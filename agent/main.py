from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
import platform
import os
import httpx
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

app = FastAPI(title="TelegramOllama Agent", version="0.1.0")

# CORS: allow local testing from file:// and any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration (same as API)
DB_PATH = os.getenv("DB_PATH", "/app/data/workledger.db")
if DB_PATH.startswith('/'):
    db_url = f"sqlite:///{DB_PATH}"
else:
    db_url = f"sqlite:///./{DB_PATH}"

engine = create_engine(db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# API configuration
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8080")

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

@app.get("/health")
def health():
    return {
        "service": "agent",
        "status": "ok",
        "ts": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
    }

class InferRequest(BaseModel):
    intent: str
    payload: dict = {}
    constraints: dict | None = None
    context: dict | None = None

class QueryRequest(BaseModel):
    text: str
    context: dict | None = None

@app.post("/v1/agent/infer")
def infer(_req: InferRequest):
    # Заглушка, чтобы контракт существовал. Реализация позже.
    raise HTTPException(status_code=501, detail="not_implemented")

async def call_ollama(prompt: str, system_prompt: str = None) -> str:
    """Вызов Ollama API для генерации ответа."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            }
            if system_prompt:
                payload["system"] = system_prompt
            
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")

def query_database(query_type: str) -> dict:
    """Выполнение запросов к базе данных."""
    db = SessionLocal()
    try:
        if query_type == "users":
            result = db.execute(text("""
                SELECT id, name, telegram_username, role, active, daily_salary
                FROM users
                WHERE active = 1
                ORDER BY name
            """)).fetchall()
            return {
                "count": len(result),
                "users": [dict(row._mapping) for row in result]
            }
        
        elif query_type == "employees":
            result = db.execute(text("""
                SELECT id, full_name, role, is_active
                FROM employees
                WHERE deleted_at IS NULL AND is_active = 1
                ORDER BY full_name
            """)).fetchall()
            return {
                "count": len(result),
                "employees": [dict(row._mapping) for row in result]
            }
        
        elif query_type == "shifts":
            result = db.execute(text("""
                SELECT s.id, s.user_id, u.name, s.start_time, s.end_time, s.status
                FROM shifts s
                JOIN users u ON s.user_id = u.id
                ORDER BY s.start_time DESC
                LIMIT 50
            """)).fetchall()
            return {
                "count": len(result),
                "shifts": [dict(row._mapping) for row in result]
            }
        
        else:
            return {"error": "unknown_query_type"}
    
    finally:
        db.close()

@app.post("/v1/agent/query")
async def agent_query(req: QueryRequest):
    """
    Основной endpoint для обработки запросов из веб-чата.
    Классифицирует намерение, выполняет запросы и генерирует ответ через Ollama.
    """
    try:
        # Системный промпт для Ollama
        system_prompt = """Ты — помощник для управления рабочими данными в системе WorkLedger.
У тебя есть доступ к базе данных с пользователями, сотрудниками, сменами, задачами и расходами.

Твои функции:
1. Отвечать на вопросы о данных (сколько сотрудников, кто работает и т.д.)
2. Помогать синхронизировать данные между веб-интерфейсом и Telegram ботом
3. Генерировать отчёты в удобном формате

Отвечай кратко, по делу, на русском языке. Если нужны данные из БД — запроси их."""

        user_text = req.text.lower()
        
        # Простая классификация намерений
        intent = "general"
        data = None
        
        if any(word in user_text for word in ["пользовател", "юзер", "user"]):
            intent = "query_users"
            data = query_database("users")
        elif any(word in user_text for word in ["сотрудник", "employee", "работник"]):
            intent = "query_employees"
            data = query_database("employees")
        elif any(word in user_text for word in ["смен", "shift", "раб"]):
            intent = "query_shifts"
            data = query_database("shifts")
        
        # Формируем промпт для Ollama
        if data:
            prompt = f"""Вопрос пользователя: {req.text}

Данные из базы:
{json.dumps(data, ensure_ascii=False, indent=2)}

Сформулируй краткий и полезный ответ на основе этих данных."""
        else:
            prompt = req.text
        
        # Получаем ответ от Ollama
        response_text = await call_ollama(prompt, system_prompt)
        
        return {
            "status": "success",
            "intent": intent,
            "result": response_text,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/v1/agent/sync-users")
async def sync_users():
    """
    Синхронизация пользователей из API work-records в базу данных бота.
    Извлекает уникальных работников из смен и создает/обновляет записи в таблице users.
    """
    db = SessionLocal()
    try:
        # 1. Получить список всех пользователей из users таблицы
        existing_users_query = "SELECT id, name, telegram_id FROM users"
        existing_users = db.execute(text(existing_users_query)).fetchall()
        existing_by_name = {row.name: row for row in existing_users}
        
        synced = []
        created = 0
        updated = 0

        # 2A. Источник №1: существующие пользователи, упомянутые в сменах (сохранение обратной совместимости)
        shifts_query = """
        SELECT DISTINCT u.id as uid, u.name as name, u.telegram_id as telegram_id
        FROM shifts s
        JOIN users u ON s.user_id = u.id
        WHERE u.name IS NOT NULL
        """
        for row in db.execute(text(shifts_query)).fetchall():
            # Просто фиксируем наличие, без изменений
            synced.append({
                "id": row.uid,
                "name": row.name,
                "telegram_id": row.telegram_id,
                "action": "existing"
            })

        # 2B. Источник №2: активные сотрудники из таблицы employees (web → agent → bot)
        employees_query = """
        SELECT DISTINCT full_name
        FROM employees
        WHERE deleted_at IS NULL AND is_active = 1 AND full_name IS NOT NULL AND TRIM(full_name) != ''
        """
        for emp in db.execute(text(employees_query)).fetchall():
            name = emp.full_name
            if name in existing_by_name:
                # уже есть в users
                continue
            # Создать нового пользователя (без telegram_id, добавится после /start)
            insert_query = """
            INSERT INTO users (name, role, active, telegram_id, created_at)
            VALUES (:name, 'worker', 1, NULL, :created_at)
            """
            db.execute(text(insert_query), {
                "name": name,
                "created_at": datetime.now(timezone.utc)
            })
            db.commit()
            created += 1
            new_user = db.execute(
                text("SELECT id, name FROM users WHERE name = :name"),
                {"name": name}
            ).fetchone()
            synced.append({
                "id": new_user.id,
                "name": new_user.name,
                "telegram_id": None,
                "action": "created"
            })
        
        return {
            "status": "success",
            "synced": len(synced),
            "created": created,
            "updated": updated,
            "users": synced,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        db.close()
