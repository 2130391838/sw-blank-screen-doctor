@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title SolidWorks Undo Last Fix
cls
python "%~dp0step_blank_doctor.py" --undo
echo.
echo ------------------------------------------------------------
echo  Press any key to close.
pause >nul
