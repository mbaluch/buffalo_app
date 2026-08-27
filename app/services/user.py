import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import AppUser, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import hash_password
from app.services.email import send_welcome_email


async def get_all_users(db: AsyncSession, jzd_id: int | None = None) -> list[AppUser]:
    q = select(AppUser).options(selectinload(AppUser.jzd)).order_by(AppUser.username)
    if jzd_id is not None:
        q = q.where(AppUser.jzd_id == jzd_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_user(user_id: int, db: AsyncSession) -> AppUser | None:
    result = await db.execute(
        select(AppUser).options(selectinload(AppUser.jzd)).where(AppUser.id == user_id)
    )
    return result.scalar_one_or_none()


async def create_user(data: UserCreate, db: AsyncSession, send_welcome: bool = True) -> AppUser:
    temp_password = data.password
    user = AppUser(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        role=data.role,
        jzd_id=data.jzd_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    if send_welcome:
        await send_welcome_email(user.email, user.username, temp_password)

    return user


async def update_user(user: AppUser, data: UserUpdate, db: AsyncSession) -> AppUser:
    for field in ("first_name", "last_name", "phone", "is_active", "role", "jzd_id"):
        value = getattr(data, field)
        if value is not None:
            setattr(user, field, value)
    if data.email is not None:
        user.email = str(data.email)

    await db.commit()
    await db.refresh(user)
    return user


async def count_users_per_jzd(db: AsyncSession) -> dict[int, int]:
    result = await db.execute(
        select(AppUser.jzd_id, func.count(AppUser.id))
        .where(AppUser.jzd_id.isnot(None))
        .group_by(AppUser.jzd_id)
    )
    return {jzd_id: count for jzd_id, count in result.all()}
