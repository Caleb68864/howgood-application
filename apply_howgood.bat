@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "CONFIG_PATH=%SCRIPT_DIR%application.yaml"
cd /d "%SCRIPT_DIR%"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" apply_howgood.py --config "%CONFIG_PATH%" %*
exit /b %ERRORLEVEL%
