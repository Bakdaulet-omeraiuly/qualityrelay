"""Expected decision loss / existing Bayesian value-of-information method.
This is a reference implementation, NOT a newly proven algorithm.
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


def action_scores(prior:float, actions:list[Inspection], *, false_pass_cost=100., false_hold_cost=3.):
    rows=[]
    for a in actions:
        if not (0<=a.sensitivity<=1 and 0<=a.specificity<=1 and a.cost>=0): raise ValueError('invalid test parameters')
        pp=prior*a.sensitivity+(1-prior)*(1-a.specificity)
        ppos=posterior(prior,a.sensitivity,a.specificity,True)
        pneg=posterior(prior,a.sensitivity,a.specificity,False)
        after=pp*risk(ppos,false_pass_cost,false_hold_cost)+(1-pp)*risk(pneg,false_pass_cost,false_hold_cost)
        rows.append({'name':a.name,'expected_loss':a.cost+after,'expected_entropy':pp*entropy(ppos)+(1-pp)*entropy(pneg), 'inspection_cost':a.cost})
    rows.append({'name':'NO_ACTION','expected_loss':risk(prior,false_pass_cost,false_hold_cost),'expected_entropy':entropy(prior),'inspection_cost':0})
    return sorted(rows,key=lambda x:(x['expected_loss'],x['name']))
