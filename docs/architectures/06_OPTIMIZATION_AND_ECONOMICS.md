# cuOpt / Smart Matching / Cost Intelligence

**Owner:** Bakdaulet + adilnurgg  
**Status:** research design + partial reference implementation; see status below.

## Decision variables
- Pair accepted Slot lot samples with compatible Tab lot samples.
- Select which parts undergo manual metrology, photo retake, expert review or quarantine.
- Schedule production with queue/shift/tool/throughput constraints and cost budgets.
- Budget for cloud GPU, caliper labor, quality escapes and rework.

## Safety-constrained objective
Minimize `inspection + rework + internal scrap + expected escaped defects + downtime + operational deployment` subject to verified quality and capacity constraints. Unsafe PASS must also be reported as a **separate** constraint/metric; risk-cost alone may create unacceptable tradeoffs. If evidence is insufficient, optimizing production must not override HOLD.

## Code and performance
`matching.py` implements exact subset dynamic programming for <=12 pairs as reproducible CPU baseline. Larger scale: compare OR-Tools CPU MIP/CP-SAT and NVIDIA cuOpt GPU (supported MIP limitations; do not assume globally optimal proof). `economics.py` ensures one terminal outcome per specimen to avoid double counting. `factory.py` compares only simulated/assumed cost, not actual savings.

## Measurement protocol
Use paired same-lot runs. Record cost assumptions for each organization; label assumed vs observed costs. Report net incremental savings after GPU bills, inference fees, integration and monitoring, not just reduced scrap. Include sensitivity analysis for defect escape severity and HOLD costs.

## Licensing and infrastructure
https://github.com/NVIDIA/cuopt (Apache 2.0, NVIDIA GPU required); https://github.com/google/or-tools (verify exact license/version before integration). Do not bundle their source in this ZIP; use dependency documentation and reproducible install manifests.

## Acceptance
- Never route unsafe unit to PASS because it reduces cost.
- Baseline OR-Tools/cuOpt use same exact objective and constraints.
- Distinguish measured savings, simulated savings and assumptions in all charts.

