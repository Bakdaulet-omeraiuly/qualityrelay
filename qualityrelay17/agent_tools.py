"""Bounded, read-only tools. A tool call request does not grant authority."""
from .roles import ROLES
from .vder import action_scores, Inspection
from .matching import optimize_pairs

ALLOWED={
 'read_evidence':{'roles':set(ROLES),'fn':lambda inp,ctx:{'events':ctx.get('evidence_summaries',[])}},
 'check_clearance':{'roles':{'tolerance_analyst','metrology_engineer','quality_inspector','assembly_engineer','operations_research','safety_governance'},
      'fn':lambda inp,ctx:{'clearance_mm':round(float(inp['slot_width_mm'])-float(inp['tab_width_mm']),5),'minimum_mm':float(inp.get('minimum_mm',0.5))}},
 'request_inspection':{'roles':{'inspection_planner'},
      'fn':lambda inp,ctx:{'ranked':action_scores(float(inp['p_defect']),[Inspection('CALIPER',0.98,0.98,0.5),Inspection('SECOND_PHOTO',0.8,0.8,0.1)])}},
 'check_visual':{'roles':{'quality_inspector','assembly_engineer','safety_governance'},
      'fn':lambda inp,ctx:{'vision_summary':ctx.get('vision_summary',{'status':'UNKNOWN'})}},
}

def execute(role,tool_name,args,context):
    if role not in ROLES:raise PermissionError('unknown role')
    if tool_name not in ROLES[role].tools:raise PermissionError('role does not own tool')
    handler=ALLOWED.get(tool_name)
    if not handler or role not in handler['roles']:raise PermissionError('server tool not authorized')
    if not isinstance(args,dict) or len(str(args))>4000:raise ValueError('tool args invalid')
    return handler['fn'](args,context)
