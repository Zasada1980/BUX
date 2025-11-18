"""
API Client для Telegram бота — единственная точка взаимодействия с API сервисом.

ПРИНЦИП: Bot НЕ должен импортировать код из api/
Всё общение через HTTP с использованием httpx.

Преимущества:
- Независимость сервисов
- Простое тестирование (моки HTTP)
- Масштабируемость (API может быть на другом сервере)
- Версионирование API (через URL paths)
"""

import httpx
from typing import Optional, Dict, Any, List
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class APIClient:
    """HTTP клиент для взаимодействия с API сервисом."""
    
    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        """
        Args:
            base_url: Base URL API (например, http://api:8080)
            token: Internal API token для аутентификации
            timeout: Timeout для запросов в секундах
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.timeout = timeout
    
    async def _request(
        self, 
        method: str, 
        path: str, 
        json: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Базовый метод для HTTP запросов.
        
        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            path: API путь (например, /api/v1/users)
            json: JSON body для запроса
            params: Query параметры
            
        Returns:
            Parsed JSON response
            
        Raises:
            httpx.HTTPError: При ошибках HTTP
        """
        url = f"{self.base_url}{path}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json,
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"API request failed: {method} {url} - {e}")
            raise
    
    # ============ USER MANAGEMENT ============
    
    async def get_users(self) -> List[Dict]:
        """Получить список всех пользователей через internal API."""
        return await self._request("GET", "/api/internal/users")
    
    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        """
        Получить пользователя по Telegram ID.
        
        Returns:
            User dict или None если не найден
        """
        try:
            return await self._request("GET", f"/api/v1/users/{telegram_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def create_user(
        self, 
        telegram_id: int, 
        username: str,
        role: str,
        full_name: Optional[str] = None
    ) -> Dict:
        """Создать нового пользователя."""
        return await self._request("POST", "/api/v1/users", json={
            "telegram_id": telegram_id,
            "username": username,
            "role": role,
            "full_name": full_name
        })
    
    # ============ SHIFT MANAGEMENT ============
    
    async def start_shift(self, user_id: int) -> Dict:
        """Начать смену для пользователя."""
        return await self._request("POST", "/api/shift/start", json={
            "user_id": user_id
        })
    
    async def end_shift(self, user_id: int) -> Dict:
        """Завершить смену для пользователя."""
        return await self._request("POST", "/api/shift/end", json={
            "user_id": user_id
        })
    
    async def get_active_shift(self, user_id: int) -> Optional[Dict]:
        """Получить активную смену пользователя."""
        try:
            return await self._request("GET", f"/api/shift/active/{user_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    # ============ TASK MANAGEMENT ============
    
    async def create_task(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        estimated_hours: Optional[float] = None
    ) -> Dict:
        """Создать новую задачу."""
        return await self._request("POST", "/api/task/create", json={
            "user_id": user_id,
            "title": title,
            "description": description,
            "estimated_hours": estimated_hours
        })
    
    async def complete_task(self, task_id: int, actual_hours: float) -> Dict:
        """Отметить задачу как выполненную."""
        return await self._request("POST", f"/api/task/{task_id}/complete", json={
            "actual_hours": actual_hours
        })
    
    async def get_user_tasks(self, user_id: int, active_only: bool = True) -> List[Dict]:
        """Получить задачи пользователя."""
        return await self._request("GET", f"/api/task/user/{user_id}", params={
            "active_only": active_only
        })
    
    # ============ EXPENSE MANAGEMENT ============
    
    async def create_expense(
        self,
        user_id: int,
        amount: Decimal,
        category: str,
        description: Optional[str] = None,
        photo_ref: Optional[str] = None
    ) -> Dict:
        """Создать новый расход."""
        return await self._request("POST", "/api/expense/create", json={
            "user_id": user_id,
            "amount": str(amount),  # Decimal → str для JSON
            "category": category,
            "description": description,
            "photo_ref": photo_ref
        })
    
    async def get_user_expenses(
        self, 
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """Получить расходы пользователя."""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        return await self._request("GET", f"/api/expense/user/{user_id}", params=params)
    
    # ============ MODERATION (INBOX) ============
    
    async def get_pending_items(self, limit: int = 10, offset: int = 0) -> Dict:
        """Получить список элементов на модерации."""
        return await self._request("GET", "/api/admin/pending", params={
            "limit": limit,
            "offset": offset
        })
    
    async def approve_item(self, item_id: int) -> Dict:
        """Одобрить элемент (foreman)."""
        return await self._request("POST", f"/api/admin/approve/{item_id}")
    
    async def reject_item(self, item_id: int, reason: str) -> Dict:
        """Отклонить элемент (foreman)."""
        return await self._request("POST", f"/api/admin/reject/{item_id}", json={
            "reason": reason
        })
    
    # ============ INVOICE MANAGEMENT ============
    
    async def get_invoices(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """Получить список счетов."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        if status:
            params["status"] = status
        
        return await self._request("GET", "/api/invoice/list", params=params)
    
    async def create_invoice(
        self,
        user_id: int,
        period_start: str,
        period_end: str
    ) -> Dict:
        """Создать новый счёт."""
        return await self._request("POST", "/api/invoice/create", json={
            "user_id": user_id,
            "period_start": period_start,
            "period_end": period_end
        })
    
    # ============ OLLAMA CHAT ============
    
    async def chat_query(self, text: str, context: Optional[Dict] = None) -> Dict:
        """
        Отправить запрос в Ollama через Agent.
        
        Args:
            text: Текст запроса пользователя
            context: Дополнительный контекст (опционально)
            
        Returns:
            {
                "status": "success",
                "intent": "query_employees",
                "result": "В базе 4 сотрудника",
                "data": {...}
            }
        """
        return await self._request("POST", "/api/chat/query", json={
            "text": text,
            "context": context or {}
        })
    
    # ============ HEALTH CHECK ============
    
    async def health_check(self) -> Dict:
        """Проверка доступности API."""
        return await self._request("GET", "/health")


# ============ SINGLETON INSTANCE ============

_api_client_instance: Optional[APIClient] = None


def get_api_client(base_url: str, token: str) -> APIClient:
    """
    Получить singleton инстанс API клиента.
    
    Args:
        base_url: API base URL
        token: Internal API token
        
    Returns:
        APIClient instance
    """
    global _api_client_instance
    
    if _api_client_instance is None:
        _api_client_instance = APIClient(base_url, token)
        logger.info(f"✅ APIClient initialized: {base_url}")
    
    return _api_client_instance
