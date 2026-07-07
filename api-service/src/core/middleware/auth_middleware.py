from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import jwt
from core.configs.config import Settings

settings = Settings()


class AuthMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/open/"):  # public routes
            return await call_next(request)

        token = request.headers.get("Authorization")
        if not token or not token.startswith("Bearer "):
            return JSONResponse({"error": "Missing token"}, status_code=401)
        token_value = token[7:]  # remove "Bearer "

        try:
            payload = jwt.decode(token_value, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            request.state.staff_id = payload.get("staff_id")
            request.state.roles = payload.get("roles", [])
        except jwt.ExpiredSignatureError:
            return JSONResponse({"error": "Token expired"}, status_code=401)
        except jwt.InvalidTokenError:
            return JSONResponse({"error": "Invalid token"}, status_code=401)

        return await call_next(request)
