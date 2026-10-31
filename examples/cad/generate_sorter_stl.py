#!/usr/bin/env python3
"""Generate the printable servo sorter parts for the QualityRelay manual track.

Python standard library only. Print on any FDM printer (designed for a Bambu Lab bed,
fits an A1 mini) in PLA, in the orientation exported, without supports:

  swivel_chute.stl  sloped U-channel that the specimen slides down into PASS, HOLD or
                    REJECT. The inlet end is a half-disc around the servo axis, so the part
                    lands on the floor at every chute angle.
  chute_hub.stl     30-degree wedge glued under the chute floor at the axis. The SG90 horn
                    is glued to its flat bottom; the horn screw is reached through the holes.
  servo_tower.stl   stands on the table and holds an SG90 shaft-up; the servo tabs rest on
                    the end walls and are screwed into them.

Usage, from the repository root:

  python3 examples/cad/generate_sorter_stl.py          # check the geometry, then write STLs
  python3 examples/cad/generate_sorter_stl.py --check  # check only

All heights assume the baseboard top is 120-130 mm above the table and the tower stands on
the table with the servo axis 45 mm in front of the board's end face, on the track centre
line. The SG90 height above its tabs varies between makers (SERVO_TAB_TO_HORN_TOP); a few
millimetres either way only change how far the specimen drops into the chute.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from generate_specimen_stl import Tri, mesh_report, split_shells, write_ascii_stl

OUT_DIR = Path(__file__).resolve().parent / 'sorter'

# ----------------------------------------------------------------------------- layout (mm)
BOARD_TOP_MIN = 120.0        # baseboard top above the table; 125 recommended, 130 max
BOARD_TOP_MAX = 130.0
CARRIER_FLOOR_ABOVE_BOARD = 2.0
PIVOT_FROM_BOARD_END = 45.0  # servo axis in front of the board's end face
SPECIMEN_HALF_WIDTH = 33.2 / 2
SPECIMEN_DIAGONAL = math.hypot(60.0, 33.2)
ROUTE_ANGLES = {'PASS': 35.0, 'HOLD': 90.0, 'REJECT': 145.0}  # firmware defaults

# ----------------------------------------------------------------------------- chute
SLOPE_DEG = 30.0             # PLA on PLA usually needs > 25 degrees to keep sliding
INNER_HALF_WIDTH = 38.0      # 76 mm inside: wider than the 68.5 mm specimen diagonal
WALL_T = 1.6
WALL_H = 15.0                # above the floor
FLOOR_T = 2.0
FORWARD_LEN = 85.0           # along the floor, from the axis to the outlet edge
ACCESS_HOLE_D = 9.0          # screwdriver access to the horn screw
FLOOR_TOP_AT_AXIS = 96.0     # above the table

# ----------------------------------------------------------------------------- hub
HUB_R = 20.0
HUB_HOLE_D = 6.5
HUB_AXIS_T = 15.0            # vertical thickness on the axis

# ----------------------------------------------------------------------------- SG90 + tower
SERVO_BODY = (22.8, 12.2)    # length, width; makers vary from 22.2 x 11.8 to 23.0 x 12.5
SERVO_SHAFT_FROM_END = 5.9   # output shaft centre from the near body end
SERVO_TAB_SPAN = 32.2        # tab tip to tab tip
SERVO_TAB_TO_HORN_TOP = 13.0  # tab underside to the top face of a fitted horn (estimate)
SERVO_TAB_TO_CASE_TOP = 7.0  # tab underside to the top of the case
POCKET_CLEAR = 0.4
END_WALL_T = 6.0
SIDE_WALL_T = 3.0
BASE = (70.0, 50.0, 4.0)

SEGMENTS = 96


def _box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> list[Tri]:
    v = {(i, j, k): (x1 if i else x0, y1 if j else y0, z1 if k else z0)
         for i in (0, 1) for j in (0, 1) for k in (0, 1)}
    faces = [((0, 0, 0), (1, 1, 0), (1, 0, 0)), ((0, 0, 0), (0, 1, 0), (1, 1, 0)),  # bottom
             ((0, 0, 1), (1, 0, 1), (1, 1, 1)), ((0, 0, 1), (1, 1, 1), (0, 1, 1)),  # top
             ((0, 0, 0), (1, 0, 0), (1, 0, 1)), ((0, 0, 0), (1, 0, 1), (0, 0, 1)),  # y0
             ((0, 1, 0), (0, 1, 1), (1, 1, 1)), ((0, 1, 0), (1, 1, 1), (1, 1, 0)),  # y1
             ((0, 0, 0), (0, 0, 1), (0, 1, 1)), ((0, 0, 0), (0, 1, 1), (0, 1, 0)),  # x0
             ((1, 0, 0), (1, 1, 0), (1, 1, 1)), ((1, 0, 0), (1, 1, 1), (1, 0, 1))]  # x1
    return [(v[a], v[b], v[c]) for a, b, c in faces]


def _ring_solid(outer: list[tuple[float, float]], inner: list[tuple[float, float]],
                z_bottom, z_top) -> list[Tri]:
    """Closed solid between a star-shaped outer loop and an inner hole loop sampled at the
    same counter-clockwise angles; z_bottom/z_top map (x, y) to a height."""
    tris: list[Tri] = []
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        (px, py), (qx, qy) = outer[i], outer[j]
        (ix, iy), (jx, jy) = inner[i], inner[j]
        P0, Q0 = (px, py, z_bottom(px, py)), (qx, qy, z_bottom(qx, qy))
        P1, Q1 = (px, py, z_top(px, py)), (qx, qy, z_top(qx, qy))
        I0, J0 = (ix, iy, z_bottom(ix, iy)), (jx, jy, z_bottom(jx, jy))
        I1, J1 = (ix, iy, z_top(ix, iy)), (jx, jy, z_top(jx, jy))
        tris += [(I1, P1, Q1), (I1, Q1, J1),      # top, normal up
                 (I0, Q0, P0), (I0, J0, Q0),      # bottom, normal down
                 (P0, Q0, Q1), (P0, Q1, P1),      # outer wall, outward
                 (I0, J1, J0), (I0, I1, J1)]      # hole wall, into the hole
    return tris


def _angles(extra: list[float]) -> list[float]:
    a = {round(2 * math.pi * k / SEGMENTS, 12) for k in range(SEGMENTS)}
    a |= {round(x % (2 * math.pi), 12) for x in extra}
    return sorted(a)


# ----------------------------------------------------------------------------- parts
def chute() -> list[Tri]:
    """Chute frame: origin on the servo axis at the floor underside, +x towards the outlet,
    floor printed flat (z = 0 .. FLOOR_T), walls standing on it."""
    b = INNER_HALF_WIDTH + WALL_T
    corner = math.atan2(b, FORWARD_LEN)
    angles = _angles([corner, -corner, math.pi / 2, -math.pi / 2, math.pi])

    def radius(phi: float) -> float:
        c, s = math.cos(phi), math.sin(phi)
        if c <= 1e-12:
            return b                          # half-disc behind the axis
        if abs(s) * FORWARD_LEN <= b * c + 1e-12:
            return FORWARD_LEN / c            # outlet edge
        return b / abs(s)                     # straight side under the wall

    outer = [(radius(p) * math.cos(p), radius(p) * math.sin(p)) for p in angles]
    r = ACCESS_HOLE_D / 2
    inner = [(r * math.cos(p), r * math.sin(p)) for p in angles]
    tris = _ring_solid(outer, inner, lambda x, y: 0.0, lambda x, y: FLOOR_T)
    for y0, y1 in ((INNER_HALF_WIDTH, b), (-b, -INNER_HALF_WIDTH)):
        tris += _box(0.0, FORWARD_LEN, y0, y1, FLOOR_T - 0.4, FLOOR_T + WALL_H)
    return tris


def hub() -> list[Tri]:
    """Hub frame: origin on the axis at the flat bottom (horn face); the top slopes down
    towards +x, the outlet side, at SLOPE_DEG."""
    t = math.tan(math.radians(SLOPE_DEG))
    angles = _angles([])
    outer = [(HUB_R * math.cos(p), HUB_R * math.sin(p)) for p in angles]
    inner = [(HUB_HOLE_D / 2 * math.cos(p), HUB_HOLE_D / 2 * math.sin(p)) for p in angles]
    return _ring_solid(outer, inner, lambda x, y: 0.0, lambda x, y: HUB_AXIS_T - x * t)


def tower_deck_height() -> float:
    cos = math.cos(math.radians(SLOPE_DEG))
    horn_top = FLOOR_TOP_AT_AXIS - FLOOR_T / cos - HUB_AXIS_T
    return horn_top - SERVO_TAB_TO_HORN_TOP


def tower() -> list[Tri]:
    """Tower frame: origin on the table under the servo shaft; +x towards the bins.
    The servo body's long end points back towards the board."""
    zd = tower_deck_height()
    L, W = SERVO_BODY
    px0, px1 = SERVO_SHAFT_FROM_END - L - POCKET_CLEAR, SERVO_SHAFT_FROM_END + POCKET_CLEAR
    py = W / 2 + POCKET_CLEAR
    yo = py + SIDE_WALL_T
    bx0, bx1 = px0 - END_WALL_T, px1 + END_WALL_T
    z0 = BASE[2] - 0.4
    win_y, win_z0, win_z1 = 3.5, zd - 22.0, zd - 10.0   # cable windows in both end walls
    cx = (bx0 + bx1) / 2
    tris = _box(cx - BASE[0] / 2, cx + BASE[0] / 2, -BASE[1] / 2, BASE[1] / 2, 0.0, BASE[2])
    for x0, x1 in ((bx0, px0), (px1, bx1)):                          # end walls with window
        tris += _box(x0, x1, -yo, yo, z0, win_z0)
        tris += _box(x0, x1, -yo, yo, win_z1, zd)
        tris += _box(x0, x1, -yo, -win_y, win_z0 - 0.4, win_z1 + 0.4)
        tris += _box(x0, x1, win_y, yo, win_z0 - 0.4, win_z1 + 0.4)
    for y0, y1 in ((py, yo), (-yo, -py)):                            # side walls
        tris += _box(px0 - 0.4, px1 + 0.4, y0, y1, z0, zd)
    fin_h = 30.0
    for y0, y1 in ((yo - 0.4, BASE[1] / 2 - 3), (-BASE[1] / 2 + 3, -yo + 0.4)):  # side fins
        tris += _box(cx - 1.5, cx + 1.5, y0, y1, z0, fin_h)
    tris += _box(bx1 - 0.4, cx + BASE[0] / 2 - 3, -1.5, 1.5, z0, fin_h)          # front fin
    tris += _box(cx - BASE[0] / 2 + 3, bx0 + 0.4, -1.5, 1.5, z0, fin_h)          # back fin
    return tris


