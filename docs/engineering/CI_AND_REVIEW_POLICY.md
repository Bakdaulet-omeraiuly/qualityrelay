# CI and review policy (REL-02)

Owner: adilnurgg. Applies to every PR into `main`.

## Checks on every PR (`.github/workflows/tests.yml`)

| Check | Command (run it locally first) | Blocks on |
|---|---|---|
| `lint` | `ruff check .` | Syntax errors, undefined names, unused imports/variables (pyflakes). Style is not enforced; the compact one-line style is deliberate. |
| `types` | `mypy qualityrelay17` | Any type error outside the research ratchet list in `pyproject.toml`. Safety, auth, actuation, ledger and agent-bus modules are not on that list. |
| `schemas` | `python scripts/check_schemas.py` | A `schemas/*.schema.json` that is invalid for its `$schema`, or an `openapi_demo.json` that no longer matches the API. Fix the second with `--fix` and commit. |
| `security` | `bandit -r qualityrelay17 scripts -ll` and `pip-audit -r requirements-demo.txt` | Medium/high bandit findings, known CVEs in runtime deps, tracked `.env` / `keys/` / `secrets/` / `*.pem` / `*.key`. |
| `dependencies` | `python scripts/check_dependencies.py check` then `env` | Manifest / requirements / lock disagree; an adapter status without its evidence; an installed package not in the lock; a licence that is unknown, denied (GPL/AGPL/SSPL/non-commercial) or changed since review. See `DEPENDENCIES_AND_ADAPTERS.md`. |
| `test (3.11)`, `test (3.13)` | `python -m pytest -q` and the synthetic demo check | Any failing test. |
| `safety-review-gate` | `.github/workflows/review-gate.yml` | See below. |

CI installs `requirements-lock.txt`, the exact transitive pin set (REL-03). Install the same locally with `pip install -r requirements-lock.txt`. Tool versions are exact pins in `requirements-dev.txt`, so a new tool release can't turn CI red by itself. Bump them in a PR that also fixes what the new version reports.

**mypy ratchet.** Twelve research/simulation/vision modules had 47 type errors when CI was introduced on 31 Oct. They are listed under `[[tool.mypy.overrides]] ignore_errors` in `pyproject.toml`. Remove a module from the list once it is clean. Never add a safety-critical module: `tests/test_ci_policy.py` fails if one appears there.

## Reviews

- **Every PR:** 1 approval, including a code owner (`.github/CODEOWNERS`, from task board §0/§7). Pushing new commits dismisses earlier approvals.
- **Safety-critical PRs:** 2 approvals from people other than the author, given on the latest commit, and no outstanding "changes requested". A PR is safety-critical if it touches any path in `.github/safety-paths.txt`: actuation, the hardware boundary, firmware, station/operator auth, keys, signatures, roles/ACL, the ledger, verification, SAFE-MESH, the signed agent bus, `api.py`, the evidence/message schemas, the tests that pin them, and the CI/review configuration itself.
  - GitHub can't require different approval counts for different paths, so the `safety-review-gate` check enforces this. It reads the path list and its own script from the PR's **base** commit, so a PR can't loosen the rule that is judging it.
  - With three owners, this means both of the other owners. Nobody self-merges safety-critical code, as the task board's release policy requires.
- `tests/test_ci_policy.py` keeps `CODEOWNERS` and `safety-paths.txt` in sync, checks that the required check names exist as jobs, and pins the gate's behaviour: author approvals, stale approvals, duplicate approvals and dismissals don't count.

## Issues and ownership board

The task board `QUALITYRELAY_18_1_TEAM_TASKS_EN.md` stays the source of truth. `scripts/github_board.py` mirrors its open items into GitHub:

```bash
python scripts/github_board.py plan                     # dry run: what would be created, by owner and priority
gh auth login --scopes project                          # once
python scripts/github_board.py apply                    # labels, one issue per open task (owner-assigned), Project board
python scripts/github_board.py protect                  # branch protection on main (repo admin only)
```

`apply` is idempotent: it skips any task whose `[ID]` already exists as an issue. GitHub's API can't create Project views, so add a **Board** view grouped by **Assignee** once in the web UI; that view is the ownership board. Issue forms live in `.github/ISSUE_TEMPLATE/` (task, bug, safety/security). The PR template asks for the evidence actually run and for the safety checklist.

`protect` sets these rules on `main`: required checks = the table above (strict, branch must be up to date), 1 approving review, code-owner review, dismiss stale reviews, approval required after the last push, conversation resolution, admins included, no force-push or deletion. Branch protection on a private repo needs a paid GitHub plan.

## Bootstrapping caveat

The PR that introduces `review-gate.yml` can't pass its own gate, because the base commit doesn't contain `scripts/review_gate.py` yet. Merge that one PR after two human approvals, then run `protect`. Every later PR is gated normally.
