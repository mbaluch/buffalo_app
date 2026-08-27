from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.services.auth import decode_access_token

# Paths that don't need a JZD context
_PUBLIC_PREFIXES = ("/auth/", "/static/", "/favicon.ico")


class JzdContextMiddleware(BaseHTTPMiddleware):
    """Decodes the JWT access token from cookie and attaches user metadata to request.state.

    Downstream code can read:
        request.state.user_id   — int | None
        request.state.jzd_id   — int | None  (None for SUPER_ADMIN and unauthenticated)
        request.state.role      — str | None
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user_id = None
        request.state.jzd_id = None
        request.state.role = None

        token = request.cookies.get("access_token")
        if token:
            payload = decode_access_token(token)
            if payload:
                request.state.user_id = int(payload["sub"])
                request.state.jzd_id = payload.get("jzd_id")
                request.state.role = payload.get("role")

        return await call_next(request)
