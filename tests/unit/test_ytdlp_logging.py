import logging

from yt2wa.domain.models import SearchProviderName
from yt2wa.infrastructure.ytdlp_downloader import YtDlpDownloader, YtDlpLogger
from yt2wa.infrastructure.ytdlp_search import YtDlpSearchProvider


def test_yt_dlp_messages_go_to_our_logs_not_the_terminal(capsys, caplog):
    logger = YtDlpLogger()
    with caplog.at_level(logging.DEBUG):
        logger.debug("a")
        logger.info("b")
        logger.warning("c")
        logger.error("d")
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert [r.getMessage() for r in caplog.records] == [
        "yt-dlp: a",
        "yt-dlp: b",
        "yt-dlp: c",
        "yt-dlp: d",
    ]


def test_every_yt_dlp_call_uses_the_logger():
    downloader = YtDlpDownloader()
    assert isinstance(downloader._base_options()["logger"], YtDlpLogger)
    search = YtDlpSearchProvider(SearchProviderName.YTSEARCH)
    assert isinstance(search._options(5)["logger"], YtDlpLogger)
