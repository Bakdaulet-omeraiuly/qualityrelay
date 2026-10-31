"""Exact small-instance assignment baseline; use OR-Tools/cuOpt adapters for large n."""
from functools import lru_cache

def pair_cost(slot:dict,tab:dict,minimum_clearance:float=0.5):
    c=slot['width_mm']-tab['width_mm']
    return (0 if c>=minimum_clearance else 1000*(minimum_clearance-c), abs(c-0.8))

def optimize_pairs(slots, tabs, minimum_clearance=0.5):
    if len(slots)!=len(tabs): raise ValueError('equal number of parts required')
    n=len(slots)
    if n>12:raise ValueError('exact DP limit 12; route larger jobs to OR-Tools/cuOpt')
    @lru_cache(None)
    def solve(i,used):
        if i==n:return ((0,0),())
        candidates=[]
        for j in range(n):
            if used>>j&1:continue
            tail,assignment=solve(i+1,used|(1<<j))
            part=pair_cost(slots[i],tabs[j],minimum_clearance)
            candidates.append(((part[0]+tail[0],part[1]+tail[1]),((slots[i]['id'],tabs[j]['id']),)+assignment))
        return min(candidates,key=lambda x:x[0])
    total,pairs=solve(0,0)
    return {'pairs':pairs,'risk_penalty':round(total[0],5),'clearance_deviation_penalty':round(total[1],5),'solver':'exact_dp_reference'}
