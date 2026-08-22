from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def read_script(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_runner_is_explicitly_opt_in_and_fail_closed():
    script = read_script("run-provider-api-acceptance.ps1")
    assert "STUDYBUDDY_RUN_THREE_ATTEMPT_PROVIDER_ACCEPTANCE -ne '1'" in script
    assert "provider_acceptance_not_enabled" in script
    assert "provider_acceptance_configuration_incomplete" in script
    assert "provider_acceptance_target_mismatch" in script
    assert "invalid_provider_acceptance_config" in script
    assert "invalid_ai_base_url" in script


def test_runner_requires_safe_config_and_target_match():
    script = read_script("run-provider-api-acceptance.ps1")
    assert "^[a-z0-9][a-z0-9-]{0,63}$" in script
    assert "$uri.Scheme -eq 'https'" in script
    assert "-not $uri.UserInfo -and -not $uri.Query -and -not $uri.Fragment" in script
    assert "STUDYBUDDY_REAL_PROVIDER_TARGET'] = $ProviderId" in script
    assert "STUDYBUDDY_AI_PROVIDER'] = $ProviderId" in script
    assert "STUDYBUDDY_AI_MODEL'] = $ModelId" in script
    assert "STUDYBUDDY_AI_BASE_URL'] = $BaseUrl.TrimEnd('/')" in script


def test_runner_uses_isolated_temp_roots_and_early_stop_threshold():
    script = read_script("run-provider-api-acceptance.ps1")
    assert "studybuddy-provider-acceptance-" in script
    assert "studybuddy-provider-pytest-" in script
    assert "--basetemp" in script
    assert "Remove-Item -LiteralPath $dataRoot -Recurse -Force" in script
    assert "Remove-Item -LiteralPath $pytestBase -Recurse -Force" in script
    assert "threshold_reached" in script
    assert "threshold_unreachable" in script
    assert "provider_connection_failed" in script
    assert "catch {" in script
    assert "2_of_3_passed" in script
    assert "2_of_3_not_met" in script


def test_runner_does_not_accept_or_print_secrets_or_child_output():
    script = read_script("run-provider-api-acceptance.ps1")
    assert "-ApiKey" not in script
    assert "-Key" not in script
    assert "-Token" not in script
    assert "-Authorization" not in script
    assert "Write-Output $output" not in script
    assert "Bearer" not in script
    assert "Authorization" not in script


def test_agnes_wrapper_uses_profile_config_only_in_child_environment():
    script = read_script("run-agnes-api-acceptance.ps1")
    assert "param([Parameter(Mandatory = $true)][string]$Profile)" in script
    assert "Get-AgnesConfig $Profile" in script
    assert "run-provider-api-acceptance.ps1" in script
    assert "STUDYBUDDY_AI_API_KEY'] = $AgnesConfig.Key" in script
    assert "STUDYBUDDY_RUN_THREE_ATTEMPT_PROVIDER_ACCEPTANCE" in script
    assert "-ApiKey" not in script
    assert "-Key" not in script
    assert "Bearer" not in script
