from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from src.rag.ingestion.pipeline import IngestionPipeline
from src.rag.embeddings.embedding_service import EmbeddingService
from src.integrations.qdrant.store import QdrantVectorStore
from src.rag.retrieval.reranker import RerankerService
from redis.asyncio import Redis

from src.core.settings import get_settings
from src.integrations.api_service.clients import APIServiceClient

settings = get_settings()

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(_api_key_header)):
    if api_key != settings.rag_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


def get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service


def get_vector_store(request: Request) -> QdrantVectorStore:
    return request.app.state.vector_store


def get_reranker_service(request: Request) -> RerankerService:
    return request.app.state.reranker_service


def get_ingestion_pipeline(request: Request) -> IngestionPipeline:
    return request.app.state.ingestion_pipeline



def get_redis_client(request: Request) -> Redis:
    redis_client = getattr(request.app.state, "redis", None)

    if redis_client is None:
        raise RuntimeError("Redis client chưa được khởi tạo trong app.state")

    return redis_client


def get_api_service_client(request: Request) -> APIServiceClient:
    api_service_client = getattr(request.app.state, "api_service_client", None)
    if api_service_client is None:
        raise RuntimeError("API service client chưa được khởi tạo trong app.state")
    return api_service_client
