@echo off
chcp 65001 >nul
echo === BIST Scanner Baslatiliyor ===
echo.
echo Uygulama: http://localhost:8010
echo Durdurmak icin bu pencereyi kapatın.
echo.

cd /d "%~dp0backend"
venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8010
