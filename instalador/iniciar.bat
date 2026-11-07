@echo off
cd /d "%~dp0"
title C4ISTAR MONITOR
echo Iniciando C4ISTAR MONITOR...
if not exist "venv\Scripts\python.exe" (
  echo Ambiente virtual ausente. Rode instalador\instalar.ps1 primeiro.
  pause
  exit /b 1
)
".\venv\Scripts\python.exe" main.py
pause
