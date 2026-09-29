"""The launcher must distinguish its own PID from a reused process ID."""

from __future__ import annotations

import shutil
import subprocess
import os
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "start-studybuddy.ps1"


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell required")
def test_start_script_matches_only_the_exact_studybuddy_command():
    powershell = """
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:STUDYBUDDY_SCRIPT_UNDER_TEST, [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count -ne 0) { throw 'start_script_parse_failed' }
$function = $ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Test-StudyBuddyCommand'
}, $true) | Select-Object -First 1
if (-not $function) { throw 'ownership_matcher_missing' }
. ([scriptblock]::Create($function.Extent.Text))
$root = 'C:\\study root'
$cases = @(
    @{ line = '"C:\\Python\\python.exe" -m backend.app serve --data-root "C:\\study root"'; expected = $true },
    @{ line = 'C:\\Python\\python.exe -m backend.app serve --data-root C:\\study root'; expected = $false },
    @{ line = 'C:\\Python\\python.exe -m backend.app serve --data-root C:\\study'; root = 'C:\\study'; expected = $true },
    @{ line = 'C:\\Python\\python.exe -m backend.app serve --data-root "C:\\study root-other"'; expected = $false },
    @{ line = 'C:\\Python\\python.exe -m backend.app other --data-root "C:\\study root"'; expected = $false },
    @{ line = 'C:\\other.exe -m another.backend.app serve --data-root "C:\\study root"'; expected = $false },
    @{ line = ''; expected = $false }
)
foreach ($case in $cases) {
    $caseRoot = if ($case.ContainsKey('root')) { $case.root } else { $root }
    if ((Test-StudyBuddyCommand $case.line $caseRoot) -ne $case.expected) {
        throw 'ownership_match_incorrect'
    }
}
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", powershell],
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "STUDYBUDDY_SCRIPT_UNDER_TEST": str(SCRIPT)},
    )
    assert result.returncode == 0, result.stderr


def test_start_script_checks_live_pid_ownership_before_removing_file():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "Get-CimInstance Win32_Process" in source
    assert "Test-StudyBuddyCommand $oldProcess.CommandLine $resolvedRoot" in source
    assert "if (-not $oldProcess -or -not $oldProcess.CommandLine)" in source
