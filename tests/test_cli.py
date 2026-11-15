import os
import re
import stat

import pytest

from git_hired import cli
from git_hired.github import CalendarError

FULL_ARGS = ["-u", "octocat", "-r", "repo", "-s", "2024-01-01", "-e", "2024-01-14", "-m", "2", "--seed", "1"]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(username):
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(cli, "fetch_calendar", fail)


@pytest.fixture
def tty(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)


@pytest.fixture
def no_tty(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)


def feed(monkeypatch, *answers):
    """Answer input() prompts in order; returns the list of prompts shown."""
    it = iter(answers)
    prompts = []

    def fake_input(text):
        prompts.append(text)
        return next(it)

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


@pytest.fixture
def busiest_day(monkeypatch):
    """Pretend the user's busiest day on GitHub had 8 contributions (default multiplier 2)."""
    monkeypatch.setattr(cli, "fetch_calendar", lambda username: "html")
    monkeypatch.setattr(cli, "max_daily_contributions", lambda html: 8)


def test_non_interactive(tmp_path, no_tty, capsys):
    out = tmp_path / "script.sh"
    assert cli.main([*FULL_ARGS, "-o", str(out)]) == 0
    script = out.read_text()
    assert "REPO=repo\n" in script
    assert "git remote add origin git@github.com:octocat/repo.git\n" in script
    assert os.stat(out).st_mode & stat.S_IXUSR
    output = capsys.readouterr().out
    assert "0 = 0 commits" in output
    assert re.search(r"Total: \d+ commits", output)


def test_seed_makes_output_reproducible(tmp_path, no_tty):
    a, b = tmp_path / "a.sh", tmp_path / "b.sh"
    cli.main([*FULL_ARGS, "-o", str(a)])
    cli.main([*FULL_ARGS, "-o", str(b)])
    assert a.read_text() == b.read_text()


def test_remote_url_override(tmp_path, no_tty):
    out = tmp_path / "script.sh"
    cli.main([*FULL_ARGS, "-o", str(out), "--remote-url", "https://ghe.example.com/me/repo.git"])
    assert "git remote add origin https://ghe.example.com/me/repo.git\n" in out.read_text()


def test_multiplier_from_github(tmp_path, no_tty, monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch_calendar", lambda username: "html")
    monkeypatch.setattr(cli, "max_daily_contributions", lambda html: 20)
    args = [a for a in FULL_ARGS if a not in ("-m", "2")]
    assert cli.main([*args, "-o", str(tmp_path / "s.sh")]) == 0
    assert "4 = 20 commits" in capsys.readouterr().out


def test_github_failure_is_reported(tmp_path, no_tty, monkeypatch, capsys):
    def fail(username):
        raise CalendarError("GitHub user 'octocat' not found")

    monkeypatch.setattr(cli, "fetch_calendar", fail)
    args = [a for a in FULL_ARGS if a not in ("-m", "2")]
    assert cli.main([*args, "-o", str(tmp_path / "s.sh")]) == 1
    err = capsys.readouterr().err
    assert "not found" in err
    assert "--multiplier" in err


def test_missing_value_without_tty_errors(no_tty, capsys):
    assert cli.main(["-u", "octocat"]) == 1
    assert "Repository name is required" in capsys.readouterr().err


def test_end_before_start(no_tty, capsys):
    assert cli.main([*FULL_ARGS[:4], "-s", "2024-02-01", "-e", "2024-01-01"]) == 1
    assert "end date" in capsys.readouterr().err


def test_unwritable_output(tmp_path, no_tty, capsys):
    assert cli.main([*FULL_ARGS, "-o", str(tmp_path / "missing" / "s.sh")]) == 1
    assert "could not write" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("flag", "value"),
    [("-u", "bad user"), ("-r", "a/b"), ("-s", "2024-13-01"), ("-e", "tomorrow"), ("-m", "0"), ("-m", "x")],
)
def test_invalid_arguments_rejected(flag, value, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([flag, value])
    assert exc.value.code == 2
    assert "error" in capsys.readouterr().err


def test_interactive(tmp_path, tty, busiest_day, monkeypatch, capsys):
    feed(monkeypatch, "octocat", "repo", "2024-01-31", "2024-02-29", "3")
    out = tmp_path / "s.sh"
    assert cli.main(["-o", str(out)]) == 0
    assert "4 = 12 commits" in capsys.readouterr().out
    # End dates at the end of a month work, and nothing is committed after them.
    assert "2024-03-" not in out.read_text()


def test_interactive_reprompts_on_invalid_input(tmp_path, tty, busiest_day, monkeypatch, capsys):
    feed(monkeypatch, "", "bad user", "octocat", "repo", "2024-1-1", "2024-01-01", "2024-01-07", "0", "1")
    assert cli.main(["-o", str(tmp_path / "s.sh")]) == 0
    err = capsys.readouterr().err
    assert "invalid GitHub username" in err
    assert "expected YYYY-MM-DD" in err
    assert "greater than 0" in err


def test_interactive_blank_multiplier_uses_github(tmp_path, tty, busiest_day, monkeypatch, capsys):
    prompts = feed(monkeypatch, "octocat", "repo", "2024-01-01", "2024-01-07", "")
    assert cli.main(["-o", str(tmp_path / "s.sh")]) == 0
    assert prompts[-1] == "Commits per shade level (blank for 2): "
    out = capsys.readouterr().out
    assert "busiest day on GitHub had 8 contributions" in out
    assert "4 = 8 commits" in out


def test_interactive_github_failure_asks_for_multiplier(tmp_path, tty, monkeypatch, capsys):
    def fail(username):
        raise CalendarError("could not fetch")

    monkeypatch.setattr(cli, "fetch_calendar", fail)
    prompts = feed(monkeypatch, "octocat", "repo", "2024-01-01", "2024-01-07", "", "3")
    assert cli.main(["-o", str(tmp_path / "s.sh")]) == 0
    assert prompts[-1] == "Commits per shade level: "  # no default offered, blank re-prompts
    assert "could not fetch" in capsys.readouterr().err


def test_ctrl_c_exits_cleanly(tty, monkeypatch):
    def interrupt(_prompt):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert cli.main([]) == 130


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("git-hired ")
