from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import User, UserRole
from app.routers import analytics, auth, tickets, users
from app.security import hash_password


def bootstrap_admin() -> None:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.lower()))
        if admin is None:
            db.add(
                User(
                    email=settings.bootstrap_admin_email.lower(),
                    full_name="Administrador SupportFlow",
                    hashed_password=hash_password(settings.bootstrap_admin_password),
                    role=UserRole.ADMIN,
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    bootstrap_admin()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Gestión auditable de tickets con roles, SLA y métricas.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
