"""The twelve-factor rules we claim, checked automatically."""

import ast
import logging
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "yt2wa"


def source_files():
    return sorted(SRC.rglob("*.py"))


def rel(path):
    return str(path.relative_to(SRC))


# ---- II. Dependencies -------------------------------------------------------


def pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_dependencies_are_declared_and_the_music_one_is_optional():
    project = pyproject()["project"]
    core = " ".join(project["dependencies"]).lower()
    extras = project["optional-dependencies"]
    assert "yt-dlp" in core
    assert "ytmusicapi" not in core
    assert any("ytmusicapi" in d.lower() for d in extras["music"])
    assert "ytmusicapi" in " ".join(extras["music"]).lower()


def test_the_container_and_ci_install_the_music_extra():
    assert "[music]" in (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "music" in ci


# ---- III. Config ------------------------------------------------------------


def uses_environment(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in (
            "environ",
            "getenv",
        ):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            if any(a.name in ("environ", "getenv") for a in node.names):
                return True
    return False


def test_only_the_settings_module_reads_the_environment():
    readers = [
        rel(p)
        for p in source_files()
        if uses_environment(ast.parse(p.read_text(encoding="utf-8")))
    ]
    assert readers == ["bootstrap/settings.py"]


def settings_variable_names():
    text = (SRC / "bootstrap" / "settings.py").read_text(encoding="utf-8")
    pattern = (
        r'(?:PREFIX \+ |_int\(env, |_float\(env, |_path\(env, )"([A-Z0-9_]+)"'
    )
    return sorted(set(re.findall(pattern, text)))


def test_every_setting_is_documented_in_env_example():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    missing = [
        name
        for name in settings_variable_names()
        if f"YT2WA_{name}" not in example
    ]
    assert not missing, f"undocumented settings: {missing}"


def test_env_example_values_are_all_valid():
    from yt2wa.bootstrap.settings import Settings

    env = {}
    for line in (
        (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    ):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    assert "YT2WA_SEARCH_PROVIDER" in env or "YT2WA_AUDIO_FORMAT" in env
    Settings.from_env(env, dotenv=ROOT / "nonexistent.env")


def test_no_environment_variable_names_are_hard_coded_outside_settings():
    for path in source_files():
        if rel(path) == "bootstrap/settings.py":
            continue
        assert "YT2WA_" not in path.read_text(encoding="utf-8").replace(
            "YT2WA_COOKIES_FILE", ""
        ).replace("YT2WA_FFMPEG_BIN", "").replace("YT2WA_FFPROBE_BIN", ""), (
            rel(path)
        )


# ---- V. Build, release, run -------------------------------------------------


def test_the_version_is_declared_in_one_consistent_way():
    declared = pyproject()["project"]["version"]
    init = (SRC / "__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{declared}"' in init


# ---- VI. Processes ----------------------------------------------------------


def test_no_module_keeps_mutable_global_state():
    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(
                node.value, (ast.List, ast.Dict, ast.Set)
            ):
                names = [getattr(t, "id", "") for t in node.targets]
                assert all(n.isupper() or n.startswith("_") for n in names), (
                    f"{rel(path)}: mutable module variable {names}"
                )


# ---- IX. Disposability ------------------------------------------------------


def test_startup_does_not_load_the_heavy_libraries():
    code = (
        "import sys\n"
        "from yt2wa.interface import cli\n"
        "from yt2wa.bootstrap.container import build_container\n"
        "from yt2wa.bootstrap.settings import Settings\n"
        "build_container(Settings())\n"
        "bad = [m for m in ('yt_dlp', 'ytmusicapi') if m in sys.modules]\n"
        "assert not bad, bad\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_sigterm_is_turned_into_a_clean_interrupt():
    from yt2wa.interface.cli import _raise_interrupt

    with pytest.raises(KeyboardInterrupt):
        _raise_interrupt(15, None)


def test_main_returns_130_on_interrupt(monkeypatch):
    from yt2wa.interface import cli

    def interrupted(settings):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "build_container", interrupted)
    assert cli.main(["doctor"]) == 130


# ---- XI. Logs ---------------------------------------------------------------


def test_only_the_interface_layer_prints():
    for path in source_files():
        if rel(path).startswith("interface/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "print"
            ):
                raise AssertionError(f"{rel(path)} calls print()")


def test_logs_go_to_stderr():
    from yt2wa.bootstrap.logging_setup import configure_logging

    root = logging.getLogger()
    saved = root.handlers[:], root.level
    try:
        configure_logging("INFO", "text")
        assert [h.stream for h in root.handlers] == [sys.stderr]
        configure_logging("INFO", "json")
        assert [h.stream for h in root.handlers] == [sys.stderr]
    finally:
        root.handlers[:], root.level = saved


# ---- XII. Admin processes ---------------------------------------------------


def test_admin_commands_exist_in_the_same_codebase():
    from yt2wa.interface.cli import COMMANDS

    assert {"doctor", "clean", "verify"} <= set(COMMANDS)


def test_a_missing_optional_package_does_not_fail_doctor(monkeypatch):
    from yt2wa.bootstrap import doctor

    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: None)
    check = doctor._check_ytmusicapi()
    assert check.ok
    assert "optional" in check.detail
