@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Desinstalador del agente de actividad
echo   (limpieza a fondo)
echo ============================================
echo.

set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

REM --- 1) Pedir parada y RESTAURAR energia mientras el codigo sigue disponible ---
REM Se hace antes de matar procesos o borrar la .venv, porque necesita python.
"%PYEXE%" -m agente --config "%~dp0config.json" --detener-vigilia >nul 2>&1
"%PYEXE%" -m agente --config "%~dp0config.json" --restaurar-energia >nul 2>&1
echo [1/5] Plan de energia restaurado a valores por defecto.

REM --- 2) Matar CUALQUIER proceso del agente (vigilia o jornada) -----------------
REM Solo toca procesos python/pythonw cuya linea de comando invoca "-m agente".
echo [2/5] Deteniendo procesos del agente en ejecucion...
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match '-m agente' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; 'detenido PID ' + $_.ProcessId } catch {} }"

REM --- 3) Borrar TODAS las tareas 'Agente de actividad*' (incluye nombres viejos) ---
echo [3/5] Eliminando tareas programadas...
powershell -NoProfile -Command ^
  "Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like 'Agente de actividad*' } | ForEach-Object { try { Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false -ErrorAction Stop; 'eliminada: ' + $_.TaskName } catch {} }"
REM Respaldo por si el modulo ScheduledTasks no estuviera disponible:
for %%T in (
  "Agente de actividad"
  "Agente de actividad - sesion"
  "Agente de actividad - cierre"
  "Agente de actividad - pantalla"
) do schtasks /delete /tn %%T /f >nul 2>&1

REM --- 4) Limpiar archivos de control y el acceso directo de Inicio ------------
echo [4/5] Limpiando archivos de control y acceso directo de inicio...
if defined USERPROFILE (
  del /q "%USERPROFILE%\AgenteActividad\DETENER.txt" >nul 2>&1
  del /q "%USERPROFILE%\AgenteActividad\DETENER-PANTALLA.txt" >nul 2>&1
  del /q "%USERPROFILE%\AgenteActividad\.trabajo_activo.json" >nul 2>&1
)
REM Accesos directos de arranque en la carpeta de Inicio (vigilia y jornada).
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Vigilia agente.lnk" >nul 2>&1
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Agente de actividad (trabajo).lnk" >nul 2>&1

REM --- 5) Opcionales: carpeta de trabajo y entorno virtual ----------------------
echo [5/5] Limpieza opcional.
echo.
choice /c SN /m "Eliminar la carpeta de trabajo (documentos, CSV, notas y logs)"
if not errorlevel 2 (
    if exist "%USERPROFILE%\AgenteActividad" (
        rmdir /s /q "%USERPROFILE%\AgenteActividad"
        echo   Carpeta de trabajo eliminada.
    ) else (
        echo   No habia carpeta de trabajo.
    )
)

echo.
choice /c SN /m "Eliminar tambien el entorno virtual .venv"
if not errorlevel 2 (
    if exist ".venv" (
        rmdir /s /q ".venv"
        echo   Entorno virtual eliminado.
    )
)

echo.
echo ============================================
echo   Desinstalacion completada.
echo   Ya puedes borrar esta carpeta si quieres.
echo ============================================
echo.
pause
endlocal
