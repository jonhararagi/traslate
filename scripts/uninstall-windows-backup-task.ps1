[CmdletBinding()]
param([string]$TaskName = "NovelTrad scheduled library backup")

$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "No existe la tarea '$TaskName'; no hay cambios."
    exit 0
}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Se eliminó la tarea '$TaskName'. Las copias ya creadas y la biblioteca no se modificaron."
