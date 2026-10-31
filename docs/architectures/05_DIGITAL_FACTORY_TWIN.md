# Multi-line Digital Factory / Discrete Event Simulation

**Owner:** Bakdaulet + 4th engineer  
**Status:** research design + partial reference implementation; see status below.

## Factory ontology
Workcell, machine, operator, supplier, lot, specimen, geometry revision, production step, metrology, vision, assembly, sorter, rework station, quarantine, quality plan, financial ledger. Each station has service time, capacity, maintenance mode, input buffer, output buffer, variability distribution and failure events.

## Three simulation fidelities
**Level 0 (implemented):** seeded specimen stream and multiple inspection policies in `factory.py`. Includes distribution shifts, two imperfect camera observations, partial network availability, and physical-safe true outcomes. Fast CPU benchmark. No conveyor physics or real visual imagery.
**Level 1 (implemented 31 Oct, Bakdaulet — `qualityrelay17/digital_twin.py`):** own event-driven DES (no SimPy dependency) coupling the Level-0 inspection policies to a 7-station line with FIFO queues, capacities, WIP, cycle time, throughput and a quarantine/Review station; purchased VOI evidence becomes station revisits. Common random numbers across policies, conservation/determinism tests, 6 fault scenarios. Results and the finding that cost-optimal VOI saturates the caliper station: `docs/research/DIGITAL_TWIN_RUN_31OCT.md`. Service times are illustrative assumptions until measured. Blocked/starved-station modelling and finite buffers remain future work.
**Level 2 (NVIDIA plugin):** Isaac Sim/Omniverse 3D workcells, photoreal sensors, mechanical chute geometry, and Replicator domain randomization. Needs an RTX GPU with RT cores; Nebius H100 alone cannot render Isaac Sim. Scene artifacts in USD and source CAD tracked by revision.

## Multi-factory extension
Scale by independent suppliers with separate data ownership and schema contracts. Simulate communication asymmetry and loss of coordinator, sample heterogeneous measurement precision, drift and supply delay. Do not claim simulated site is a certified digital twin without calibrated, continually updated physical mapping and VVUQ.

## Verification and Validation
Verify discrete event conservation (input = good+hold+scrap+WIP), determinism under seeded replay, no impossible negative WIP or duplicate unit IDs. Validate each service-time and defect distribution against REAL logs if a factory agrees to pilot. Disclose simulation-to-real gap and confidence intervals.

## GitHub reuse
https://github.com/simpx/simpy ; https://github.com/FactorySimPy/FactorySimPy ; https://github.com/isaac-sim/IsaacSim ; https://github.com/NVIDIA/warp ; https://github.com/newton-physics/newton . Their licenses and additional assets must be checked at version pinning time.

## Acceptance
- One physical Slot/Tab production story mirrors one simulated line.
- At least 3 seeded fault scenarios and common random numbers across policy baselines.
- Report inventory, WIP, cycle time and throughput with all origin labels.

