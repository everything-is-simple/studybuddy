[CmdletBinding()]
param(
    [string]$DataRoot = 'H:\studybuddy-data',
    [int]$Port = 8787,
    [string]$Python,
    [switch]$OpenBrowser
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = if ($Python) { $Python } elseif (Test-Path 'D:/miniconda/py310/python.exe') { 'D:/miniconda/py310/python.exe' } else { Join-Path $root '.venv/Scripts/python.exe' }
if (-not (Test-Path $python)) { throw 'studybuddy_python_unavailable' }

$env:STUDYBUDDY_DATA_ROOT = [System.IO.Path]::GetFullPath($DataRoot)
$env:STUDYBUDDY_HOST = '127.0.0.1'
$env:STUDYBUDDY_PORT = [string]$Port
$env:STUDYBUDDY_REPORT_DELIVERY_MODE = 'off'
$env:STUDYBUDDY_REPORT_DELIVERY_ENABLED = 'false'
$env:STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED = 'false'

& (Join-Path $root 'backend/scripts/start-studybuddy.ps1') -DataRoot $env:STUDYBUDDY_DATA_ROOT -Port $Port -Python $python -OpenBrowser:$OpenBrowser
