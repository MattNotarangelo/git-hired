# git-hired: one-command run

* **Author:** Matt Notarangelo
* **Date:** 2026-11-15

## Overview

Today git-hired is two programs. The Python tool asks questions and writes a bash script, then the user runs that
script to make the commits and push them. This change makes it one command. By default git-hired checks the remote
and the commit email, shows what it is about to do, asks for confirmation, then makes and pushes the commits itself.
`--script` keeps the old behaviour of writing the script to a file without running it.

The target user is one person running the tool now and then on their own Mac or Linux machine. A typical run covers
one year at a few commits a day: about 1,100 commits, about 30 seconds on a Mac (measured: 742 commits in 18.4 s,
about 25 ms per commit).

## Analysis

Six reviewers (design, codebase details, zoom-out, comprehension, implementation readiness, structure) looked at the
concept and the current code. Their findings, most important first:

1. **The current script merges instead of adding on top.** It builds an unrelated history, then runs
   `git pull --allow-unrelated-histories ... || true` and pushes (`core.py`). This never rewrites the remote, but:
   - it adds a merge commit dated today, which appears on the graph and is not in the preview total;
   - `|| true` hides real failures (auth, network, conflicts), so the user learns of them only when the push is
     rejected about 30 seconds later, with a misleading error.

   The fix: fetch the remote branch first (`git fetch --depth=1`), start from it (`git checkout -B BRANCH FETCH_HEAD`),
   add the empty commits, then run a plain `git push`. The `touch README.md git-hired` step goes too.
   **Checked:** against local bare repos, two reruns on a `master` with 50 existing commits each added commits on top,
   with no merge commits; the old tip stayed in the history and `git fsck --strict` passed. An empty remote also
   worked.

2. **The email shown could differ from the email used.** The commits are made inside a temp folder, so the user's
   per-repo git config and `includeIf` rules don't apply there. Running `git config user.email` from the current
   folder could show the work email while the commits use the personal one. GitHub would then count nothing, and
   nothing would say so. If no email is set at all, the first commit fails after the user has already confirmed.
   - Fix: work out the identity with `git var GIT_AUTHOR_IDENT` from outside any repo, which follows the same rules
     as the real commits. Stop before the confirm prompt if it is missing. Pass the resolved identity to the script,
     so what is shown is what is used.

3. **Runs without a terminal would push with no confirmation.** A CI job or script that passes every flag used to
   write a file. Now it would push commits that can only be undone by deleting the repo.
   - Fix: add `-y/--yes`. Without a terminal and without `--yes`, exit with an error naming the flag. The
     interactive default answer is No.

4. **"Reachable" and "empty" need exact meanings.** A single `git ls-remote --symref URL HEAD` answers both:
   - a non-zero exit means missing, no access or unreachable;
   - empty output means an empty remote;
   - otherwise the output names the default branch.

   Edge cases:
   - GitHub gives the same "Repository not found" error for a missing repo and for one you can't access, so one
     message must cover both and say what to do (create the repo at github.com/new, check the name, run
     `ssh -T git@github.com`).
   - The first SSH connection may ask to trust the host, and some keys ask for a passphrase, so the check must be
     allowed to prompt in the terminal.
   - A read check does not prove you can push.

5. **The default repo name `git-hired` could be a fork of this tool.** Commits in forks don't count on GitHub. The
   confirm screen must show the full remote URL and mention forks.

6. **Reruns raise the default multiplier.** Run 2 works out its default from a graph that already includes run 1's
   fake busiest day, so every rerun pushes more than the last. Warn about this when the remote isn't empty.

7. **Commit signing and hooks.** A user with `commit.gpgsign=true` could face 1,100 signing prompts, and a global
   hook runs once per commit. Add `--no-verify --no-gpg-sign` to the commit command; it costs nothing for empty
   commits.

8. **No upper limit on commit count.** A user whose busiest day was 300 contributions gets about 100,000 commits,
   roughly 40 minutes. The estimate on the confirm screen should make this obvious.

9. **How the script is run matters.** Piping it into `bash` lets any program that reads input (a credential helper,
   a hook) swallow the rest of the script. `bash -c "<script>"` hits Linux's 128 KB per-argument limit at about
   1,100 commits. Write the script to a temp file and run `bash FILE` instead, as the tests already do.

10. **The existing CLI tests would push for real.** They call `main()` expecting only a file to be written. All git
    and bash calls must go through one small module that tests replace with fakes. The current assertions move to
    `--script`.

11. **With `--script`, the checks go stale.** The script may run later or on another machine, so in `--script` mode
    the checks only warn. The script still detects the branch itself when it runs, and prints the identity it uses.

12. **Order of steps.** Today the file is written before the preview is shown. The new order:
    1. Collect inputs.
    2. Check the remote.
    3. Work out the email.
    4. Fetch the calendar for the default multiplier.
    5. Build the grid.
    6. Show the summary.
    7. Confirm.
    8. Run, or write the file.

    Nothing changes on disk or on GitHub before step 7.

13. **Errors and Ctrl-C.**
    - Each failure names its step: check, commits or push.
    - A rejected push says "the remote changed since the check; run again". There is no automatic retry and no force
      push.
    - On Ctrl-C, the parent waits for bash so the script's cleanup runs, then exits with code 130.

