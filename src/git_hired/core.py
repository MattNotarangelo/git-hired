"""Pure logic: build a random commit matrix and the shell script that replays it."""

# Copyright (c) 2021 by Matthew Notarangelo (@MattNotarangelo)
# Developed from Gitfiti - 2013 Eric Romano (@gelstudios)
# Released under The MIT license (MIT) http://opensource.org/licenses/MIT

import random
import re
import shlex
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from math import ceil

DAYS_PER_WEEK = 7
# GitHub shades each day with one of five levels: 0 (empty) to 4 (darkest).
LEVELS = 5
# Scripts with more commits than this print progress while running.
PROGRESS_THRESHOLD = 100
# Time of day used for every generated commit.
COMMIT_TIME = time(12)

# https://github.com/shinnn/github-username-regex
_USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

Matrix = list[list[int]]


def validate_username(username: str) -> str:
    """Return the username if it is a valid GitHub username, else raise ValueError."""
    if not _USERNAME_RE.match(username):
        raise ValueError(f"invalid GitHub username: {username!r}")
    return username


def validate_repo(repo: str) -> str:
    """Return the repo name if it is a valid GitHub repository name, else raise ValueError."""
    if not _REPO_RE.match(repo) or repo in {".", ".."}:
        raise ValueError(f"invalid repository name: {repo!r}")
    return repo


def default_remote_url(username: str, repo: str) -> str:
    """Return the SSH remote URL for a GitHub repository."""
    return f"git@github.com:{username}/{repo}.git"


def grid_start(start: date) -> date:
    """Return the Sunday on or before ``start``; GitHub's graph rows run Sunday to Saturday."""
    return start - timedelta(days=(start.weekday() + 1) % DAYS_PER_WEEK)


def generate_random_matrix(start: date, end: date, rng: random.Random | None = None) -> Matrix:
    """Return a 7 x weeks matrix of shade levels laid out like GitHub's graph.

    Cell ``[row][col]`` is the day ``grid_start(start) + col * 7 + row``; cells outside start..end are 0.
    """
    if end < start:
        raise ValueError("end date must not be before start date")
    rng = rng or random.Random()
    days = (end - start).days + 1
    lead = (start - grid_start(start)).days
    weeks = ceil((lead + days) / DAYS_PER_WEEK)
    # A range of a week or less has little to show, so make sure every day gets at least one commit.
    low = 1 if days <= DAYS_PER_WEEK else 0
    matrix = [[rng.randint(low, LEVELS - 1) for _ in range(weeks)] for _ in range(DAYS_PER_WEEK)]
    for offset in range(weeks * DAYS_PER_WEEK):
        if not lead <= offset < lead + days:
            week, day = divmod(offset, DAYS_PER_WEEK)
            matrix[day][week] = 0
    return matrix


def calculate_multiplier(max_commits: int) -> int:
    """Return commits per shade level so the darkest level matches max_commits."""
    return max(1, ceil(max_commits / (LEVELS - 1)))


def values_in_date_order(matrix: Matrix, multiplier: int = 1) -> Iterator[int]:
    """Yield commit counts from the matrix, one per day, starting at the first day."""
    for col in range(len(matrix[0])):
        for row in range(len(matrix)):
            yield matrix[row][col] * multiplier


def commit_command(when: datetime) -> str:
    """Return a shell line that creates an empty commit dated ``when``."""
    stamp = shlex.quote(when.isoformat())
    return f"GIT_AUTHOR_DATE={stamp} GIT_COMMITTER_DATE={stamp} git commit --allow-empty -m git-hired > /dev/null\n"


def commit_commands(matrix: Matrix, start: date, multiplier: int = 1) -> list[str]:
    """Return one commit command per commit described by a matrix from ``generate_random_matrix(start, ...)``."""
    first = grid_start(start)
    commands = []
    for offset, count in enumerate(values_in_date_order(matrix, multiplier)):
        when = datetime.combine(first + timedelta(days=offset), COMMIT_TIME)
        commands.extend([commit_command(when)] * count)
    return commands


def with_progress(commands: list[str]) -> list[str]:
    """Interleave progress messages into long command lists."""
    total = len(commands)
    if total <= PROGRESS_THRESHOLD:
        return commands
    marks = {total * quarter // 4: quarter * 25 for quarter in range(4)}
    out = []
    for i, command in enumerate(commands):
        if i in marks:
            out.append(f'echo "{marks[i]}% complete"\n')
        out.append(command)
    out.append('echo "100% complete"\n')
    return out


def build_script(matrix: Matrix, start: date, repo: str, remote_url: str, multiplier: int = 1) -> str:
    """Return a bash script that creates ``repo`` with the matrix's commit history and pushes it."""
    commands = with_progress(commit_commands(matrix, start, multiplier))
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"REPO={shlex.quote(repo)}\n"
        'if [ -e "$REPO" ]; then\n'
        '  echo "error: $REPO already exists in $(pwd)" >&2\n'
        "  exit 1\n"
        "fi\n"
        'git init --quiet "$REPO"\n'
        'cd "$REPO"\n'
        "touch README.md git-hired\n"
        "git add README.md git-hired\n"
        f"{''.join(commands)}"
        f"git remote add origin {shlex.quote(remote_url)}\n"
        "# GitHub only counts commits on the default branch, so use the remote's (main if it is empty).\n"
        'BRANCH=$(git ls-remote --symref origin HEAD | awk \'$1 == "ref:" {sub("refs/heads/", "", $2); print $2}\')\n'
        "BRANCH=${BRANCH:-main}\n"
        'git branch -M "$BRANCH"\n'
        "# Merge anything already on the remote; fails harmlessly if the remote is empty.\n"
        'git pull --no-rebase --no-edit --allow-unrelated-histories origin "$BRANCH" || true\n'
        'git push -u origin "$BRANCH"\n'
    )


def format_matrix(matrix: Matrix) -> str:
    """Return the matrix as rows of space-separated levels."""
    return "\n".join(" ".join(str(level) for level in row) for row in matrix)
