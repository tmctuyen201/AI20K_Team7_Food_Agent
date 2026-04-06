"""JWT authentication utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("foodie.auth")


class AuthError(Exception):
    """Raised when token verification fails."""
    pass


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        data: Payload to encode. Must include at least ``user_id``.
        expires_delta: Optional custom expiration window.
                     Defaults to settings.jwt_expiration_minutes.

    Returns:
        Encoded JWT string.
    """
    payload = data.copy()

    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_expiration_minutes
        )

    payload["exp"] = expire
    payload["iat"] = datetime.now(timezone.utc)

    encoded = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    logger.debug("token_created", user_id=data.get("user_id"), expires_at=expire.isoformat())
    return encoded


def verify_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT access token.

    Args:
        token: The JWT string to verify.

    Returns:
        The decoded payload dict.

    Raises:
        AuthError: If the token is invalid, expired, or malformed.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("token_expired", token_preview=token[:20])
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("token_invalid", error=str(e), token_preview=token[:20])
        raise AuthError(f"Invalid token: {e}")
