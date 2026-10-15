[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PythonExe,
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$TaskName = "NovelTrad scheduled library backup"
)

$ErrorActionPreference = "Stop"
$pythonPath = (Resolve-Path -LiteralPath $PythonExe).Path
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$runner = Join-Path $root "scripts/run-windows-backup.ps1"
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "No se encuentra el ejecutor de copias: $runner"
}

$env:PYTHONPATH = Join-Path $root "src"
& $pythonPath -c "import noveltrad.backup_cli"
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo importar NovelTrad con el Python indicado. Verifica las dependencias y -PythonExe."
}

$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -PythonExe `"$pythonPath`" -ProjectRoot `"$root`""
$action = New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot "System32/WindowsPowerShell/v1.0/powershell.exe") -Argument $arguments -WorkingDirectory $root
# Check once per hour; NovelTrad's own persisted interval decides whether a backup is due.
# Runs as the current user while the app is closed; the user must be logged in.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Crea copias locales de NovelTrad sin iniciar la aplicación; respeta frecuencia y retención configuradas." -Force | Out-Null
Write-Host "Tarea '$TaskName' registrada. Comprueba su estado en el Programador de tareas de Windows."
Write-Host "Nota: se ejecuta con el usuario actual; no necesita NovelTrad abierto, pero sí una sesión de Windows iniciada."
