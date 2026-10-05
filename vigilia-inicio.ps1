# Deja el agente arrancando por la CARPETA DE INICIO de Windows, sin depender de
# tareas programadas "al iniciar sesion" (onlogon), que en equipos gestionados
# (CrowdStrike / GPO) suelen estar bloqueadas: las diarias entran, las onlogon no.
#
# La carpeta de Inicio NO es una "tarea programada", asi que la politica no la
# bloquea, y no necesita permisos de administrador. Crea accesos directos que
# arrancan en cada inicio de sesion:
#   - Vigilia agente.lnk          -> mantiene la pantalla encendida (F15) 24/7
#   - Agente de actividad (trabajo).lnk  (solo con -Trabajo) -> la jornada diaria
# y ademas los arranca ahora mismo, para no esperar al proximo inicio de sesion.
#
#   activar-vigilia.bat                       -> solo la vigilia
#   powershell -File vigilia-inicio.ps1 -Trabajo   -> vigilia + jornada (lo usa el instalador)
#   powershell -File vigilia-inicio.ps1 -Quitar    -> quita los accesos directos
param(
    [string]$Dir = $PSScriptRoot,
    [string]$Startup,
    [switch]$Trabajo,
    [switch]$NoArrancar,
    [switch]$Quitar
)

$ErrorActionPreference = "Stop"
if (-not $Dir) { $Dir = (Get-Location).Path }
$Dir = (Resolve-Path $Dir).Path
if (-not $Startup) { $Startup = [Environment]::GetFolderPath('Startup') }

$lnkVigilia = Join-Path $Startup "Vigilia agente.lnk"
$lnkTrabajo = Join-Path $Startup "Agente de actividad (trabajo).lnk"

# --- quitar los accesos directos --------------------------------------------
if ($Quitar) {
    foreach ($l in @($lnkVigilia, $lnkTrabajo)) {
        if (Test-Path $l) { Remove-Item $l -Force; Write-Host "[OK] Eliminado: $l" }
    }
    if (-not (Test-Path $lnkVigilia) -and -not (Test-Path $lnkTrabajo)) {
        Write-Host "No quedan accesos directos de inicio del agente."
    }
    return
}

# pythonw.exe no abre ventana; python.exe se usa solo para leer codigos de salida
$pyw = Join-Path $Dir ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = "pythonw" }
$py = Join-Path $Dir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$cfg = Join-Path $Dir "config.json"

Write-Host "Carpeta del agente : $Dir"
Write-Host "Interprete (pythonw): $pyw"
if (-not (Test-Path $cfg)) { Write-Warning "No encuentro config.json; se usara la configuracion por defecto." }
Write-Host ""

# --- crea un acceso directo en la carpeta de Inicio -------------------------
function Nuevo-Acceso($ruta, $argumentos, $descripcion) {
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($ruta)
    $sc.TargetPath       = $pyw
    $sc.Arguments        = $argumentos
    $sc.WorkingDirectory = $Dir
    $sc.WindowStyle      = 7           # minimizado (pythonw no muestra ventana igualmente)
    $sc.Description      = $descripcion
    $sc.Save()
    Write-Host "[OK] Acceso de inicio: $ruta"
}

# 1) vigilia (siempre) --------------------------------------------------------
Nuevo-Acceso $lnkVigilia "-m agente --config `"$cfg`" --vigilia" `
    "Mantiene la pantalla encendida (vigilia del agente de actividad)"

# 2) jornada de trabajo (solo con -Trabajo) ----------------------------------
if ($Trabajo) {
    Nuevo-Acceso $lnkTrabajo "-m agente --config `"$cfg`"" `
        "Agente de actividad: jornada diaria simulada"
}

# --- arrancar ahora ---------------------------------------------------------
function Corre-Vigilia {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match '--vigilia' }
}

if (-not $NoArrancar) {
    Write-Host ""
    # vigilia ahora (si no hay ya una corriendo, para no duplicar)
    if (Corre-Vigilia) {
        Write-Host "[OK] La vigilia ya estaba corriendo."
    } else {
        # -ArgumentList como UNA cadena con la ruta entre comillas. En Windows
        # PowerShell 5.1, pasar un @(array) NO entrecomilla los elementos con
        # espacios y parte la ruta de --config (rutas tipo 'Agente definitivo').
        Start-Process -FilePath $pyw -ArgumentList "-m agente --config `"$cfg`" --vigilia" `
            -WorkingDirectory $Dir -WindowStyle Hidden | Out-Null
        Start-Sleep -Seconds 3
        $v = Corre-Vigilia
        if ($v) { Write-Host ("[OK] Vigilia corriendo AHORA. PID {0}" -f ($v.ProcessId -join ', ')) }
        else {
            Write-Host "[AVISO] No detecto la vigilia tras arrancarla. Comprueba con validar.bat;"
            Write-Host "        si no aparece, puede que el antivirus la cierre (revisa CrowdStrike)."
        }
    }

    # jornada ahora, solo si estamos dentro del horario laboral
    if ($Trabajo) {
        & $py -m agente --config $cfg --en-ventana *> $null
        if ($LASTEXITCODE -eq 0) {
            Start-Process -FilePath $pyw -ArgumentList "-m agente --config `"$cfg`"" `
                -WorkingDirectory $Dir -WindowStyle Hidden | Out-Null
            Write-Host "[OK] En horario: la jornada arranca AHORA."
        } else {
            Write-Host "[OK] Fuera de horario: por ahora solo la pantalla encendida (F15)."
        }
    }
}

Write-Host ""
if ($Trabajo) { Write-Host "Listo. En cada inicio de sesion arrancaran solos la vigilia y la jornada." }
else          { Write-Host "Listo. En cada inicio de sesion arrancara sola la vigilia." }
Write-Host "Comprueba con validar.bat que la vigilia aparezca 'SI, corriendo' y el VEREDICTO OK."
