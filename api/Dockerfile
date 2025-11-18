FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# --- OCR layer + sqlite3 CLI ---
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus sqlite3 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn[standard] alembic pydantic-settings jinja2 pillow pytesseract pyjwt bcrypt sqlalchemy pytest httpx passlib
COPY . /app
RUN mkdir -p /app/db

# CI-8E: Create symlink for api.* imports (supports 'from api.xxx' in tests)
RUN if [ ! -e api ]; then ln -s . api; fi

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

