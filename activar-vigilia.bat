@echo off
REM Activa la vigilia 24/7 por la carpeta de Inicio de Windows.
REM Usar cuando la instalacion mostro [AVISO] al registrar las tareas
REM "al iniciar sesion" (la politica de la empresa bloquea esas tareas).
REM No necesita permisos de administrador.
cd /d "%~dp0"

echo ============================================
echo   Activar vigilia (carpeta de Inicio)
echo ============================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vigilia-inicio.ps1" -Dir "%~dp0."

echo.
echo ------------------------------------------------------------
echo Terminado. Ejecuta ahora  validar.bat  para confirmar la vigilia
echo y pega aqui el VEREDICTO.
echo ------------------------------------------------------------
echo.
pause
