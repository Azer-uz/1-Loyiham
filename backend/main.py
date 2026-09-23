import sys
import io

# Windows konsolida UTF-8 emoji va belgilarni to'g'ri ko'rsatish
if sys.platform == "win32":
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

import asyncio
from routers import demands, payments, customers, dashboard, currencies, settings, test, auth, webhooks, supply
from database import init_db, AsyncSessionLocal
from auth_utils import ensure_default_admin, get_current_user
from tasks import start_background_scheduler, scheduler, sync_all_data

app = FastAPI(
    title="MoySklad Boshqaruv Paneli",
    description="Otgruzka, to'lov va mijozlar boshqaruvi (Optimizatsiyalangan)",
    version="2.0.0",
    docs_url="/swagger",
    redoc_url=None,
)

# CORS sozlamalari
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Avtorizatsiya himoyasi bog'liqligi
auth_deps = [Depends(get_current_user)]

# Routerlarni ulash
app.include_router(auth.router, prefix="/api/auth", tags=["Avtorizatsiya"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks & Sync"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"], dependencies=auth_deps)
app.include_router(demands.router, prefix="/api/demands", tags=["Otgruzkalar"], dependencies=auth_deps)
app.include_router(payments.router, prefix="/api/payments", tags=["To'lovlar"], dependencies=auth_deps)
app.include_router(customers.router, prefix="/api/customers", tags=["Mijozlar"], dependencies=auth_deps)
app.include_router(currencies.router, prefix="/api/currency", tags=["Valyuta"], dependencies=auth_deps)
app.include_router(settings.router, prefix="/api/settings", tags=["Sozlamalar"], dependencies=auth_deps)
app.include_router(supply.router, prefix="/api/supply", tags=["Tovar Kirimi"], dependencies=auth_deps)
app.include_router(test.router, prefix="/api/test", tags=["Test"])

# Frontend statik fayllar
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


# HTML Sahifalar uchun toza URL marshrutlari
@app.get("/")
async def root():
    return FileResponse(str(frontend_path / "index.html"))


@app.get("/login")
async def login_page():
    return FileResponse(str(frontend_path / "login.html"))


@app.get("/demands")
async def demands_page():
    return FileResponse(str(frontend_path / "demands.html"))


@app.get("/customers")
async def customers_page():
    return FileResponse(str(frontend_path / "customers.html"))


@app.get("/payments")
async def payments_page():
    return FileResponse(str(frontend_path / "payments.html"))


@app.get("/settings")
async def settings_page():
    return FileResponse(str(frontend_path / "settings.html"))


@app.get("/supply")
async def supply_page():
    return FileResponse(str(frontend_path / "supply.html"))


@app.get("/docs")
@app.get("/help")
@app.get("/manual")
async def docs_page():
    return FileResponse(str(frontend_path / "docs.html"))


@app.get("/health")
async def health():
    """Server holatini tekshirish"""
    return {"status": "ok", "service": "MoySklad App", "version": "2.0.0"}


@app.on_event("startup")
async def startup_event():
    """Ilova ishga tushganda bazani tayyorlash va orqa fon sinxronizatorini yoqish"""
    print("🚀 Ilova ishga tushmoqda...")
    await init_db()
    async with AsyncSessionLocal() as session:
        await ensure_default_admin(session)
    
    # Orqa fon schedulerini yoqish
    start_background_scheduler()
    
    # Darhol dastlabki ma'lumotlarni sinxronlash (orqa fonda, ilovani to'xtatmasdan)
    asyncio.create_task(sync_all_data())


@app.on_event("shutdown")
async def shutdown_event():
    """Ilova yopilganda tozalash"""
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    from moysklad_client import ms_client
    await ms_client.close()


if __name__ == "__main__":
    import uvicorn
    from config import get_settings
    s = get_settings()
    uvicorn.run("main:app", host=s.app_host, port=s.app_port, reload=True)