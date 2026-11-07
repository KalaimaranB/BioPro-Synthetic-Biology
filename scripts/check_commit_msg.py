"""Reject commit messages that do not follow Conventional Commits.

Runs as a pre-commit ``commit-msg`` hook, which receives the path to the file
holding the prepared commit message as its first argument.

CONTRIBUTING section 2 requires every commit subject to start with a
Conventional Commits type, and the ``enforce-workflow`` CI job checks the same
thing on PR titles. Catching it locally costs a second; catching it in CI costs
a push and a round trip.
"""

# ruff: noqa: T201
# This hook talks to the developer on stderr at commit time. It is a standalone
# script, never imported by the plugin, so it is outside the msgpack IPC channel
# that makes stray prints dangerous elsewhere (see ui_daemon.py).

from __future__ import annotations

import re
import sys

PATTERN = re.compile(
    r"^(feat|fix|chore|docs|refactor|test|perf|build|ci|style|revert)"
    r"(\([a-z0-9,._/-]+\))?!?: .+"
)

TYPES = "feat fix chore docs refactor test perf build ci style revert"

# argv is [script_path, commit_msg_file].
EXPECTED_ARGC = 2

# Git's own generated subjects, which no human authored.
EXEMPT = ("Merge ", "Revert ", "fixup! ", "squash! ")


def main(argv: list[str]) -> int:
    """Validate the commit subject in the file named by ``argv[1]``.

    Args:
        argv: Process arguments, as passed by pre-commit.

    Returns:
        0 when the subject is acceptable, 1 otherwise.
    """
    if len(argv) < EXPECTED_ARGC:
        print("check_commit_msg.py: expected the commit-message file path", file=sys.stderr)
        return 1

    with open(argv[1], encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    subject = next((ln for ln in lines if ln.strip() and not ln.startswith("#")), "")

    if subject.startswith(EXEMPT):
        return 0

    if subject != subject.strip():
        print(
            f"\n  Commit subject has leading or trailing whitespace: {subject!r}\n",
            file=sys.stderr,
        )
        return 1

    if not PATTERN.match(subject):
        print(
            "\n  Commit subject must follow Conventional Commits.\n"
            f"    got:      {subject}\n"
            "    expected: <type>(<optional scope>): <description>\n"
            f"    types:    {TYPES}\n\n"
            "  Examples:\n"
            "    feat(primer): add rubric screening and NN thermodynamics\n"
            "    fix(primer): exclude the overhang from GC content\n",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
