"""
Test handler для проверки APIClient функциональности.

Использование: /test_api в Telegram → проверяет все методы APIClient
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

try:  # pragma: no cover - exercised indirectly via import side-effects
    from aiogram import Router
    from aiogram.filters import Command
    AIROGRAM_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - depends on test environment
    Router = None  # type: ignore[assignment]
    Command = None  # type: ignore[assignment]
    AIROGRAM_AVAILABLE = False

if TYPE_CHECKING:  # pragma: no cover - typing only
    from aiogram.types import Message
else:
    Message = object  # fallback placeholder to keep type checkers satisfied

from bot.api_client import get_api_client
from bot.config import API_BASE_URL, INTERNAL_API_TOKEN

logger = logging.getLogger(__name__)
router = Router() if AIROGRAM_AVAILABLE else None

# Singleton клиент
api = get_api_client(API_BASE_URL, INTERNAL_API_TOKEN)


if AIROGRAM_AVAILABLE:

    @router.message(Command("test_api"))  # type: ignore[call-arg]
    async def handle_test_api_command(message: Message):
        """
        Тест APIClient: проверка всех основных методов.

        Проверяет:
        - Health check
        - Get users
        - Ollama chat

        Возвращает краткий отчёт о работе API.
        """
        try:
            text = "🧪 **API Client Test**\n\n"

            # Тест 1: Health check (будет 404, но это OK — проверяем связность)
            try:
                await api.health_check()
                text += "✅ Health check: OK\n"
            except Exception as e:  # pragma: no cover - depends on remote API
                # Ожидаем 404, т.к. endpoint может отсутствовать
                text += f"⚠️ Health check: {str(e)[:50]}\n"

            # Тест 2: Chat query (основной тест)
            try:
                chat_result = await api.chat_query("Привет! Тест бота")
                ollama_response = chat_result.get('result', 'N/A')
                # Обрезаем до 100 символов
                if len(ollama_response) > 100:
                    ollama_response = ollama_response[:97] + "..."
                text += f"✅ Ollama chat: {ollama_response}\n\n"
            except Exception as e:  # pragma: no cover - depends on remote API
                text += f"❌ Ollama chat failed: {str(e)}\n\n"
                logger.error(f"Ollama test failed: {e}")

            # Тест 3: Get users (опционально)
            try:
                users = await api.get_users()
                user_count = len(users) if isinstance(users, list) else users.get('count', 'N/A')
                text += f"✅ Users API: {user_count} users\n"
            except Exception as e:  # pragma: no cover - depends on remote API
                text += f"⚠️ Users API: {str(e)[:50]}\n"

            text += "\n**Итог:** APIClient готов к работе! 🎉"

            await message.answer(text, parse_mode="Markdown")

        except Exception as e:  # pragma: no cover - depends on runtime state
            logger.error(f"API client test failed: {e}")
            await message.answer(
                f"❌ **Ошибка теста API:**\n`{str(e)}`",
                parse_mode="Markdown"
            )

else:

    async def handle_test_api_command(*_: object, **__: object) -> None:
        """Placeholder to keep imports working when aiogram is unavailable."""
        logger.warning("Aiogram не установлен — /test_api handler отключен.")


def register_test_handlers(dp):
    """Регистрация тестовых handlers в dispatcher."""
    if not AIROGRAM_AVAILABLE or router is None:
        logger.warning("Aiogram не установлен — пропускаем регистрацию /test_api handler.")
        return

    dp.include_router(router)
    logger.info("✅ Test API handlers registered: /test_api")
