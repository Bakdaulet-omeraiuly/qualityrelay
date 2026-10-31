#!/usr/bin/env python3
"""Generate and check QualityRelay specimen STL files (Python standard library only).

The geometry mirrors examples/cad/qualityrelay_printkit.scad:

  slot_coupon(w): 60 mm long U-channel, (w + 12) mm wide, 6 mm high. A 12 mm closed
                  base at x = 0..12 and two 6 mm rails; the opening is at x = 60 and the
                  gap between the rails is w.
  tab_coupon(w):  60 x w x 6 mm bar.

Usage, from the repository root:

  python3 examples/cad/generate_specimen_stl.py write slot_defect tab_defect
  python3 examples/cad/generate_specimen_stl.py check
  python3 examples/cad/generate_specimen_stl.py plate

`plate` writes examples/cad/formlabs/qualityrelay_specimen_plate.stl: all 9 specimens plus
2 optional spares in one file, standing on end, as clean single-body solids (the original
slot files are three touching boxes each, which resin slicers may flag as broken).

`write` creates one closed (watertight) solid per part and never overwrites an existing
file unless --force is given.

`check` reads every STL listed in examples/cad/print_manifest.csv, measures the critical
width directly from the triangles (ray casting at mid-height), compares it with the
manifest, and prints the CAD slot/tab clearance matrix. It exits with status 1 on any
mismatch. CAD values are design intent only: printed parts must be measured.
"""
from __future__ import annotations

import argparse
import csv
import struct
import sys
from collections import Counter
from pathlib import Path

CAD_DIR = Path(__file__).resolve().parent
STL_DIR = CAD_DIR / 'stl'
MANIFEST = CAD_DIR / 'print_manifest.csv'

COUPON_LENGTH = 60.0
COUPON_HEIGHT = 6.0
SLOT_BASE_LENGTH = 12.0
SLOT_RAIL_WIDTH = 6.0

# Same part names and widths as the `part` switch in qualityrelay_printkit.scad.
PARTS: dict[str, tuple[str, float, str]] = {
    'slot_good': ('slot', 21.20, 'slot_good_21p20'),
    'slot_nominal': ('slot', 21.00, 'slot_nominal_21p00'),
    'slot_risk': ('slot', 20.70, 'slot_risk_20p70'),
    'slot_defect': ('slot', 19.40, 'slot_defect_19p40'),
    'tab_good': ('tab', 19.80, 'tab_good_19p80'),
    'tab_nominal': ('tab', 20.00, 'tab_nominal_20p00'),
    'tab_risk': ('tab', 20.30, 'tab_risk_20p30'),
    'tab_defect': ('tab', 21.60, 'tab_defect_21p60'),
    'repeatability_bar': ('tab', 20.00, 'repeatability_bar_20p00'),
}

Vec = tuple[float, float, float]
Tri = tuple[Vec, Vec, Vec]


# --------------------------------------------------------------------------- geometry
def _prism(outline: list[tuple[float, float]], top: list[tuple[int, int, int]],
           height: float) -> list[Tri]:
    """Closed prism. `outline` is counter-clockwise seen from +Z and `top` triangulates
    it (counter-clockwise) using only outline vertices, so there are no T-junctions."""
    lo = [(x, y, 0.0) for x, y in outline]
    hi = [(x, y, height) for x, y in outline]
    tris: list[Tri] = []
    for a, b, c in top:
        tris.append((hi[a], hi[b], hi[c]))  # top face, normal +Z
        tris.append((lo[a], lo[c], lo[b]))  # bottom face, normal -Z
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        tris.append((lo[i], lo[j], hi[j]))  # side wall, outward normal
        tris.append((lo[i], hi[j], hi[i]))
    return tris


