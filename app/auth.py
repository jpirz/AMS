import os

from fastapi import Header, HTTPException

from app.services.auth_service import role_allows
from app.services.core import auth_service


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def require_role(
    required_role: str,
    authorization: str | None = Header(default=None),
    x_control_pin: str | None = Header(default=None),
) -> dict | None:
    token = _bearer_token(authorization)
    user = auth_service.get_user_for_token(token)
    if user and role_allows(user["role"], required_role):
        return user

    expected = os.getenv("YACHTOS_CONTROL_PIN")
    if expected and x_control_pin == expected and required_role in {"operator", "admin"}:
        return {"username": "pin-fallback", "role": "admin"}

    if not expected and not auth_service.users_exist():
        return None

    raise HTTPException(status_code=401, detail=f"{required_role} role required")


def require_viewer_auth(
    authorization: str | None = Header(default=None),
    x_control_pin: str | None = Header(default=None),
) -> dict | None:
    return require_role("viewer", authorization=authorization, x_control_pin=x_control_pin)


def require_control_auth(
    authorization: str | None = Header(default=None),
    x_control_pin: str | None = Header(default=None),
) -> dict | None:
    return require_role("operator", authorization=authorization, x_control_pin=x_control_pin)


def require_admin_auth(
    authorization: str | None = Header(default=None),
    x_control_pin: str | None = Header(default=None),
) -> dict | None:
    return require_role("admin", authorization=authorization, x_control_pin=x_control_pin)


def require_pin_or_open(x_control_pin: str | None = Header(default=None)) -> None:
    expected = os.getenv("YACHTOS_CONTROL_PIN")
    if not expected:
        return
    if x_control_pin != expected:
        raise HTTPException(status_code=401, detail="Invalid control PIN")
