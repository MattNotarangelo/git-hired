#!/usr/bin/env python
#
# Copyright (c) 2021 by Matthew Notarangelo (@MattNotarangelo)
# Developed from Gitfiti - 2013 Eric Romano (@gelstudios)
# released under The MIT license (MIT) http://opensource.org/licenses/MIT

import itertools
import math
import os
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import numpy as np


def request_user_input(prompt="> "):
    """Request input from the user and return what has been entered."""
    return input(prompt)


def generate_random_matrix(start_date, end_date):
    """Takes start and end dates to return numpy matrix of randint [0,5]"""
    days_diff = (end_date - start_date).days

    weeks = days_diff
    to_subtract_from_matrix = 0

    while weeks % 7 != 0:
        to_subtract_from_matrix += 1
        weeks += 1

    weeks = int(weeks / 7)

    random = np.random.randint(0, 5, (7, weeks))

    for i in range(to_subtract_from_matrix):
        random[-1 - i][-1] = 0

    return random


def retrieve_contributions_calendar(username, base_url):
    """retrieves the GitHub commit calendar data for a username"""

    base_url = base_url + "users/" + username

    try:
        url = base_url + "/contributions"
        page = urlopen(url)
    except (HTTPError, URLError) as e:
        print("There was a problem fetching data from {0}".format(base_url))
        print(e)
        raise SystemExit

    return page.read().decode("utf-8")


def find_max_daily_commits(contributions_calendar):
    """finds the highest number of commits in one day"""
    daily_counts = parse_contributions_calendar(contributions_calendar)
    return max(daily_counts)


def parse_contributions_calendar(contributions_calendar):
    """Yield daily counts extracted from the contributions SVG."""
    for line in contributions_calendar.splitlines():
        for day in line.split():
            if "data-count=" in day:
                commit = day.split("=")[1]
                commit = commit.strip('"')
                yield int(commit)


def calculate_multiplier(max_commits):
    """calculates a multiplier to scale GitHub colors to commit history"""
    m = max_commits / 4.0

    if not m:
        return 1

    return math.ceil(m)


def get_start_date():
    """returns start datetime object from user input"""
    year = int(request_user_input("Start year: "))
    month = int(request_user_input("Start month: "))
    day = int(request_user_input("Start day: "))

    return datetime(year, month, day, 12)


def get_end_date():
    """returns end datetime object from user input"""
    year = int(request_user_input("End year: "))
    month = int(request_user_input("End month: "))
    day = int(request_user_input("End day: "))

    return datetime(year, month, day + 1, 12)


def generate_next_dates(start_date):
    """generator that returns the next date, requires a datetime object as
    input. The offset is in weeks"""
    start = 0
    for i in itertools.count(start):
        yield start_date + timedelta(i)


def generate_values_in_date_order(image, multiplier=1):
    height = 7
    width = len(image[0])

    for w in range(width):
        for h in range(height):
            try:
                yield image[h][w] * multiplier
            except:
                yield 0


def commit(commitdate):

    template = (
        """GIT_AUTHOR_DATE={0} GIT_COMMITTER_DATE={1} """
        """git commit --allow-empty -m "gitfiti" > /dev/null\n"""
    )

    return template.format(commitdate.isoformat(), commitdate.isoformat())


def fake_it(image, start_date, username, repo, git_url, multiplier=1):
    template = (
        "#!/usr/bin/env bash\n"
        "REPO={0}\n"
        "git init $REPO\n"
        "cd $REPO\n"
        "touch README.md\n"
        "git add README.md\n"
        "touch gitfiti\n"
        "git add gitfiti\n"
        "{1}\n"
        "git branch -M main\n"
        "git remote add origin {2}:{3}/$REPO.git\n"
        "git pull origin main\n"
        "git push -u origin main\n"
    )

    strings = []
    for value, date in zip(
        generate_values_in_date_order(image, multiplier),
        generate_next_dates(start_date),
    ):
        for _ in range(value):
            strings.append(commit(date))

    return template.format(repo, "".join(strings), git_url, username)


def save(output, filename):
    """Saves the list to a given filename"""
    with open(filename, "w") as f:
        f.write(output)
    os.chmod(filename, 0o755)  # add execute permissions


def main():

    username = request_user_input("Enter your GitHub username: ")

    git_base = "https://github.com/"

    contributions_calendar = retrieve_contributions_calendar(username, git_base)

    max_daily_commits = find_max_daily_commits(contributions_calendar)

    m = calculate_multiplier(max_daily_commits)

    repo = request_user_input("Enter the name of the repository to use by gitfiti: ")

    print(
        (
            "By default gitfiti.py matches the darkest pixel to the highest\n"
            "number of commits found in your GitHub commit/activity calendar,\n"
            "\n"
            "Currently this is: {0} commits\n"
            "\n"
            'Enter the word "gitfiti" to exceed your max\n'
            "(this option generates WAY more commits)\n"
            "Any other input will cause the default matching behavior"
        ).format(max_daily_commits)
    )
    match = request_user_input()

    match = m if (match == "gitfiti") else 1

    start_date = get_start_date()
    end_date = get_end_date()

    image = generate_random_matrix(start_date, end_date)

    fake_it_multiplier = m * match

    git_url = "git@github.com"

    output = fake_it(image, start_date, username, repo, git_url, fake_it_multiplier)

    output_filename = "gitfiti.sh"
    save(output, output_filename)
    print(f"{output_filename} saved.")
    print(f"Create a new(!) repo named {repo} at {git_base} and run the script")


if __name__ == "__main__":
    main()
