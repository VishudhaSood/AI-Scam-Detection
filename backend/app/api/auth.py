from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_required
from app.auth.security import create_access_token, hash_password, verify_password
from app.database import crud
from app.database.connection import get_db
from app.database.models import User
from app.models.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Create an account and return a bearer token. Email is normalised to
    lower-case; duplicates are a 409 so the caller can prompt to log in instead."""
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please enter a valid email address.")
    if crud.get_user_by_email(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = crud.create_user(db, email, hash_password(body.password))
    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=UserOut(id=user.id, email=user.email))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Verify credentials and return a bearer token. A missing account and a wrong
    password give the same 401, so the response doesn't reveal which emails exist."""
    email = body.email.strip().lower()
    user = crud.get_user_by_email(db, email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=UserOut(id=user.id, email=user.email))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user_required)) -> UserOut:
    """Return the current user; used by the frontend to validate a stored token."""
    return UserOut(id=user.id, email=user.email)