def slot_mesh(inner_width: float) -> list[Tri]:
    if not 5.0 < inner_width < 40.0:
        raise ValueError('implausible slot width')
    L, B, R, w = COUPON_LENGTH, SLOT_BASE_LENGTH, SLOT_RAIL_WIDTH, inner_width
    W = w + 2 * R
    outline = [(0, 0), (B, 0), (L, 0), (L, R), (B, R), (B, R + w), (L, R + w),
               (L, W), (B, W), (0, W)]
    top = [(0, 1, 4), (0, 4, 5), (0, 5, 8), (0, 8, 9),  # closed base, x = 0..12
           (1, 2, 3), (1, 3, 4),                        # rail at y = 0..6
           (5, 6, 7), (5, 7, 8)]                        # rail at y = 6 + w .. 12 + w
    return _prism([(float(x), float(y)) for x, y in outline], top, COUPON_HEIGHT)


def tab_mesh(width: float) -> list[Tri]:
    if not 5.0 < width < 40.0:
        raise ValueError('implausible tab width')
    outline = [(0.0, 0.0), (COUPON_LENGTH, 0.0), (COUPON_LENGTH, width), (0.0, width)]
    return _prism(outline, [(0, 1, 2), (0, 2, 3)], COUPON_HEIGHT)


def part_mesh(name: str) -> list[Tri]:
    kind, width, _ = PARTS[name]
    return slot_mesh(width) if kind == 'slot' else tab_mesh(width)


# --------------------------------------------------------------------------- STL io
def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normal(a: Vec, b: Vec, c: Vec) -> Vec:
    n = _cross(_sub(b, a), _sub(c, a))
    length = _dot(n, n) ** 0.5
    return (0.0, 0.0, 0.0) if length == 0 else (n[0] / length, n[1] / length, n[2] / length)


def _fmt(v: float) -> str:
    s = f'{v:.6f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def write_ascii_stl(path: Path, name: str, tris: list[Tri]) -> None:
    lines = [f'solid {name}']
    for a, b, c in tris:
        lines.append('  facet normal ' + ' '.join(_fmt(x) for x in _normal(a, b, c)))
        lines.append('    outer loop')
        for v in (a, b, c):
            lines.append('      vertex ' + ' '.join(_fmt(x) for x in v))
        lines.append('    endloop')
        lines.append('  endfacet')
    lines.append(f'endsolid {name}')
    path.write_text('\n'.join(lines) + '\n', encoding='ascii')


def read_stl(path: Path) -> list[Tri]:
    data = path.read_bytes()
    if data.lstrip().startswith(b'solid') and b'facet' in data[:2000]:
        verts = []
        for line in data.decode('ascii', errors='replace').splitlines():
            parts = line.split()
            if parts and parts[0] == 'vertex':
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
        if not verts or len(verts) % 3:
            raise ValueError(f'{path.name}: unreadable ASCII STL')
        return [(verts[i], verts[i + 1], verts[i + 2]) for i in range(0, len(verts), 3)]
    (count,) = struct.unpack_from('<I', data, 80)
    if len(data) != 84 + 50 * count:
        raise ValueError(f'{path.name}: unreadable binary STL')
    tris = []
    for k in range(count):
        v = struct.unpack_from('<12f', data, 84 + 50 * k)
        tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))
    return tris


# --------------------------------------------------------------------------- checks
def mesh_report(tris: list[Tri]) -> dict:
    """closed: every directed edge has a reverse partner (no holes, consistent winding).
    single_shell: additionally every edge belongs to exactly two triangles."""
    def key(v: Vec) -> tuple[float, float, float]:
        return (round(v[0], 6), round(v[1], 6), round(v[2], 6))

    directed: Counter = Counter()
    for a, b, c in tris:
        ka, kb, kc = key(a), key(b), key(c)
        for edge in ((ka, kb), (kb, kc), (kc, ka)):
            directed[edge] += 1
    closed = all(directed[(b, a)] == n for (a, b), n in directed.items())
    undirected: Counter = Counter()
    for (a, b), n in directed.items():
        undirected[frozenset((a, b))] += n
    single_shell = closed and all(n == 2 for n in undirected.values())
    volume = sum(_dot(a, _cross(b, c)) for a, b, c in tris) / 6.0
    xs, ys, zs = zip(*[v for t in tris for v in t])
    return {'triangles': len(tris), 'closed': closed, 'single_shell': single_shell,
            'volume_mm3': volume,
            'bbox_mm': (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))}


