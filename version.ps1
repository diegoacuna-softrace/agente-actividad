# Detecta que version del agente esta INSTALADA en este equipo y si es antigua.
# Solo lee; no cambia nada. Opcional: version.ps1 -Ruta "C:\ruta\instalada"
param([string]$Ruta = "")

# Version que trae ESTE paquete (la mas reciente conocida).
$ULTIMA = "2.4"

function Linea($t) { "`n===== $t =====" }

# --- 1) Encontrar la carpeta instalada -------------------------------------
# Prioridad: parametro -Ruta > carpeta apuntada por la tarea programada > carpeta de este script.
$carpeta = ""
if ($Ruta -and (Test-Path $Ruta)) { $carpeta = $Ruta }

if (-not $carpeta) {
  try {
    $q = schtasks /query /tn "Agente de actividad" /fo LIST /v 2>$null | Out-String
    $m = [regex]::Match($q, '([A-Za-z]:\\[^"''\r\n]+?)\\ejecutar\.bat')
    if ($m.Success -and (Test-Path $m.Groups[1].Value)) { $carpeta = $m.Groups[1].Value }
  } catch {}
}
if (-not $carpeta) { $carpeta = $PSScriptRoot }

Linea "CARPETA ANALIZADA"
"$carpeta"
if (-not (Test-Path (Join-Path $carpeta "agente"))) {
  "`n[!] Aqui no hay una instalacion del agente (no existe la subcarpeta 'agente')."
  "    Pasa la ruta correcta:  version.bat C:\ruta\donde\esta\instalado"
  return
}

# --- 2) Marca de version (si existe) ---------------------------------------
Linea "VERSION INSTALADA"
$verTxt = Join-Path $carpeta "VERSION.txt"
$verInstalada = ""
if (Test-Path $verTxt) {
  Get-Content $verTxt
  $vm = Select-String -Path $verTxt -Pattern 'Version:\s*(\S+)'
  if ($vm) { $verInstalada = $vm.Matches[0].Groups[1].Value }
} else {
  $ini = Join-Path $carpeta "agente\__init__.py"
  $im = if (Test-Path $ini) { Select-String -Path $ini -Pattern '__version__\s*=\s*"([^"]+)"' } else { $null }
  if ($im) {
    $verInstalada = $im.Matches[0].Groups[1].Value
    "Sin VERSION.txt. __version__ del codigo: $verInstalada"
  } else {
    "Sin marca de version: es una version ANTIGUA (anterior a la 2.0)."
  }
}

# --- 3) Deteccion de funciones (sirve aunque no haya marca) -----------------
Linea "FUNCIONES PRESENTES"
$cfg = ""
$cfgPath = Join-Path $carpeta "config.json"
if (Test-Path $cfgPath) { $cfg = Get-Content $cfgPath -Raw }

function Tiene($cond) { if ($cond) { "SI " } else { "no " } }

$fEnergia   = Test-Path (Join-Path $carpeta "agente\energia.py")
$fEscritorio= Test-Path (Join-Path $carpeta "agente\escritorio.py")
$fSinCorreo = -not (Test-Path (Join-Path $carpeta "agente\acciones\correo.py"))
$fHorarioAl = $cfg -match '"inicio_min"'
$fForzEnerg = $cfg -match '"forzar_energia"'
$fVigilia   = $cfg -match '"vigilia_evita_bloqueo"'
$fCierre    = $cfg -match '"modo_cierre"'
$fDiag      = Test-Path (Join-Path $carpeta "diagnostico.ps1")
$fInicio    = Test-Path (Join-Path $carpeta "vigilia-inicio.ps1")

"$(Tiene $fForzEnerg) Forzar energia (powercfg, para Modern Standby)"
"$(Tiene $fEnergia)   Modulo energia.py"
"$(Tiene $fVigilia)   Vigilia con F15 (anti-bloqueo)"
"$(Tiene $fInicio)    Arranque por carpeta de Inicio (empresas que bloquean tareas onlogon)"
"$(Tiene $fHorarioAl) Horario de inicio/fin aleatorio (ventanas 8-9 / 5-6)"
"$(Tiene $fCierre)    Cierre total al terminar (modo_cierre)"
"$(Tiene $fEscritorio) Cierre de todas las ventanas (escritorio.py)"
"$(Tiene $fSinCorreo) Sin acciones de correo (Outlook/mailto eliminados)"
"$(Tiene $fDiag)      Scripts de diagnostico incluidos"

# --- 4) Veredicto ----------------------------------------------------------
Linea "VEREDICTO"
$faltan = @()
if (-not $fForzEnerg) { $faltan += "forzar energia (Modern Standby)" }
if (-not $fHorarioAl) { $faltan += "horario aleatorio" }
if (-not $fVigilia)   { $faltan += "vigilia F15 anti-bloqueo" }
if (-not $fInicio)    { $faltan += "arranque por carpeta de Inicio (onlogon bloqueado)" }
if (-not $fSinCorreo) { $faltan += "eliminacion del correo" }
if (-not $fDiag)      { $faltan += "diagnostico" }

if ($verInstalada -eq $ULTIMA -and $faltan.Count -eq 0) {
  "ESTA AL DIA: version $verInstalada (la mas reciente)."
} elseif ($faltan.Count -eq 0) {
  "Version instalada $verInstalada; la mas reciente es $ULTIMA. Casi al dia, conviene actualizar."
} else {
  if ($verInstalada) { "Version instalada: $verInstalada  ->  la mas reciente es $ULTIMA." }
  else { "Version ANTIGUA (sin marca) -> la mas reciente es $ULTIMA." }
  "Le faltan estas funciones:"
  $faltan | ForEach-Object { "   - $_" }
  "Recomendacion: desinstalar.bat en esa carpeta, borrarla, y reinstalar el zip nuevo."
}
"`n===== FIN ====="
