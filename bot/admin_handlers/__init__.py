"""Admin handlers package"""
from bot.admin_handlers.admin_users import router as admin_users_router
from bot.admin_handlers.admin_user_card import router as admin_card_router
from bot.admin_handlers.admin_add_user import router as admin_add_router

__all__ = ["admin_users_router", "admin_card_router", "admin_add_router"]
