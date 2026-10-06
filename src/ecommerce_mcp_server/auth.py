"""Authentication provider and token verifier for E-Commerce FastMCP Server."""

from __future__ import annotations

import base64
import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator, Optional

import jwt
from fastmcp.server.auth import AccessToken, TokenVerifier
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

logger = logging.getLogger("ecommerce_mcp_server.auth")


class ECommerceTokenVerifier(TokenVerifier):
    """FastMCP TokenVerifier for the e-commerce platform's JWT access tokens.
    
    Cryptographically verifies the HMAC-SHA384 JWT signature, token expiration,
    and access token type using the secret key configured by User Service.
    
    Security rules:
    - Fails closed if JWT_SECRET is missing or not configured.
    - Strictly accepts only the HS384 algorithm used by the User Service.
    - Never uses verify_signature=False.
    - Strictly rejects refresh tokens, unsigned tokens, and invalid signatures.
    """

    # The User Service exclusively signs tokens with HS384 (HMAC-SHA384)
    # using a 51-byte (408-bit) Base64-decoded key via Keys.hmacShaKeyFor.
    ALGORITHM = "HS384"

    def __init__(self, secret_key: Optional[str | bytes] = None):
        super().__init__()
        raw_secret = (
            secret_key
            if secret_key is not None
            else (os.getenv("JWT_SECRET") or os.getenv("SECURITY_JWT_SECRET"))
        )
        self.secret_bytes: Optional[bytes] = (
            self._resolve_secret_bytes(raw_secret) if raw_secret else None
        )

    @staticmethod
    def _resolve_secret_bytes(secret: str | bytes) -> Optional[bytes]:
        """Convert secret string or bytes to cryptographic HMAC key bytes.
        
        The User Service stores the secret as a Base64 string in application.properties
        and decodes it via Decoders.BASE64.decode(secret).
        
        Fails closed (returns None) if:
        - The secret is missing or empty.
        - The secret is not valid Base64.
        - The decoded key is too short for HS384 (< 48 bytes / 384 bits).
        """
        if isinstance(secret, bytes):
            if len(secret) >= 48:
                return secret
            logger.error(
                "Raw secret bytes are too short for HS384 (minimum 48 bytes required). Failing closed."
            )
            return None

        if not secret or not isinstance(secret, str):
            return None

        cleaned = secret.strip()
        if not cleaned:
            return None

        try:
            decoded = base64.b64decode(cleaned, validate=True)
            if len(decoded) >= 48:
                return decoded
            logger.error(
                "Decoded Base64 secret is too short for HS384 (%d bytes, minimum 48 bytes required). Failing closed.",
                len(decoded),
            )
            return None
        except Exception as exc:
            logger.error("Failed to Base64-decode JWT secret (%s). Failing closed.", exc)
            return None

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify the Bearer access token and return AccessToken if valid.
        
        Fails closed if JWT_SECRET is missing or signature verification fails.
        Never falls back to unverified claim parsing.
        """
        if not token or not isinstance(token, str):
            return None

        clean_token = token.strip()
        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()

        if not clean_token:
            return None

        # Fail closed: reject authentication immediately if secret key is not configured
        if not self.secret_bytes:
            logger.error(
                "JWT_SECRET is missing or not configured. "
                "Cannot verify JWT signature. Failing closed."
            )
            return None

        try:
            payload = jwt.decode(
                clean_token,
                self.secret_bytes,
                algorithms=[self.ALGORITHM],
                options={"verify_signature": True, "verify_exp": True},
            )

            # Strictly require the token type to be exactly "access"
            token_type = payload.get("type")
            if token_type != "access":
                logger.warning(
                    "Rejected token with invalid or missing access type: %s", token_type
                )
                return None

            sub = payload.get("sub") or payload.get("userId") or "authenticated_user"
            role = payload.get("role")
            scopes = [role] if role else ["BUYER"]
            exp = payload.get("exp")

            return AccessToken(
                token=clean_token,
                client_id=str(sub),
                scopes=scopes,
                expires_at=int(exp) if exp is not None else None,
                subject=str(sub),
                claims=payload,
            )
        except jwt.ExpiredSignatureError:
            logger.info("Access token expired.")
            return None
        except jwt.InvalidSignatureError:
            logger.warning("JWT signature verification failed.")
            return None
        except jwt.InvalidAlgorithmError as exc:
            logger.warning("JWT algorithm not allowed: %s", exc)
            return None
        except (jwt.PyJWTError, Exception) as exc:
            logger.info("Token verification failed: %s", exc)
            return None


@contextmanager
def authenticated_context(
    token: str,
    client_id: str = "user@example.com",
    scopes: Optional[list[str]] = None,
) -> Iterator[AccessToken]:
    """Context manager for setting the active FastMCP request authentication context.
    
    Used in tests and request pipelines to bind the current authenticated user token.
    """
    clean_token = token.strip()
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()

    auth_info = AccessToken(
        token=clean_token,
        client_id=client_id,
        scopes=scopes or ["BUYER"],
        subject=client_id,
    )
    user = AuthenticatedUser(auth_info)
    ctx_token = auth_context_var.set(user)
    try:
        yield auth_info
    finally:
        auth_context_var.reset(ctx_token)
