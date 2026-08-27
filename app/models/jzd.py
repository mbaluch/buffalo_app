from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.farm import Farm
    from app.models.user import AppUser


class Jzd(Base):
    __tablename__ = "jzd"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2), default="CZ")
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 8))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    settings: Mapped[Optional["JzdSettings"]] = relationship(
        "JzdSettings", back_populates="jzd", uselist=False, cascade="all, delete-orphan"
    )
    users: Mapped[list["AppUser"]] = relationship("AppUser", back_populates="jzd")
    farms: Mapped[list["Farm"]] = relationship("Farm", back_populates="jzd")


class JzdSettings(Base):
    __tablename__ = "jzd_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jzd_id: Mapped[int] = mapped_column(Integer, ForeignKey("jzd.id"), nullable=False, unique=True)
    gestation_days: Mapped[int] = mapped_column(Integer, default=283)
    recovery_days: Mapped[int] = mapped_column(Integer, default=60)
    # Monotonic counter for auto-generating Czech cattle registration numbers
    next_registration_seq: Mapped[int] = mapped_column(Integer, default=1)

    jzd: Mapped["Jzd"] = relationship("Jzd", back_populates="settings")
