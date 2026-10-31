"""Registered B0..B7 scenario grid (docs/research/COLLECTIVE_GATE_A_REGISTRATION.md).
Fixed before the first full run; do not edit after it -- add new IDs instead.

Calibration for EVERY scenario is the nominal held-out calibration (seeds 1000-1009): a team
calibrates once and then conditions change, so S02-S08 and S14 are out-of-calibration stresses
by design (17.1 sec 4.3 item 5 -- calibration drift).
"""
from ..economics import Costs
from .collective_env import CollectiveScenario as S

GRID = (
    S('S01', 'nominal'),
    S('S02', 'process drift (shift 0.25 mm)', process_shift_mm=0.25),
    S('S03', 'noisy cameras / frequent phone-Pi disagreement', camera_noise=0.15),
    S('S04', 'shared lighting: common-mode camera error', shared_camera_noise=0.15),
    S('S05', 'duplicated photo: Pi frame is a phone re-upload half the time', duplicate_photo_p=0.5),
    S('S06', 'Pi offline for every part', network_outage=1.0),
    S('S07', 'partial network partition (30% of parts)', network_outage=0.30),
    S('S08', 'noisy caliper (true sigma 0.15 mm, model still assumes 0.05)', caliper_sigma_mm=0.15),
    S('S09', 'constrained inspection budget (2 observations)', budget=2),
    S('S10', 'cost shock: escaped defect 500', costs=Costs(escaped_defect=500.0)),
    S('S11', 'cheap messages (peer_request 0.05)', costs=Costs(peer_request=0.05)),
    S('S12', 'hold priced as review labour (hold 5.0)', costs=Costs(hold=5.0)),
    S('S13', 'hold 5.0 + cheap messages 0.05', costs=Costs(hold=5.0, peer_request=0.05)),
    S('S14', 'combined stress: duplicates 0.5 + shared lighting 0.10 + outage 0.20',
      duplicate_photo_p=0.5, shared_camera_noise=0.10, network_outage=0.20),
)
BY_ID = {s.sid: s for s in GRID}
