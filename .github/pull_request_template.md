## What and why
<!-- Task ID(s) from QUALITYRELAY_18_1_TEAM_TASKS_EN.md, e.g. BACK-03, REL-02. Link the issue: Closes #NN -->

## Evidence
<!-- What you ran and what it showed. Paste the pytest summary line. Say plainly what was NOT run
     (hardware, live LLM, GPU). Results are SIMULATED / TEST_FIXTURE unless a physical capture says otherwise. -->

## Checklist
- [ ] `python -m pytest -q` passes locally
- [ ] `ruff check .`, `mypy qualityrelay17`, `python scripts/check_schemas.py` pass (CI runs them too)
- [ ] API changed? OpenAPI snapshot regenerated with `python scripts/check_schemas.py --fix`
- [ ] No keys, tokens, `.env` or personal photos added
- [ ] Claims in docs/README match what was actually measured (no `VERIFIED`/`WORKING` without evidence)

## Safety-critical? (paths in `.github/safety-paths.txt`)
- [ ] This PR touches actuation, auth/keys/signatures, the ledger/verification, SAFE-MESH, the agent-message bus, firmware, or CI/review rules
  - Needs **two approvals from people other than the author, on the latest commit** (`safety-review-gate` check). Pushing again resets it.
  - Describe the failure mode you considered and the test that pins it:
