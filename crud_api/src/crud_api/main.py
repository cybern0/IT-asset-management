# Initialise FastAPI et declare les routes
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from crud_api.config import get_settings
from crud_api.core.database import SessionLocal, engine
from crud_api.core.errors import ServiceError
from crud_api.routers import api_router, auth_router
from crud_api.services.user_service import user_service

settings = get_settings()
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auth_enabled and len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "AUTH_ENABLED=true exige un JWT_SECRET d'au moins 32 caracteres (voir .env.example)."
        )
    if settings.bootstrap_admin_password:
        async with SessionLocal() as db:
            await user_service.bootstrap_admin(db, settings.bootstrap_admin_password)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    """Erreurs metier -> {"detail": "...", "field": "nom_du_champ" | null}."""
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail, "field": exc.field}, headers=headers
    )


@app.get("/")
def read_root():
    return {"message": "API du parc informatique", "docs": "/docs"}


@app.get("/health", tags=["Santé"])
async def health():
    async with SessionLocal() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")
