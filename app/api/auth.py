from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.auth import require_viewer_auth
from app.services.core import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    try:
        return auth_service.login(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.get("/me", dependencies=[Depends(require_viewer_auth)])
def me(authorization: str | None = Header(default=None)):
    token = _token(authorization)
    user = auth_service.get_user_for_token(token)
    return user or {"username": "dev", "role": "admin"}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    token = _token(authorization)
    if token:
        auth_service.logout(token)
    return {"status": "ok"}


def _token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token or None
