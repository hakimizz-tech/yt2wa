from yt2wa.domain.errors import (
    AgeRestrictedError,
    GeoBlockedError,
    NetworkError,
    PrivateVideoError,
    RemovedVideoError,
    SourceUnavailableError,
)
from yt2wa.infrastructure.ffprobe_probe import parse_ffprobe_json
from yt2wa.infrastructure.ytdlp_downloader import classify_download_error


def test_download_errors_are_translated():
    cases = {
        "ERROR: Private video. Sign in": PrivateVideoError,
        "Sign in to confirm your age": AgeRestrictedError,
        "not available in your country": GeoBlockedError,
        "Video unavailable": RemovedVideoError,
        "Sign in to confirm you're not a bot": SourceUnavailableError,
        "HTTP Error 429: Too Many Requests": NetworkError,
        "something odd": SourceUnavailableError,
    }
    for message, expected in cases.items():
        assert isinstance(classify_download_error(message), expected)


def test_ffprobe_json_is_parsed():
    data = {
        "format": {"format_name": "mov,mp4", "duration": "12.5"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "profile": "High",
                "level": 31,
                "pix_fmt": "yuv420p",
                "width": 1080,
                "height": 1920,
                "avg_frame_rate": "30000/1001",
                "side_data_list": [{"rotation": -90}],
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "profile": "LC",
                "channels": 2,
                "sample_rate": "48000",
            },
        ],
    }
    facts = parse_ffprobe_json(data, 1234, True)
    assert facts.vcodec == "h264"
    assert round(facts.fps, 2) == 29.97
    assert facts.rotation == 90
    assert facts.display_size == (1920, 1080)
    assert facts.sample_rate == 48000
    assert facts.faststart is True
    assert facts.duration_s == 12.5
