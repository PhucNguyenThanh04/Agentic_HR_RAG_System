from fastapi import Request
from redis.asyncio import Redis
import httpx


def get_redis_client(request: Request) -> Redis:
    redis_client = getattr(request.app.state, "redis", None)

    if redis_client is None:
        raise RuntimeError("Redis client chưa được khởi tạo trong app.state")

    return redis_client


def get_ai_http_client(request: Request) -> httpx.AsyncClient:
    ai_http = getattr(request.app.state, "ai_http", None)
    if ai_http is None:
        raise RuntimeError("HTTP client chưa được khởi tạo trong app.state")
    return ai_http


def get_chatbox_http_client(request: Request) -> httpx.AsyncClient:
    chatbox_http = getattr(request.app.state, "chatbox_http", None)
    if chatbox_http is None:
        raise RuntimeError("Chatbox HTTP client chưa được khởi tạo trong app.state")
    return chatbox_http
