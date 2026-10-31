"""Expected decision loss / existing Bayesian value-of-information method.
This is a reference implementation, NOT a newly proven algorithm.

31 Oct additions (Bakdaulet): `combined_defect_probability` and `two_axis_action_scores`
extend the single-hypothesis VOI to the two independent fault axes the factory generator
actually has (surface defect; dimensional clearance). Still textbook one-step (myopic)
expected-loss VOI, cf. docs/research/COLLECTIVE_17_1_BAKDAULET.md section 4 -- nothing new
is claimed, it is just now wired to the same loss scale the benchmark grades with.
"""
from dataclasses import dataclass
from math import log2

@dataclass(frozen=True)
class Inspection:
    name:str
    sensitivity:float
    specificity:float
    cost:float


def posterior(prior, sens, spec, positive):
    likelihood_defect=sens if positive else 1-sens
    likelihood_good=1-spec if positive else spec
    denom=prior*likelihood_defect+(1-prior)*likelihood_good
    return prior*likelihood_defect/denom if denom>0 else prior


def risk(p_defect, false_pass_cost=100., false_hold_cost=3.):
    if not 0<=p_defect<=1:raise ValueError('p outside [0,1]')
    # 'HOLD' means delay/inspection, not a confirmed reject. Both costs are illustrative.
    return min(p_defect*false_pass_cost, (1-p_defect)*false_hold_cost)


def entropy(p):
    return 0 if p in (0,1) else -p*log2(p)-(1-p)*log2(1-p)


def _check(a:Inspection):
    if not (0<=a.sensitivity<=1 and 0<=a.specificity<=1 and a.cost>=0): raise ValueError('invalid test parameters')


def action_scores(prior:float, actions:list[Inspection], *, false_pass_cost=100., false_hold_cost=3.):
    rows=[]
    for a in actions:
        _check(a)
        pp=prior*a.sensitivity+(1-prior)*(1-a.specificity)
        ppos=posterior(prior,a.sensitivity,a.specificity,True)
        pneg=posterior(prior,a.sensitivity,a.specificity,False)
        after=pp*risk(ppos,false_pass_cost,false_hold_cost)+(1-pp)*risk(pneg,false_pass_cost,false_hold_cost)
        rows.append({'name':a.name,'expected_loss':a.cost+after,'expected_entropy':pp*entropy(ppos)+(1-pp)*entropy(pneg), 'inspection_cost':a.cost})
    rows.append({'name':'NO_ACTION','expected_loss':risk(prior,false_pass_cost,false_hold_cost),'expected_entropy':entropy(prior),'inspection_cost':0})
    return sorted(rows,key=lambda x:(x['expected_loss'],x['name']))


def combined_defect_probability(surface_p:float, dimensional_p:float)->float:
    """P(part unsafe) when surface and dimensional faults are independent and either one
    alone makes the part unsafe (matches `safe = clearance>=0.5 and not surface_defect`
    in factory.seeded_scenario)."""
    for p in (surface_p,dimensional_p):
        if not 0<=p<=1:raise ValueError('p outside [0,1]')
    return 1-(1-surface_p)*(1-dimensional_p)


def two_axis_action_scores(surface_p:float, dimensional_p:float,
                           surface_actions:list[Inspection], dimensional_actions:list[Inspection], *,
                           false_pass_cost=100., false_hold_cost=3.):
    """One-step NetVOI (17.1 section 4): R(D) - [c(q) + sum_y P(y|D,q) R(D u {y})] for each
    candidate test on either axis, plus NO_ACTION. A surface test updates only surface_p and
    a dimensional test only dimensional_p; the decision risk is always evaluated on the
    combined unsafe probability so both axes share one loss scale.

    Assumes the test's errors are conditionally independent of the evidence already held
    given the true state -- factory.py deliberately breaks this with shared_camera_noise so
    the assumption gets stress-tested, not hidden."""
    p0=combined_defect_probability(surface_p,dimensional_p)
    r0=risk(p0,false_pass_cost,false_hold_cost)
    h0=entropy(p0)
    rows=[]
    for axis,actions in (('surface',surface_actions),('dimensional',dimensional_actions)):
        p_axis=surface_p if axis=='surface' else dimensional_p
        for a in actions:
            _check(a)
            pp=p_axis*a.sensitivity+(1-p_axis)*(1-a.specificity)
            ppos=posterior(p_axis,a.sensitivity,a.specificity,True)
            pneg=posterior(p_axis,a.sensitivity,a.specificity,False)
            if axis=='surface':
                cpos,cneg=combined_defect_probability(ppos,dimensional_p),combined_defect_probability(pneg,dimensional_p)
            else:
                cpos,cneg=combined_defect_probability(surface_p,ppos),combined_defect_probability(surface_p,pneg)
            after=pp*risk(cpos,false_pass_cost,false_hold_cost)+(1-pp)*risk(cneg,false_pass_cost,false_hold_cost)
            rows.append({'name':a.name,'axis':axis,'expected_loss':a.cost+after,'net_voi':r0-(a.cost+after),
                         'expected_entropy_reduction':max(0.0,h0-(pp*entropy(cpos)+(1-pp)*entropy(cneg))),
                         'inspection_cost':a.cost})
    rows.append({'name':'NO_ACTION','axis':None,'expected_loss':r0,'net_voi':0.0,'expected_entropy_reduction':0.0,'inspection_cost':0})
    return sorted(rows,key=lambda x:(x['expected_loss'],x['name']))
