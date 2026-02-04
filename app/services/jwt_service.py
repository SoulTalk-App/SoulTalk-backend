import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from jose import JWTError, jwt

from app.core.config import settings


class JWTService:
    def __init__(self):
        self.secret_key = settings.JWT_SECRET
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    def create_access_token(
        self,
        user_id: uuid.UUID,
        email: str,
        additional_claims: Optional[dict] = None
    ) -> Tuple[str, int]:
        """
        Create an access token.
        Returns (token, expires_in_seconds)
        """
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        expire = datetime.now(timezone.utc) + expires_delta

        to_encode = {
            "sub": str(user_id),
            "email": email,
            "type": "access",
            "exp": expire,
            "iat": datetime.now(timezone.utc)
        }

        if additional_claims:
            to_encode.update(additional_claims)

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt, int(expires_delta.total_seconds())

    def create_refresh_token(self) -> Tuple[str, str, datetime]:
        """
        Create a refresh token.
        Returns (raw_token, token_hash, expires_at)
        """
        raw_token = secrets.token_urlsafe(64)
        token_hash = self._hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)

        return raw_token, token_hash, expires_at

    def decode_access_token(self, token: str) -> Optional[dict]:
        """Decode and verify an access token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )

            if payload.get("type") != "access":
                return None

            return payload
        except JWTError:
            return None

    def _hash_token(self, token: str) -> str:
        """Hash a token using SHA-256"""
        return hashlib.sha256(token.encode()).hexdigest()

    def verify_refresh_token_hash(self, raw_token: str, stored_hash: str) -> bool:
        """Verify a refresh token against its stored hash"""
        return self._hash_token(raw_token) == stored_hash

    def hash_refresh_token(self, raw_token: str) -> str:
        """Hash a refresh token for storage"""
        return self._hash_token(raw_token)

    def create_verification_token(self) -> Tuple[str, str]:
        """
        Create an email verification or password reset token.
        Returns (raw_token, token_hash)
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        return raw_token, token_hash


jwt_service = JWTService()
