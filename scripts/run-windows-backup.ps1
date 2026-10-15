[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PythonExe,
    [Parameter(Mandatory = $true)][string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$env:PYTHONPATH = Join-Path $root "src"
Set-Location -LiteralPath $root

& $python -m noveltrad.backup_cli
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    exit $exitCode
}
exit 0
