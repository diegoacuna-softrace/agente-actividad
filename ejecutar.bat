@echo off
REM Lanzador del agente. Usa el entorno virtual .venv si existe.
REM La tarea programada lo invoca con /tarea: en ese modo no hay pausa final,
REM para que la consola se cierre sola al acabar la jornada.
setlocal
cd /d "%~dp0"

set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

set "PYWEXE=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYWEXE%" set "PYWEXE=pythonw"

if /i "%~1"=="/tarea" (
    "%PYEXE%" -m agente --config "%~dp0config.json"
    goto :fin
)

REM Red de seguridad: cierre total aunque el agente no este corriendo.
if /i "%~1"=="/cierre" (
    "%PYEXE%" -m agente --config "%~dp0config.json" --cierre-programado
    goto :fin
)

REM Vigilia 24/7: mantiene la pantalla encendida sin hacer nada mas.
REM Se lanza con pythonw (sin ventana de consola) y en segundo plano, para que
REM no quede una consola abierta todo el dia.
if /i "%~1"=="/vigilia" (
    start "" "%PYWEXE%" -m agente --config "%~dp0config.json" --vigilia
    goto :fin
)

"%PYEXE%" -m agente --config "%~dp0config.json" %*

REM Con doble clic la consola se cerraria sin dejar leer nada.
REM %cmdcmdline% solo contiene el nombre de este .bat en ese caso.
echo %cmdcmdline% | find /i "%~nx0" >nul
if not errorlevel 1 (
    echo.
    pause
)

:fin
endlocal
