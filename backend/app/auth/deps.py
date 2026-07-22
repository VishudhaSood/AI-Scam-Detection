"""FastAPI auth dependencies.

Anonymous use is allowed everywhere except /auth/me, so the *optional* dependency
is the default across the app and simply returns None when no valid bearer token
is present.
"""
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.database import crud
from app.database.connection import get_db
from app.database.models import User


def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Resolve the 'Authorization: Bearer <jwt>' header to a User, or None.

    Never raises: a missing, malformed, expired, or unknown token all resolve to
    an anonymous (None) caller, which every non-auth endpoint tolerates.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    return crud.get_user_by_id(db, user_id)


def get_current_user_required(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """Same as above but 401s when unauthenticated. Used only by /auth/me."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
