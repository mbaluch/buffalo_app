import json
import math
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.farm import Farm
from app.models.livestock import Livestock, LivestockSex, LivestockStatus, PregnancyStatus


# Haversine formula — returns distance in km
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Numeric attribute keys used in scoring
_SCORE_ATTRS = ["weight", "height", "hip_width", "chest_girth"]


def _score_pair(cow: Livestock, bull: Livestock) -> tuple[float, dict]:
    """
    Score a cow–bull pair 0-100.
    - Breed match: 40 pts
    - Attribute similarity (each of 4 numeric attrs): up to 15 pts each → 60 pts total
    """
    details: dict = {}
    score = 0.0

    # Breed compatibility (same breed = full points)
    cow_breed = (cow.attributes or {}).get("breed", "")
    bull_breed = (bull.attributes or {}).get("breed", "")
    breed_pts = 40.0 if cow_breed and cow_breed == bull_breed else 0.0
    score += breed_pts
    details["breed_match"] = breed_pts

    # Numeric attribute similarity
    per_attr = 60.0 / len(_SCORE_ATTRS)
    for key in _SCORE_ATTRS:
        cow_val = (cow.attributes or {}).get(key)
        bull_val = (bull.attributes or {}).get(key)
        if cow_val is None or bull_val is None:
            details[key] = 0.0
            continue
        try:
            cv, bv = float(cow_val), float(bull_val)
        except (TypeError, ValueError):
            details[key] = 0.0
            continue
        # linear decay: 0 difference → full pts; 50% difference → 0 pts
        avg = (cv + bv) / 2 if (cv + bv) > 0 else 1
        rel_diff = abs(cv - bv) / avg
        attr_pts = max(0.0, per_attr * (1 - rel_diff / 0.5))
        score += attr_pts
        details[key] = round(attr_pts, 2)

    return round(score, 2), details


async def find_breeding_matches(
    jzd_id: int,
    db: AsyncSession,
    *,
    max_distance_km: Optional[float] = None,
    cow_id: Optional[int] = None,
    top_n: int = 10,
    cross_jzd: bool = False,
) -> list[dict]:
    """
    Return ranked breeding match recommendations.

    For each eligible cow (FEMALE, ACTIVE, available, not currently PREGNANT)
    score against every eligible bull (MALE, ACTIVE).

    When cross_jzd=True, bulls from all JZDs are considered (for
    SPERM_COLLECTOR / INSEMINATOR / VETERINARIAN roles).
    """
    # Fetch cows
    cow_q = (
        select(Livestock)
        .where(
            Livestock.jzd_id == jzd_id,
            Livestock.sex == LivestockSex.FEMALE,
            Livestock.status == LivestockStatus.ACTIVE,
            Livestock.is_available_for_breeding.is_(True),
            Livestock.pregnancy_status.is_(None),
        )
        .options(selectinload(Livestock.farm))
    )
    if cow_id:
        cow_q = cow_q.where(Livestock.id == cow_id)
    cows = list((await db.execute(cow_q)).scalars().all())

    # Fetch bulls
    bull_q = (
        select(Livestock)
        .where(
            Livestock.sex == LivestockSex.MALE,
            Livestock.status == LivestockStatus.ACTIVE,
        )
        .options(selectinload(Livestock.farm))
    )
    if not cross_jzd:
        bull_q = bull_q.where(Livestock.jzd_id == jzd_id)
    bulls = list((await db.execute(bull_q)).scalars().all())

    results: list[dict] = []

    for cow in cows:
        cow_lat = float(cow.farm.latitude) if cow.farm and cow.farm.latitude else None
        cow_lon = float(cow.farm.longitude) if cow.farm and cow.farm.longitude else None

        ranked: list[dict] = []
        for bull in bulls:
            # Distance filter
            distance_km: Optional[float] = None
            if cow_lat is not None and cow_lon is not None and bull.farm:
                b_lat = float(bull.farm.latitude) if bull.farm.latitude else None
                b_lon = float(bull.farm.longitude) if bull.farm.longitude else None
                if b_lat is not None and b_lon is not None:
                    distance_km = _haversine_km(cow_lat, cow_lon, b_lat, b_lon)
                    if max_distance_km and distance_km > max_distance_km:
                        continue

            score, details = _score_pair(cow, bull)
            ranked.append(
                {
                    "cow_id": cow.id,
                    "cow_reg": cow.registration_number,
                    "cow_name": cow.name,
                    "bull_id": bull.id,
                    "bull_reg": bull.registration_number,
                    "bull_name": bull.name,
                    "bull_jzd_id": bull.jzd_id,
                    "score": score,
                    "distance_km": round(distance_km, 2) if distance_km is not None else None,
                    "score_details": details,
                }
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        results.extend(ranked[:top_n])

    return results
