import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.jzd import Jzd


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    JZD_ADMIN = "JZD_ADMIN"
    FARM_OWNER = "FARM_OWNER"
    SPERM_COLLECTOR = "SPERM_COLLECTOR"
    INSEMINATOR = "INSEMINATOR"
    VETERINARIAN = "VETERINARIAN"

    @property
    def is_cross_jzd_reader(self) -> bool:
        """Roles that can read livestock across all JZDs."""
        return self in {
            UserRole.SPERM_COLLECTOR,
            UserRole.INSEMINATOR,
            UserRole.VETERINARIAN,
        }


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        Index("idx_user_jzd", "jzd_id"),
        Index("idx_user_role", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # NULL for SUPER_ADMIN — they belong to no JZD
    jzd_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("jzd.id"))
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    jzd: Mapped[Optional["Jzd"]] = relationship("Jzd", back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        parts = filter(None, [self.first_name, self.last_name])
        return " ".join(parts) or self.username


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["AppUser"] = relationship("AppUser", back_populates="refresh_tokens")
