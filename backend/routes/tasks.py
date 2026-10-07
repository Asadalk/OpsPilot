"""Compatibility wrapper for the relocated task routes."""
from app.api.routes.tasks import build_task_router
from app.main import task_service

router = build_task_router(task_service)