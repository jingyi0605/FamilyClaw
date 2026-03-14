from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal
from app.modules.account.service import ensure_bootstrap_admin_account, ensure_pending_household_bootstrap_accounts
from app.modules.plugin.job_worker import PluginJobWorker

setup_logging(
    settings.log_level,
    conversation_debug_enabled=settings.conversation_debug_log_enabled,
)
logger = logging.getLogger(__name__)
plugin_job_worker = PluginJobWorker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s", settings.app_name)
    db = SessionLocal()
    try:
        ensure_bootstrap_admin_account(db)
        ensure_pending_household_bootstrap_accounts(db)
    finally:
        db.close()
    if settings.plugin_job_worker_enabled:
        await plugin_job_worker.start()
    yield
    if settings.plugin_job_worker_enabled:
        await plugin_job_worker.stop()
    logger.info("Stopping %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "ok",
    }

