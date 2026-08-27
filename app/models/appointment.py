import enum
from datetime import date, datetime, time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.livestock import Livestock
    from app.models.user import AppUser


class AppointmentType(str, enum.Enum):
    VIEWING = "VIEWING"
    INSEMINATION = "INSEMINATION"
    CHECKUP = "CHECKUP"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Appointment(Base):
    __tablename__ = "appointment"
    __table_args__ = (
        Index("idx_appointment_jzd", "jzd_id"),
        Index("idx_appointment_livestock", "livestock_id"),
        Index("idx_appointment_date", "scheduled_date"),
        Index("idx_appointment_requester", "requester_id"),
        Index("idx_appointment_assignee", "assignee_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jzd_id: Mapped[int] = mapped_column(Integer, ForeignKey("jzd.id"), nullable=False)
    livestock_id: Mapped[int] = mapped_column(Integer, ForeignKey("livestock.id"), nullable=False)
    appointment_type: Mapped[AppointmentType] = mapped_column(Enum(AppointmentType), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.SCHEDULED
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    requester_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.id"), nullable=False)
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    livestock: Mapped["Livestock"] = relationship("Livestock")
    requester: Mapped["AppUser"] = relationship("AppUser", foreign_keys=[requester_id])
    assignee: Mapped[Optional["AppUser"]] = relationship("AppUser", foreign_keys=[assignee_id])
