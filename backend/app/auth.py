"""Mock identity verification, real server-validated/revocable sessions."""
import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from app.config import settings
from app.database import get_db
from app.models import AuthSession, User, UserSettings, now_utc
from app.schemas import ChallengeOut, IdentifierInput, ProfileInput, SessionOut, UserOut, VerifyInput

COOKIE_NAME = "signal_session"
Db = Annotated[Session, Depends(get_db)]


def mutation_origin(request: HTTPConnection) -> None:
    if request.scope["type"] == "websocket":
        return  # The socket route performs its own pre-handshake Origin check.
    # SameSite protects cross-site requests; this also rejects other local origins.
    origin = request.headers.get("origin")
    if origin is not None and origin != settings.frontend_origin:
        raise HTTPException(403, "Request origin is not allowed")


def current_session(request: Request, db: Db) -> AuthSession:
    return validated_session(db, request.cookies.get(COOKIE_NAME))


def validated_session(db, token) -> AuthSession:
    if not token or len(token) > 200:
        raise HTTPException(401, "Please sign in to continue")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = db.scalar(select(AuthSession).where(
        AuthSession.token_hash == token_hash,
        AuthSession.revoked_at.is_(None), AuthSession.expires_at > now_utc(),
    ))
    if session is None:
        raise HTTPException(401, "Your session has expired. Please sign in again")
    return session


def current_user(session: Annotated[AuthSession, Depends(current_session)]) -> User:
    return session.user


CurrentUser = Annotated[User, Depends(current_user)]
router = APIRouter(prefix="/api/v1", dependencies=[Depends(mutation_origin)])


def session_response(user: User) -> SessionOut:
    # An avatar is mandatory in this demo's profile step. Existing seed profiles
    # lacking avatars complete this once; the persisted avatar restores the step.
    return SessionOut(user=UserOut.model_validate(user), needs_profile=user.avatar_url is None)


@router.post("/auth/challenges", response_model=ChallengeOut)
def challenge(body: IdentifierInput):
    return ChallengeOut(identifier=body.identifier, mock_code=settings.mock_otp,
        message="Demo verification only: no SMS is sent. Use the displayed fixed code. Anyone with this code can access a demo identity.")


@router.post("/auth/verify", response_model=SessionOut)
def verify(body: VerifyInput, response: Response, db: Db):
    if not secrets.compare_digest(body.otp, settings.mock_otp):
        raise HTTPException(422, "Incorrect demo verification code")
    column = User.phone_e164 if body.identifier.startswith("+") else User.username
    user = db.scalar(select(User).where(column == body.identifier))
    if user is None:
        user = User(display_name="New user" if body.identifier.startswith("+") else body.identifier,
                    phone_e164=body.identifier if body.identifier.startswith("+") else None,
                    username=None if body.identifier.startswith("+") else body.identifier)
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            # Concurrent registration of the same normalized identifier.
            db.rollback()
            user = db.scalar(select(User).where(column == body.identifier))
            if user is None:
                raise HTTPException(409, "Registration conflicted. Please retry")
        else:
            db.add(UserSettings(user_id=user.id))
    token = secrets.token_urlsafe(32)
    created = now_utc()
    db.add(AuthSession(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                       created_at=created, expires_at=created + timedelta(days=settings.session_days)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=settings.session_days * 86400,
                        httponly=True, secure=settings.session_cookie_secure, samesite="lax", path="/")
    return session_response(user)


@router.get("/auth/session", response_model=SessionOut)
def restore(user: CurrentUser):
    return session_response(user)


@router.post("/auth/logout")
async def logout(response: Response, db: Db, session: Annotated[AuthSession, Depends(current_session)]):
    session.revoked_at = now_utc()
    db.commit()
    from app.realtime import manager
    await manager.revoke(session.id)
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.session_cookie_secure,
                           httponly=True, samesite="lax")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=SessionOut)
def update_profile(body: ProfileInput, user: CurrentUser, db: Db):
    user.display_name = body.display_name
    user.avatar_url = body.avatar_url
    db.commit()
    from app.realtime import manager
    for connection in list(manager.connections):
        if connection.user_id == user.id:
            connection.name = user.display_name
    return session_response(user)
