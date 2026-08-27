from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    role: UserRole
    jzd_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_jzd_for_role(self) -> "UserCreate":
        if self.role == UserRole.SUPER_ADMIN and self.jzd_id is not None:
            raise ValueError("SUPER_ADMIN must not be assigned to a JZD")
        if self.role != UserRole.SUPER_ADMIN and self.jzd_id is None:
            raise ValueError("Non-SUPER_ADMIN users must be assigned to a JZD")
        return self


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    jzd_id: Optional[int] = None


class PasswordChange(BaseModel):
    new_password: str = Field(min_length=8, max_length=100)


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    role: UserRole
    jzd_id: Optional[int]
    is_active: bool
    full_name: str
