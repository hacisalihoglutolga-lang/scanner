@echo off
chcp 65001 >nul
echo === BIST Scanner Kurulum ===

:: Backend
echo.
echo --^> Python bagimliliklar kuruluyor...
cd /d "%~dp0backend"
python -m venv venv
if errorlevel 1 (
    echo HATA: Python bulunamadi. python.org adresinden kurun.
    pause & exit /b 1
)
venv\Scripts\pip install -r requirements.txt -q

:: Frontend
echo.
echo --^> Node bagimliliklar kuruluyor...
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 (
    echo HATA: Node.js bulunamadi. nodejs.org adresinden kurun.
    pause & exit /b 1
)

echo.
echo --^> Frontend build ediliyor...
call npm run build

echo.
echo Kurulum tamamlandi!
echo.
echo Baslatmak icin:
echo   start.bat
echo.
pause
