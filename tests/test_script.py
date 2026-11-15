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


def test_script_creates_and_pushes_history(tmp_path, git_env):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True, env=git_env)
    work = tmp_path / "work"
    work.mkdir()

    matrix = [[1, 3], [0, 2], [2, 0], [0, 0], [4, 0], [0, 0], [1, 0]]
    multiplier = 30  # enough commits to exercise the progress output
    result = run_script(build_script(matrix, date(2024, 2, 25), str(remote), multiplier), work, git_env)
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


def test_script_can_rerun_and_leaves_nothing_behind(tmp_path, git_env):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True, env=git_env)
    work = tmp_path / "work"
    work.mkdir()
    script = build_script([[1]] * 7, date(2024, 1, 7), str(remote))
    for _ in range(2):
        result = run_script(script, work, git_env)
        assert result.returncode == 0, result.stderr
        assert [p.name for p in work.iterdir()] == ["git-hired.sh"]


@pytest.mark.parametrize("branch", ["main", "master"])
def test_script_merges_into_existing_default_branch(tmp_path, git_env, branch):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", "-b", branch, str(remote)], check=True, env=git_env)
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "--quiet", "-b", branch, str(seed)], check=True, env=git_env)
    (seed / "README.md").write_text("existing\n")
    for args in (["add", "README.md"], ["commit", "-qm", "existing"], ["push", "-q", str(remote), branch]):
        subprocess.run(["git", *args], cwd=seed, check=True, env=git_env)

    result = run_script(build_script([[1]] * 7, date(2024, 1, 7), str(remote)), tmp_path, git_env)
    assert result.returncode == 0, result.stderr

    def git(*args):
        return subprocess.run(["git", *args], cwd=remote, env=git_env, capture_output=True, text=True).stdout

    assert git("for-each-ref", "--format=%(refname:short)", "refs/heads").split() == [branch]
    assert "existing" in git("log", branch, "--format=%s")
    assert git("log", branch, "--format=%s").count("git-hired") == 7
    assert git("show", f"{branch}:README.md") == "existing\n"