# ----------------------------------------------------------------------------- checks
def geometry_check() -> list[tuple[str, bool, str]]:
    s, c = math.sin(math.radians(SLOPE_DEG)), math.cos(math.radians(SLOPE_DEG))
    t = s / c
    b = INNER_HALF_WIDTH + WALL_T
    res: list[tuple[str, bool, str]] = []

    back_edge = FLOOR_TOP_AT_AXIS + b * s
    res.append(('chute back edge below the carrier floor', back_edge <= BOARD_TOP_MIN - 4,
                f'back edge {back_edge:.1f} mm; carrier floor >= {BOARD_TOP_MIN + CARRIER_FLOOR_ABOVE_BOARD:.0f} mm'
                f' (board top {BOARD_TOP_MIN:.0f}-{BOARD_TOP_MAX:.0f}); drop '
                f'{BOARD_TOP_MIN + CARRIER_FLOOR_ABOVE_BOARD - back_edge:.0f}-'
                f'{BOARD_TOP_MAX + CARRIER_FLOOR_ABOVE_BOARD - FLOOR_TOP_AT_AXIS:.0f} mm'))
    swing = max(abs(a - 90) for a in ROUTE_ANGLES.values()) + 5
    reach = b * math.sqrt((c * math.cos(math.radians(swing))) ** 2 + math.sin(math.radians(swing)) ** 2)
    res.append(('rotating chute clears the board end', reach < PIVOT_FROM_BOARD_END - 4,
                f'max reach behind the axis {reach:.1f} mm at +/-{swing:.0f} deg; board end at '
                f'{PIVOT_FROM_BOARD_END:.0f} mm'))
    res.append(('specimen turns freely in the chute', 2 * INNER_HALF_WIDTH > SPECIMEN_DIAGONAL + 5,
                f'inside width {2 * INNER_HALF_WIDTH:.0f} mm vs specimen diagonal {SPECIMEN_DIAGONAL:.1f} mm'))
    worst = 1e9
    for a in ROUTE_ANGLES.values():          # wall start must stay out of the entry lane
        psi = math.radians(a - 90)
        v = (-math.sin(psi), math.cos(psi))  # wall direction; only its normal is used below
        for side in (1, -1):
            wy = side * INNER_HALF_WIDTH
            x = PIVOT_FROM_BOARD_END + wy * v[0]
            y = wy * v[1]
            if x < PIVOT_FROM_BOARD_END:
                worst = min(worst, abs(y) - SPECIMEN_HALF_WIDTH)
    res.append(('chute walls stay out of the entry lane', worst > 3,
                f'smallest clearance to a centred specimen {worst:.1f} mm'))
    hub_min = HUB_AXIS_T - HUB_R * t
    res.append(('hub is thick enough at its thin edge', hub_min >= 3, f'{hub_min:.1f} mm'))
    zd = tower_deck_height()
    floor_under_axis = FLOOR_TOP_AT_AXIS - FLOOR_T / c
    L, W = SERVO_BODY
    front = SERVO_SHAFT_FROM_END + (SERVO_TAB_SPAN - L) / 2
    r_corner = math.hypot(front + END_WALL_T, W / 2 + POCKET_CLEAR + SIDE_WALL_T)
    gap_servo = floor_under_axis - front * t - (zd + SERVO_TAB_TO_CASE_TOP)
    gap_tower = floor_under_axis - r_corner * t - zd
    res.append(('chute floor clears servo and tower while turning', min(gap_servo, gap_tower) > 5,
                f'{gap_servo:.1f} mm over the servo case, {gap_tower:.1f} mm over the tower top'))
    outlet_z = FLOOR_TOP_AT_AXIS - FORWARD_LEN * s
    res.append(('outlet is above 35 mm bins', outlet_z - 35 >= 10,
                f'outlet floor {outlet_z:.1f} mm above the table, {FORWARD_LEN * c:.0f} mm from the axis'))
    return res


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--check', action='store_true', help='check only, write nothing')
    args = parser.parse_args()
    ok = True
    for name, good, detail in geometry_check():
        ok = ok and good
        print(f'{"ok  " if good else "FAIL"} {name}: {detail}')
    parts = {'swivel_chute': chute(), 'chute_hub': hub(), 'servo_tower': tower()}
    for name, tris in parts.items():
        shells = split_shells(tris)
        closed = all(mesh_report(sh)['closed'] for sh in shells)
        rep = mesh_report(tris)
        sx, sy, sz = rep['bbox_mm']
        fits = max(sx, sy) <= 175 and sz <= 175
        ok = ok and closed and fits
        print(f'{"ok  " if closed and fits else "FAIL"} {name}: {sx:.1f} x {sy:.1f} x {sz:.1f} mm, '
              f'{len(shells)} closed solid(s) {"(overlapping; the slicer merges them)" if len(shells) > 1 else ""}')
    print(f'     tower deck (servo tab underside) {tower_deck_height():.1f} mm above the table')
    if not ok:
        print('geometry check failed; nothing written', file=sys.stderr)
        return 1
    if args.check:
        return 0
    OUT_DIR.mkdir(exist_ok=True)
    for name, tris in parts.items():
        write_ascii_stl(OUT_DIR / f'{name}.stl', name, tris)
    print(f'wrote {", ".join(f"examples/cad/sorter/{n}.stl" for n in parts)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
