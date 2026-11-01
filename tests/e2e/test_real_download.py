"""Opt-in test that touches the real internet.

Run with:  pytest -m network --url <link to a video you may download>
"""

import os

import pytest

from yt2wa.domain.url_rules import classify_url

pytestmark = pytest.mark.network

URL = os.environ.get("YT2WA_E2E_URL", "")


@pytest.mark.skipif(not URL, reason="set YT2WA_E2E_URL to a video you may use")
def test_probe_real_video():
    from yt2wa.infrastructure.ytdlp_downloader import YtDlpDownloader

    metadata = YtDlpDownloader().probe(classify_url(URL))
    assert metadata.duration_s > 0
