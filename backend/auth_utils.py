# backend/auth_utils.py
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import get_settings
from database import get_db
from models_db import User

settings = get_settings()

SECRET_KEY = getattr(settings, "secret_key", "moysklad_secret_super_key_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 kun

http_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Parolni xavfsiz bcrypt bilan xesh qilish"""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiritilgan parolni xesh bilan tekshirish"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT kirish tokenini yaratish"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Token orqali joriy foydalanuvchini aniqlash (Avtorizatsiya talab qiluvchi yo'llar uchun)"""
    if not auth or not auth.credentials:
        # Token berilmagan bo'lsa
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tizimga kirish talab qilinadi (Token topilmadi)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Yaroqsiz token",
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token muddati o'tgan yoki yaroqsiz",
        )
        
    result = await db.execute(select(User).where(User.username == username, User.is_active == True))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Foydalanuvchi topilmadi yoki faol emas",
        )
    return user


async def ensure_default_admin(db: AsyncSession):
    """Bazada kamida 1 ta admin borligini kafolatlash"""
    result = await db.execute(select(User).limit(1))
    existing = result.scalars().first()
    if not existing:
        admin_user = User(
            username="admin",
            hashed_password=hash_password("admin123"),
            full_name="Bosh Admin",
            role="admin",
            is_active=True,
        )
        db.add(admin_user)
        await db.commit()
        print("👤 Default admin foydalanuvchi yaratildi (admin / admin123)")
