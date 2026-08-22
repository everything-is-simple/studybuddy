from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def read_script(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_agnes_launcher_uses_namespaced_config_and_fixed_target():
    common = read_script("agnes-common.ps1")
    assert "STUDYBUDDY_AGNES_KEY" in common
    assert "STUDYBUDDY_AGNES_MODEL_" in common
    assert "throw 'agnes_invalid_profile'" in common
    assert "$Profile -notmatch '^[a-z0-9][a-z0-9-]{0,31}$'" in common
    assert "STUDYBUDDY_AI_API_KEY'] = $Config.Key" in common
    assert "STUDYBUDDY_REAL_PROVIDER_TARGET'] = 'agnes-ai-hub'" in common
    assert "-ne 'agnes-ai-hub'" in common
    assert "throw 'agnes_configuration_incomplete'" in common
    assert "throw 'invalid_ai_base_url'" in common


def test_agnes_launchers_do_not_accept_secret_command_line_arguments():
    for script in SCRIPTS.glob("*agnes*.ps1"):
        content = script.read_text(encoding="utf-8")
        assert "STUDYBUDDY_AGNES_KEY" not in content or script.name == "agnes-common.ps1"
        assert "Bearer" not in content
        assert "-ApiKey" not in content
        assert "-Key" not in content


def test_agnes_entrypoints_set_expected_gate():
    provider = read_script("test-agnes-provider.ps1")
    ui = read_script("test-agnes-ui.ps1")
    start = read_script("start-agnes.ps1")
    assert "test_real_provider_smoke.py" in provider
    assert "STUDYBUDDY_RUN_REAL_PROVIDER_UI_SMOKE'] = '1'" in ui
    assert "STUDYBUDDY_REAL_PROVIDER_UI_TARGET'] = 'agnes-ai-hub'" in ui
    assert "Remove('STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE')" in start
    for script in (provider, ui, start):
        assert "param([string]$Profile)" in script
        assert "Get-AgnesConfig $Profile" in script
