from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx
import logging

from redis.exceptions import AuthenticationError
from sqlalchemy import text
from src.core.cache.redis_client import create_redis_async_client
from src.core.bootstrap.admin_seed import ensure_bootstrap_admin
from src.core.configs.settings import settings
from src.core.db.database import engine
from src.core.middleware.logging_middleware import LoggingMiddleware
from src.core.middleware.timing_middleware import TimingMiddleware

from src.core.exception_handlers import register_exception_handlers

from src.utils.setup_logger import setup_logger


from src.api.v1.routers import api_router

logger = setup_logger(__name__, level=logging.DEBUG if settings.debug else logging.INFO)
UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def parse_cors_origins(raw_origins: str) -> list[str]:
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = None
    ai_http_client = None
    chatbox_http_client = None

    try:
        # Startup
        redis_client = create_redis_async_client()
        try:
            await redis_client.ping()
        except AuthenticationError as exc:
            # Redis server không bật password nhưng client lại gửi AUTH.
            if "without any password configured" not in str(exc):
                raise

            logger.warning(
                "Redis AUTH bị từ chối vì server không cấu hình password; fallback no-auth."
            )
            await redis_client.aclose()
            redis_client = create_redis_async_client(force_no_auth=True)
            await redis_client.ping()

        app.state.redis = redis_client
        logger.info("Redis kết nối thành công")

        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            tz_result = await connection.execute(text("SHOW TIME ZONE"))
            db_timezone = tz_result.scalar_one()
        logger.info("PostgreSQL kết nối thành công")
        logger.info("PostgreSQL session timezone: %s", db_timezone)

        await ensure_bootstrap_admin()
        logger.info("Bootstrap admin check completed")

        ai_http_client = httpx.AsyncClient(
            base_url=settings.ai_service_base_url,
            timeout=httpx.Timeout(10.0, connect=3.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        app.state.ai_http = ai_http_client

        chatbox_http_client = httpx.AsyncClient(
            base_url=settings.rag_api_url.rstrip("/"),
            timeout=httpx.Timeout(120.0, connect=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )
        app.state.chatbox_http = chatbox_http_client
        logger.info(
            "HTTP client khởi tạo thành công"
        )

        yield
    except Exception:
        logger.exception("Lỗi khởi tạo tài nguyên trong lifespan")
        raise
    finally:
        if chatbox_http_client is not None:
            await chatbox_http_client.aclose()
            logger.info("Chatbox HTTP client đã đóng")
        if ai_http_client is not None:
            await ai_http_client.aclose()
            logger.info("HTTP client đã đóng")
        if redis_client is not None:
            await redis_client.aclose()
            logger.info("Redis client đã đóng")


def create_app() -> FastAPI:
    app = FastAPI(
    title="Face Attendance API",
    description="Hệ thống chấm công nhận diện khuôn mặt",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,   # tắt docs trên production
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
    )

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=parse_cors_origins(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TimingMiddleware)

    app.include_router(api_router, prefix="/api/v1")
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

    return app

app = create_app()


# ── Health check ──────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Hello, world!"}
