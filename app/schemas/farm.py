from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class FarmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    contact_phone: Optional[str] = Field(None, max_length=50)
    owner_id: Optional[int] = None


class FarmUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    contact_phone: Optional[str] = None
    owner_id: Optional[int] = None
    is_active: Optional[bool] = None


class FarmResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    jzd_id: int
    owner_id: Optional[int]
    name: str
    registration_number: Optional[str]
    address: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    latitude: Decimal
    longitude: Decimal
    contact_phone: Optional[str]
    is_active: bool
