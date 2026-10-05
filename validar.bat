@echo off
REM Valida si el equipo se va a suspender/bloquear. Solo lee, no cambia nada.
REM Ejecutalo DESPUES del horario (p.ej. tras las 6pm) y NO toques raton/teclado
REM durante la prueba (dura ~2-3 minutos).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0validar.ps1"
echo.
echo ------------------------------------------------------------
echo Copia el resultado (sobre todo el VEREDICTO) y pegalo en la conversacion.
echo ------------------------------------------------------------
pause
