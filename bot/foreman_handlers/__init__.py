"""
Foreman (Бригадир) handlers package.
Handles foreman-specific operations: approvals, team management, schedule oversight.
"""

from .foreman_panel import router as foreman_router

__all__ = ["foreman_router"]
