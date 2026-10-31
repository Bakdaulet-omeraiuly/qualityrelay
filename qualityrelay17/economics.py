"""Avoid double counting via exclusive per-unit terminal outcome categories."""
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Costs:
    inspection:float=0.5
    hold:float=2.0
    scrap:float=20.0
    rework:float=8.0
    escaped_defect:float=150.0
    platform:float=0.0


# Additive reference point, NOT the default and not a replacement for it -- ratios follow
# the widely-cited "1-10-100" cost-of-quality escalation (catch at source ~1x, catch at
# assembly/appraisal ~10x, escape to the customer ~100x+), per Manufacturo's cost-of-quality
# writeup and the User Solutions summary of the same rule. These are published INDUSTRY
# ratio benchmarks, not a measurement of any factory this project has built or run -- use
# for sensitivity analysis alongside the default Costs(), cite the source if shown to
# judges, and never present it as "our measured cost structure."
INDUSTRY_GROUNDED_COSTS = Costs(inspection=1.0, hold=5.0, scrap=25.0, rework=10.0, escaped_defect=100.0, platform=0.0)


def calculate(rows:list[dict],c:Costs):
    counts={'pass':0,'hold':0,'scrap':0,'rework':0,'escaped_defect':0}
    seen=set(); inspections=0
    for row in rows:
        sid=row['specimen_id']
        if sid in seen:raise ValueError('specimen must have exactly one terminal outcome')
        seen.add(sid)
        outcome=row['outcome']
        if outcome not in counts:raise ValueError('invalid outcome')
        counts[outcome]+=1
        inspections+=row.get('inspections',0)
    total=inspections*c.inspection+counts['hold']*c.hold+counts['scrap']*c.scrap+counts['rework']*c.rework+counts['escaped_defect']*c.escaped_defect+c.platform
    return {'total_cost':round(total,4),'cost_per_unit':round(total/max(1,len(rows)),4),'counts':counts,'inspections':inspections}


def compare(before:list[dict], after:list[dict], costs_before:Costs, costs_after:Costs):
    a=calculate(before,costs_before);b=calculate(after,costs_after)
    if len(before)!=len(after):raise ValueError('equal sample counts required')
    if {x['specimen_id'] for x in before}!={x['specimen_id'] for x in after}:raise ValueError('paired specimens required')
    return {'baseline':a,'qualityrelay':b,'net_savings':round(a['total_cost']-b['total_cost'],4),'status':'SIMULATED_OR_ASSUMPTION_BASED'}
