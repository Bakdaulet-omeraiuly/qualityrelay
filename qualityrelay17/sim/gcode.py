"""Illustrative G-code for the CNC demo scenario (D01). SIMULATED.

The correction the closed loop applies is written into the program as a cutter-compensation (wear) register,
the way a machinist corrects a size error: the toolpath stays the same, the D2 radius changes. A real machine
needs its own post-processor, tool table and work offsets; nothing here is sent to any machine.

Sign convention (engine): a part is made at latent_width + offset_mm. A slot opening is cut by an end mill
running inside the opening with G41 compensation, so a LARGER compensated radius makes the opening SMALLER:
D2 wear = -offset/2. A tab is profiled on the outside, so a larger radius makes the tab WIDER: D2 wear = +offset/2.
"""
from __future__ import annotations

TOOL_DIAMETER_MM = 6.0
COUPON_LENGTH_MM = 60.0
COUPON_HEIGHT_MM = 6.0


def wear_mm(kind: str, offset_mm: float) -> float:
    return (-offset_mm if kind == 'slot' else offset_mm) / 2.0


def program(kind: str, design: dict, offset_mm: float, *, measured_dev_mm: float | None = None, cad_revision: str | None = None) -> list[str]:
    """One illustrative program for a slot or tab coupon with the given correction. Deterministic text."""
    if kind not in ('slot', 'tab'):
        raise ValueError('kind must be slot|tab')
    w = design['slot_opening_mm'] if kind == 'slot' else design['tab_width_mm']
    r = TOOL_DIAMETER_MM / 2 + wear_mm(kind, offset_mm)
    rev = cad_revision or design.get('cad_revision', 'unknown')
    dev = '' if measured_dev_mm is None else f', chamber deviation {measured_dev_mm:+.3f} mm'
    head = [
        f'( QualityRelay {kind} coupon {COUPON_LENGTH_MM:.0f} x {w:.2f} x {COUPON_HEIGHT_MM:.0f} mm, CAD {rev} )',
        f'( D2 wear {wear_mm(kind, offset_mm):+.3f} mm = correction {offset_mm:+.3f} mm on the {kind} width{dev} )',
        '( SIMULATED, illustrative program: not post-processed for any machine )',
        'G21 G90 G17 G94',
        f'T2 M06 ( {TOOL_DIAMETER_MM:.0f} mm end mill )',
        f'G10 L1 P2 R{r:.3f} ( D2 radius incl. wear )',
        'S9000 M03',
        'G54 G00 X-5.000 Y0.000 Z5.000',
    ]
    if kind == 'slot':
        y = w / 2
        body = [
            'G01 Z-6.200 F300 ( through the 6 mm coupon )',
            f'G41 D2 G01 X0.000 Y{-y:.3f} F600 ( opening wall 1, comp left )',
            f'G01 X{COUPON_LENGTH_MM - 12.0:.3f} ( stop at the 12 mm base )',
            f'G01 Y{y:.3f} ( base face )',
            'G01 X0.000 ( opening wall 2 )',
            'G40 G00 Z5.000',
        ]
    else:
        y = w / 2
        body = [
            'G01 Z-6.200 F300 ( through the 6 mm coupon )',
            f'G41 D2 G01 X0.000 Y{y:.3f} F600 ( profile side 1, comp left )',
            f'G01 X{COUPON_LENGTH_MM:.3f}',
            f'G01 Y{-y:.3f} ( end face )',
            'G01 X0.000 ( profile side 2 )',
            'G40 G00 Z5.000',
        ]
    return head + body + ['M05', 'M30']


def diff(before: list[str], after: list[str]) -> list[dict]:
    """Line-by-line difference of two programs of equal length: [{line, before, after}]."""
    if len(before) != len(after):
        raise ValueError('programs must have the same number of lines')
    return [dict(line=i + 1, before=a, after=b) for i, (a, b) in enumerate(zip(before, after)) if a != b]
