@echo off
REM Diagnostico del equipo (solo lee, no cambia nada). Doble clic para ejecutar.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0diagnostico.ps1" > "%~dp0diagnostico.txt" 2>&1
type "%~dp0diagnostico.txt"
echo.
echo ------------------------------------------------------------
echo Resultados guardados en:  %~dp0diagnostico.txt
echo Copia TODO ese contenido y pegalo en la conversacion.
echo ------------------------------------------------------------
pause
