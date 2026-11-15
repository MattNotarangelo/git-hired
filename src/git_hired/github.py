"""Fetch and parse a user's public GitHub contribution calendar."""

import re
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from git_hired import __version__

CONTRIBUTIONS_URL = "https://github.com/users/{username}/contributions"
TIMEOUT_SECONDS = 15

# Each day has a tooltip such as "4 contributions on October 12th." or "No contributions on ...".
# (The cells' data-level attribute is only the 0-4 shade, not the count.)
_TOOLTIP_RE = re.compile(r"<tool-tip\b[^>]*>\s*(No|[\d,]+) contributions? on", re.IGNORECASE)


class CalendarError(RuntimeError):
    """The contribution calendar could not be fetched or understood."""


def fetch_calendar(username: str, timeout: float = TIMEOUT_SECONDS) -> str:
    """Return the HTML of the user's contribution calendar."""
    url = CONTRIBUTIONS_URL.format(username=username)
    request = Request(url, headers={"User-Agent": f"git-hired/{__version__}"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body: bytes = response.read()
            return body.decode("utf-8")
    except HTTPError as e:
        if e.code == 404:
            raise CalendarError(f"GitHub user {username!r} not found") from e
        raise CalendarError(f"could not fetch {url}: {e}") from e
    # OSError covers URLError, timeouts and dropped connections; HTTPException covers truncated replies.
    except (OSError, HTTPException) as e:
        raise CalendarError(f"could not fetch {url}: {e}") from e


def parse_daily_counts(html: str) -> list[int]:
    """Return the contribution count for each day in the calendar HTML."""
    return [0 if count.lower() == "no" else int(count.replace(",", "")) for count in _TOOLTIP_RE.findall(html)]


def max_daily_contributions(html: str) -> int:
    """Return the highest number of contributions made on a single day."""
    counts = parse_daily_counts(html)
    if not counts:
        raise CalendarError("no contribution data found; GitHub may have changed its page format")
    return max(counts)
