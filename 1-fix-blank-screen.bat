@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title SolidWorks Fix Blank View
cls
python "%~dp0step_blank_doctor.py" --fix
echo.
echo ------------------------------------------------------------
echo  Press any key to close.
pause >nul