def _y_hits(tris: list[Tri], x: float, z: float) -> list[float]:
    """y coordinates where the line through (x, *, z) parallel to Y crosses the surface."""
    hits = []
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in tris:
        d = (bx - ax) * (cz - az) - (cx - ax) * (bz - az)
        if abs(d) < 1e-12:
            continue  # triangle is parallel to the line
        u = ((x - ax) * (cz - az) - (cx - ax) * (z - az)) / d
        v = ((bx - ax) * (z - az) - (x - ax) * (bz - az)) / d
        if u < 0 or v < 0 or u + v > 1:
            continue
        hits.append(ay + u * (by - ay) + v * (cy - ay))
    hits.sort()
    unique: list[float] = []
    for h in hits:
        if not unique or h - unique[-1] > 1e-7:
            unique.append(h)
    return unique


def critical_width(tris: list[Tri], kind: str) -> float:
    """Slot: gap between the rails. Tab/bar: full width. Measured at mid-height, at three
    positions along the part; the three values must agree (parallel faces)."""
    widths = []
    for x in (24.7013, 40.1237, 55.3109):  # inside the rail region, off any edge
        hits = _y_hits(tris, x, COUPON_HEIGHT / 2 + 0.0571)
        if len(hits) % 2:
            raise ValueError('open mesh: odd number of surface crossings')
        spans = [(hits[i], hits[i + 1]) for i in range(0, len(hits), 2)]
        if kind == 'slot':
            if len(spans) != 2:
                raise ValueError(f'expected two rails, found {len(spans)} solid spans')
            widths.append(spans[1][0] - spans[0][1])
        else:
            if len(spans) != 1:
                raise ValueError(f'expected one solid span, found {len(spans)}')
            widths.append(spans[0][1] - spans[0][0])
    if max(widths) - min(widths) > 1e-6:
        raise ValueError('critical faces are not parallel')
    return widths[0]


def _kind(part_type: str) -> str:
    return 'slot' if part_type.startswith('slot') else 'tab'


# --------------------------------------------------------------------------- commands
def cmd_write(names: list[str], force: bool) -> int:
    for name in names:
        if name not in PARTS:
            print(f'unknown part {name!r}; choose from: {", ".join(PARTS)}', file=sys.stderr)
            return 1
        kind, width, stem = PARTS[name]
        path = STL_DIR / f'{stem}.stl'
        if path.exists() and not force:
            print(f'{path.relative_to(CAD_DIR.parent.parent)} exists; not overwritten '
                  '(use --force)', file=sys.stderr)
            return 1
        tris = part_mesh(name)
        report = mesh_report(tris)
        measured = critical_width(tris, kind)
        if not report['closed'] or abs(measured - width) > 1e-6:
            print(f'{name}: generated mesh failed its own check', file=sys.stderr)
            return 1
        write_ascii_stl(path, stem, tris)
        print(f'wrote {path.relative_to(CAD_DIR.parent.parent)}: {kind} width {measured:.2f} mm, '
              f'{report["triangles"]} triangles, closed single shell, '
              f'volume {report["volume_mm3"]:.1f} mm3')
    return 0


