FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    aiogram==3.13.1 \
    aiohttp \
    sqlalchemy \
    python-dotenv \
    httpx

# Create directory structure
RUN mkdir -p /app/bot /app/api /app/logs

# Copy bot code (from context root)
COPY ./bot /app/bot

# HOTFIX TD-BOT-ISO-1: Copy minimal API dependencies until HTTP refactoring
# Required modules: models, models_users, crud_users, utils (for bot handlers)
COPY ./api/models.py /app/api/
COPY ./api/models_users.py /app/api/
COPY ./api/crud_users.py /app/api/
COPY ./api/utils /app/api/utils
RUN echo "# stub" > /app/api/__init__.py

# Set PYTHONPATH so "from bot.config" and "from api.crud_users" work
# Also add /app/api for api module's internal imports (models_users, crud_*, etc.)
ENV PYTHONPATH=/app:/app/api

WORKDIR /app/bot

CMD ["python", "-m", "bot.main"]
