# git-hired

Boost your chances of getting hired by faking your GitHub contribution graph!

## Example

**Before**:
![image](https://user-images.githubusercontent.com/81910488/131299688-afb378a6-9297-4a65-98c2-d217e9e8e455.png)

**After**:
![image](https://user-images.githubusercontent.com/81910488/131299599-99170c31-a18e-4a61-8d14-0b5b60408853.png)

## Requirements

- [uv](https://github.com/astral-sh/uv) (or any Python 3.10+ with `pip`)
- `git` and `bash`, plus an SSH key added to GitHub

## Usage

1.  Create an **empty** GitHub repository (no README, licence or `.gitignore`).
2.  Generate the script, answering the prompts:

    ```sh
    uvx --from git+https://github.com/MattNotarangelo/git-hired git-hired
    ```

    Or pass everything up front to skip the prompts:

    ```sh
    uvx --from git+https://github.com/MattNotarangelo/git-hired git-hired \
        --username octocat --repo my-repo --start 2025-01-01 --end 2025-12-31
    ```

3.  Run `./git-hired.sh` from any folder. It builds the commits in a temporary folder and pushes them (this may take a while). Rerunning it after a successful push adds a second set of commits.

### Options

| Option | Description |
| --- | --- |
| `-u, --username` | Your GitHub username |
| `-r, --repo` | Name of the repository to create |
| `-s, --start` / `-e, --end` | First and last day (inclusive), `YYYY-MM-DD` |
| `-m, --multiplier` | Commits per shade level. Defaults to matching the darkest shade to your busiest day on GitHub (which requires fetching your public contribution calendar) |
| `-o, --output` | Where to write the script (default `git-hired.sh`) |
| `--remote-url` | Remote to push to, e.g. an HTTPS or GitHub Enterprise URL (default `git@github.com:USERNAME/REPO.git`) |
| `--seed` | Random seed, for a reproducible pattern |

Run `git-hired --help` for the full list.

## Removal

Just delete the repository with all the commits.

## Development

```sh
uv sync
uv run pytest             # tests + coverage
uv run ruff check .       # lint
uv run ruff format .      # format
uv run mypy               # type check
uv run git-hired --help   # run from source
```

CI runs all of the above on Linux and macOS for Python 3.10 to 3.14.

## Notes

This project was inspired by [gitfiti](https://github.com/gelstudios/gitfiti)
