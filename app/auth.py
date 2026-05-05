import os

from fastapi import Header, HTTPException


def require_control_auth(x_control_pin: str | None = Header(default=None)) -> None:
    expected = os.getenv("YACHTOS_CONTROL_PIN")
    if not expected:
        return
    if x_control_pin != expected:
        raise HTTPException(status_code=401, detail="Invalid control PIN")
