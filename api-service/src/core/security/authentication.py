import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.configs.settings import settings

JWT_SECRET_KEY = settings.jwt_secret_key
REFRESH_TOKEN_SECRET_KEY = settings.refresh_token_secret_key
ALGORITHM = settings.jwt_algorithm

ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return bcrypt_context.hash(password)


def create_access_token(
    *,
    user_id: str,
    role: str,
    token_version: int,
) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "token_version": token_version,
        "jti": jti,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return token, jti, expire


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except JWTError:
        raise TokenError("Invalid access token")

    if payload.get("type") != "access":
        raise TokenError("Invalid token type")

    required_fields = ["sub", "jti", "token_version", "exp"]

    for field in required_fields:
        if field not in payload:
            raise TokenError(f"Missing token field: {field}")

    return payload


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(refresh_token: str) -> str:
    return hmac.new(
        REFRESH_TOKEN_SECRET_KEY.encode(),
        refresh_token.encode(),
        hashlib.sha256,
    ).hexdigest()


def get_refresh_token_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def get_remaining_seconds(exp_timestamp: int) -> int:
    now = int(datetime.now(timezone.utc).timestamp())
    return max(exp_timestamp - now, 0)


def build_access_token_blacklist_key(jti: str) -> str:
    return f"auth:blacklist:access:{jti}"


def create_password_reset_token() -> str:
    return secrets.token_urlsafe(48)


def hash_password_reset_token(reset_token: str) -> str:
    return hmac.new(
        REFRESH_TOKEN_SECRET_KEY.encode(),
        reset_token.encode(),
        hashlib.sha256,
    ).hexdigest()

