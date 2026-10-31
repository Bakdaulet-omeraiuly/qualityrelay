"""Opt-in Nebius reasoning; no hidden credentials; may not authorize actuation.
Live calls not executed as part of reference tests.
"""
import os, json
from .agent_tools import execute,ALLOWED
from .roles import ROLES

class NebiusExpert:
    def __init__(self,*, client=None,model=None,enabled=False):
        self.enabled=enabled
        if not enabled: self.client=None;self.model=None;return
        if not os.getenv('NEBIUS_API_KEY'):raise RuntimeError('NEBIUS_API_KEY missing')
        if not model: raise RuntimeError('select verified entitled model from GET /v1/models')
        if client is None:
            from openai import OpenAI
            client=OpenAI(api_key=os.environ['NEBIUS_API_KEY'],base_url='https://api.tokenfactory.nebius.com/v1/',timeout=15,max_retries=0)
        self.client,self.model=client,model

    def review(self,role,evidence_summaries,max_rounds=3):
        if not self.enabled: return {'status':'DISABLED_NO_LIVE_MODEL','role':role}
        if role not in ROLES:raise ValueError('bad role')
        prompt=('You are a manufacturing research advisor. Only discuss grounded evidence; '
                'never invent measurements, sources or approve hardware actions. '
                'Return a recommendation with cited event IDs, and request remeasurement if uncertain.')
        tools=[{'type':'function','function':{'name':name,'description':name,'parameters':{'type':'object','properties':{},'additionalProperties':True}}}
               for name in ROLES[role].tools if name in ALLOWED]
        messages=[{'role':'system','content':prompt},{'role':'user','content':'Review evidence summaries only: '+json.dumps(evidence_summaries)[:3000]}]
        for _ in range(max_rounds):
            resp=self.client.chat.completions.create(model=self.model,messages=messages,tools=tools,temperature=0)
            msg=resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                return {'role':role,'status':'NON_AUTHORITATIVE_LLM_REVIEW','text':msg.content,'evidence_ids':[x.get('event_id') for x in evidence_summaries if x.get('event_id')]}
            for call in msg.tool_calls:
                try:result=execute(role,call.function.name,json.loads(call.function.arguments or '{}'),{'evidence_summaries':evidence_summaries})
                except (ValueError,PermissionError,KeyError,TypeError) as exc:result={'error':str(exc)}
                messages.append({'role':'tool','tool_call_id':call.id,'content':json.dumps(result)})
        return {'status':'TOOL_ROUND_LIMIT','role':role}
