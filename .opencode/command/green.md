---
description: Generate batches of meaningful commits for the GitHub contribution chart. Splits work into conventional commits, finds low-hanging refactors/tests/docs, and verifies email matches your GitHub account.
---

Load the green-commits skill and follow its workflow:

1. Verify `git config user.email` matches the GitHub account
2. Check `git status` for uncommitted work
3. Split into granular conventional commits (one file/logical change per commit)
4. Scan for Tier 2 wins (unused imports, missing docs, refactors)
5. Run `pytest -x -q` and `ruff check .` after each commit
6. Push to master

$ARGUMENTS
