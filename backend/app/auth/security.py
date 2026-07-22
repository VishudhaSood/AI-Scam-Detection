"""Authentication primitives: password hashing (stdlib PBKDF2) and JWT tokens
(PyJWT).

Deliberately free of any *app* imports so app.database.connection can import
hash_password for demo-user seeding without creating an import cycle.
"""
import base64
import hashlib
import hmac
import os
import time

import jwt  # PyJWT

# HS256 signing secret. The dev default keeps local runs working out of the box;
# set AUTH_SECRET_KEY in the environment (run.py / .env) for anything real.
SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "aiscamguard-dev-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 7 * 24 * 3600  # 7 days

_PBKDF2_ROUNDS = 200_000


def hash_password(password: str) -> str:
    """Salted PBKDF2-SHA256 hash, serialised as 'pbkdf2$<salt_b64>$<dk_b64>'."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of a password against a stored PBKDF2 hash."""
    try:
        scheme, salt_b64, dk_b64 = stored.split("$")
        if scheme != "pbkdf2":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def create_access_token(user_id: int, email: str) -> str:
    """Signed JWT carrying the user id (sub) and email, expiring in 7 days."""
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Return the token payload, or None if invalid / expired / tampered."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
