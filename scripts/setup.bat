@echo off
:: Foodie Agent — Setup script for Windows
:: Creates virtual environment and installs dependencies

echo ======================================
echo   Foodie Agent — Setup
echo ======================================

:: Get script directory
set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
cd /d "%PROJECT_DIR%"

:: 1. Create .env from example
echo [1/4] Creating .env from .env.example ...
if not exist ".env" (
    copy ".env.example" ".env"
    echo     .env created — please edit it and fill in your API keys!
) else (
    echo     .env already exists, skipping.
)

:: 2. Create virtual environment
echo.
echo [2/4] Creating virtual environment ...
if exist ".venv" (
    echo     .venv already exists, skipping.
) else (
    python -m venv .venv
    echo     .venv created.
)

:: 3. Install dependencies
echo.
echo [3/4] Installing dependencies ...
call .venv\Scripts\pip install -r requirements.txt
echo     Dependencies installed.

:: 4. Run
echo.
echo ======================================
echo   Setup complete!
echo.
echo   Next steps:
echo   1. Edit .env — fill in your API keys
echo   2. Activate: .venv\Scripts\activate
echo   3. Run:      py main.py
echo ======================================
pause
