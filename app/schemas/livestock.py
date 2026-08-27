import re
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.livestock import LivestockSex, LivestockStatus, PregnancyStatus

CZ_ID_RE = re.compile(r"^CZ\d{12}$")


class LivestockCreate(BaseModel):
    farm_id: int
    registration_number: str = Field(min_length=14, max_length=14)
    name: Optional[str] = Field(None, max_length=255)
    sex: LivestockSex
    status: LivestockStatus = LivestockStatus.ACTIVE
    attributes: dict[str, Any] = {}
    is_available_for_breeding: bool = True

    @field_validator("registration_number")
    @classmethod
    def validate_reg_number(cls, v: str) -> str:
        if not CZ_ID_RE.match(v):
            raise ValueError("Registration number must match CZ followed by 12 digits (e.g. CZ000123456789)")
        return v


class LivestockUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    farm_id: Optional[int] = None
    status: Optional[LivestockStatus] = None
    attributes: Optional[dict[str, Any]] = None
    is_available_for_breeding: Optional[bool] = None


class LivestockSearchParams(BaseModel):
    sex: Optional[LivestockSex] = None
    farm_id: Optional[int] = None
    status: Optional[LivestockStatus] = LivestockStatus.ACTIVE
    available_for_breeding: Optional[bool] = None
    pregnancy_status: Optional[PregnancyStatus] = None
    breed: Optional[str] = None
    min_weight: Optional[float] = None
    max_weight: Optional[float] = None
    min_height: Optional[float] = None
    max_height: Optional[float] = None
    min_leg_length: Optional[float] = None
    max_leg_length: Optional[float] = None
    q: Optional[str] = None  # free-text: name or registration number
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=24, ge=1, le=100)


class LivestockResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    jzd_id: int
    farm_id: int
    registration_number: str
    name: Optional[str]
    sex: LivestockSex
    status: LivestockStatus
    attributes: dict[str, Any]
    is_available_for_breeding: bool
    pregnancy_status: Optional[PregnancyStatus]
    expected_calving_date: Optional[date]
    type_label: str
    display_name: str


class AttributeDefinitionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    attribute_key: str
    attribute_name: str
    data_type: str
    unit: Optional[str]
    is_searchable: bool
    is_required: bool
    enum_values: Optional[list]
    validation_rules: Optional[dict]
    display_order: int
