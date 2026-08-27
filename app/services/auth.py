import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _utcnow() -> datetime:
    """Timezone-naive UTC datetime for storage in naive DB columns."""
    from datetime import timezone as _tz
    return datetime.now(_tz.utc).replace(tzinfo=None)

from app.config import settings
from app.models.user import AppUser, RefreshToken, UserRole

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user: AppUser) -> str:
    # Must use timezone-aware datetime so .timestamp() gives correct UTC Unix time
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "jzd_id": user.jzd_id,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_refresh_token(user: AppUser, db: AsyncSession) -> str:
    raw = secrets.token_urlsafe(64)
    expires_at = _utcnow() + timedelta(days=settings.refresh_token_expire_days)
    record = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=expires_at,
    )
    db.add(record)
    await db.commit()
    return raw


async def rotate_refresh_token(raw_token: str, db: AsyncSession) -> tuple[AppUser, str] | None:
    """Validate and rotate a refresh token. Returns (user, new_raw_token) or None."""
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > _utcnow(),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        return None

    user_result = await db.execute(
        select(AppUser).where(AppUser.id == record.user_id, AppUser.is_active.is_(True))
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return None

    record.is_revoked = True
    new_raw = secrets.token_urlsafe(64)
    new_expires = _utcnow() + timedelta(days=settings.refresh_token_expire_days)
    new_record = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(new_raw),
        expires_at=new_expires,
    )
    db.add(new_record)
    await db.commit()
    return user, new_raw


async def revoke_refresh_token(raw_token: str, db: AsyncSession) -> None:
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()
    if record:
        record.is_revoked = True
        await db.commit()


async def authenticate_user(username: str, password: str, db: AsyncSession) -> AppUser | None:
    result = await db.execute(
        select(AppUser).where(AppUser.username == username, AppUser.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return None
    user.last_login = _utcnow()
    await db.commit()
    return user


def set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    secure = not settings.is_dev
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/auth/refresh")
