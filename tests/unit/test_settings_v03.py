from pathlib import Path

import pytest

from yt2wa.bootstrap.profiles import load_audio_profile, load_profiles
from yt2wa.bootstrap.settings import Settings
from yt2wa.domain.errors import ConfigError
from yt2wa.domain.models import AudioFormat, SearchProviderName


def settings(env):
    return Settings.from_env(env, dotenv=Path("does-not-exist"))


def test_new_defaults():
    result = settings({})
    assert result.search_limit == 5
    assert result.search_provider is None
    assert result.min_confidence == 0.6
    assert result.audio_format is AudioFormat.M4A
    assert result.audio_bitrate_k is None


def test_new_environment_variables():
    result = settings(
        {
            "YT2WA_SEARCH_LIMIT": "10",
            "YT2WA_SEARCH_PROVIDER": "ytmusic-url",
            "YT2WA_MIN_CONFIDENCE": "0.8",
            "YT2WA_AUDIO_FORMAT": "mp3",
            "YT2WA_AUDIO_BITRATE_K": "96",
        }
    )
    assert result.search_limit == 10
    assert result.search_provider is SearchProviderName.YTMUSIC_URL
    assert result.min_confidence == 0.8
    assert result.audio_format is AudioFormat.MP3
    assert load_audio_profile(result).default_bitrate_k == 96


def test_auto_is_the_same_as_no_provider():
    assert settings({"YT2WA_SEARCH_PROVIDER": "auto"}).search_provider is None


@pytest.mark.parametrize(
    "env",
    [
        {"YT2WA_SEARCH_LIMIT": "0"},
        {"YT2WA_SEARCH_LIMIT": "26"},
        {"YT2WA_SEARCH_LIMIT": "many"},
        {"YT2WA_MIN_CONFIDENCE": "1.5"},
        {"YT2WA_MIN_CONFIDENCE": "high"},
        {"YT2WA_SEARCH_PROVIDER": "spotify"},
        {"YT2WA_AUDIO_FORMAT": "flac"},
    ],
)
def test_invalid_values_raise_config_errors(env):
    with pytest.raises(ConfigError):
        settings(env)


def test_size_cap_override_applies_to_audio_too():
    result = settings({"YT2WA_MAX_SIZE_MB": "8"})
    assert load_audio_profile(result).size_cap_mb == 8
    assert load_profiles(result)["chat"].size_cap_mb == 8


def test_audio_profile_file_overrides_values(tmp_path):
    path = tmp_path / "audio.toml"
    path.write_text("[audio]\ndefault_bitrate_k = 96\nmin_bitrate_k = 32\n")
    profile = load_audio_profile(
        settings({"YT2WA_AUDIO_PROFILE_FILE": str(path)})
    )
    assert profile.default_bitrate_k == 96
    assert profile.min_bitrate_k == 32
    assert profile.sample_rates == (44100, 48000)


def test_bad_audio_profile_files_are_config_errors(tmp_path):
    unknown = tmp_path / "unknown.toml"
    unknown.write_text("[audio]\ncolour = 1\n")
    with pytest.raises(ConfigError):
        load_audio_profile(
            settings({"YT2WA_AUDIO_PROFILE_FILE": str(unknown)})
        )
    broken = tmp_path / "broken.toml"
    broken.write_text("[audio\n")
    with pytest.raises(ConfigError):
        load_audio_profile(settings({"YT2WA_AUDIO_PROFILE_FILE": str(broken)}))
    with pytest.raises(ConfigError):
        load_audio_profile(
            settings({"YT2WA_AUDIO_PROFILE_FILE": str(tmp_path / "missing")})
        )


def test_shipped_audio_config_matches_the_built_in_defaults():
    import tomllib

    from yt2wa.domain.audio_profile import (
        DEFAULT_AUDIO,
        audio_profile_from_mapping,
    )

    root = Path(__file__).resolve().parents[2]
    data = tomllib.loads((root / "config" / "audio.default.toml").read_text())
    assert audio_profile_from_mapping(data["audio"]) == DEFAULT_AUDIO
