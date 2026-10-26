@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title SolidWorks Diagnose Only
cls
python "%~dp0step_blank_doctor.py" --dry
echo.
echo ------------------------------------------------------------
echo  Report only. Nothing was changed. Press any key to close.
pause >nul
