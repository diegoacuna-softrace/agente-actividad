@echo off
REM Muestra que version del agente esta instalada y si es antigua. Solo lee.
REM Uso opcional para revisar otra carpeta:  version.bat "C:\ruta\instalada"
cd /d "%~dp0"
if "%~1"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0version.ps1"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0version.ps1" -Ruta "%~1"
)
echo.
pause
