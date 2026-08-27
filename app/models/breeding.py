from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.livestock import Livestock


class BreedingMatchRecommendation(Base):
    __tablename__ = "breeding_match_recommendation"
    __table_args__ = (
        Index("idx_breedmatch_cow", "cow_id"),
        Index("idx_breedmatch_bull", "bull_id"),
        Index("idx_breedmatch_jzd", "jzd_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jzd_id: Mapped[int] = mapped_column(Integer, ForeignKey("jzd.id"), nullable=False)
    cow_id: Mapped[int] = mapped_column(Integer, ForeignKey("livestock.id"), nullable=False)
    bull_id: Mapped[int] = mapped_column(Integer, ForeignKey("livestock.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    distance_km: Mapped[Optional[float]] = mapped_column(Float)
    score_details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cow: Mapped["Livestock"] = relationship("Livestock", foreign_keys=[cow_id])
    bull: Mapped["Livestock"] = relationship("Livestock", foreign_keys=[bull_id])
