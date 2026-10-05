<#
.SYNOPSIS
    Genera el paquete distribuible del agente para llevarlo a otro equipo.

.DESCRIPTION
    Copia solo lo necesario (sin .venv, sin logs, sin __pycache__) y produce
    dist\agente-actividad.zip.

    Con -SinInternet incluye ademas las dependencias descargadas en vendor\,
    para instalar en un PC sin acceso a PyPI. Ese paquete queda atado a la
    version de Python y a la arquitectura de ESTE equipo.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File empaquetar.ps1
    powershell -ExecutionPolicy Bypass -File empaquetar.ps1 -SinInternet
#>
param(
    [string]$Destino = "",
    [switch]$SinInternet
)

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
if (-not $Destino) { $Destino = Join-Path $raiz "dist" }

$staging = Join-Path $Destino "agente-actividad"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null

# --- codigo fuente, sin cache de bytecode ---------------------------------
Copy-Item (Join-Path $raiz "agente") $staging -Recurse
Get-ChildItem (Join-Path $staging "agente") -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force

# --- marca de version ------------------------------------------------------
$verMatch = Select-String -Path (Join-Path $raiz "agente\__init__.py") -Pattern '__version__\s*=\s*"([^"]+)"'
$version = if ($verMatch) { $verMatch.Matches[0].Groups[1].Value } else { "0" }
$sello = Get-Date -Format "yyyy-MM-dd HH:mm"
Set-Content -Path (Join-Path $staging "VERSION.txt") -Encoding utf8 -Value @"
Agente de actividad
Version: $version
Empaquetado: $sello
"@
Write-Host "Marca de version: $version ($sello)"

# --- archivos sueltos ------------------------------------------------------
$archivos = @(
    "LEEME-PRIMERO.txt", "config.json", "requirements.txt", "README.md",
    "ejecutar.bat", "instalar.bat", "desinstalar.bat", "configurar.bat",
    "activar-vigilia.bat", "vigilia-inicio.ps1",
    "diagnostico.bat", "diagnostico.ps1", "version.bat", "version.ps1",
    "validar.bat", "validar.ps1"
)
foreach ($archivo in $archivos) {
    $origen = Join-Path $raiz $archivo
    if (Test-Path $origen) { Copy-Item $origen $staging }
    else { Write-Warning "No se encontro $archivo" }
}

# --- instalador de Python (opcional) ---------------------------------------
# Si hay un instalador de Python en la raiz o en dist\, se incluye en el paquete
# para poder instalar Python en un equipo que no lo tenga, sin depender de nada.
$buscarEn = @($raiz, (Join-Path $raiz "dist"))
$instalador = Get-ChildItem -Path $buscarEn -Filter "python-*" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in ".msix", ".exe", ".msi" } |
    Select-Object -First 1
if ($instalador) {
    Copy-Item $instalador.FullName $staging
    $mb = [math]::Round($instalador.Length / 1MB, 1)
    Write-Host "Incluido el instalador de Python: $($instalador.Name) ($mb MB)"
} else {
    Write-Host "Sin instalador de Python en el paquete (no se encontro python-*.msix/.exe/.msi)."
}

# --- dependencias para instalacion sin conexion ----------------------------
if ($SinInternet) {
    $vendor = Join-Path $staging "vendor"
    New-Item -ItemType Directory -Path $vendor -Force | Out-Null

    $version = & python -c "import sys;print('%d.%d' % sys.version_info[:2])"
    Write-Host "Descargando dependencias para Python $version (64 bits) ..."

    # setuptools y wheel se incluyen porque pyautogui se distribuye como sdist
    # y hay que poder compilarlo en el equipo destino sin salir a internet.
    & python -m pip download --quiet -r (Join-Path $raiz "requirements.txt") -d $vendor
    if ($LASTEXITCODE -ne 0) { throw "Fallo la descarga de las dependencias." }
    & python -m pip download --quiet setuptools wheel -d $vendor
    if ($LASTEXITCODE -ne 0) { throw "Fallo la descarga de setuptools/wheel." }

    $paquetes = (Get-ChildItem $vendor -File).Count
    Write-Host "  $paquetes paquetes en vendor\"

    Set-Content -Path (Join-Path $staging "LEEME-SIN-INTERNET.txt") -Encoding utf8 -Value @"
Este paquete incluye la carpeta vendor\ con las dependencias ya descargadas.

Fue generado para Python $version en Windows de 64 bits. El equipo destino
debe tener esa misma version de Python (misma X.Y), porque pywin32 se compila
por version de interprete.

Si alla hay otra version de Python, borra la carpeta vendor\ y ejecuta
instalar.bat con conexion a internet: descargara lo que corresponda.
"@
}

# --- comprimir -------------------------------------------------------------
$zip = Join-Path $Destino "agente-actividad.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $staging -DestinationPath $zip

$tamano = [math]::Round((Get-Item $zip).Length / 1MB, 2)
Write-Host ""
Write-Host "Paquete generado: $zip ($tamano MB)"
Write-Host "En el otro PC: descomprimir y ejecutar instalar.bat"
