from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenPayload(BaseModel):
    sub: int  # user id
    role: str
    jzd_id: int | None
    exp: int
