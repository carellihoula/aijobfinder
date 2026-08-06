from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin.router import router as admin_router
from app.analysis.router import router as analysis_router
from app.applications.router import router as applications_router
from app.auth.router import router as auth_router
from app.cover_letter.router import router as cover_letter_router
from app.config import settings
from app.cortex.db import init_cortex
from app.cortex.router import router as cortex_router
from app.db.session import init_db
from app.logger import get_logger, setup_logging
from app.users.router import router as users_router

setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s ...", settings.APP_NAME)
    await init_db()
    logger.info("Main DB ready")
    await init_cortex()
    yield
    logger.info("%s shutdown", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered CV to Job Matching API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(analysis_router)
app.include_router(applications_router)
app.include_router(cover_letter_router)
app.include_router(cortex_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}