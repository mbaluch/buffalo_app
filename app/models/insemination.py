import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.livestock import Livestock
    from app.models.user import AppUser


class InseminationMethod(str, enum.Enum):
    ARTIFICIAL = "ARTIFICIAL"
    NATURAL = "NATURAL"


class InseminationStatus(str, enum.Enum):
    PERFORMED = "PERFORMED"
    CONFIRMED_PREGNANT = "CONFIRMED_PREGNANT"
    FAILED = "FAILED"
    CALVED = "CALVED"


class InseminationRecord(Base):
    __tablename__ = "insemination_record"
    __table_args__ = (
        Index("idx_insem_cow", "cow_id"),
        Index("idx_insem_bull", "bull_id"),
        Index("idx_insem_jzd", "jzd_id"),
        Index("idx_insem_date", "insemination_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jzd_id: Mapped[int] = mapped_column(Integer, ForeignKey("jzd.id"), nullable=False)
    cow_id: Mapped[int] = mapped_column(Integer, ForeignKey("livestock.id"), nullable=False)
    bull_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("livestock.id"))
    inseminator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.id"))
    method: Mapped[InseminationMethod] = mapped_column(Enum(InseminationMethod), nullable=False)
    status: Mapped[InseminationStatus] = mapped_column(
        Enum(InseminationStatus), nullable=False, default=InseminationStatus.PERFORMED
    )
    insemination_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_calving_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_calving_date: Mapped[Optional[date]] = mapped_column(Date)
    pregnancy_confirmed_date: Mapped[Optional[date]] = mapped_column(Date)
    pregnancy_confirmed_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    calf_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("livestock.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    cow: Mapped["Livestock"] = relationship("Livestock", foreign_keys=[cow_id])
    bull: Mapped[Optional["Livestock"]] = relationship("Livestock", foreign_keys=[bull_id])
    calf: Mapped[Optional["Livestock"]] = relationship("Livestock", foreign_keys=[calf_id])
    inseminator: Mapped[Optional["AppUser"]] = relationship("AppUser", foreign_keys=[inseminator_id])
    pregnancy_confirmed_by: Mapped[Optional["AppUser"]] = relationship(
        "AppUser", foreign_keys=[pregnancy_confirmed_by_id]
    )
