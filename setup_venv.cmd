@echo off
setlocal

REM Check for Python
where python >nul 2>nul
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    exit /b 1
)

set "VENV_DIR=%APPDATA%\Pedroverse"
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment at: %VENV_DIR%
    python -m venv "%VENV_DIR%"
)

call %VENV_DIR%\Scripts\activate.bat

python -m pip install --upgrade pip

pip install -r requirements.txt

echo Virtual environment setup complete!

endlocal
pause
