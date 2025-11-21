FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# --- OCR layer + sqlite3 CLI ---
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus sqlite3 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn[standard] alembic pydantic-settings jinja2 pillow pytesseract pyjwt bcrypt sqlalchemy pytest httpx passlib

# HOTFIX: Copy from root context (when building with `context: .`)
# If building with `context: ./api`, this will fail — use root context!
COPY api /app
COPY alembic.ini /app/alembic.ini
# Keep migrations in BOTH locations for compatibility:
# /app/db/alembic for Docker (alembic.ini: %(here)s/db/alembic)
# /app/api/db/alembic for GitHub Actions (where api/ is at repo root)
COPY api/db/alembic /app/db/alembic

RUN mkdir -p /app/db

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]


