import io
from urllib.error import HTTPError, URLError

import pytest

from git_hired import github
from git_hired.github import CalendarError, fetch_calendar, max_daily_contributions, parse_daily_counts

# Trimmed from a real https://github.com/users/<name>/contributions response.
CALENDAR_HTML = """
<td tabindex="0" data-ix="0" data-date="2025-10-12" id="contribution-day-component-0-0" data-level="1"
  role="gridcell" class="ContributionCalendar-day"></td>
<tool-tip id="tooltip-1" for="contribution-day-component-0-0" popover="manual" data-direction="n"
  data-type="label" class="sr-only position-absolute">4 contributions on October 12th.</tool-tip>
<td data-date="2025-10-19" id="contribution-day-component-0-1" data-level="0"></td>
<tool-tip id="tooltip-2" for="contribution-day-component-0-1">No contributions on October 19th.</tool-tip>
<td data-date="2025-10-26" id="contribution-day-component-0-2" data-level="1"></td>
<tool-tip id="tooltip-3" for="contribution-day-component-0-2">1 contribution on October 26th.</tool-tip>
<td data-date="2025-11-02" id="contribution-day-component-0-3" data-level="4"></td>
<tool-tip id="tooltip-4" for="contribution-day-component-0-3">1,234 contributions on November 2nd.</tool-tip>
"""


def test_parse_daily_counts():
    assert parse_daily_counts(CALENDAR_HTML) == [4, 0, 1, 1234]


def test_parse_daily_counts_ignores_data_level():
    assert parse_daily_counts('<td data-level="4"></td>') == []


def test_max_daily_contributions():
    assert max_daily_contributions(CALENDAR_HTML) == 1234


def test_max_daily_contributions_no_data():
    with pytest.raises(CalendarError, match="page format"):
        max_daily_contributions("<html></html>")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_calendar(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return FakeResponse(b"<html>ok</html>")

    monkeypatch.setattr(github, "urlopen", fake_urlopen)
    assert fetch_calendar("octocat") == "<html>ok</html>"
    assert seen["url"] == "https://github.com/users/octocat/contributions"
    assert seen["agent"].startswith("git-hired/")
    assert seen["timeout"] == github.TIMEOUT_SECONDS


def test_fetch_calendar_user_not_found(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", None, None)

    monkeypatch.setattr(github, "urlopen", fake_urlopen)
    with pytest.raises(CalendarError, match="not found"):
        fetch_calendar("nobody")


def test_fetch_calendar_http_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 500, "Server Error", None, None)

    monkeypatch.setattr(github, "urlopen", fake_urlopen)
    with pytest.raises(CalendarError, match="500"):
        fetch_calendar("octocat")


@pytest.mark.parametrize("error", [URLError("no network"), TimeoutError("timed out")])
def test_fetch_calendar_network_error(monkeypatch, error):
    def fake_urlopen(request, timeout):
        raise error

    monkeypatch.setattr(github, "urlopen", fake_urlopen)
    with pytest.raises(CalendarError, match="could not fetch"):
        fetch_calendar("octocat")
