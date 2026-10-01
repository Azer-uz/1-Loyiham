# backend/routers/auth.py
import base64
import urllib.parse
import asyncio
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models_db import User
from auth_utils import verify_password, hash_password, create_access_token, get_current_user
from moysklad_client import ms_client

router = APIRouter()


def save_moysklad_token_to_env(new_token: str):
    """Yangi olingan MoySklad API tokenni .env fayllariga yozish"""
    env_paths = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent / ".env",
        Path("/var/www/moysklad-app/backend/.env"),
        Path("/var/www/moysklad-app/.env"),
    ]
    for p in env_paths:
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                if "MOYSKLAD_TOKEN=" in content:
                    content = re.sub(r"MOYSKLAD_TOKEN=.*", f"MOYSKLAD_TOKEN={new_token}", content)
                else:
                    content += f"\nMOYSKLAD_TOKEN={new_token}\n"
                p.write_text(content, encoding="utf-8")
                print(f"[Env] MOYSKLAD_TOKEN saqlandi: {p}")
            except Exception as e:
                print(f"[Env] {p} ga saqlashda xato: {e}")


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
    """Tizimga kirish — MoySklad orqali token olish va tizimni to'liq yangilash"""
    import httpx
    from tasks import sync_all_data

    username = req.username.strip()
    password = req.password

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Login va parol kiritilishi shart",
        )

    ms_auth_success = False
    ms_employee_name = username
    ms_token = ""

    try:
        # UTF-8 Basic auth header
        raw_cred = f"{username}:{password}".encode("utf-8")
        basic_token = base64.b64encode(raw_cred).decode("ascii")

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. MoySklad'dan yangi API token olish
            auth_resp = await client.post(
                "https://api.moysklad.ru/api/remap/1.2/security/token",
                headers={
                    "Authorization": f"Basic {basic_token}",
                    "Content-Type": "application/json",
                }
            )

            print(f"[MoySklad auth] Status: {auth_resp.status_code}, User: {username}")

            if auth_resp.status_code in (200, 201):
                ms_auth_success = True
                resp_json = auth_resp.json()
                ms_token = resp_json.get("access_token", "")
                
                # Yangi tokenni tizimga faollashtirish
                if ms_token:
                    ms_client.update_token(ms_token)
                    save_moysklad_token_to_env(ms_token)

                    # Xodim ismini olish
                    try:
                        emp_resp = await client.get(
                            "https://api.moysklad.ru/api/remap/1.2/context/employee",
                            headers={
                                "Authorization": f"Bearer {ms_token}",
                                "Content-Type": "application/json"
                            }
                        )
                        if emp_resp.status_code == 200:
                            emp_data = emp_resp.json()
                            ms_employee_name = emp_data.get("name", username) or username
                    except Exception as emp_err:
                        print(f"[MoySklad auth] Xodim ismini olishda xato: {emp_err}")

                    # Orqa fonda barcha qoldiqlar, to'lovlar va ma'lumotlarni sinxronlash
                    asyncio.create_task(sync_all_data())
            else:
                # MoySklad xato xabarini o'qish
                err_msg = ""
                auth_header_msg = auth_resp.headers.get("x-lognex-auth-message", "")
                if auth_header_msg:
                    try:
                        err_msg = urllib.parse.unquote_plus(auth_header_msg)
                    except Exception:
                        pass

                if not err_msg:
                    try:
                        err_body = auth_resp.json()
                        if isinstance(err_body, dict):
                            errors = err_body.get("errors", [])
                            if errors and len(errors) > 0:
                                err_msg = errors[0].get("error", "")
                    except Exception:
                        pass

                print(f"[MoySklad auth] Rad etildi ({auth_resp.status_code}): {err_msg}")

                detail_msg = f"MoySklad: {err_msg}" if err_msg else "MoySklad login yoki parol noto'g'ri. Iltimos, parolni ko'zcha tugmasi orqali tekshirib qayta kiriting."

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=detail_msg,
                )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[MoySklad auth] Ulanish xatosi: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MoySklad serveri bilan bog'lanishda xatolik. Iltimos, qayta urinib ko'ring.",
        )

    if not ms_auth_success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MoySklad login yoki parol noto'g'ri",
        )

    # Foydalanuvchini lokal bazada saqlash/yangilash
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()

    if user:
        user.hashed_password = hash_password(password)
        user.full_name = ms_employee_name
        await db.commit()
        await db.refresh(user)
    else:
        user = User(
            username=username,
            hashed_password=hash_password(password),
            full_name=ms_employee_name,
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

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
