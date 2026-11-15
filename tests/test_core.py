import random
from datetime import date, datetime

import pytest

from git_hired.core import (
    PROGRESS_THRESHOLD,
    build_script,
    calculate_multiplier,
    commit_command,
    commit_commands,
    default_remote_url,
    format_matrix,
    generate_random_matrix,
    validate_repo,
    validate_username,
    values_in_date_order,
    with_progress,
)


@pytest.mark.parametrize("name", ["octocat", "a", "a-b", "A1-b2-c3", "x" * 39])
def test_validate_username_valid(name):
    assert validate_username(name) == name


@pytest.mark.parametrize("name", ["", "-a", "a-", "a--b", "a_b", "x" * 40, "a;rm -rf ~", "$(whoami)"])
def test_validate_username_invalid(name):
    with pytest.raises(ValueError):
        validate_username(name)


@pytest.mark.parametrize("repo", ["repo", "my-repo", "my_repo.v2", ".github"])
def test_validate_repo_valid(repo):
    assert validate_repo(repo) == repo


@pytest.mark.parametrize("repo", ["", ".", "..", "a b", "a/b", "a;b", "$(x)", "x" * 101])
def test_validate_repo_invalid(repo):
    with pytest.raises(ValueError):
        validate_repo(repo)


def test_default_remote_url():
    assert default_remote_url("octocat", "repo") == "git@github.com:octocat/repo.git"


def test_generate_random_matrix_shape():
    matrix = generate_random_matrix(date(2024, 1, 1), date(2024, 1, 28))
    assert len(matrix) == 7
    assert all(len(row) == 4 for row in matrix)


def test_generate_random_matrix_values_in_range():
    matrix = generate_random_matrix(date(2024, 1, 1), date(2024, 12, 31))
    assert all(0 <= level <= 4 for row in matrix for level in row)


def test_generate_random_matrix_single_week_has_no_empty_days():
    matrix = generate_random_matrix(date(2024, 1, 1), date(2024, 1, 7))
    assert len(matrix[0]) == 1
    assert all(row[0] >= 1 for row in matrix)


def test_generate_random_matrix_single_day():
    matrix = generate_random_matrix(date(2024, 1, 1), date(2024, 1, 1))
    values = list(values_in_date_order(matrix))
    assert values[0] >= 1
    assert values[1:] == [0] * 6


def test_generate_random_matrix_no_commits_after_end_date():
    # 10 days span two weeks; the last 4 cells fall after the end date.
    for seed in range(20):
        matrix = generate_random_matrix(date(2024, 1, 1), date(2024, 1, 10), random.Random(seed))
        assert list(values_in_date_order(matrix))[10:] == [0, 0, 0, 0]


def test_generate_random_matrix_is_reproducible_with_seed():
    a = generate_random_matrix(date(2024, 1, 1), date(2024, 6, 1), random.Random(42))
    b = generate_random_matrix(date(2024, 1, 1), date(2024, 6, 1), random.Random(42))
    assert a == b


def test_generate_random_matrix_rejects_reversed_dates():
    with pytest.raises(ValueError):
        generate_random_matrix(date(2024, 1, 2), date(2024, 1, 1))


@pytest.mark.parametrize(("max_commits", "expected"), [(0, 1), (1, 1), (4, 1), (5, 2), (8, 2), (20, 5), (21, 6)])
def test_calculate_multiplier(max_commits, expected):
    assert calculate_multiplier(max_commits) == expected


def test_values_in_date_order_is_column_major():
    matrix = [[1, 8], [2, 9], [3, 0], [4, 0], [5, 0], [6, 0], [7, 0]]
    assert list(values_in_date_order(matrix, multiplier=2)) == [2, 4, 6, 8, 10, 12, 14, 16, 18, 0, 0, 0, 0, 0]


def test_commit_command():
    cmd = commit_command(datetime(2024, 6, 24, 12))
    assert cmd == (
        "GIT_AUTHOR_DATE=2024-06-24T12:00:00 GIT_COMMITTER_DATE=2024-06-24T12:00:00 "
        "git commit --allow-empty -m git-hired > /dev/null\n"
    )


def test_commit_commands_dates_and_counts():
    matrix = [[2], [0], [1], [0], [0], [0], [0]]
    commands = commit_commands(matrix, date(2024, 1, 30), multiplier=1)
    assert len(commands) == 3
    assert commands[0].startswith("GIT_AUTHOR_DATE=2024-01-30T12:00:00")
    assert commands[1].startswith("GIT_AUTHOR_DATE=2024-01-30T12:00:00")
    assert commands[2].startswith("GIT_AUTHOR_DATE=2024-02-01T12:00:00")


def test_with_progress_leaves_short_lists_alone():
    commands = ["x\n"] * PROGRESS_THRESHOLD
    assert with_progress(commands) == commands


def test_with_progress_marks_quarters():
    out = with_progress(["x\n"] * 200)
    echoes = [line for line in out if line.startswith("echo")]
    assert echoes == [f'echo "{p}% complete"\n' for p in (0, 25, 50, 75, 100)]
    assert out.index('echo "50% complete"\n') == 100 + 2
    assert out.count("x\n") == 200


def test_build_script_structure():
    matrix = [[1, 0], [0, 1], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]
    script = build_script(matrix, date(2024, 1, 1), "testrepo", "git@github.com:testuser/testrepo.git")
    assert script.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert "REPO=testrepo\n" in script
    assert "git remote add origin git@github.com:testuser/testrepo.git\n" in script
    assert script.count("git commit") == 2


def test_build_script_quotes_values():
    matrix = [[0]] * 7
    script = build_script(matrix, date(2024, 1, 1), "repo", "https://example.com/a b.git")
    assert "git remote add origin 'https://example.com/a b.git'\n" in script


def test_format_matrix():
    assert format_matrix([[1, 2], [3, 4]]) == "1 2\n3 4"
