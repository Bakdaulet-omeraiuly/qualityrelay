"""3D Lab check: no two parts interpenetrate at any time of a run (assembled pairs excepted).

Needs the Studio running on 127.0.0.1:8000 and Playwright with Chrome:
    python scripts/check_3d_overlap.py
Samples 401 moments per run and intersects the parts' 3D bounding boxes (shrunk 12 mm*0.016).
"""
import time, sys
from playwright.sync_api import sync_playwright
JS = """(() => {
  const lab = window.__qrLab, v = lab.views[0]; lab.playing = false;
  let worst = 0, frames = 0, bad = 0, ex = null;
  for (let k = 0; k <= 400; k++) {
    const t = lab.t0 + (lab.T - lab.t0) * k / 400; v.update(t, 0, false, true);
    const vis = v.parts.filter((x) => x.m.visible).map((x) => { x.m.updateMatrixWorld(); x.m.geometry.computeBoundingBox();
      const b = x.m.geometry.boundingBox.clone().applyMatrix4(x.m.matrixWorld); b.expandByScalar(-0.012); return [x, b]; });
    let n = 0;
    for (let i = 0; i < vis.length; i++) for (let j = i + 1; j < vis.length; j++) {
      const [a, A] = vis[i], [c, B] = vis[j];
      const assembled = a.p.pair && a.p.pair === c.p.pair && a.p.kind !== c.p.kind && ((a.asmT !== null && t >= a.asmT) || (c.asmT !== null && t >= c.asmT));
      if (!assembled && A.intersectsBox(B)) { n++; if (!ex) ex = [t.toFixed(0), a.p.id, c.p.id, a.m.position.toArray().map(q=>q.toFixed(2)), c.m.position.toArray().map(q=>q.toFixed(2))]; }
    }
    frames++; if (n) bad++; worst = Math.max(worst, n);
  }
  return { frames, framesWithOverlap: bad, worstPairs: worst, example: ex };
})()"""
with sync_playwright() as p:
    bad = False
    b = p.chromium.launch(channel='chrome', headless=True, args=['--use-angle=metal','--enable-gpu'])
    for sc, seed, n in [('F01', 0, 60), ('F02', 1, 100), ('F03', 3, 100), ('F04', 2, 100), ('F05', 0, 150), ('M01', 0, 100), ('M05', 1, 100)]:
        pg = b.new_page(viewport={'width': 1200, 'height': 800})
        pg.goto(f'http://127.0.0.1:8000/?nolive=1&debug=1&scenario={sc}&seed={seed}&pairs={n}#lab'); time.sleep(5)
        r = pg.evaluate(JS); print(sc, r); bad = bad or r['framesWithOverlap'] > 0; pg.close()
    b.close()
sys.exit(1 if bad else 0)
