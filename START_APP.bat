@echo off
echo ================================================
echo   AI Question Generation System
echo ================================================
echo.

REM Change to the folder where this bat file lives
cd /d "%~dp0"

echo [1/3] Checking Python...
python --version 2>nul
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit
)

echo [2/3] Installing packages...
pip install -r requirements.txt --quiet

echo [3/3] Starting app...
echo.
echo App will open at: http://localhost:8501
echo Press Ctrl+C to stop.
echo.
streamlit run app.py
pause
