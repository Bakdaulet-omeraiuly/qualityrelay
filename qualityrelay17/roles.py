"""The same 21 specialist names as v12/v14; role policy lives on server.
This registry does NOT claim that 21 separate AI models were trained.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Role:
    name: str
    domain: str
    tools: tuple[str, ...]
    required_sources: tuple[str, ...]

# Domain scopes: read evidence of owned domain or explicitly authorized summary only.
ROLE_ROWS = [
    ("design_geometry", "design", ("read_evidence",), ("CAD",)),
    ("tolerance_analyst", "design", ("read_evidence", "check_clearance"), ("CAD", "METROLOGY")),
    ("materials_engineer", "materials", ("read_evidence",), ("CERTIFICATE",)),
    ("process_engineer", "process", ("read_evidence",), ("PROCESS",)),
    ("cnc_expert", "process", ("read_evidence",), ("CNC",)),
    ("additive_manufacturing_expert", "process", ("read_evidence",), ("PRINT_LOG", "VISION")),
    ("metrology_engineer", "metrology", ("read_evidence", "check_clearance"), ("METROLOGY",)),
    ("spc_agent", "quality", ("read_evidence",), ("SPC",)),
    ("quality_inspector", "quality", ("read_evidence", "check_clearance", "check_visual"), ("METROLOGY", "VISION")),
    ("assembly_engineer", "assembly", ("read_evidence", "check_clearance", "check_visual"), ("METROLOGY", "VISION")),
    ("causal_diagnosis", "process", ("read_evidence",), ("PROCESS",)),
    ("bayesian_statistician", "science", ("read_evidence",), ("MODEL",)),
    ("inspection_planner", "science", ("read_evidence", "request_inspection"), ("METROLOGY", "VISION")),
    ("operations_research", "assembly", ("read_evidence", "check_clearance"), ("METROLOGY",)),
    ("maintenance_engineer", "maintenance", ("read_evidence",), ("MAINTENANCE",)),
    ("supplier_boundary", "governance", ("read_evidence",), ("SUPPLIER",)),
    ("safety_governance", "governance", ("read_evidence", "check_clearance", "check_visual"), ("METROLOGY", "VISION")),
    ("privacy_security", "security", ("read_evidence",), ("AUTH_AUDIT",)),
    ("reliability_network", "network", ("read_evidence",), ("NETWORK",)),
    ("scientific_auditor", "audit", ("read_evidence",), ("RUN_MANIFEST",)),
    ("kaizen_pdca", "process", ("read_evidence",), ("IMPROVEMENT",)),
]
ROLES = {name: Role(name, domain, tuple(tools), tuple(req)) for name, domain, tools, req in ROLE_ROWS}
assert len(ROLES) == 21

# Agent count is not scientific evidence. Trigger only relevant roles for a problem.
def plan_roles(has_visual: bool, suspected_assembly: bool, budget: int = 4) -> list[str]:
    ordered = ["metrology_engineer", "quality_inspector"]
    if has_visual:
        ordered.append("additive_manufacturing_expert")
    if suspected_assembly:
        ordered.append("assembly_engineer")
    ordered.extend(["inspection_planner", "safety_governance", "scientific_auditor"])
    return ordered[:max(0, min(budget, len(ordered), 21))]
