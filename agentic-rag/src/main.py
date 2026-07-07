from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.exceptions import AuthenticationError

from src.core.settings import get_settings
from src.core.setup_logging import (
    AGENT_TRACE_LOG_FILE,
    RUN_LOG_FILE,
    configure_file_logging,
    setup_logger,
)
from src.integrations.qdrant.client import QdrantClientManager
from src.integrations.qdrant.store import QdrantVectorStore
from src.rag.embeddings.embedding_client import EmbeddingClient
from src.rag.embeddings.embedding_service import EmbeddingService
from src.rag.ingestion.chunkers.legachunker import LegalStructureAwareChunker
from src.rag.ingestion.indexer import DocumentIndexer
from src.rag.ingestion.loaders.factory_loader import LoaderFactory
from src.rag.ingestion.pipeline import IngestionPipeline
from src.rag.retrieval.reranker import RerankerClient, RerankerService
from src.integrations.cache.redis_client import create_redis_async_client
from src.integrations.api_service.clients import APIServiceClient
from src.api.v1.routers import router as v1_router


settings = get_settings()

logger = setup_logger(
    __name__,
    level=logging.DEBUG if settings.api_debug else logging.INFO,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_file_logging(logging.DEBUG if settings.api_debug else logging.INFO)
    logger.info("Starting up RAG service...")
    logger.info("System log file: %s", RUN_LOG_FILE)
    logger.info("Agent trace log file: %s", AGENT_TRACE_LOG_FILE)
    redis_client = None
    qdrant_manager = None
    api_service_http_client = None

    try:
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

        logger.info("Redis kết nối thành công")

        # --- Embedding ---
        client = EmbeddingClient()
        embedding_service = EmbeddingService(client)
        logger.info("Warming up embedding model on device: %s", client.device)
        await embedding_service.warmup()
        logger.info("Embedding model warmup completed")

        # --- Qdrant ---
        qdrant_manager = QdrantClientManager()
        await qdrant_manager.ensure_collection(settings.default_qdrant_collection)
        vector_store = QdrantVectorStore(qdrant_manager.get_client())
        logger.info("Qdrant client initialized and collection ensured: %s", \
                    settings.default_qdrant_collection)

        # --- Reranker ---
        reranker_client = RerankerClient()
        reranker_service = RerankerService(reranker_client)
        logger.info("Warming up reranker model on device: %s", reranker_client.device)
        await reranker_service.warmup()
        logger.info("Reranker model warmup completed")

        # --- Ingestion pipeline ---
        ingestion_pipeline = IngestionPipeline(
            loader=LoaderFactory,
            chunker=LegalStructureAwareChunker(),
            indexer=DocumentIndexer(embedding_service, vector_store),
            qdrant_manager=qdrant_manager,
        )

        # --- API service client ---
        api_service_http_client = httpx.AsyncClient(
            base_url=settings.api_server_base_url.rstrip("/"),
            timeout=httpx.Timeout(10.0, connect=3.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        api_service_client = APIServiceClient(api_service_http_client)
        
        # Lưu services lên app.state để routes/DI dùng:
        app.state.embedding_service = embedding_service
        app.state.vector_store = vector_store
        app.state.reranker_service = reranker_service
        app.state.ingestion_pipeline = ingestion_pipeline
        app.state.qdrant_manager = qdrant_manager
        app.state.redis = redis_client
        app.state.api_service_http = api_service_http_client
        app.state.api_service_client = api_service_client


        logger.info("RAG service ready")

        yield

    except Exception:
        logger.exception("Lỗi khởi tạo tài nguyên trong lifespan")
        raise
    finally:
        if api_service_http_client is not None:
            await api_service_http_client.aclose()
            logger.info("api-service HTTP client đã đóng")
        if qdrant_manager is not None:
            await qdrant_manager.close()
            logger.info("Qdrant client đã đóng")
        if redis_client is not None:
            await redis_client.aclose()
            logger.info("Redis client đã đóng")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic RAG — Attendance System",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.api_debug,
    )

    app.include_router(v1_router)

    return app


app = create_app()


@app.get("/health")
async def health_check():
    return {"status": "ok"}
