"""
GitHub Contribution Commit Script

This script generates a shell script to simulate GitHub commit activity between two dates, matching the style of your contribution graph. It fetches your current contribution data, calculates commit density, and produces a bash script to create a new repository with randomized commit history.

Usage:
    Run this script and follow the prompts. The output will be a shell script you can execute after creating a new repository on GitHub.
"""

# Copyright (c) 2021 by Matthew Notarangelo (@MattNotarangelo)
# Developed from Gitfiti - 2013 Eric Romano (@gelstudios)
# Released under The MIT license (MIT) http://opensource.org/licenses/MIT

from datetime import datetime, timedelta
from itertools import count
from math import ceil
from os import chmod, get_terminal_size
import os
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import numpy as np


def print_section() -> None:
    """Print a horizontal section divider based on terminal width."""
    s = "-" * (get_terminal_size()[0] - 1)
    print(s)


def request_user_input(prompt: str = "> ") -> str:
    """Request input from the user and return the entered value."""
    user_input = input(prompt)
    if not user_input:
        raise SystemExit("Error: Input cannot be empty.")
    return user_input


def generate_random_matrix(start_date: datetime, end_date: datetime) -> np.ndarray:
    """Generate a random matrix of commit counts between two dates."""
    days = (end_date - start_date).days + 1
    weeks = ceil(days / 7)
    if weeks <= 1:
        random = np.random.randint(1, 5, (7, weeks))
    else:
        random = np.random.randint(0, 5, (7, weeks))
    for i in range(days % 7):
        random[-1 - i][-1] = 0
    return random


def retrieve_contributions_calendar(username: str, base_url: str) -> str:
    """Retrieve the GitHub commit calendar SVG data for a username."""
    url = f"{base_url}users/{username}/contributions"
    try:
        page = urlopen(url)
    except (HTTPError, URLError) as e:
        print(f"Error: Unable to fetch data from {url}")
        print(e)
        raise SystemExit from e
    return page.read().decode("utf-8")


def parse_contributions_calendar(contributions_calendar: str):
    """Yield daily commit counts extracted from the contributions SVG."""
    for line in contributions_calendar.splitlines():
        for day in line.split():
            if "data-level=" in day:
                commit_data = day.split("=")[1]
                commit_data = commit_data.split('"')[1].strip('"')
                yield int(commit_data)


def find_max_daily_commits(contributions_calendar: str) -> int:
    """Find the highest number of commits in a single day."""
    return max(parse_contributions_calendar(contributions_calendar))


def calculate_multiplier(max_commits: int) -> int:
    """Calculate a multiplier to scale commit counts to GitHub color levels."""
    m = max_commits / 4.0
    if not m:
        return 1
    return ceil(m)


def get_dates() -> tuple[datetime, datetime]:
    """Prompt the user for start and end dates and return them as datetime objects."""
    try:
        year = int(request_user_input("Start year: "))
        month = int(request_user_input("Start month: "))
        day = int(request_user_input("Start day: "))
        start = datetime(year, month, day, 12)
        year = int(request_user_input("End year: "))
        month = int(request_user_input("End month: "))
        day = int(request_user_input("End day: "))
        end = datetime(year, month, day + 1, 12)
    except ValueError as e:
        raise SystemExit("Error: Please enter valid integer values for dates.") from e
    if start > end:
        raise SystemExit("Error: End date must be after start date.")
    return (start, end)


def generate_next_dates(start_date: datetime):
    """Generator that yields the next date, starting from start_date."""
    for i in count(0):
        yield start_date + timedelta(days=i)


def generate_values_in_date_order(matrix: np.ndarray, multiplier: int = 1):
    """Yield commit counts in date order from the random matrix."""
    height = 7
    width = len(matrix[0])
    for w in range(width):
        for h in range(height):
            try:
                yield matrix[h][w] * multiplier
            except IndexError:
                yield 0


def commit(commitdate: datetime) -> str:
    """Return a formatted git commit command for a given date."""
    template = "GIT_AUTHOR_DATE={0} GIT_COMMITTER_DATE={1} " 'git commit --allow-empty -m "git-hired" > /dev/null\n'
    return template.format(commitdate.isoformat(), commitdate.isoformat())


def fake_it(
    matrix: np.ndarray,
    start_date: datetime,
    username: str,
    repo: str,
    git_url: str,
    multiplier: int = 1,
) -> str:
    """Generate a shell script to create a repository and simulate commit history."""
    template = (
        "#!/usr/bin/env bash\n"
        "REPO={0}\n"
        "git init $REPO\n"
        "cd $REPO\n"
        "touch README.md\n"
        "git add README.md\n"
        "touch git-hired\n"
        "git add git-hired\n"
        "{1}\n"
        "git branch -M main\n"
        "git remote add origin {2}:{3}/$REPO.git\n"
        "git pull origin main\n"
        "git push -u origin main\n"
    )
    commit_cmds = []
    for value, date in zip(
        generate_values_in_date_order(matrix, multiplier),
        generate_next_dates(start_date),
    ):
        for _ in range(value):
            commit_cmds.append(commit(date))

    if len(commit_cmds) > 100:
        commit_cmds.insert(0, 'echo "0% complete"\n')
        commit_cmds.insert(1 * len(commit_cmds) // 4, 'echo "25% complete"\n')
        commit_cmds.insert(2 * len(commit_cmds) // 4, 'echo "50% complete"\n')
        commit_cmds.insert(3 * len(commit_cmds) // 4, 'echo "75% complete"\n')
        commit_cmds.insert(4 * len(commit_cmds) // 4, 'echo "100% complete"\n')
    return template.format(repo, "".join(commit_cmds), git_url, username)


def save(output: str, filename: str) -> None:
    """Save the output string to a file and make it executable."""
    with open(filename, "w") as f:
        f.write(output)
    chmod(filename, 0o755)


def main() -> None:
    print_section()
    username = request_user_input("Enter your GitHub username: ")
    git_base = "https://github.com/"
    contributions_calendar = retrieve_contributions_calendar(username, git_base)
    max_daily_commits = find_max_daily_commits(contributions_calendar)
    m = calculate_multiplier(max_daily_commits)
    repo = request_user_input("Enter the name of the repository to use by git-hired: ")
    start_date, end_date = get_dates()
    matrix = generate_random_matrix(start_date, end_date)
    fake_it_multiplier = m
    print_section()
    print(
        "By default, the script matches the darkest pixel to the highest "
        "number of commits found in your GitHub commit activity. "
        "Enter how many commits the lightest pixel should have or leave blank for default."
    )
    user_input = input("")
    if user_input:
        try:
            if int(user_input) <= 0:
                raise SystemExit("Error: Please enter an integer greater than 0.")
        except Exception:
            raise SystemExit("Error: Please enter a valid integer greater than 0.")
        fake_it_multiplier = m = int(user_input)
    print("Commits will be added as per the following matrix, where:")
    for i in range(5):
        print(f"'{i}' = {i*m} commits")
    print(matrix)
    print_section()
    git_url = "git@github.com"
    output = fake_it(matrix, start_date, username, repo, git_url, fake_it_multiplier)
    output_filename = "git-hired.sh"
    save(output, output_filename)
    print(f"{output_filename} saved to pwd: {os.getcwd()}.")
    print(f"Create a new repository named {repo} at {git_base}, then move the script to your root folder and run it.")


if __name__ == "__main__":
    main()
