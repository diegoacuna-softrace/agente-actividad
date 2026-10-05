@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Instalador del agente de actividad
echo ============================================
echo.

REM ---------------------------------------------------------------- Python
set "PY="
where py >nul 2>&1
if %errorlevel% equ 0 set "PY=py -3"
if defined PY goto :hay_python
where python >nul 2>&1
if %errorlevel% equ 0 set "PY=python"
:hay_python

if not defined PY (
    echo [ERROR] No se encontro Python en este equipo.
    echo.
    echo         Descargalo de https://www.python.org/downloads/windows/
    echo         y marca la casilla "Add python.exe to PATH" al instalar.
    echo.
    pause
    exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no respondio, o es anterior a la version 3.9.
    echo.
    echo         Si se abrio la Microsoft Store, lo que hay instalado es el
    echo         acceso directo de Windows, no Python. Instala Python real
    echo         desde https://www.python.org/downloads/windows/ marcando
    echo         "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% -c "import sys;print(sys.version.split()[0])"') do set "VERSION=%%v"
echo [1/4] Python detectado: !VERSION!

REM ------------------------------------------------------- entorno virtual
if exist ".venv\Scripts\python.exe" (
    echo [2/4] El entorno virtual .venv ya existe.
) else (
    echo [2/4] Creando el entorno virtual .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)
set "VPY=%~dp0.venv\Scripts\python.exe"

REM ---------------------------------------------------------- dependencias
if exist "vendor" (
    echo [3/4] Instalando dependencias sin conexion desde vendor\ ...
    "%VPY%" -m pip install --quiet --no-index --find-links "%~dp0vendor" -r requirements.txt
    if errorlevel 1 (
        echo       Los paquetes de vendor\ no sirven para esta version de Python.
        echo       Reintentando con descarga desde internet ...
        "%VPY%" -m pip install --quiet -r requirements.txt
    )
) else (
    echo [3/4] Descargando e instalando dependencias ...
    "%VPY%" -m pip install --quiet -r requirements.txt
)
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la instalacion de dependencias.
    echo         Con internet: revisa la conexion o el proxy corporativo.
    echo         Sin internet: instala en el otro PC la misma version de Python
    echo         con la que se genero el paquete, o vuelve a empaquetar con
    echo             powershell -File empaquetar.ps1 -SinInternet
    pause
    exit /b 1
)

REM ------------------------------------------------------------ validacion
echo [4/4] Comprobando que acciones quedan activas en este equipo ...
echo.
"%VPY%" -m agente --config "%~dp0config.json" --listar
if errorlevel 1 (
    echo [ERROR] El agente no arranco correctamente.
    pause
    exit /b 1
)

echo.
echo Instalacion terminada. Prueba el plan del dia con:
echo     ejecutar.bat --plan
echo.

REM ------------------------------------------------------ tareas programadas
REM Se crean con /sc daily y /it a proposito:
REM   - daily evita los nombres de dia, que cambian con el idioma de Windows.
REM     El propio agente decide si hoy es dia habil.
REM   - /it las ejecuta solo con el usuario conectado, que es obligatorio:
REM     cerrar ventanas y automatizar Office exige un escritorio interactivo.
REM La segunda tarea es la red de seguridad del cierre: lo hace aunque el
REM agente no este corriendo (equipo encendido tarde, consola cerrada a mano,
REM parada o errores). Su hora sale de config.json: fin de jornada + 10 min.
REM Las horas salen de config.json: la de arranque es el inicio de la ventana
REM (el agente espera hasta la hora aleatoria que sortee), y la de cierre de
REM respaldo es el fin maximo de la ventana + 10 min.
set "HORA_INICIO="
for /f "delims=" %%h in ('.venv\Scripts\python.exe -m agente --config config.json --hora-inicio') do set "HORA_INICIO=%%h"
if not defined HORA_INICIO set "HORA_INICIO=08:00"
set "HORA_CIERRE="
for /f "delims=" %%h in ('.venv\Scripts\python.exe -m agente --config config.json --hora-respaldo') do set "HORA_CIERRE=%%h"
if not defined HORA_CIERRE set "HORA_CIERRE=18:10"

choice /c SN /m "Dejar el agente arrancando solo (trabajo diario + pantalla 24/7)"
if errorlevel 2 goto :fin

echo.
REM --- Solo tareas DIARIAS: son las que las politicas de empresa permiten. Las
REM     "al iniciar sesion" (onlogon) suelen estar bloqueadas por CrowdStrike/GPO,
REM     asi que el arranque en cada sesion se hace por la carpeta de Inicio (abajo).
REM   - Arranque diario: el agente decide si hoy es dia habil y espera a la hora
REM     aleatoria que sortee dentro de la ventana.
REM   - Cierre de respaldo: cierra todo aunque el agente no estuviera corriendo.
REM   Se usan 'if' de una sola linea a proposito: los bloques (...) con parentesis
REM   son fragiles en .bat y pueden cortar el script.
schtasks /create /tn "Agente de actividad" /tr "\"%~dp0ejecutar.bat\" /tarea" /sc daily /st !HORA_INICIO! /it /f >nul 2>&1
if errorlevel 1 echo [AVISO] No se pudo registrar la tarea diaria de arranque (posible politica de empresa).
if not errorlevel 1 echo [OK] Tarea diaria de arranque registrada a las !HORA_INICIO!.

schtasks /create /tn "Agente de actividad - cierre" /tr "\"%~dp0ejecutar.bat\" /cierre" /sc daily /st !HORA_CIERRE! /it /f >nul 2>&1
if errorlevel 1 echo [AVISO] No se pudo registrar la tarea diaria de cierre.
if not errorlevel 1 echo [OK] Tarea diaria de cierre registrada a las !HORA_CIERRE!.

echo.
REM Plan de energia: pantalla y suspension en "nunca" (fiable en Modern Standby).
"%VPY%" -m agente --config "%~dp0config.json" --forzar-energia

echo.
REM Arranque por la CARPETA DE INICIO (no es una tarea onlogon, asi que la politica
REM no lo bloquea): crea los accesos de vigilia y de trabajo, arranca la vigilia
REM AHORA y, si estamos en horario, tambien la jornada AHORA. Todo sin intervencion.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vigilia-inicio.ps1" -Dir "%~dp0." -Trabajo

echo.
echo Si cambias las ventanas de horario en config.json, vuelve a ejecutar este instalador.
echo Para quitar todo usa desinstalar.bat

:fin
echo.
pause
endlocal
