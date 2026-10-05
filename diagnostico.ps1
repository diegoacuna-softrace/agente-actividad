# Diagnostico del equipo para adaptar el agente de actividad.
# SOLO LEE informacion; no cambia ningun ajuste ni instala nada.

function Seccion($t) { "`n===== $t =====" }

Seccion "EQUIPO"
"Fecha         : $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
"Nombre        : $env:COMPUTERNAME"
try {
  $os = Get-CimInstance Win32_OperatingSystem
  "Windows       : $($os.Caption) $($os.Version)"
} catch {}
try {
  $cs = Get-CimInstance Win32_ComputerSystem
  $dominio = if ($cs.PartOfDomain) { "SI, dominio: $($cs.Domain)" } else { "NO (equipo suelto)" }
  "En dominio    : $dominio"
} catch {}

Seccion "ENERGIA (suspension / Modern Standby)"
try { (powercfg /a) 2>&1 } catch { "powercfg /a no disponible" }
"`n-- Tiempos actuales del plan activo (0 = nunca) --"
function Timeout($sub,$idle,$etq) {
  try {
    $o = (powercfg /q SCHEME_CURRENT $sub $idle) | Out-String
    # Los dos ultimos indices hexadecimales son los valores actuales de CA y CC.
    $vals = [regex]::Matches($o,'0x[0-9a-fA-F]{8}') | ForEach-Object { [Convert]::ToInt32($_.Value,16) }
    if ($vals.Count -ge 2) {
      "{0,-18}: AC={1}s  DC={2}s" -f $etq, $vals[$vals.Count-2], $vals[$vals.Count-1]
    }
  } catch { "$etq : no se pudo leer" }
}
Timeout SUB_VIDEO VIDEOIDLE "Apagar pantalla"
Timeout SUB_SLEEP STANDBYIDLE "Suspender"

Seccion "BLOQUEO"
try {
  $p = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name InactivityTimeoutSecs -ErrorAction Stop
  "Politica InactivityTimeoutSecs: $($p.InactivityTimeoutSecs) s (la empresa fuerza bloqueo por inactividad)"
} catch { "Politica InactivityTimeoutSecs: no definida (no la fuerza una GPO)" }
try {
  $d = Get-ItemProperty "HKCU:\Control Panel\Desktop" -ErrorAction Stop
  "Protector activo   : $($d.ScreenSaveActive)   Seguro(pide clave): $($d.ScreenSaverIsSecure)   Timeout: $($d.ScreenSaveTimeOut)s"
} catch { "Protector de pantalla: sin datos" }

Seccion "PYTHON"
try { "py -0:`n$((py -0 2>&1) | Out-String)" } catch { "py launcher: no encontrado" }
try { "python --version: $((python --version 2>&1) | Out-String)".Trim() } catch { "python: no encontrado" }

Seccion "OFFICE / OUTLOOK (COM)"
foreach ($p in 'Word.Application','Excel.Application','PowerPoint.Application','Outlook.Application') {
  $ok = Test-Path "Registry::HKEY_CLASSES_ROOT\$p"
  "{0,-22}: {1}" -f $p, $(if ($ok) { 'instalado' } else { 'NO' })
}
try {
  $mailto = (Get-ItemProperty "Registry::HKEY_CLASSES_ROOT\mailto\shell\open\command" -ErrorAction Stop).'(default)'
  "Cliente mailto        : $mailto"
} catch { "Cliente mailto        : ninguno" }

Seccion "TAREAS PROGRAMADAS DEL AGENTE"
foreach ($t in 'Agente de actividad','Agente de actividad - sesion','Agente de actividad - cierre','Agente de actividad - pantalla') {
  try {
    $q = schtasks /query /tn "$t" /fo LIST 2>&1 | Select-String 'Estado|Status'
    "{0,-32}: {1}" -f $t, ($q -join ' ').Trim()
  } catch { "{0,-32}: no registrada" -f $t }
}

Seccion "PROCESOS DEL AGENTE EN EJECUCION"
try {
  $ps = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -match 'agente' }
  if ($ps) { $ps | ForEach-Object { " PID $($_.ProcessId): $($_.CommandLine)" } }
  else { " ninguno" }
} catch { " no se pudo consultar" }

Seccion "ANTIVIRUS / SEGURIDAD"
try {
  $av = Get-CimInstance -Namespace root/SecurityCenter2 -Class AntiVirusProduct -ErrorAction Stop
  if ($av) { $av | ForEach-Object { " - $($_.displayName)" } } else { " no reportado" }
} catch { " no se pudo consultar (normal en equipos de dominio)" }

Seccion "SESION"
"Bloqueada ahora?: revisa manualmente. Usuario: $env:USERNAME"
"`n===== FIN DEL DIAGNOSTICO ====="
