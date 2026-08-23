[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)][string[]]$Spec,
    [switch]$Install
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$npx = if ($env:STUDYBUDDY_NPX) { $env:STUDYBUDDY_NPX } else { (Get-Command 'npx.cmd' -ErrorAction Stop).Source }
if ($Install) {
    & $npx playwright install chromium
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$paths = foreach ($item in $Spec) {
    if ($item -match '[\\/]') { $item } else { "backend/tests/$item" }
}
Push-Location $root
try {
    # Browser evidence is serial by policy; each spec owns its isolated runtime data.
    # Pass the resolved array as a native-command argument value.  `@paths`
    # is not PowerShell array splatting and silently caused Playwright to
    # ignore the requested spec after the environment rebuild.
    & $npx playwright test $paths '--workers=1' '--reporter=line'
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
