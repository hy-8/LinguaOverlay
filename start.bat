@echo off
setlocal
cd /d "%~dp0"

if not exist ".runtime\python.exe" (
    echo Local runtime was not found.
    echo Run install.ps1 -InstallCudaRuntime in PowerShell first.
    echo.
    pause
    exit /b 1
)

start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0run.ps1"

if errorlevel 1 (
    echo Startup failed. Run run.ps1 -Diagnose for details.
    echo.
    pause
    exit /b 1
)

endlocal
