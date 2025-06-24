import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import pytest
import numpy as np
from datetime import datetime, timedelta
from main import (
    print_section,
    request_user_input,
    generate_random_matrix,
    retrieve_contributions_calendar,
    parse_contributions_calendar,
    find_max_daily_commits,
    calculate_multiplier,
    get_dates,
    generate_next_dates,
    generate_values_in_date_order,
    commit,
    fake_it,
    save,
)


def test_print_section_1(monkeypatch, capsys):
    # Patch get_terminal_size in the correct module to avoid OSError
    monkeypatch.setattr("main.get_terminal_size", lambda: (10, 20))
    print_section()
    out, _ = capsys.readouterr()
    assert out.strip() == "-" * 9


def test_print_section_2(monkeypatch, capsys):
    monkeypatch.setattr("main.get_terminal_size", lambda: (50, 20))
    print_section()
    out, _ = capsys.readouterr()
    assert out.strip() == "-" * 49


def test_request_user_input_valid(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "test123")
    assert request_user_input() == "test123"


def test_request_user_input_empty(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(SystemExit):
        request_user_input()


def test_generate_random_matrix_shape():
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 28)
    matrix = generate_random_matrix(start, end)
    assert matrix.shape[0] == 7
    assert matrix.shape[1] == 4


def test_generate_random_matrix_values():
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 8)
    matrix = generate_random_matrix(start, end)
    assert np.all((matrix >= 0) & (matrix <= 4))


def test_generate_random_matrix_one_week():
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 7)
    matrix = generate_random_matrix(start, end)
    print(matrix)
    assert matrix.shape == (7, 1)
    assert np.all(matrix >= 1)


def test_generate_random_matrix_excess_days():
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 10)
    matrix = generate_random_matrix(start, end)
    # Last column's last days should be zero
    print(matrix)
    assert matrix[-1][-1] == 0
    assert matrix[-2][-1] == 0
    assert matrix[-3][-1] == 0


def test_parse_contributions_calendar():
    svg = """<rect class="day" data-level="0"/><rect class="day" data-level="2"/><rect class="day" data-level="4"/>"""
    counts = list(parse_contributions_calendar(svg))
    assert counts == [0, 2, 4]


def test_parse_contributions_calendar_empty():
    svg = ""  # No data-level
    counts = list(parse_contributions_calendar(svg))
    assert counts == []


def test_find_max_daily_commits():
    svg = """<rect class="day" data-level="0"/><rect class="day" data-level="2"/><rect class="day" data-level="4"/>"""
    assert find_max_daily_commits(svg) == 4


def test_find_max_daily_commits_empty():
    # Should raise ValueError if no commits
    with pytest.raises(ValueError):
        find_max_daily_commits("")


def test_calculate_multiplier():
    assert calculate_multiplier(0) == 1
    assert calculate_multiplier(4) == 1
    assert calculate_multiplier(8) == 2
    assert calculate_multiplier(20) == 5
    assert calculate_multiplier(21) == 6


def test_get_dates_valid(monkeypatch):
    from main import get_dates

    inputs = iter(["2024", "1", "1", "2024", "1", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    start, end = get_dates()
    assert start < end


def test_get_dates_invalid(monkeypatch):
    from main import get_dates

    inputs = iter(["2024", "1", "1", "2023", "1", "1"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    with pytest.raises(SystemExit):
        get_dates()


def test_get_dates_valueerror(monkeypatch):
    from main import get_dates

    inputs = iter(["bad", "1", "1", "2024", "1", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    with pytest.raises(SystemExit):
        get_dates()


def test_generate_next_dates():
    start = datetime(2024, 1, 1)
    gen = generate_next_dates(start)
    dates = [next(gen) for _ in range(3)]
    assert dates[0] == start
    assert dates[1] == start + timedelta(days=1)
    assert dates[2] == start + timedelta(days=2)


def test_generate_values_in_date_order():
    matrix = np.array([[1], [2], [0], [0], [0], [0], [0]])
    values = list(generate_values_in_date_order(matrix, multiplier=2))
    assert values[:4] == [2, 4, 0, 0]


def test_generate_values_in_date_order_2():
    matrix = np.array([[1, 5], [2, 16]])
    values = list(generate_values_in_date_order(matrix, multiplier=2))
    assert values == [2, 4, 0, 0, 0, 0, 0, 10, 32, 0, 0, 0, 0, 0]


def test_generate_values_in_date_order_indexerror():
    # Matrix with missing columns
    matrix = np.array([[1], [2], [3], [4], [5], [6], [7]])
    values = list(generate_values_in_date_order(matrix, multiplier=1))
    assert values == [1, 2, 3, 4, 5, 6, 7]


def test_commit_format():
    date = datetime(2024, 1, 1, 12, 0, 0)
    cmd = commit(date)
    assert "GIT_AUTHOR_DATE" in cmd
    assert "git commit --allow-empty" in cmd


def test_commit_date_format():
    date = datetime(2024, 6, 24, 15, 30, 0)
    cmd = commit(date)
    assert date.isoformat() in cmd


def test_fake_it_script_structure():
    matrix = np.array([[1, 0], [0, 1], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]])
    start_date = datetime(2024, 1, 1)
    username = "testuser"
    repo = "testrepo"
    git_url = "git@github.com"
    script = fake_it(matrix, start_date, username, repo, git_url, multiplier=1)
    assert script.startswith("#!/usr/bin/env bash")
    assert f"REPO={repo}" in script
    assert f"git remote add origin {git_url}:{username}/$REPO.git" in script


def test_fake_it_progress():
    # Test progress echo insertion
    matrix = np.ones((7, 30), dtype=int)
    start_date = datetime(2024, 1, 1)
    username = "testuser"
    repo = "testrepo"
    git_url = "git@github.com"
    script = fake_it(matrix, start_date, username, repo, git_url, multiplier=1)
    assert 'echo "0% complete"' in script
    assert 'echo "100% complete"' in script


def test_save_creates_file(tmp_path):
    file_path = tmp_path / "test.sh"
    save("echo test", str(file_path))
    with open(file_path) as f:
        content = f.read()
    assert "echo test" in content
