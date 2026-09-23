[CmdletBinding()]
param(
    [string]$Python = 'D:\miniconda\py310\python.exe'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$venv = Join-Path $root '.venv'
if (-not (Test-Path $Python)) { throw 'studybuddy_python_unavailable' }
if (-not (Test-Path (Join-Path $venv 'Scripts/python.exe'))) {
    & $Python -m venv $venv
}
$venvPython = Join-Path $venv 'Scripts/python.exe'
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $root 'backend/requirements.txt')
& $venvPython -m pip check
& $venvPython -m backend.app version
