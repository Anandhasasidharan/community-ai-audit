"""Registration and login endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from community_ai_audit.api.auth import hash_password, verify_password, create_jwt, generate_api_key
from community_ai_audit.api.database import get_session, Organization, User, ApiKey

router = APIRouter(prefix="/auth")


class RegisterBody(BaseModel):
    email: str
    password: str
    org_name: str = "default"


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(body: RegisterBody):
    db = get_session()
    if db.query(User).filter(User.email == body.email).first():
        db.close()
        raise HTTPException(409, "Email already registered")
    org = Organization(name=body.org_name)
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    key = ApiKey(key=generate_api_key(), user_id=user.id, name="default")
    db.add(key)
    db.commit()
    db.close()
    return {"user_id": user.id, "org_id": org.id, "api_key": key.key}


@router.post("/login")
async def login(body: LoginBody):
    db = get_session()
    user = db.query(User).filter(User.email == body.email).first()
    db.close()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    token = create_jwt({"user_id": user.id, "org_id": user.org_id})
    return {"token": token}