def cmd_check() -> int:
    with MANIFEST.open(newline='') as f:
        rows = list(csv.DictReader(f))
    ok = True
    measured: dict[str, tuple[str, float]] = {}
    print(f'{"file":34} {"label":7} {"CAD mm":>7} {"STL mm":>7} {"closed":>6} '
          f'{"1 shell":>7} {"volume":>8}')
    for row in rows:
        path = CAD_DIR / row['file']
        kind = _kind(row['part_type'])
        cad = float(row['critical_cad_dimension_mm'])
        if not path.exists():
            print(f'{row["file"]:34} MISSING')
            ok = False
            continue
        tris = read_stl(path)
        rep = mesh_report(tris)
        width = critical_width(tris, kind)
        match = abs(width - cad) <= 0.005
        ok = ok and match and rep['closed']
        stem = path.stem
        for name, (pkind, pwidth, pstem) in PARTS.items():
            if pstem == stem:  # same solid volume as the SCAD parameters predict
                expected = mesh_report(part_mesh(name))['volume_mm3']
                if abs(expected - rep['volume_mm3']) > 1e-3:
                    ok = False
                    print(f'  volume differs from SCAD parameters for {name}')
        measured[row['manual_id']] = (row['part_type'], width)
        print(f'{row["file"]:34} {row["manual_id"]:7} {cad:7.2f} {width:7.2f} '
              f'{"yes" if rep["closed"] else "NO":>6} {"yes" if rep["single_shell"] else "no":>7} '
              f'{rep["volume_mm3"]:8.1f}{"" if match else "  <-- MISMATCH"}')
    slots = [(k, w) for k, (t, w) in measured.items() if t == 'slot_inner_width']
    tabs = [(k, w) for k, (t, w) in measured.items() if t == 'tab_width']
    print('\nCAD clearance = slot gap - tab width (mm); negative = interference, cannot fit')
    print(' ' * 8 + ''.join(f'{k:>9}' for k, _ in tabs))
    for sk, sw in slots:
        print(f'{sk:8}' + ''.join(f'{sw - tw:+9.2f}' for _, tw in tabs))
    print('\n"1 shell = no" means the file is several touching boxes (the original slot exports);'
          ' slicers merge them.')
    print('CAD values only. Measure the printed parts and fit-test them (bench test phase S).')
    return 0 if ok else 1


# --------------------------------------------------------------------------- SLA plate
FORMLABS_DIR = CAD_DIR / 'formlabs'
PLATE_STEM = 'qualityrelay_specimen_plate'
PLATE_GAP = 10.0  # mm between parts: room for supports, rafts and washing
# Rows of (label, part). Rows 1-3 are the 9 required specimens; row 4 holds optional spares.
PLATE_ROWS: list[list[tuple[str, str]]] = [
    [('S-GOOD', 'slot_good'), ('S-NOM', 'slot_nominal'), ('RPT-20', 'repeatability_bar')],
    [('S-RISK', 'slot_risk'), ('S-DEF', 'slot_defect'), ('T-DEF', 'tab_defect')],
    [('T-GOOD', 'tab_good'), ('T-NOM', 'tab_nominal'), ('T-RISK', 'tab_risk')],
    [('S-RISK-2', 'slot_risk'), ('T-RISK-2', 'tab_risk')],
]
# Smallest Formlabs build platforms (mm): Form 2/3/3+ 145 x 145; Form 4 200 x 125.
PLATFORM_LIMIT = (145.0, 125.0, 175.0)


def _outer_width(name: str) -> float:
    kind, width, _ = PARTS[name]
    return width + 2 * SLOT_RAIL_WIDTH if kind == 'slot' else width


def _upright(tris: list[Tri], ox: float, oy: float) -> list[Tri]:
    """Stand a part on its x = 0 end: (X, Y, Z) -> (Y + ox, Z + oy, X).

    A cyclic axis permutation is a proper rotation, so triangle winding stays outward.
    Slots end up with the closed base at the bottom and the opening at the top, so supports
    touch only the end face; the measured faces stay vertical and support-free."""
    return [tuple((v[1] + ox, v[2] + oy, v[0]) for v in t) for t in tris]  # type: ignore[misc]


def _from_upright(tris: list[Tri], ox: float, oy: float) -> list[Tri]:
    return [tuple((v[2], v[0] - ox, v[1] - oy) for v in t) for t in tris]  # type: ignore[misc]


def split_shells(tris: list[Tri]) -> list[list[Tri]]:
    """Group triangles into connected shells (shared vertices)."""
    parent: dict = {}

    def key(v: Vec) -> tuple[float, float, float]:
        return (round(v[0], 6), round(v[1], 6), round(v[2], 6))

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for t in tris:
        ka, kb, kc = key(t[0]), key(t[1]), key(t[2])
        ra = find(ka)
        for k in (kb, kc):
            rk = find(k)
            if rk != ra:
                parent[rk] = ra
    groups: dict = {}
    for t in tris:
        groups.setdefault(find(key(t[0])), []).append(t)
    return list(groups.values())


