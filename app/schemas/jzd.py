from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class JzdSettingsSchema(BaseModel):
    gestation_days: int = Field(default=283, ge=200, le=400)
    recovery_days: int = Field(default=60, ge=0, le=365)


class JzdCreate(BaseModel):
    registration_number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = Field(default="CZ", max_length=2)
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    settings: JzdSettingsSchema = JzdSettingsSchema()


class JzdUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_active: Optional[bool] = None
    settings: Optional[JzdSettingsSchema] = None


class JzdResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    registration_number: str
    name: str
    address: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    country: str
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    is_active: bool
    gestation_days: int = 283
    recovery_days: int = 60

    @classmethod
    def from_orm_with_settings(cls, jzd) -> "JzdResponse":
        data = {
            "id": jzd.id,
            "registration_number": jzd.registration_number,
            "name": jzd.name,
            "address": jzd.address,
            "city": jzd.city,
            "postal_code": jzd.postal_code,
            "country": jzd.country,
            "latitude": jzd.latitude,
            "longitude": jzd.longitude,
            "contact_phone": jzd.contact_phone,
            "contact_email": jzd.contact_email,
            "is_active": jzd.is_active,
            "gestation_days": jzd.settings.gestation_days if jzd.settings else 283,
            "recovery_days": jzd.settings.recovery_days if jzd.settings else 60,
        }
        return cls(**data)
