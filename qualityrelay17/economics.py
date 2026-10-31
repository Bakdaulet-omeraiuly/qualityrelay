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
    # 18.1 SCI-02: a peer evidence request (REQUEST_EVIDENCE -> RESPONSE_EVIDENCE message pair)
    # is charged SEPARATELY from the sensor observation it delivers. 0.3 is the illustrative
    # value the 17.1 slice already used; set it to 0 only on purpose (explicit zero-cost config).
    peer_request:float=0.3
    # Per LLM/tool call. 0 because every agent in this package is a deterministic mock; a live
    # Nebius run must set this from its token/latency log (adilnurgg, AGENT-04).
    compute_call:float=0.0


# Additive reference point, NOT the default and not a replacement for it -- ratios follow
# the widely-cited "1-10-100" cost-of-quality escalation (catch at source ~1x, catch at
# assembly/appraisal ~10x, escape to the customer ~100x+), per Manufacturo's cost-of-quality
# writeup and the User Solutions summary of the same rule. These are published INDUSTRY
# ratio benchmarks, not a measurement of any factory this project has built or run -- use
# for sensitivity analysis alongside the default Costs(), cite the source if shown to
# judges, and never present it as "our measured cost structure."
INDUSTRY_GROUNDED_COSTS = Costs(inspection=1.0, hold=5.0, scrap=25.0, rework=10.0, escaped_defect=100.0, platform=0.0)


def calculate(rows:list[dict],c:Costs):
    """Itemised cost. 18.1 SCI-01/02: every consumed sensor observation is charged exactly once
    (`inspections`), every peer request once (`peer_requests`), every LLM/tool call once
    (`compute_calls`), each on its own line. If a row lists the signals it consumed
    (`observations`), the charge must match that list -- a policy cannot read three sensors and
    pay for two."""
    counts={'pass':0,'hold':0,'scrap':0,'rework':0,'escaped_defect':0}
    seen=set(); inspections=0; peer_requests=0; compute_calls=0
    for row in rows:
        sid=row['specimen_id']
        if sid in seen:raise ValueError('specimen must have exactly one terminal outcome')
        seen.add(sid)
        outcome=row['outcome']
        if outcome not in counts:raise ValueError('invalid outcome')
        counts[outcome]+=1
        n_obs=row.get('inspections',0)
        if 'observations' in row and len(row['observations'])!=n_obs:
            raise ValueError(f"{sid}: consumed {len(row['observations'])} observations but is charged for {n_obs}")
        if 'requested_pi_evidence' in row and 'peer_requests' not in row:
            raise ValueError(f'{sid}: a request-capable policy must report peer_requests explicitly')
        inspections+=n_obs
        peer_requests+=row.get('peer_requests',0)
        compute_calls+=row.get('compute_calls',0)
    inspection_cost=inspections*c.inspection
    request_cost=peer_requests*c.peer_request
    compute_cost=compute_calls*c.compute_call
    outcome_cost=counts['hold']*c.hold+counts['scrap']*c.scrap+counts['rework']*c.rework+counts['escaped_defect']*c.escaped_defect
    total=inspection_cost+request_cost+compute_cost+outcome_cost+c.platform
    return {'total_cost':round(total,4),'cost_per_unit':round(total/max(1,len(rows)),4),'counts':counts,'inspections':inspections,
            'peer_requests':peer_requests,'compute_calls':compute_calls,
            'inspection_cost':round(inspection_cost,4),'request_cost':round(request_cost,4),
            'compute_cost':round(compute_cost,4),'outcome_cost':round(outcome_cost,4)}


def compare(before:list[dict], after:list[dict], costs_before:Costs, costs_after:Costs):
    a=calculate(before,costs_before);b=calculate(after,costs_after)
    if len(before)!=len(after):raise ValueError('equal sample counts required')
    if {x['specimen_id'] for x in before}!={x['specimen_id'] for x in after}:raise ValueError('paired specimens required')
    return {'baseline':a,'qualityrelay':b,'net_savings':round(a['total_cost']-b['total_cost'],4),'status':'SIMULATED_OR_ASSUMPTION_BASED'}
