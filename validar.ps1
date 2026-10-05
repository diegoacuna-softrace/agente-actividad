# Valida si el equipo se va a suspender/bloquear. Solo lee (salvo que envia un
# F15 inofensivo para la prueba). No cambia ninguna configuracion.
#
# MODO POR DEFECTO: sirve A CUALQUIER HORA. Envia un F15 en un momento sin
# actividad y comprueba si reinicia el contador de inactividad (es el mecanismo
# que usa la vigilia tras las 5pm). Durante la prueba, mejor no toques el equipo
# unos 10-20 segundos.
#
#   validar.bat            -> prueba del F15 (recomendada, cualquier hora)
#   validar.bat -Pasivo    -> muestreo pasivo (solo util despues de las 6pm)
param([switch]$Pasivo, [int]$Muestras = 4, [int]$Intervalo = 40)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class _Idle {
  [StructLayout(LayoutKind.Sequential)] struct LII { public uint cbSize; public uint dwTime; }
  [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII p);
  [DllImport("kernel32.dll")] static extern uint GetTickCount();
  [DllImport("user32.dll")] static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
  public static double Seg() {
    LII l = new LII(); l.cbSize = (uint)Marshal.SizeOf(l);
    GetLastInputInfo(ref l); return (GetTickCount() - l.dwTime) / 1000.0;
  }
  public static void F15() { keybd_event(0x7E,0,0,UIntPtr.Zero); keybd_event(0x7E,0,2,UIntPtr.Zero); }
}
"@

function Linea($t) { "`n===== $t =====" }

Linea "1) VIGILIA EN EJECUCION"
$vig = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -match '--vigilia' }
if ($vig) { $vig | ForEach-Object { "SI, corriendo. PID $($_.ProcessId)" }; $vigiliaOK = $true }
else { "NO esta corriendo.  <-- si es esto, por aqui se suspende (revisa CrowdStrike / reinstala)."; $vigiliaOK = $false }

Linea "2) PLAN DE ENERGIA (0 = nunca)"
function TO($sub,$idle,$etq) {
  $o = (powercfg /q SCHEME_CURRENT $sub $idle) | Out-String
  $v = [regex]::Matches($o,'0x[0-9a-fA-F]{8}') | ForEach-Object { [Convert]::ToInt32($_.Value,16) }
  if ($v.Count -ge 2) { "{0,-16}: AC={1}s  DC={2}s" -f $etq, $v[$v.Count-2], $v[$v.Count-1] }
}
TO SUB_VIDEO VIDEOIDLE "Apagar pantalla"
TO SUB_SLEEP STANDBYIDLE "Suspender"
try {
  $p = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name InactivityTimeoutSecs -EA Stop).InactivityTimeoutSecs
  "Bloqueo por politica (GPO): $p s ($([math]::Round($p/60)) min)"
} catch { "Bloqueo por politica (GPO): no definido" }

$f15OK = $null
if ($Pasivo) {
  Linea "3) MUESTREO PASIVO ($Muestras muestras cada $Intervalo s) - NO toques el equipo"
  $max = 0.0
  for ($i=1; $i -le $Muestras; $i++) {
    $s = [_Idle]::Seg(); if ($s -gt $max) { $max = $s }
    "  muestra {0}: inactividad = {1:N0} s" -f $i, $s
    if ($i -lt $Muestras) { Start-Sleep -Seconds $Intervalo }
  }
  "Inactividad maxima: {0:N0} s" -f $max
  $f15OK = ($max -lt 90)
} else {
  Linea "3) PRUEBA DEL F15 (cualquier hora) - no toques el equipo ~15 s"
  "Se espera un momento sin actividad, se envia un F15 y se mira si baja el contador."
  $probado = $false
  for ($i=0; $i -lt 40 -and -not $probado; $i++) {
    if ([_Idle]::Seg() -lt 7) { Start-Sleep -Seconds 2; continue }
    $antes = [_Idle]::Seg()
    [_Idle]::F15()
    Start-Sleep -Milliseconds 500
    $despues = [_Idle]::Seg()
    "  Inactividad ANTES del F15: {0:N0} s    DESPUES: {1:N1} s" -f $antes, $despues
    $f15OK = ($despues -lt 2)
    $probado = $true
  }
  if (-not $probado) { "  No hubo un hueco sin actividad para probar (algo movia el raton). Reintenta." }
}

Linea "VEREDICTO"
if (-not $vigiliaOK) {
  "SE VA A SUSPENDER: la vigilia no esta corriendo; nada reinicia la inactividad tras las 5pm."
  if ($f15OK -eq $true) { "  (El F15 en si SI funciona en este equipo; solo falta que la vigilia este corriendo.)" }
  if ($f15OK -eq $false) { "  (Ademas el F15 esta bloqueado: sospecha de CrowdStrike.)" }
  "  -> Reinstala la 2.0 y comprueba con validar.bat que la vigilia aparezca y SIGA apareciendo."
} elseif ($f15OK -eq $true) {
  "OK: la vigilia corre y el F15 reinicia la inactividad. NO deberia suspenderse tras las 5pm."
} elseif ($f15OK -eq $false) {
  "RIESGO: la vigilia corre pero el F15 NO reinicia la inactividad (esta bloqueado)."
  "  -> Tipico de CrowdStrike bloqueando la entrada sintetica. Aun asi, si 'Suspender' esta"
  "     en 0 (arriba) y la politica GPO no fuerza el bloqueo, podria aguantar solo con la energia."
} else {
  "SIN CONCLUSION: no se pudo probar el F15. Vuelve a ejecutar sin tocar el equipo unos segundos."
}
"`n===== FIN ====="
