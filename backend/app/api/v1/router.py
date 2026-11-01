from fastapi import APIRouter

from app.api.v1.endpoints import admin, assistant, health, schemes, sources

API_V1_PREFIX = "/api/v1"

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(assistant.router)
api_router.include_router(schemes.router)
api_router.include_router(schemes.budget_router)
api_router.include_router(sources.router)
api_router.include_router(admin.router)
