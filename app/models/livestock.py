import enum
import re
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.farm import Farm
    from app.models.jzd import Jzd
    from app.models.user import AppUser

CZ_CATTLE_ID_RE = re.compile(r"^CZ\d{12}$")


class LivestockSex(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class LivestockStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DECEASED = "DECEASED"
    SOLD = "SOLD"


class PregnancyStatus(str, enum.Enum):
    PREGNANT = "PREGNANT"
    CALVED = "CALVED"


class AttributeDataType(str, enum.Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    ENUM = "ENUM"


class LivestockType(Base):
    __tablename__ = "livestock_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # CATTLE
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    attribute_definitions: Mapped[list["AttributeDefinition"]] = relationship(
        "AttributeDefinition", back_populates="livestock_type"
    )
    livestock: Mapped[list["Livestock"]] = relationship("Livestock", back_populates="livestock_type")


class AttributeDefinition(Base):
    __tablename__ = "attribute_definition"
    __table_args__ = (
        Index("idx_attr_def_type", "livestock_type_id"),
        Index("idx_attr_def_searchable", "is_searchable"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    livestock_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("livestock_type.id"), nullable=False)
    attribute_key: Mapped[str] = mapped_column(String(100), nullable=False)
    attribute_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[AttributeDataType] = mapped_column(Enum(AttributeDataType), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    is_searchable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # For ENUM: ["Holstein", "Angus", ...]
    enum_values: Mapped[Optional[list]] = mapped_column(JSON)
    # For NUMBER/DECIMAL: {"min": 0, "max": 2000}; for STRING: {"pattern": "..."}
    validation_rules: Mapped[Optional[dict]] = mapped_column(JSON)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    livestock_type: Mapped["LivestockType"] = relationship("LivestockType", back_populates="attribute_definitions")

    def validate_value(self, value: Any) -> str | None:
        """Return error message or None if valid."""
        if value is None or value == "":
            return f"{self.attribute_name} is required" if self.is_required else None

        if self.data_type == AttributeDataType.ENUM:
            if self.enum_values and str(value) not in self.enum_values:
                return f"{self.attribute_name} must be one of: {', '.join(self.enum_values)}"

        elif self.data_type in (AttributeDataType.NUMBER, AttributeDataType.DECIMAL):
            try:
                num = float(value)
                if self.validation_rules:
                    if "min" in self.validation_rules and num < self.validation_rules["min"]:
                        return f"{self.attribute_name} must be ≥ {self.validation_rules['min']}"
                    if "max" in self.validation_rules and num > self.validation_rules["max"]:
                        return f"{self.attribute_name} must be ≤ {self.validation_rules['max']}"
            except (TypeError, ValueError):
                return f"{self.attribute_name} must be a number"

        return None


class Livestock(Base):
    __tablename__ = "livestock"
    __table_args__ = (
        Index("idx_livestock_jzd", "jzd_id"),
        Index("idx_livestock_farm", "farm_id"),
        Index("idx_livestock_type", "livestock_type_id"),
        Index("idx_livestock_status", "status"),
        Index("idx_livestock_available", "is_available_for_breeding"),
        Index("idx_livestock_pregnancy", "pregnancy_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jzd_id: Mapped[int] = mapped_column(Integer, ForeignKey("jzd.id"), nullable=False)
    farm_id: Mapped[int] = mapped_column(Integer, ForeignKey("farm.id"), nullable=False)
    livestock_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("livestock_type.id"), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    sex: Mapped[LivestockSex] = mapped_column(Enum(LivestockSex), nullable=False)
    status: Mapped[LivestockStatus] = mapped_column(
        Enum(LivestockStatus), nullable=False, default=LivestockStatus.ACTIVE
    )
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_available_for_breeding: Mapped[bool] = mapped_column(Boolean, default=True)
    pregnancy_status: Mapped[Optional[PregnancyStatus]] = mapped_column(Enum(PregnancyStatus))
    pregnancy_start_date: Mapped[Optional[date]] = mapped_column(Date)
    expected_calving_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_calving_date: Mapped[Optional[date]] = mapped_column(Date)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    jzd: Mapped["Jzd"] = relationship("Jzd")
    farm: Mapped["Farm"] = relationship("Farm")
    livestock_type: Mapped["LivestockType"] = relationship("LivestockType", back_populates="livestock")
    photos: Mapped[list["LivestockPhoto"]] = relationship(
        "LivestockPhoto", back_populates="livestock",
        cascade="all, delete-orphan", order_by="LivestockPhoto.display_order"
    )
    creator: Mapped[Optional["AppUser"]] = relationship("AppUser", foreign_keys=[created_by])

    @property
    def display_name(self) -> str:
        return self.name or self.registration_number

    @property
    def primary_photo(self) -> Optional["LivestockPhoto"]:
        for p in self.photos:
            if p.is_primary:
                return p
        return self.photos[0] if self.photos else None

    @property
    def type_label(self) -> str:
        if self.sex == LivestockSex.FEMALE:
            return "Cow"
        return "Bull"


class LivestockPhoto(Base):
    __tablename__ = "livestock_photo"
    __table_args__ = (
        Index("idx_photo_livestock", "livestock_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    livestock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("livestock.id", ondelete="CASCADE"), nullable=False
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    thumbnail_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("app_user.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    livestock: Mapped["Livestock"] = relationship("Livestock", back_populates="photos")
