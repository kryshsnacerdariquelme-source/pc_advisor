$ErrorActionPreference = 'Stop'

# PC Advisor usa LHM 0.9.4 porque es la versión que funciona con el proveedor
# WMI que consulta Backend/hardware.py. No se actualiza automáticamente a 0.9.6.
$version = '0.9.4'
$url = 'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.4/LibreHardwareMonitor-net472.zip'
$hashEsperado = 'D2E397CC4D33D65C6493DFF83B9335BC341A3AF31CAAFCEEF83F717FDAB37448'
$instalacion = Join-Path $env:ProgramFiles 'LibreHardwareMonitor'
$zip = Join-Path $env:TEMP 'LibreHardwareMonitor-net472-0.9.4.zip'

Write-Host '=== PC Advisor - Sensores automaticos ===' -ForegroundColor Cyan

# Pedir elevacion si no se ejecuta como administrador.
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Solicitando permisos de administrador...' -ForegroundColor Yellow
    $script = $MyInvocation.MyCommand.Definition
    Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$script`"" -Wait
    exit
}

# Detener una versión anterior para evitar archivos bloqueados.
Get-Process LibreHardwareMonitor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Descargando Libre Hardware Monitor $version..." -ForegroundColor Green
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

Write-Host 'Verificando integridad del archivo...' -ForegroundColor Green
$hashReal = (Get-FileHash -Path $zip -Algorithm SHA256).Hash.ToUpperInvariant()
if ($hashReal -ne $hashEsperado) {
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    throw "El hash SHA-256 no coincide. Descarga abortada por seguridad."
}

if (Test-Path $instalacion) {
    Remove-Item $instalacion -Recurse -Force
}
New-Item -ItemType Directory -Path $instalacion -Force | Out-Null
Expand-Archive -Path $zip -DestinationPath $instalacion -Force
Remove-Item $zip -Force -ErrorAction SilentlyContinue

# El ZIP puede contener una carpeta intermedia. Localizar el ejecutable real.
$exe = Get-ChildItem $instalacion -Filter 'LibreHardwareMonitor.exe' -Recurse -File | Select-Object -First 1
if (-not $exe) {
    throw 'No se encontro LibreHardwareMonitor.exe despues de la instalacion.'
}

# Acceso directo en Inicio.
$inicio = [Environment]::GetFolderPath('Programs')
$shortcut = Join-Path $inicio 'Libre Hardware Monitor.lnk'
$ws = New-Object -ComObject WScript.Shell
$link = $ws.CreateShortcut($shortcut)
$link.TargetPath = $exe.FullName
$link.WorkingDirectory = $exe.DirectoryName
$link.Save()

Write-Host 'Iniciando Libre Hardware Monitor como administrador...' -ForegroundColor Green
Start-Process -FilePath $exe.FullName -Verb RunAs

Write-Host ''
Write-Host 'Libre Hardware Monitor 0.9.4 quedo instalado y ejecutandose.' -ForegroundColor Green
Write-Host 'Ahora ejecuta PC Advisor:' -ForegroundColor Cyan
Write-Host '  python Backend\monitor.py'
Write-Host '  streamlit run Frontend\app.py'
