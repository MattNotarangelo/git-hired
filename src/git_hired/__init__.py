"""Generate a shell script that fills a GitHub contribution graph between two dates."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("git-hired")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.0.0"