def plate_layout() -> list[dict]:
    placed = []
    for r, row in enumerate(PLATE_ROWS):
        x = 0.0
        y = r * (COUPON_HEIGHT + PLATE_GAP)
        for c, (label, name) in enumerate(row):
            w = _outer_width(name)
            kind, width, stem = PARTS[name]
            placed.append({'label': label, 'part': name, 'source_stl': f'stl/{stem}.stl', 'kind': kind,
                           'critical_width_mm': width, 'row': r + 1, 'position': c + 1,
                           'spare': r == len(PLATE_ROWS) - 1,
                           'x_min': x, 'x_max': x + w, 'y_min': y, 'y_max': y + COUPON_HEIGHT})
            x += w + PLATE_GAP
    return placed


def plate_map_svg(layout: list[dict]) -> str:
    s = 4.0  # px per mm
    width_mm = max(p['x_max'] for p in layout)
    depth_mm = max(p['y_max'] for p in layout)
    m, top = 30.0, 92.0
    W, H = width_mm * s + 2 * m + 170, depth_mm * s + top + 120
    X = lambda x: m + x * s                    # noqa: E731
    Y = lambda y: top + (depth_mm - y) * s     # noqa: E731  (+Y drawn upwards)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
           f'viewBox="0 0 {W:.0f} {H:.0f}" font-family="Arial, sans-serif">',
           f'<rect width="{W:.0f}" height="{H:.0f}" fill="#ffffff"/>',
           '<text x="30" y="26" font-size="16" font-weight="700">QualityRelay specimen plate: '
           'which part is which</text>',
           '<text x="30" y="44" font-size="11">Top view of qualityrelay_specimen_plate.stl, parts standing '
           'on end, scale 4 px = 1 mm.</text>',
           '<text x="30" y="58" font-size="11">Rows 1-3: the 9 required specimens. Row 4: optional spares.</text>']
    for p in layout:
        x0, x1, y0, y1 = X(p['x_min']), X(p['x_max']), Y(p['y_max']), Y(p['y_min'])
        fill = '#fde7c4' if p['spare'] else '#d8ecf3'
        if p['kind'] == 'slot':  # seen from above: the two rail ends of the U
            rail = SLOT_RAIL_WIDTH * s
            out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" '
                       'fill="none" stroke="#555" stroke-dasharray="3 2"/>')
            for rx in (x0, x1 - rail):
                out.append(f'<rect x="{rx:.1f}" y="{y0:.1f}" width="{rail:.1f}" height="{y1 - y0:.1f}" '
                           f'fill="{fill}" stroke="#222"/>')
        else:
            out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" '
                       f'fill="{fill}" stroke="#222"/>')
        cx = (x0 + x1) / 2
        out.append(f'<text x="{cx:.1f}" y="{y0 - 5:.1f}" font-size="12" font-weight="700" '
                   f'text-anchor="middle">{p["label"]}</text>')
        out.append(f'<text x="{cx:.1f}" y="{y1 + 12:.1f}" font-size="9" text-anchor="middle">'
                   f'{p["kind"]} {p["critical_width_mm"]:.2f}</text>')
    for r in range(len(PLATE_ROWS)):
        yc = Y(r * (COUPON_HEIGHT + PLATE_GAP) + COUPON_HEIGHT / 2)
        out.append(f'<text x="{X(width_mm) + 14:.1f}" y="{yc + 4:.1f}" font-size="11">row {r + 1}'
                   f'{" (spares)" if r == len(PLATE_ROWS) - 1 else ""}</text>')
    ax, ay = m, H - 40
    out += [f'<line x1="{ax}" y1="{ay}" x2="{ax + 40}" y2="{ay}" stroke="#222" stroke-width="2"/>',
            f'<text x="{ax + 44}" y="{ay + 4}" font-size="11">+X</text>',
            f'<line x1="{ax}" y1="{ay}" x2="{ax}" y2="{ay - 40}" stroke="#222" stroke-width="2"/>',
            f'<text x="{ax - 6}" y="{ay - 44}" font-size="11">+Y</text>',
            f'<text x="{ax + 80}" y="{ay - 8}" font-size="10">If your view is mirrored or rotated, or parts '
            'got mixed up: measure the critical width.</text>',
            f'<text x="{ax + 80}" y="{ay + 6}" font-size="10">Slots by gap: S-DEF &lt; S-RISK &lt; S-NOM &lt; '
            'S-GOOD.  Tabs by width: T-GOOD &lt; T-NOM = RPT-20 &lt; T-RISK &lt; T-DEF.</text>',
            '</svg>']
    return '\n'.join(out) + '\n'


