"""yt2wa: download YouTube videos and make them WhatsApp friendly."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yt2wa")
except PackageNotFoundError:  # Running from a source tree.
    __version__ = "0.1.0"
