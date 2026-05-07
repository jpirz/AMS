import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.db import get_connection


ROLE_LEVELS = {"viewer": 1, "operator": 2, "admin": 3}


class AuthService:
    def seed_env_users(self) -> None:
        """
        Optional bootstrap. If passwords are not configured, dev mode remains open
        unless YACHTOS_CONTROL_PIN is set.
        """
        self._seed_one("YACHTOS_ADMIN_USER", "admin", "YACHTOS_ADMIN_PASSWORD", "admin")
        self._seed_one("YACHTOS_OPERATOR_USER", "operator", "YACHTOS_OPERATOR_PASSWORD", "operator")
        self._seed_one("YACHTOS_VIEWER_USER", "viewer", "YACHTOS_VIEWER_PASSWORD", "viewer")

    def users_exist(self) -> bool:
        conn = get_connection()
        try:
            row = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
        finally:
            conn.close()
        return row is not None

    def login(self, username: str, password: str) -> Dict[str, Any]:
        user = self.get_user_by_username(username)
        if user is None or not verify_password(password, user["password_hash"]):
            raise ValueError("Invalid username or password")

        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=int(os.getenv("YACHTOS_SESSION_HOURS", "12")))

        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO auth_sessions (token, user_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token, user["id"], now.isoformat(), expires.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "token": token,
            "token_type": "bearer",
            "expires_at": expires.isoformat(),
            "user": self._public_user(user),
        }

    def logout(self, token: str) -> None:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()

    def get_user_for_token(self, token: str | None) -> Optional[Dict[str, Any]]:
        if not token:
            return None

        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT u.id, u.username, u.role, s.expires_at "
                "FROM auth_sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token = ?",
                (token,),
            ).fetchone()
            if row and row["expires_at"] <= now:
                conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
                conn.commit()
                return None
        finally:
            conn.close()

        if row is None:
            return None
        return {"id": row["id"], "username": row["username"], "role": row["role"]}

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "password_hash": row["password_hash"],
            "role": row["role"],
        }

    def _seed_one(
        self,
        username_env: str,
        default_username: str,
        password_env: str,
        role: str,
    ) -> None:
        password = os.getenv(password_env)
        if not password:
            return

        username = os.getenv(username_env, default_username)
        now = datetime.now(timezone.utc).isoformat()
        password_hash = hash_password(password)

        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(username) DO UPDATE SET "
                "password_hash = excluded.password_hash, role = excluded.role",
                (username, password_hash, role, now),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _public_user(user: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": user["id"], "username": user["username"], "role": user["role"]}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 150_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, digest = encoded.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 150_000)
    return hmac.compare_digest(check.hex(), digest)


def role_allows(actual: str, required: str) -> bool:
    return ROLE_LEVELS.get(actual, 0) >= ROLE_LEVELS.get(required, 99)