def cmd_plate() -> int:
    layout = plate_layout()
    tris: list[Tri] = []
    for p in layout:
        tris += _upright(part_mesh(p['part']), p['x_min'], p['y_min'])
    shells = split_shells(tris)
    ok = len(shells) == len(layout)
    for p in layout:  # re-measure every placed part from the combined mesh
        mine = [t for t in tris if p['x_min'] - 1e-6 <= t[0][0] <= p['x_max'] + 1e-6
                and p['y_min'] - 1e-6 <= t[0][1] <= p['y_max'] + 1e-6]
        rep = mesh_report(mine)
        width = critical_width(_from_upright(mine, p['x_min'], p['y_min']), p['kind'])
        good = rep['single_shell'] and abs(width - p['critical_width_mm']) < 1e-6
        ok = ok and good
        print(f'{p["label"]:9} row {p["row"]} {p["kind"]:4} critical width {width:6.2f} mm  '
              f'single closed shell: {"yes" if rep["single_shell"] else "NO"}')
    xs, ys, zs = zip(*[v for t in tris for v in t])
    size = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    gaps = min(b['x_min'] - a['x_max'] for a, b in zip(layout, layout[1:]) if a['row'] == b['row'])
    fits = all(sz <= lim for sz, lim in zip(size, PLATFORM_LIMIT))
    ok = ok and fits
    print(f'{len(shells)} separate solids; plate {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm; '
          f'smallest gap {gaps:.1f} mm; fits a 145 x 125 mm platform: {"yes" if fits else "NO"}')
    if not ok:
        print('plate check failed; nothing written', file=sys.stderr)
        return 1
    FORMLABS_DIR.mkdir(exist_ok=True)
    write_ascii_stl(FORMLABS_DIR / f'{PLATE_STEM}.stl', PLATE_STEM, tris)
    with (FORMLABS_DIR / 'plate_layout.csv').open('w', newline='') as f:
        fields = ['label', 'part', 'source_stl', 'kind', 'critical_width_mm', 'row', 'position', 'spare',
                  'x_min', 'x_max', 'y_min', 'y_max']
        wr = csv.DictWriter(f, fieldnames=fields)
        wr.writeheader()
        for p in layout:
            wr.writerow({k: (f'{p[k]:.2f}' if isinstance(p[k], float) else p[k]) for k in fields})
    (FORMLABS_DIR / 'plate_map.svg').write_text(plate_map_svg(layout), encoding='utf-8')
    print(f'wrote examples/cad/formlabs/{PLATE_STEM}.stl, plate_layout.csv, plate_map.svg')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    w = sub.add_parser('write', help='generate STL files for the named parts')
    w.add_argument('parts', nargs='+')
    w.add_argument('--force', action='store_true', help='overwrite existing files')
    sub.add_parser('check', help='measure every STL in print_manifest.csv')
    sub.add_parser('plate', help='write one combined, upright SLA plate of all specimens + spares')
    args = parser.parse_args()
    if args.command == 'write':
        return cmd_write(args.parts, args.force)
    return cmd_plate() if args.command == 'plate' else cmd_check()


if __name__ == '__main__':
    sys.exit(main())
