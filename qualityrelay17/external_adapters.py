"""Provider-neutral adapter contracts, NOT working NVIDIA/Isaac/Pi integrations."""
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ExternalResult:
    provider:str
    capability:str
    state:Literal['NOT_CONFIGURED','UNAVAILABLE','EXECUTED']
    origin:Literal['SIMULATED','TEST_FIXTURE','PHYSICAL_CAPTURE','VERIFIED_PHYSICAL']
    artifact_uri:str|None
    model_version:str|None
    warning:str

class ExternalAdapter:
    def __init__(self,provider,capability):self.provider=provider;self.capability=capability
    def health(self):return ExternalResult(self.provider,self.capability,'NOT_CONFIGURED','TEST_FIXTURE',None,None,
                                          'No live external service configured; cannot claim real provider inference.')

NVIDIA_ADAPTERS={x:ExternalAdapter('NVIDIA',x) for x in [
    'isaac_sim','replicator','cuopt','physicsnemo','deepstream','cosmos','metropolis_vss','warp_newton']}
