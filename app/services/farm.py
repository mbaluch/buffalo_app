from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmUpdate


async def get_farms(
    db: AsyncSession, jzd_id: int | None = None, active_only: bool = True
) -> list[Farm]:
    q = select(Farm).options(selectinload(Farm.owner))
    if jzd_id is not None:
        q = q.where(Farm.jzd_id == jzd_id)
    if active_only:
        q = q.where(Farm.is_active.is_(True))
    q = q.order_by(Farm.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_farm(farm_id: int, db: AsyncSession) -> Farm | None:
    result = await db.execute(
        select(Farm).options(selectinload(Farm.owner)).where(Farm.id == farm_id)
    )
    return result.scalar_one_or_none()


async def create_farm(jzd_id: int, data: FarmCreate, db: AsyncSession) -> Farm:
    farm = Farm(
        jzd_id=jzd_id,
        owner_id=data.owner_id,
        name=data.name,
        registration_number=data.registration_number,
        address=data.address,
        city=data.city,
        postal_code=data.postal_code,
        latitude=data.latitude,
        longitude=data.longitude,
        contact_phone=data.contact_phone,
    )
    db.add(farm)
    await db.commit()
    await db.refresh(farm)
    return farm


async def update_farm(farm: Farm, data: FarmUpdate, db: AsyncSession) -> Farm:
    for field in ("name", "registration_number", "address", "city", "postal_code",
                  "latitude", "longitude", "contact_phone", "owner_id", "is_active"):
        value = getattr(data, field)
        if value is not None:
            setattr(farm, field, value)
    await db.commit()
    await db.refresh(farm)
    return farm
