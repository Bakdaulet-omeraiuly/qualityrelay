#!/usr/bin/env python3
"""Send caliper readings from a measurement CSV to the SentiLab tolerance and fit check.

Collaboration ticket 3b5fc17f. Only physical-tier rows (OPERATOR_CONFIRMED, PHYSICAL_CAPTURE,
VERIFIED_PHYSICAL) of the functional widths are used, exactly as qualityrelay17.sim.physical_data
selects them. For each specimen the reading closest to a spec limit is checked on its own; every
slot x tab pair is checked with the narrowest slot reading against the widest tab reading.

The service is a rule check that applies our own spec. Its answers are advisory evidence
(origin EXTERNAL_SERVICE); any failure to get a clean answer is recorded as HOLD. Nothing here
decides a disposition or moves anything.

Usage:
  python3 scripts/check_measurements_with_service.py measurements.csv [more.csv ...] [--out run.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qualityrelay17.sim.physical_data import functional_readings, load_measurements  # noqa: E402
from qualityrelay17.tolerance_service import SPECS, URL, check  # noqa: E402


def _flat(spec: dict) -> list[float]:
    return [v for vals in spec['readings'].values() for v in vals]


def worst_reading(kind: str, values: list[float]) -> float:
    """The reading nearest a spec limit, i.e. farthest from the spec nominal."""
    nominal = SPECS[kind]['nominal']
    return max(values, key=lambda v: (abs(v - nominal), v))


def run(csv_paths, *, url: str = URL, post=None) -> dict:
    paths = [Path(p) for p in csv_paths]
    specimens = functional_readings(load_measurements(paths))
    parts, pairs = [], []
    for sid, spec in sorted(specimens.items()):
        width = worst_reading(spec['kind'], _flat(spec))
        v = check(sid, spec['kind'], width, url=url, post=post)
        parts.append({'specimen_id': sid, 'part_type': spec['kind'], 'readings': len(_flat(spec)),
                      'width_sent_mm': round(width, 2), 'disposition': v.disposition, 'verdict': v.verdict,
                      'score': v.score, 'reasons': list(v.reasons), 'service_version': v.service_version})
    slots = {s: d for s, d in specimens.items() if d['kind'] == 'slot'}
    tabs = {s: d for s, d in specimens.items() if d['kind'] == 'tab'}
    for tid, tab in sorted(tabs.items()):
        for sid, slot in sorted(slots.items()):
            t_w, s_w = max(_flat(tab)), min(_flat(slot))
            v = check(tid, 'tab', t_w, mate=(sid, 'slot', s_w), url=url, post=post)
            pairs.append({'tab': tid, 'slot': sid, 'tab_width_mm': round(t_w, 2), 'slot_width_mm': round(s_w, 2),
                          'clearance_mm': v.clearance_mm, 'fit': v.fit,
                          'answered': v.verdict is not None, 'reasons': list(v.reasons)})
    return {
        'service': 'SentiLab tolerance and fit check (aneta-claude), ticket 3b5fc17f',
        'url': url, 'origin': 'EXTERNAL_SERVICE',
        'note': 'Rule check applying our own spec; advisory evidence only. safe_mesh makes every decision.',
        'run_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'inputs': [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
        'spec': SPECS, 'parts': parts, 'pairs': pairs,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('csv', nargs='+')
    ap.add_argument('--out', help='write the run record as JSON here')
    ap.add_argument('--url', default=URL)
    a = ap.parse_args(argv)
    rec = run(a.csv, url=a.url)
    if not rec['parts']:
        print('No physical-tier slot_inner_width / width rows found; nothing sent.')
        return 1
    print(f"{'specimen':<12}{'type':<6}{'sent mm':>9}  {'service':<8}{'advisory':<9}score")
    for p in rec['parts']:
        print(f"{p['specimen_id']:<12}{p['part_type']:<6}{p['width_sent_mm']:>9.2f}  "
              f"{str(p['verdict']):<8}{p['disposition']:<9}{p['score'] if p['score'] is not None else '-'}")
    if rec['pairs']:
        print(f"\n{'tab':<12}{'slot':<12}{'clearance':>10}  fit")
        for q in rec['pairs']:
            c = '-' if q['clearance_mm'] is None else f"{q['clearance_mm']:.2f}"
            print(f"{q['tab']:<12}{q['slot']:<12}{c:>10}  {q['fit'] if q['answered'] else 'HOLD (no answer)'}")
    if a.out:
        Path(a.out).write_text(json.dumps(rec, indent=2) + '\n')
        print(f'\nrun record: {a.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
