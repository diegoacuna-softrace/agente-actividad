@echo off
REM Registra las tareas + fuerza la energia + arranca la vigilia, SIN reinstalar
REM todo. Util cuando el agente ya esta descomprimido (existe .venv) pero las
REM tareas no quedaron. Sin bloques (...) con parentesis, para que no se cierre.
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Configurar tareas del agente
echo ============================================
echo.

set "VPY=%~dp0.venv\Scripts\python.exe"
if not exist "%VPY%" set "VPY=python"

"%VPY%" -m agente --version >nul 2>&1
if not errorlevel 1 goto :hay_codigo
echo [ERROR] No encuentro el agente en esta carpeta.
echo         Corre este archivo DENTRO de la carpeta de la version 2.0,
echo         la que tiene la subcarpeta 'agente'. Si no existe '.venv',
echo         ejecuta primero instalar.bat.
echo.
pause
goto :eof
:hay_codigo

for /f "delims=" %%v in ('"%VPY%" -m agente --version') do echo Detectado: %%v

set "HORA_INICIO="
for /f "delims=" %%h in ('"%VPY%" -m agente --config "%~dp0config.json" --hora-inicio') do set "HORA_INICIO=%%h"
if not defined HORA_INICIO set "HORA_INICIO=08:00"
set "HORA_CIERRE="
for /f "delims=" %%h in ('"%VPY%" -m agente --config "%~dp0config.json" --hora-respaldo') do set "HORA_CIERRE=%%h"
if not defined HORA_CIERRE set "HORA_CIERRE=18:10"

echo.
echo Registrando tareas (arranque !HORA_INICIO!, cierre !HORA_CIERRE!, pantalla 24/7)...
echo.

REM Solo tareas DIARIAS (las que la politica de empresa permite). El arranque en
REM cada sesion va por la carpeta de Inicio, mas abajo.
schtasks /create /tn "Agente de actividad" /tr "\"%~dp0ejecutar.bat\" /tarea" /sc daily /st !HORA_INICIO! /it /f >nul 2>&1
if errorlevel 1 echo [AVISO] NO se pudo registrar la tarea diaria de arranque (posible politica de empresa).
if not errorlevel 1 echo [OK] Tarea diaria de arranque registrada a las !HORA_INICIO!.

schtasks /create /tn "Agente de actividad - cierre" /tr "\"%~dp0ejecutar.bat\" /cierre" /sc daily /st !HORA_CIERRE! /it /f >nul 2>&1
if errorlevel 1 echo [AVISO] NO se pudo registrar la tarea diaria de cierre.
if not errorlevel 1 echo [OK] Tarea diaria de cierre registrada a las !HORA_CIERRE!.

echo.
echo Forzando plan de energia a 'nunca'...
"%VPY%" -m agente --config "%~dp0config.json" --forzar-energia

echo.
echo Activando vigilia y jornada por la carpeta de Inicio (arrancan solas cada sesion)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vigilia-inicio.ps1" -Dir "%~dp0." -Trabajo

echo.
echo ------------------------------------------------------------
echo Terminado. Si arriba ves algun [AVISO], copialo y pegalo en la conversacion.
echo Luego corre  validar.bat  para confirmar que la vigilia quedo corriendo.
echo ------------------------------------------------------------
echo.
pause
endlocal
