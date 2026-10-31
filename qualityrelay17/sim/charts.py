"""SIM-07: static SVG charts for slides / the dashboard (no plotting dependency).

Palette: dataviz reference categorical slots 1-3, validated (light: all checks pass; slot 3
aqua is below 3:1 contrast -> every series is direct-labelled and a CSV table ships next to
each chart). Dark-mode steps are selected via prefers-color-scheme. Native <title> tooltips give
a per-mark hover. Every chart is captioned SIMULATED.
"""
from __future__ import annotations
from html import escape

STYLE = """<style>
.root{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a}
@media (prefers-color-scheme: dark){.root{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#3a3936;--s1:#3987e5;--s2:#d95926;--s3:#199e70}}
text{font-family:system-ui,-apple-system,Segoe UI,sans-serif;fill:var(--ink)}
.t2{fill:var(--ink2);font-size:11px}.t1{font-size:12px}.h{font-size:15px;font-weight:600}
.grid{stroke:var(--grid);stroke-width:1}.base{stroke:var(--ink2);stroke-width:1}
.s1{fill:var(--s1)}.s2{fill:var(--s2)}.s3{fill:var(--s3)}.l1{stroke:var(--s1)}.l2{stroke:var(--s2)}.l3{stroke:var(--s3)}
</style>"""


def _svg(w, h, body, title, caption):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="root" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(title)}">{STYLE}<rect width="{w}" height="{h}" style="fill:var(--bg)"/>'
            f'<text x="16" y="24" class="h">{escape(title)}</text>'
            f'<text x="16" y="{h - 10}" class="t2">{escape(caption)}</text>{body}</svg>')


def _ticks(lo, hi, n=5):
    span = hi - lo or 1
    raw = span / n
    mag = 10 ** len(str(int(raw))) / 10 if raw >= 1 else 0.1
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    t = (lo // step) * step
    out = []
    while t <= hi + 1e-9:
        out.append(round(t, 6)); t += step
    return out


def dot_plot(rows, series, title, x_label, caption, *, width=760):
    """rows: [(label, {series_key: value})]; series: [(key, display, slot)]. Horizontal dot plot."""
    top, left, right, row_h = 70, 250, 40, 24
    h = top + row_h * len(rows) + 60
    vals = [v for _, d in rows for v in d.values()]
    lo, hi = min(0, min(vals)), max(vals) * 1.08
    ticks = _ticks(lo, hi)
    hi = max(hi, ticks[-1])
    X = lambda v: left + (v - lo) / (hi - lo) * (width - left - right)  # noqa: E731
    b = []
    for t in ticks:
        b.append(f'<line class="grid" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 8}" y2="{top + row_h * len(rows)}"/>'
                 f'<text class="t2" x="{X(t):.1f}" y="{top + row_h * len(rows) + 16}" text-anchor="middle">{t:g}</text>')
    b.append(f'<text class="t2" x="{(left + width - right) / 2:.0f}" y="{top + row_h * len(rows) + 34}" text-anchor="middle">{escape(x_label)}</text>')
    lx = left
    for key, disp, slot in series:  # legend = direct labels at the top
        b.append(f'<circle class="s{slot}" cx="{lx + 5}" cy="46" r="5"/><text class="t1" x="{lx + 15}" y="50">{escape(disp)}</text>')
        lx += 15 + 7.2 * len(disp) + 24
    for i, (label, d) in enumerate(rows):
        y = top + row_h * i + row_h / 2
        b.append(f'<text class="t1" x="{left - 10}" y="{y + 4}" text-anchor="end">{escape(label)}</text>')
        xs = [X(d[k]) for k, _, _ in series if k in d]
        if len(xs) > 1:
            b.append(f'<line class="grid" x1="{min(xs):.1f}" x2="{max(xs):.1f}" y1="{y}" y2="{y}" style="stroke-width:2"/>')
        for key, disp, slot in series:
            if key in d:
                b.append(f'<circle class="s{slot}" cx="{X(d[key]):.1f}" cy="{y}" r="5" style="stroke:var(--bg);stroke-width:2">'
                         f'<title>{escape(label)} · {escape(disp)}: {d[key]:.1f}</title></circle>')
    return _svg(width, h, ''.join(b), title, caption)


def interval_plot(rows, title, x_label, caption, *, width=760):
    """rows: [(label, p05, p50, p95)] -- one series, zero reference line."""
    top, left, right, row_h = 56, 250, 40, 24
    h = top + row_h * len(rows) + 60
    lo = min(0, min(r[1] for r in rows)); hi = max(0, max(r[3] for r in rows))
    pad = 0.06 * (hi - lo or 1); lo -= pad; hi += pad
    ticks = _ticks(lo, hi)
    X = lambda v: left + (v - lo) / (hi - lo) * (width - left - right)  # noqa: E731
    b = []
    for t in ticks:
        if lo <= t <= hi:
            b.append(f'<line class="grid" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top - 8}" y2="{top + row_h * len(rows)}"/>'
                     f'<text class="t2" x="{X(t):.1f}" y="{top + row_h * len(rows) + 16}" text-anchor="middle">{t:g}</text>')
    b.append(f'<line class="base" x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{top - 8}" y2="{top + row_h * len(rows)}"/>')
    b.append(f'<text class="t2" x="{(left + width - right) / 2:.0f}" y="{top + row_h * len(rows) + 34}" text-anchor="middle">{escape(x_label)}</text>')
    for i, (label, p05, p50, p95) in enumerate(rows):
        y = top + row_h * i + row_h / 2
        b.append(f'<text class="t1" x="{left - 10}" y="{y + 4}" text-anchor="end">{escape(label)}</text>'
                 f'<line class="l1" x1="{X(p05):.1f}" x2="{X(p95):.1f}" y1="{y}" y2="{y}" style="stroke-width:2;stroke-linecap:round"/>'
                 f'<circle class="s1" cx="{X(p50):.1f}" cy="{y}" r="5" style="stroke:var(--bg);stroke-width:2">'
                 f'<title>{escape(label)}: median {p50:.1f}, 90% interval [{p05:.1f}, {p95:.1f}]</title></circle>')
    return _svg(width, h, ''.join(b), title, caption)


def bar_plot(rows, title, x_label, caption, *, width=760):
    """rows: [(label, value)] -- one series, horizontal bars anchored at 0, value labels."""
    top, left, right, row_h = 56, 250, 70, 30
    h = top + row_h * len(rows) + 60
    hi = max(v for _, v in rows) * 1.05
    X = lambda v: left + v / hi * (width - left - right)  # noqa: E731
    b = [f'<line class="base" x1="{left}" x2="{left}" y1="{top - 6}" y2="{top + row_h * len(rows)}"/>',
         f'<text class="t2" x="{(left + width - right) / 2:.0f}" y="{top + row_h * len(rows) + 30}" text-anchor="middle">{escape(x_label)}</text>']
    for i, (label, v) in enumerate(rows):
        y = top + row_h * i + 6
        b.append(f'<text class="t1" x="{left - 10}" y="{y + 13}" text-anchor="end">{escape(label)}</text>'
                 f'<rect class="s1" x="{left}" y="{y}" width="{max(2, X(v) - left):.1f}" height="16" rx="4">'
                 f'<title>{escape(label)}: {v:.1f}</title></rect>'
                 f'<text class="t1" x="{X(v) + 6:.1f}" y="{y + 13}">{v:.1f}</text>')
    return _svg(width, h, ''.join(b), title, caption)
