"""Provenance DAG for avoiding double-use of derived observations.
References are IDs of source evidence, NOT independent confidence votes.
"""
from collections import defaultdict

def lineage_groups(events:list[dict]):
    """Return connected components among observations sharing an ancestor.
    Parent roots are raw camera/instrument IDs, not agent consensus messages.
    """
    ids={e['event_id'] for e in events}
    if len(ids)!=len(events):raise ValueError('duplicate event ids')
    roots={}
    for e in events:
        row=set(e.get('parent_source_roots',[]) or [])
        row.add(e['source_root'])
        roots[e['event_id']]=row
    seen=set();groups=[]
    for k in roots:
        if k in seen:continue
        group={k};seen.add(k)
        change=True
        while change:
            change=False
            union=set().union(*(roots[x] for x in group))
            for other in roots:
                if other not in seen and roots[other]&union:
                    seen.add(other);group.add(other);change=True
        groups.append(sorted(group))
    return sorted(groups,key=lambda x:x[0])


def effective_source_count(events):
    return len(lineage_groups(events))
