@echo off
:: Foodie Agent — Run script for Windows

cd /d "%~dp0"

:: Activate venv if not already activated
if "%VIRTUAL_ENV%"=="" (
    if not exist ".venv\Scripts\activate.bat" (
        echo .venv not found. Run setup.bat first.
        pause
        exit /b 1
    )
    echo Activating virtual environment ...
    call .venv\Scripts\activate.bat
)

echo Running Foodie Agent ...
py main.py
pause
