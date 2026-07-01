---
name: green-commits
description: >
  Generate batches of meaningful commits that count toward GitHub's contribution
  chart. Splits work into conventional commits, finds low-hanging refactors/tests/docs,
  and verifies the email matches the GitHub account. Use when the user says
  "/green", "more green", "commits for chart", "green commit", or wants to stack
  contribution squares.
---

# Green Commits — Contribution Chart Optimizer

## Ground Rules — These Make Commits Count

GitHub counts a commit as a contribution ONLY when ALL of these are true:

1. **Email matches** — the commit author email is connected to the GitHub account
2. **Default branch** — the commit is on the repo's default branch (usually `master`/`main`)
3. **Not a fork** — the repo is standalone, not a fork (or the PR was merged)
4. **Not a squash merge** — individual commits don't count if merged via squash

**Before every session, verify:**
```bash
git config user.email   # must match GitHub account
git config user.name
```

If wrong, fix it immediately — past commits can't be retroactively attributed
without force-push.

## Strategy — Three Tiers

Always work top-down. Stop when the user has enough commits.

### Tier 1 — Split Existing Work

Take unstaged/uncommitted changes and split them into the most granular
**conventional commits** that each compile and pass tests independently.

| Granularity | Example |
|-------------|---------|
| One file per commit | `feat(api): add rate limiter middleware` |
| One concern per commit | `feat(db): add schedule model`, `feat(api): add schedule CRUD routes` |

**Rules:**
- Each commit must pass `pytest -x -q` and `ruff check .`
- Never commit broken intermediate states
- Max 1 logical change per commit (one model, one route file, one test file)
- Use conventional commits: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `style`

### Tier 2 — Low-Hanging Improvements

Scan the codebase for quick, safe wins that produce quality commits:

| Opportunity | Typical Commits | Time |
|-------------|-----------------|------|
| Missing `__init__.py` in packages | 1 per package | 10s |
| Dead code / unused imports (scan with `ruff check .`) | 1 per module | 30s |
| Missing docstrings on public APIs | 1 per module | 1m |
| Type annotations on untyped functions | 1 per module | 2m |
| `.gitignore` improvements | 1 file | 10s |
| Badge updates in README | 1 commit | 10s |
| `# noqa` comments where lint is suppressed | 1 per suppression batch | 1m |

**Run the scanner:**
```bash
ruff check . --select F401,F841   # unused imports and variables
mypy . --ignore-missing-imports   # type issues
```

### Tier 3 — Planned Improvements

Only when Tiers 1-2 are exhausted. Pick ONE, implement, split into commits:

| Category | Ideas |
|----------|-------|
| **Tests** | Add tests for untested modules, edge cases, error paths |
| **Docs** | Write docstrings, README sections, examples, CONTRIBUTING.md |
| **Refactor** | Extract repeated logic, simplify conditionals, rename unclear variables |
| **CI** | Add/improve workflow files, lint configs, pre-commit hooks |
| **Config** | Add example configs, env var documentation, docker-compose overrides |

## Workflow

Each batch produces 5-20 commits. Run in this order:

```
1. git status                    → identify what's dirty/new
2. git config user.email         → verify it matches GitHub
3. pytest -x -q                  → baseline: all tests pass
4. ruff check .                  → baseline: no lint errors
5. split work into commits       → Tier 1, then Tier 2, then Tier 3
6. git log --oneline -5          → verify commit chain
7. git push origin master        → commits appear on profile in ~24h
```

## Emergency Fix — Wrong Email on Past Commits

If commits were already pushed with the wrong email:

```bash
# Option A: add the old email to GitHub Settings → Emails (safest, zero force-push)
# Option B: rewrite history (only if you're the sole contributor)
git rebase HEAD~N --exec "git commit --amend --author 'Name <email>' --no-edit"
git push --force-with-lease origin master
```

## Output

After each batch, report:
- `X commits pushed`
- `Time until green squares appear: ~24h`
- `Next batch available: now`
