from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.jzd import Jzd, JzdSettings
from app.schemas.jzd import JzdCreate, JzdUpdate


async def get_all_jzds(db: AsyncSession) -> list[Jzd]:
    result = await db.execute(
        select(Jzd).options(selectinload(Jzd.settings)).order_by(Jzd.name)
    )
    return list(result.scalars().all())


async def get_jzd(jzd_id: int, db: AsyncSession) -> Jzd | None:
    result = await db.execute(
        select(Jzd).options(selectinload(Jzd.settings)).where(Jzd.id == jzd_id)
    )
    return result.scalar_one_or_none()


async def create_jzd(data: JzdCreate, db: AsyncSession) -> Jzd:
    jzd = Jzd(
        registration_number=data.registration_number,
        name=data.name,
        address=data.address,
        city=data.city,
        postal_code=data.postal_code,
        country=data.country,
        latitude=data.latitude,
        longitude=data.longitude,
        contact_phone=data.contact_phone,
        contact_email=str(data.contact_email) if data.contact_email else None,
    )
    db.add(jzd)
    await db.flush()  # get jzd.id before creating settings

    settings_record = JzdSettings(
        jzd_id=jzd.id,
        gestation_days=data.settings.gestation_days,
        recovery_days=data.settings.recovery_days,
    )
    db.add(settings_record)
    await db.commit()
    await db.refresh(jzd)
    return jzd


async def update_jzd(jzd: Jzd, data: JzdUpdate, db: AsyncSession) -> Jzd:
    for field in ("name", "address", "city", "postal_code", "contact_phone",
                  "latitude", "longitude", "is_active"):
        value = getattr(data, field)
        if value is not None:
            setattr(jzd, field, value)
    if data.contact_email is not None:
        jzd.contact_email = str(data.contact_email)

    if data.settings is not None and jzd.settings:
        jzd.settings.gestation_days = data.settings.gestation_days
        jzd.settings.recovery_days = data.settings.recovery_days

    await db.commit()
    await db.refresh(jzd)
    return jzd
