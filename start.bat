@echo off
title MoySklad App Server
echo ============================================
echo    MoySklad Boshqaruv Paneli
echo    Server ishga tushmoqda...
echo ============================================
echo.

cd /d "%~dp0backend"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [XATO] venv topilmadi! Avval "python -m venv venv" buyrug'ini bering.
    pause
    exit /b 1
)

echo.
echo [OK] Virtual muhit faollashtirildi
echo [OK] Server: http://localhost:8000
echo [OK] Brauzerda ochilmoqda...
echo.

start "" http://localhost:8000

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
