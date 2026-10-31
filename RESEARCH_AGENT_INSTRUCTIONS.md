# Coding-agent collaboration rules (Codex, Claude Code, etc.)

## Task scope
Use the checked-in `QUALITYRELAY_17_MASTER_BLUEPRINT.md` as plan. Never claim an external NVIDIA plugin is active based on an adapter stub. Preserve all legacy originals. Open PRs per architecture owner. Do not merge external code without licensing/commit review.

## Safety-first constraints
- No invented measurements, physical experiment results, simulator performance, cost savings, statistical significance or novelty.
- Do not let LLM text actuate hardware, release PASS, set calibrated risk, or overwrite source records.
- Every evidence source has a root capture/instrument ID; derived CAD/photo model output can depend on the same source and is **not** another independent sensor.
- No shadow promotion: phone-mode Pi emulation is TEST_FIXTURE, not physical Hailo inference.
- Any uncertainty => HOLD and request reinspection, never silently green.

## Useful commands
```bash
pip install -r requirements-demo.txt
python -m pytest -q
python -m qualityrelay17.demo
uvicorn qualityrelay17.api:app --host 127.0.0.1 --port 8000
```

## PR acceptance template
- Purpose/research hypothesis
- Owned modules changed
- Traceability to source, external refs and license
- Tests introduced and exact results
- What was actually physically tested
- New assumptions and limitations
- Security/physical action review status
- Reproducible run manifest (commit, seed, model, inputs)
