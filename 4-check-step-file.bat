@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title STEP Health Check
cls
if "%~1"=="" (
  echo.
  echo   Drag a .step / .stp file onto this icon and drop it here.
  echo.
  pause >nul
  exit /b 1
)
python "%~dp0step_health_check.py" "%~1"
echo.
echo ------------------------------------------------------------
echo  Press any key to close.
pause >nul
