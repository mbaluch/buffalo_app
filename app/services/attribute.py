from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.livestock import AttributeDefinition, LivestockType


async def get_livestock_type(code: str, db: AsyncSession) -> LivestockType | None:
    result = await db.execute(select(LivestockType).where(LivestockType.code == code))
    return result.scalar_one_or_none()


async def get_cattle_type(db: AsyncSession) -> LivestockType:
    lt = await get_livestock_type("CATTLE", db)
    if not lt:
        raise RuntimeError("CATTLE livestock type not found — run migrations first")
    return lt


async def get_attribute_definitions(
    livestock_type_id: int,
    db: AsyncSession,
    active_only: bool = True,
) -> list[AttributeDefinition]:
    q = select(AttributeDefinition).where(
        AttributeDefinition.livestock_type_id == livestock_type_id
    )
    if active_only:
        q = q.where(AttributeDefinition.is_active.is_(True))
    q = q.order_by(AttributeDefinition.display_order)
    result = await db.execute(q)
    return list(result.scalars().all())


async def validate_attributes(
    attributes: dict,
    livestock_type_id: int,
    db: AsyncSession,
) -> list[str]:
    """Returns a list of validation error messages (empty = valid)."""
    definitions = await get_attribute_definitions(livestock_type_id, db)
    errors = []
    for defn in definitions:
        value = attributes.get(defn.attribute_key)
        err = defn.validate_value(value)
        if err:
            errors.append(err)
    return errors
