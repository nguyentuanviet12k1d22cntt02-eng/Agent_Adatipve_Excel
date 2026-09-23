@echo off
title GHI NHAN THAO TAC EXCEL - AI ADAPTIVE TUTOR
cls
where python >nul 2>nul
if %errorlevel% equ 0 (
    python "%~dp0bat_dau_ghi_nhan.py"
) else (
    "%~dp0dist\BAT_DAU_GHI_NHAN.exe"
)
pause
