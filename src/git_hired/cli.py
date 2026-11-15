"""Command-line interface for git-hired."""

import argparse
import random
import shutil
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import TypeVar

from git_hired import __version__
from git_hired.core import (
    LEVELS,
    build_script,
    calculate_multiplier,
    default_remote_url,
    format_matrix,
    generate_random_matrix,
    validate_repo,
    validate_username,
)
from git_hired.github import CalendarError, fetch_calendar, max_daily_contributions

T = TypeVar("T")


class CliError(Exception):
    """A user-facing error that should end the program with a message."""


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"invalid date {value!r}, expected YYYY-MM-DD") from None


def parse_positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"invalid number {value!r}") from None
    if number <= 0:
        raise ValueError(f"expected a number greater than 0, got {number}")
    return number


def _arg_type(convert: Callable[[str], T]) -> Callable[[str], T]:
    """Adapt a converter that raises ValueError into an argparse type with a readable message."""

    def wrapper(value: str) -> T:
        try:
            return convert(value)
        except ValueError as e:
            raise argparse.ArgumentTypeError(str(e)) from None

    return wrapper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-hired",
        description=(
            "Generate a shell script that fills your GitHub contribution graph between two dates. "
            "Any option not given on the command line is prompted for."
        ),
    )
    parser.add_argument("-u", "--username", type=_arg_type(validate_username), help="your GitHub username")
    parser.add_argument("-r", "--repo", type=_arg_type(validate_repo), help="name of the repository to create")
    parser.add_argument("-s", "--start", type=_arg_type(parse_date), help="first day, YYYY-MM-DD")
    parser.add_argument("-e", "--end", type=_arg_type(parse_date), help="last day (inclusive), YYYY-MM-DD")
    parser.add_argument(
        "-m",
        "--multiplier",
        type=_arg_type(parse_positive_int),
        help="commits per shade level (default: derived from your busiest day on GitHub)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("git-hired.sh"),
        help="where to write the script (default: %(default)s)",
    )
    parser.add_argument("--remote-url", help="git remote to push to (default: git@github.com:USERNAME/REPO.git)")
    parser.add_argument("--seed", type=int, help="random seed, for a reproducible pattern")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def print_section() -> None:
    """Print a horizontal divider the width of the terminal."""
    print("-" * (shutil.get_terminal_size().columns - 1))


def prompt(label: str, convert: Callable[[str], T]) -> T:
    """Ask for a value until ``convert`` accepts it."""
    if not sys.stdin.isatty():
        raise CliError(f"{label} is required; pass it as an option or run interactively")
    while True:
        raw = input(f"{label}: ").strip()
        try:
            return convert(raw)
        except ValueError as e:
            print(f"  {e}", file=sys.stderr)


def prompt_multiplier() -> int | None:
    """Ask for commits per shade level; blank (or non-interactive) means derive it from GitHub."""
    if not sys.stdin.isatty():
        return None
    print("By default the darkest shade matches your busiest day on GitHub.")
    return prompt("Commits per shade level (blank for default)", lambda raw: parse_positive_int(raw) if raw else None)


def run(args: argparse.Namespace) -> None:
    print_section()
    username = args.username or prompt("GitHub username", validate_username)
    repo = args.repo or prompt("Repository name", validate_repo)
    start = args.start or prompt("Start date (YYYY-MM-DD)", parse_date)
    end = args.end or prompt("End date (YYYY-MM-DD)", parse_date)
    if end < start:
        raise CliError("end date must not be before start date")

    multiplier = args.multiplier or prompt_multiplier()
    if multiplier is None:
        try:
            multiplier = calculate_multiplier(max_daily_contributions(fetch_calendar(username)))
        except CalendarError as e:
            raise CliError(f"{e} (use --multiplier to skip this lookup)") from e

    matrix = generate_random_matrix(start, end, random.Random(args.seed))
    remote_url = args.remote_url or default_remote_url(username, repo)
    script = build_script(matrix, start, repo, remote_url, multiplier)
    try:
        args.output.write_text(script)
        args.output.chmod(0o755)
    except OSError as e:
        raise CliError(f"could not write {args.output}: {e}") from e

    print_section()
    print("Commits will be added as per the following matrix, where:")
    for level in range(LEVELS):
        print(f"  {level} = {level * multiplier} commits")
    print(format_matrix(matrix))
    print_section()
    print(f"Wrote {args.output.resolve()}")
    print(f"1. Create an empty repository named {repo!r} on GitHub.")
    print("2. Move the script to a folder that is not inside a git repository and run it.")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except CliError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print(file=sys.stderr)
        return 130
    return 0
