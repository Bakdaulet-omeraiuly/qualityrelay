# External software notices

Apart from the one contributed file listed under "Contributed code" below, no third-party source code, models or datasets have been copied into this package. The included GitHub links are references to separately installed dependencies. Their licenses, copyrights and model/data terms remain with upstream owners. User-supplied QualityRelay 5.0–15.0 work is preserved as separate historical archives, and one 21-role registry was copied from the user's prior 14.2 code for direct integration; its ownership/licensing remains as designated by the original team.

The reviewed record of every Python dependency (pinned version, licence, what its wheel reports), every separately installed upstream component, and every adapter's status is `THIRD_PARTY_MANIFEST.json`. CI enforces it (`scripts/check_dependencies.py`, REL-03).

## Contributed code

- `collab/sentilab-tolerance-check/api/check.mjs`: a tolerance and fit rule check written by **aneta-claude (SentiLab)** for ScienceClaw collaboration ticket 3b5fc17f, kept byte-for-byte as posted (SHA-256 `753e763ef6166f752091f8830474ce06cd253d03e475735518e260ee354f84ab`, verified by `tests/test_collab_tolerance_check.py`). The contributor asked to be credited; no licence was stated, so treat it as usable within this project only until one is confirmed in the ticket. It is not listed in `THIRD_PARTY_MANIFEST.json`, whose schema currently only allows non-bundled upstream components (`"bundled": false`); recording bundled contributions there is a schema decision for the REL-03 owner.

Before releasing as open-source or commercial software, the team must choose its own project license, review all upstream licenses and security vulnerabilities, and confirm rights for any dataset/model weights.
