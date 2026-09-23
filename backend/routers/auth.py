# backend/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models_db import User
from auth_utils import verify_password, hash_password, create_access_token, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = ""
    role: Optional[str] = "manager"


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Tizimga kirish va JWT token olish"""
    result = await db.execute(select(User).where(User.username == req.username.strip()))
    user = result.scalars().first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Login yoki parol noto'g'ri",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ushbu foydalanuvchi hisobi faol emas",
        )

    token = create_access_token(data={"sub": user.username, "role": user.role})
    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "avatar_url": user.avatar_url or "",
        }
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Joriy tizimga kirgan foydalanuvchi ma'lumotlari"""
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "full_name": current_user.full_name or current_user.username,
            "role": current_user.role,
            "avatar_url": current_user.avatar_url or "",
        }
    }


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = None
    avatar_url: Optional[str] = None


@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """Foydalanuvchi profili"""
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "full_name": current_user.full_name or current_user.username,
            "role": current_user.role,
            "avatar_url": current_user.avatar_url or "",
        }
    }


@router.put("/profile")
async def update_profile(
    req: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Foydalanuvchi profili (ism, parol, avatar)ni yangilash"""
    user = await db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    if req.full_name is not None:
        user.full_name = req.full_name.strip()
    if req.avatar_url is not None:
        user.avatar_url = req.avatar_url.strip()
    if req.password and req.password.strip():
        user.hashed_password = hash_password(req.password.strip())

    await db.commit()
    await db.refresh(user)

    return {
        "success": True,
        "message": "Profil muvaffaqiyatli yangilandi",
        "data": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "avatar_url": user.avatar_url or "",
        }
    }


@router.get("/users")
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Barcha foydalanuvchilar (faqat admin uchun)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Faqat admin uchun ruxsat berilgan")
    
    result = await db.execute(select(User).order_by(User.id.asc()))
    users = result.scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
            }
            for u in users
        ]
    }


@router.post("/users")
async def create_user(
    req: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Yangi foydalanuvchi qo'shish (faqat admin uchun)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Faqat admin uchun ruxsat berilgan")

    existing = await db.execute(select(User).where(User.username == req.username.strip()))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Bunday username mavjud")

    new_user = User(
        username=req.username.strip(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name.strip() if req.full_name else "",
        role=req.role or "manager",
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "success": True,
        "message": "Foydalanuvchi muvaffaqiyatli yaratildi",
        "data": {
            "id": new_user.id,
            "username": new_user.username,
            "full_name": new_user.full_name,
            "role": new_user.role,
        }
    }
