from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.jzd import JzdSettings
from app.models.livestock import Livestock, LivestockSex, LivestockStatus
from app.schemas.livestock import LivestockCreate, LivestockSearchParams, LivestockUpdate
from app.services.attribute import get_cattle_type, validate_attributes


async def _next_reg_number(jzd_id: int, db: AsyncSession) -> str:
    """Atomically fetch and increment the JZD registration counter."""
    result = await db.execute(
        select(JzdSettings).where(JzdSettings.jzd_id == jzd_id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise ValueError(f"No settings found for JZD {jzd_id}")
    seq = settings.next_registration_seq
    settings.next_registration_seq = seq + 1
    await db.flush()
    return f"CZ{seq:012d}"


async def get_livestock(livestock_id: int, db: AsyncSession) -> Livestock | None:
    result = await db.execute(
        select(Livestock)
        .options(
            selectinload(Livestock.farm),
            selectinload(Livestock.jzd),
            selectinload(Livestock.photos),
            selectinload(Livestock.livestock_type),
            selectinload(Livestock.creator),
        )
        .where(Livestock.id == livestock_id)
    )
    return result.scalar_one_or_none()


async def search_livestock(
    params: LivestockSearchParams,
    db: AsyncSession,
    jzd_id: int | None = None,
) -> tuple[list[Livestock], int]:
    """Returns (results, total_count). Pass jzd_id to restrict to one cooperative."""
    q = (
        select(Livestock)
        .options(
            selectinload(Livestock.farm),
            selectinload(Livestock.photos),
            selectinload(Livestock.livestock_type),
        )
        .where(Livestock.status == (params.status or LivestockStatus.ACTIVE))
    )

    if jzd_id is not None:
        q = q.where(Livestock.jzd_id == jzd_id)

    if params.sex:
        q = q.where(Livestock.sex == params.sex)
    if params.farm_id:
        q = q.where(Livestock.farm_id == params.farm_id)
    if params.available_for_breeding is not None:
        q = q.where(Livestock.is_available_for_breeding == params.available_for_breeding)
    if params.pregnancy_status:
        q = q.where(Livestock.pregnancy_status == params.pregnancy_status)

    if params.q:
        like = f"%{params.q}%"
        q = q.where(
            Livestock.name.ilike(like) | Livestock.registration_number.ilike(like)
        )

    # JSONB attribute filters
    if params.breed:
        q = q.where(
            text("livestock.attributes->>'breed' = :breed").bindparams(breed=params.breed)
        )
    if params.min_weight is not None:
        q = q.where(
            text("(livestock.attributes->>'weight')::numeric >= :min_w").bindparams(min_w=params.min_weight)
        )
    if params.max_weight is not None:
        q = q.where(
            text("(livestock.attributes->>'weight')::numeric <= :max_w").bindparams(max_w=params.max_weight)
        )
    if params.min_height is not None:
        q = q.where(
            text("(livestock.attributes->>'height')::numeric >= :min_h").bindparams(min_h=params.min_height)
        )
    if params.max_height is not None:
        q = q.where(
            text("(livestock.attributes->>'height')::numeric <= :max_h").bindparams(max_h=params.max_height)
        )
    if params.min_leg_length is not None:
        q = q.where(
            text("(livestock.attributes->>'leg_length')::numeric >= :min_ll").bindparams(min_ll=params.min_leg_length)
        )
    if params.max_leg_length is not None:
        q = q.where(
            text("(livestock.attributes->>'leg_length')::numeric <= :max_ll").bindparams(max_ll=params.max_leg_length)
        )

    # Count query (without pagination)
    count_q = select(text("count(*)")).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    offset = (params.page - 1) * params.page_size
    q = q.order_by(Livestock.updated_at.desc()).offset(offset).limit(params.page_size)
    rows = await db.execute(q)
    return list(rows.scalars().all()), int(total)


async def create_livestock(
    data: LivestockCreate,
    jzd_id: int,
    created_by: int,
    db: AsyncSession,
) -> tuple[Livestock, list[str]]:
    cattle_type = await get_cattle_type(db)
    errors = await validate_attributes(data.attributes, cattle_type.id, db)
    if errors:
        return None, errors  # type: ignore[return-value]

    livestock = Livestock(
        jzd_id=jzd_id,
        farm_id=data.farm_id,
        livestock_type_id=cattle_type.id,
        registration_number=data.registration_number,
        name=data.name,
        sex=data.sex,
        status=data.status,
        attributes=data.attributes,
        is_available_for_breeding=data.is_available_for_breeding
        if data.sex == LivestockSex.FEMALE
        else False,
        created_by=created_by,
    )
    db.add(livestock)
    await db.commit()
    await db.refresh(livestock)
    return livestock, []


async def update_livestock(
    livestock: Livestock, data: LivestockUpdate, db: AsyncSession
) -> tuple[Livestock, list[str]]:
    if data.attributes is not None:
        errors = await validate_attributes(data.attributes, livestock.livestock_type_id, db)
        if errors:
            return livestock, errors

    if data.farm_id is not None:
        livestock.farm_id = data.farm_id
    if data.name is not None:
        livestock.name = data.name
    if data.status is not None:
        livestock.status = data.status
    if data.attributes is not None:
        livestock.attributes = data.attributes
    if data.is_available_for_breeding is not None and livestock.sex == LivestockSex.FEMALE:
        livestock.is_available_for_breeding = data.is_available_for_breeding

    livestock.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(livestock)
    return livestock, []


async def generate_registration_number(jzd_id: int, db: AsyncSession) -> str:
    return await _next_reg_number(jzd_id, db)
