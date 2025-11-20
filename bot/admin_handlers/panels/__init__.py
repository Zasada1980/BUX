"""
Admin panel modules - каждая кнопка в отдельном файле

Структура:
- main_panel.py — Главная панель управления (/admin команда)
- stats_panel.py — 📊 Аналитика (admin:stats)
- refresh_panel.py — 🔄 Перезагрузка систем (admin:refresh)
- filters_panel.py — Фильтры по ролям (admin:filter:*)
- users_panel.py — 👥 Экипаж (список пользователей)
- clients_panel.py — 👔 Контрагенты (заглушка)
- schedule_panel.py — 📅 Полётный план (заглушка)
"""

from .main_panel import show_main_panel, get_main_panel_keyboard
from .stats_panel import show_stats_panel
from .refresh_panel import handle_refresh
from .filters_panel import handle_filter
from .users_panel import show_users_list
from .clients_panel import show_clients_panel
from .schedule_panel import show_schedule_panel

__all__ = [
    'show_main_panel',
    'get_main_panel_keyboard',
    'show_stats_panel',
    'handle_refresh',
    'handle_filter',
    'show_users_list',
    'show_clients_panel',
    'show_schedule_panel',
]
