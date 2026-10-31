"""18.1 SIM-01..07 (Bakdaulet): Digital Factory, scenarios, CAD geometry, optimisation,
economics/ROI, multi-site/scale experiments and dashboard exports.

CPU-only, stdlib + SciPy + trimesh (the packages CI installs). SimPy / FactorySimPy / OR-Tools /
cuOpt / Isaac Sim / Replicator / Warp are optional adapters reported as NOT_CONFIGURED when not
installed -- the main workflow never needs them. Every number produced here is SIMULATED;
nothing in this package can produce a VERIFIED_PHYSICAL record.
"""
SOURCE_TIER = 'SIMULATED'
MODEL_VERSION = 'qr-sim-18.1.0'
