"""Worker panel handlers."""
from aiogram import Router
from . import worker_panel, worker_shift, worker_tasks

router = Router()
router.include_router(worker_panel.router)
router.include_router(worker_shift.router)
router.include_router(worker_tasks.router)

__all__ = ["router"]
