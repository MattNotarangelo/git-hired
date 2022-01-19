""" Program to add random github commit data between two dates """
# Copyright (c) 2021 by Matthew Notarangelo (@MattNotarangelo)
# Developed from Gitfiti - 2013 Eric Romano (@gelstudios)
# released under The MIT license (MIT) http://opensource.org/licenses/MIT

from datetime import datetime, timedelta
from itertools import count
from math import ceil
from os import chmod, get_terminal_size
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import numpy as np


def print_section():
    s = "-" * (get_terminal_size()[0] - 1)
    print(s)
    return


def request_user_input(prompt="> "):
    """Request input from the user and return what has been entered."""
    user_input = input(prompt)
    if not user_input:
        raise SystemExit("ValueError: not a valid input")

    return user_input


def generate_random_matrix(start_date, end_date):
    """Takes start and end dates to return numpy matrix of randint [0,5]"""
    weeks = (end_date - start_date).days  # gets days between two dates
    to_subtract_from_matrix = 0

    while weeks % 7 != 0:  # round up to whole number of weeks
        to_subtract_from_matrix += 1  # counts excess days to remove later
        weeks += 1

    weeks = int(weeks / 7)  # convert to weeks
    if weeks <= 1:
        random = np.random.randint(1, 5, (7, weeks))  # force non-zero values if <= 1 week
    else:
        random = np.random.randint(0, 5, (7, weeks))

    for i in range(to_subtract_from_matrix):
        random[-1 - i][-1] = 0  # make additional days = 0

    return random


def retrieve_contributions_calendar(username, base_url):
    """retrieves the GitHub commit calendar data for a username"""

    base_url = base_url + "users/" + username

    try:
        url = base_url + "/contributions"
        page = urlopen(url)
    except (HTTPError, URLError) as e:
        print(f"There was a problem fetching data from {base_url}")
        print(e)
        raise SystemExit from e

    return page.read().decode("utf-8")


def parse_contributions_calendar(contributions_calendar):
    """Yield daily counts extracted from the contributions SVG."""
    for line in contributions_calendar.splitlines():
        for day in line.split():
            if "data-count=" in day:
                commit_data = day.split("=")[1]
                commit_data = commit_data.strip('"')
                yield int(commit_data)


def find_max_daily_commits(contributions_calendar):
    """finds the highest number of commits in one day"""
    daily_counts = parse_contributions_calendar(contributions_calendar)

    return max(daily_counts)


def calculate_multiplier(max_commits):
    """calculates a multiplier to scale GitHub colors to commit history"""
    m = max_commits / 4.0

    if not m:
        return 1

    return ceil(m)


def get_dates():
    """returns datetime objects from user input"""
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
        raise SystemExit("ValueError: Not a valid input") from e

    if start > end:
        raise SystemExit("ValueError: End date must be after start date")

    return (start, end)


def generate_next_dates(start_date):
    """generator that returns the next date, requires a datetime object as
    input. The offset is in weeks"""
    start = 0

    for i in count(start):
        yield start_date + timedelta(i)


def generate_values_in_date_order(matrix, multiplier=1):
    """generator iterates through random matrix in order and returns number of
    commits required"""
    height = 7
    width = len(matrix[0])

    for w in range(width):
        for h in range(height):
            try:
                yield matrix[h][w] * multiplier
            except IndexError:
                yield 0


def commit(commitdate):
    """returns commit commands"""
    template = ("""GIT_AUTHOR_DATE={0} GIT_COMMITTER_DATE={1} """
                """git commit --allow-empty -m "git-hired" > /dev/null\n""")

    return template.format(commitdate.isoformat(), commitdate.isoformat())


def fake_it(matrix, start_date, username, repo, git_url, multiplier=1):
    """return completed shell script"""
    template = ("#!/usr/bin/env bash\n"
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
                "git push -u origin main\n")

    strings = []
    for value, date in zip(
            generate_values_in_date_order(matrix, multiplier),
            generate_next_dates(start_date),
    ):
        for _ in range(value):
            strings.append(commit(date))

    return template.format(repo, "".join(strings), git_url, username)


def save(output, filename):
    """Saves the list to a given filename"""
    with open(filename, "w") as f:
        f.write(output)
    chmod(filename, 0o755)  # add execute permissions


def main():

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

    print("By default git-hired.py matches the darkest pixel to the highest "
          "number of commits found in your GitHub commit activity. Enter "
          "how many commits the lightest pixel should have or leave blank "
          "for default")

    user_input = input()

    if user_input:
        try:
            if int(user_input) <= 0:
                raise SystemExit("ValueError: need to enter an int > 0")
        except:
            raise SystemExit("ValueError: need to enter an int > 0")

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
    print(f"{output_filename} saved.")
    print(f"Create a new(!!!) repo named {repo} at {git_base}, then move the script to your root folder and run.")


if __name__ == "__main__":
    main()
