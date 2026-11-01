from pathlib import Path

import pytest

from yt2wa.bootstrap.profiles import load_profiles
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import ConfigError
from yt2wa.domain.models import Target


def settings(env):
    return Settings.from_env(env, dotenv=Path("does-not-exist"))


def test_defaults():
    result = settings({})
    assert result.default_target is Target.CHAT
    assert result.default_resolution == 480
    assert result.max_size_mb is None


def test_environment_overrides():
    result = settings(
        {
            "YT2WA_DEFAULT_TARGET": "status",
            "YT2WA_DEFAULT_RESOLUTION": "720",
            "YT2WA_MAX_SIZE_MB": "8",
        }
    )
    assert result.default_target is Target.STATUS
    assert result.default_resolution == 720
    assert load_profiles(result)["chat"].size_cap_mb == 8


def test_bad_values_raise_config_errors():
    with pytest.raises(ConfigError):
        settings({"YT2WA_DEFAULT_TARGET": "tv"})
    with pytest.raises(ConfigError):
        settings({"YT2WA_NET_RETRIES": "many"})


def test_profile_file_can_override_values(tmp_path):
    profile_file = tmp_path / "profiles.toml"
    profile_file.write_text("[chat]\ncrf = 30\n")
    result = settings({"YT2WA_PROFILE_FILE": str(profile_file)})
    profiles = load_profiles(result)
    assert profiles["chat"].crf == 30
    assert profiles["status"].crf == 30
    assert profiles["status"].advisory_aspect is not None