14. **Smaller points.**
    - "Last 365 days" means today minus 364 days up to today. End dates in the future are rejected.
    - The README, `--help` text and closing message need rewriting, and the README should stop requiring an empty
      repo.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * One command that checks, previews, confirms, then makes and pushes the commits.
  * `--script [PATH]` writes exactly the same script and does not run it.
  * The only required input is the username. The repo defaults to `git-hired` and the dates to the last 365 days.
    The confirm screen shows these values; there are no extra prompts for them.
  * One `ls-remote` check that tells reachable, empty, and the default branch apart.
  * The author identity is worked out, shown and actually used; the run stops if there is none.
  * The confirm screen shows: remote URL, branch, empty or existing state, email and caveats, grid, total, estimate.
  * `--yes` for runs without a terminal; without it, those runs fail.
  * History only grows: fetch, commit on top, plain push. No force push, no merge commits.
  * Failing or interrupting at any point leaves the remote unchanged.
* **Out-of-Scope Non-Goals:**
  * `git fast-import` (speed is within the one-minute target).
  * Checking the email against the GitHub account.
  * Creating the GitHub repo through the API or `gh`.
  * Signed commits. Windows.
  * Automatic retry or rebase after a rejected push.
  * Replacing or removing earlier git-hired commits on rerun (reruns only add).
  * A separate dry-run flag (`--script` covers it).

## Alternatives Weighed

* **Run git from Python, with `--script` as a second implementation.** Rejected by all six reviewers. The fetch,
  commit and push steps would exist twice, in Python and in bash, and could drift apart. Its benefit (clean errors)
  only matters for the checks, which are read-only Python calls either way.
* **Pipe the script into `bash`.** Rejected: a program reading input mid-script swallows the rest of it.
* **`bash -c "<script>"`.** Rejected: hits the 128 KB argument limit on Linux at typical sizes.
* **Keep `git pull --allow-unrelated-histories || true`.** Rejected: an uncounted merge commit dated today, and
  hidden failures.
* **Replace earlier git-hired commits on rerun (force push).** Rejected by the user: reruns must only add commits.
* **`git fast-import`.** Rejected: the measured speed meets the one-minute target.
* **Drop `--script`.** Rejected by the user; nobody is known to use it, but it stays.
* **No time estimate.** Considered, because it will be wrong on some machines. Kept as one rough line (commits ×
  25 ms, plus push time), because it is the cheapest warning for very large runs.
* **Prompt for repo and dates with defaults.** Rejected: the confirm screen already shows them, and fewer prompts
  is the point.
* **Keep `-o` as an alias for `--script PATH`.** Rejected by the user: one option is enough.
* **Make `--repo` together with `--remote-url` an error.** Rejected by the user: `--remote-url` wins.
* **Separate checks for "reachable" and "empty".** Rejected: one `ls-remote` answers both.
* **Commit through the GitHub API, or push to a side branch.** Rejected: needs a token, or the commits don't count.

## Key Decisions & Staging for Next Steps

1. **One source of truth.** `build_script` remains the only code that changes anything. By default git-hired writes
   it to a temp file and runs `bash FILE` in the user's terminal. `--script PATH` writes the same text and stops.
   Python itself only runs read-only checks (`git ls-remote`, `git var`).
2. **New git sequence in the script:**
   - `remote add` and branch detection first.
   - Shallow fetch and `checkout -B` if the branch exists.
   - Empty commits with `--no-verify --no-gpg-sign`.
   - `git push origin HEAD:BRANCH`.
   - No merge, no `|| true`, no placeholder files.
3. **Identity:** `git var GIT_AUTHOR_IDENT` outside any repo. Stop if it is empty. Pass it to the script as
   environment variables. Show the caveats: the email must be verified on GitHub, forks don't count, and private
   repos need "include private contributions" switched on.
4. **Checks:** required by default, warning-only with `--script`. One error message per failure.
5. **Options:**
   - Add `--script [PATH]` and `-y/--yes`.
   - Keep `--remote-url` and `--seed`.
   - Repo defaults to `git-hired`; dates default to today−364 through today, and end dates in the future are
     rejected.
   - **Decided:** remove `-o` (a breaking change, recorded in the README); `--script PATH` replaces it.
   - **Decided:** if both `--repo` and `--remote-url` are given, `--remote-url` wins, and the confirm screen shows
     the URL that will be used.
6. **Confirm screen:**
   - It shows:
     - the remote URL;
     - the branch;
     - "empty, will create BRANCH" or "adds N on top of BRANCH";
     - the email and its caveats;
     - the grid;
     - the total;
     - the estimate;
     - the multiplier warning on reruns;
     - "the only undo is deleting the repo".
   - The default answer is No.
7. **Layout:**
   - `core.py` stays pure. It gains `ls-remote` parsing, default dates (with `today` as a parameter) and the estimate.
   - A new small module holds the git and bash calls: check remote, get identity, run script.
   - `cli.py` ties them together.
   - Tests fake that module, and add end-to-end runs against local bare repos for:
     - an empty remote;
     - an existing `master`;
     - a rerun;
     - a missing remote;
     - a remote that changed mid-run.
8. **Ctrl-C:** the parent waits for bash so cleanup runs, then exits with code 130.
9. **Docs:** rewrite the README for the new flow, the rerun behaviour, the option changes and the email caveats.

**Still to verify while implementing:**
- what GitHub's `ls-remote` returns for an empty repo;
- Ctrl-C timing with `subprocess`;
- the Linux argument limit, which only matters if anything ever uses `bash -c`.
