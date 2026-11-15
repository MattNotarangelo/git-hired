"""Run a generated script end to end against a local bare repository."""

import os
import shutil
import subprocess
from collections import Counter
from datetime import date

import pytest

from git_hired.core import build_script, values_in_date_order

pytestmark = pytest.mark.skipif(not (shutil.which("git") and shutil.which("bash")), reason="needs git and bash")


@pytest.fixture
def git_env(tmp_path):
    return {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }


def run_script(script, cwd, env):
    path = cwd / "git-hired.sh"
    path.write_text(script)
    return subprocess.run(["bash", str(path)], cwd=cwd, env=env, capture_output=True, text=True)


@pytest.mark.parametrize("inside_repo", [False, True])
def test_script_creates_and_pushes_history(tmp_path, git_env, inside_repo):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True, env=git_env)
    work = tmp_path / "work"
    work.mkdir()
    if inside_repo:  # the script works even when run from inside another repository
        subprocess.run(["git", "init", "--quiet", str(work)], check=True, env=git_env)

    matrix = [[1, 3], [0, 2], [2, 0], [0, 0], [4, 0], [0, 0], [1, 0]]
    multiplier = 30  # enough commits to exercise the progress output
    result = run_script(build_script(matrix, date(2024, 2, 25), "fake", str(remote), multiplier), work, git_env)
    assert result.returncode == 0, result.stderr
    assert "100% complete" in result.stdout

    log = subprocess.run(
        ["git", "log", "main", "--format=%ad", "--date=short"],
        cwd=remote,
        env=git_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    expected = {
        str(date.fromordinal(date(2024, 2, 25).toordinal() + offset)): count
        for offset, count in enumerate(values_in_date_order(matrix, multiplier))
        if count
    }
    assert Counter(log) == expected


def test_script_refuses_to_overwrite_existing_directory(tmp_path, git_env):
    (tmp_path / "fake").mkdir()
    result = run_script(build_script([[1]] * 7, date(2024, 1, 1), "fake", "unused"), tmp_path, git_env)
    assert result.returncode == 1
    assert "already exists" in result.stderr
