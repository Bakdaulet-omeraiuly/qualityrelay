#!/usr/bin/env python
"""Run the Level-1 digital twin over the default fault scenarios (10 seeds x 1000 parts, all
policies, common random numbers) and write examples/results/digital_twin_31oct/.
Everything is SIMULATED; service times are illustrative assumptions (digital_twin.TwinTiming)."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.digital_twin import run_twin_scenarios, REFERENCE  # noqa: E402


def main():
    res = run_twin_scenarios()
    for sid, s in res['scenarios'].items():
        print(f"\n== {sid} {s['params']}")
        for p, m in s['mean_by_policy'].items():
            d = s['paired_vs_rules'][p]
            print(f"  {p:24s} cycle {m['mean_cycle_time_s']:8.1f}s  thr {m['throughput_per_hour']:7.1f}/h  maxWIP {m['max_wip']:5.1f}  "
                  f"holds {m['hold']:6.1f}  unsafe {m['unsafe_pass']:5.1f}  | d_cycle vs {REFERENCE} {d['mean_cycle_time_s']['mean']:+8.1f} {d['mean_cycle_time_s']['ci95']}")
    print(f"\nwrote examples/results/digital_twin_31oct in {res['manifest']['elapsed_s']}s")


if __name__ == '__main__':
    main()
