import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.livestock import Livestock
    from app.models.user import AppUser


class HealthRecordType(str, enum.Enum):
    CHECKUP = "CHECKUP"
    TREATMENT = "TREATMENT"
    VACCINATION = "VACCINATION"
    DIAGNOSIS = "DIAGNOSIS"
    CALVING = "CALVING"


class HealthRecord(Base):
    __tablename__ = "health_record"
    __table_args__ = (
        Index("idx_health_livestock", "livestock_id"),
        Index("idx_health_jzd", "jzd_id"),
        Index("idx_health_date", "record_date"),
        Index("idx_health_vet", "veterinarian_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jzd_id: Mapped[int] = mapped_column(Integer, ForeignKey("jzd.id"), nullable=False)
    livestock_id: Mapped[int] = mapped_column(Integer, ForeignKey("livestock.id"), nullable=False)
    veterinarian_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.id"))
    record_type: Mapped[HealthRecordType] = mapped_column(Enum(HealthRecordType), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    diagnosis: Mapped[Optional[str]] = mapped_column(String(500))
    treatment: Mapped[Optional[str]] = mapped_column(Text)
    medication: Mapped[Optional[str]] = mapped_column(String(500))
    dosage: Mapped[Optional[str]] = mapped_column(String(200))
    next_checkup_date: Mapped[Optional[date]] = mapped_column(Date)
    temperature: Mapped[Optional[float]] = mapped_column(Numeric(4, 1))
    weight_at_record: Mapped[Optional[float]] = mapped_column(Numeric(7, 2))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    livestock: Mapped["Livestock"] = relationship("Livestock")
    veterinarian: Mapped[Optional["AppUser"]] = relationship("AppUser", foreign_keys=[veterinarian_id])
