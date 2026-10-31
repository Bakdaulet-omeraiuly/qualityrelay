// QualityRelay Studio (18.1). Everything shown is SIMULATED.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { STLLoader } from 'three/addons/STLLoader.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/CSS2DRenderer.js';
import { RoomEnvironment } from 'three/addons/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/EffectComposer.js';
import { RenderPass } from 'three/addons/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/OutputPass.js';

// ---------------------------------------------------------------- utils
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const C = Object.fromEntries(['slot', 'tab', 'review', 'scrap', 'escape', 'caught', 'accent'].map((k) => [k, new THREE.Color(css(`--${k}`))]));
const BLACK = new THREE.Color(0x000000), LAMP_OFF = new THREE.Color(0x1d2026);
const fmt = (x, d = 1) => (x === null || x === undefined || Number.isNaN(+x)) ? '—' : (+x).toFixed(d);
const sign = (x, d = 1) => (x > 0 ? '+' : '') + fmt(x, d);
const pct = (x, d = 2) => x === null || x === undefined ? '—' : `${(100 * x).toFixed(d)}%`;
const mmss = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
const api = async (url, opts) => { const r = await fetch(url, opts); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); };
const hash = (s) => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return (h >>> 0) / 4294967295; };
const ease = (u) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);

// ---------------------------------------------------------------- STL
const stlLoader = new STLLoader();
const stlCache = new Map();
const loadSTL = (name) => {
  if (!stlCache.has(name)) stlCache.set(name, new Promise((res, rej) => stlLoader.load(`/sim/stl/${name}`, (g) => { g.computeVertexNormals(); res(g); }, undefined, rej)));
  return stlCache.get(name);
};
const metal = (color, o = {}) => new THREE.MeshStandardMaterial({ color, metalness: 0.2, roughness: 0.55, envMapIntensity: 0.45, ...o });

// ---------------------------------------------------------------- renderer stage (env light + bloom + labels)
function makeStage(el, { camPos = [0, 14, 18], target = [0, 0, 0], bloom = true, labels = true } = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.85;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  el.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07090c);
  scene.fog = new THREE.Fog(0x07090c, 38, 80);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 400);
  camera.position.set(...camPos);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(...target); controls.enableDamping = true; controls.dampingFactor = 0.08;
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(10, 22, 12); key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048); Object.assign(key.shadow.camera, { left: -26, right: 26, top: 20, bottom: -20 }); key.shadow.bias = -0.0005;
  scene.add(key, new THREE.HemisphereLight(0xbfd4ff, 0x15181d, 0.35));
  let composer = null;
  if (bloom) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(256, 256), 0.5, 0.4, 0.92));
    composer.addPass(new OutputPass());
  }
  let labelRenderer = null;
  if (labels) {
    labelRenderer = new CSS2DRenderer();
    Object.assign(labelRenderer.domElement.style, { position: 'absolute', inset: '0', pointerEvents: 'none' });
    el.appendChild(labelRenderer.domElement);
  }
  const resize = () => {
    const w = el.clientWidth, h = el.clientHeight; if (!w || !h) return;
    renderer.setSize(w, h); composer?.setSize(w, h); labelRenderer?.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(el); resize();
  let tween = null;
  return {
    el, renderer, scene, camera, controls, labelRenderer,
    flyTo(pos, tgt, dur = 1.3) {
      tween = { t0: performance.now(), dur: dur * 1000, p0: camera.position.clone(), q0: controls.target.clone(),
        p1: new THREE.Vector3(...pos), q1: new THREE.Vector3(...tgt) };
    },
    render() {
      if (tween) {
        const u = Math.min(1, (performance.now() - tween.t0) / tween.dur), e = ease(u);
        camera.position.lerpVectors(tween.p0, tween.p1, e); controls.target.lerpVectors(tween.q0, tween.q1, e);
        if (u >= 1) tween = null;
      }
      controls.update();
      if (composer) composer.render(); else renderer.render(scene, camera);
      labelRenderer?.render(scene, camera);
    },
  };
}
const ann = (text, cls = 'ann') => { const d = document.createElement('div'); d.className = cls; d.textContent = text; return new CSS2DObject(d); };

// ---------------------------------------------------------------- factory layout
const P = {
  printer_slot: [-14, -2.6], printer_tab: [-14, 2.6], phone: [-8.5, 0], pi: [-5.5, 0], caliper: [-2.5, 0],
  buffer: [1, 0], assembly: [4.5, 0], sorting: [7.5, 0], ship: [11.5, 0], review: [2.5, -6], rework: [6.5, -6], scrap: [11.5, -6],
  phone_local: [-5.5, 6], caliper_local: [-2.5, 6],
};
const STATION_INFO = {
  printer_slot: ['Slot printers', 'Print jobs of 4 parts (one lot). Width drift, warping and cracks are generated here; MTBF/MTTR failures.'],
  printer_tab: ['Tab printers', 'Print jobs of 4 parts (one lot). Kit-based CONWIP stops printing when the buffer is full.'],
  phone: ['Phone camera', 'First independent surface check. A missing reading is never treated as "clear".'],
  pi: ['Pi camera', 'Second independent surface check (edge device). It is unreachable during network partitions.'],
  caliper: ['Caliper + operator', 'Measures width (σ 0.05 mm). It shares the operator pool with review and rework.'],
  buffer: ['Pairing buffer', 'Slots and tabs wait here to be paired: FIFO, or risk-optimised by linear assignment (SciPy).'],
  assembly: ['Assembly', 'Assembles a pair only after the pair gate says PASS_REVIEW.'],
  sorting: ['Sorter', 'Sends assembled pairs to shipping.'],
  ship: ['Shipped', 'Shipped assemblies. Red marks a shipped defect (ground truth, evaluator only).'],
  review: ['Review (HOLD)', 'A held part or pair is re-checked by an expert (45 s, operator). It is released, reworked or scrapped.'],
  rework: ['Rework', 'Tab sanded to the design clearance (80% success).'],
  scrap: ['Scrap', 'Parts with confirmed defects, or failed rework.'],
  phone_local: ['Assembly-site camera', 'Used only when supplier evidence sharing is lost (scenario M03).'],
  caliper_local: ['Assembly-site caliper', 'Used only when supplier evidence sharing is lost (scenario M03).'],
};

class FactoryView {
  constructor(el, partGeo) {
    this.el = el; this.partGeo = partGeo;
    this.s = makeStage(el, { camPos: [-2, 30, 34], target: [-1.2, 0, -1.2] });
    this.s.controls.maxPolarAngle = Math.PI / 2.1; this.s.controls.minDistance = 6; this.s.controls.maxDistance = 70;
    this.parts = []; this.stations = {}; this.labels = []; this.readouts = {}; this.selected = null; this.data = null;
    this.build();
  }
  build() {
    const sc = this.s.scene;
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(200, 160), new THREE.MeshStandardMaterial({ color: 0x0b0e12, roughness: 0.95, metalness: 0.0, envMapIntensity: 0.2 }));
    floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; sc.add(floor);
    const grid = new THREE.GridHelper(80, 80, 0x1e252e, 0x151a20); grid.position.y = 0.005; sc.add(grid);
    // floor markings: zone pads and yellow safety lines along the walkway
    const pad = (x, z, w, d, c) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshStandardMaterial({ color: c, roughness: 1 })); m.rotation.x = -Math.PI / 2; m.position.set(x, 0.008, z); m.receiveShadow = true; sc.add(m); };
    pad(-14, 0, 4.4, 8.6, 0x121821); pad(-5.5, 0, 9, 3.6, 0x111720); pad(6, 0, 12, 3.6, 0x111720); pad(5.5, -6, 12, 4.2, 0x16140f);
    const dash = new THREE.MeshBasicMaterial({ color: 0x8a6d00 });
    for (const z of [-1.75, 1.75]) for (let x = -12; x < 13; x += 1.2) { const d = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.07), dash); d.rotation.x = -Math.PI / 2; d.position.set(x, 0.012, z); sc.add(d); }
    const cv = document.createElement('canvas'); cv.width = 256; cv.height = 32; const g = cv.getContext('2d');
    g.fillStyle = '#1b2129'; g.fillRect(0, 0, 256, 32); g.fillStyle = '#28303a'; for (let i = 0; i < 256; i += 16) g.fillRect(i, 0, 6, 32);
    this.beltTex = new THREE.CanvasTexture(cv); this.beltTex.wrapS = THREE.RepeatWrapping; this.beltTex.repeat.set(12, 1); this.beltTex.colorSpace = THREE.SRGBColorSpace;
    const side = metal(0x2a313a);
    const belt = new THREE.Mesh(new THREE.BoxGeometry(23, 0.14, 1.4), [side, side, new THREE.MeshStandardMaterial({ map: this.beltTex, roughness: 0.7 }), side, side, side]);
    belt.position.set(-1.5, 0.07, 0); belt.receiveShadow = true; sc.add(belt);
    for (const z of [-0.78, 0.78]) { const rail = new THREE.Mesh(new THREE.BoxGeometry(23, 0.08, 0.06), metal(0x4b5562, { metalness: 0.8, roughness: 0.25 })); rail.position.set(-1.5, 0.18, z); sc.add(rail); }
    const box = (key, w, d, h, color) => {
      const [x, z] = P[key];
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), metal(color)); m.position.set(x, h / 2, z);
      m.castShadow = m.receiveShadow = true; m.userData = { station: key }; sc.add(m);
      const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 12), new THREE.MeshStandardMaterial({ color: LAMP_OFF, emissive: BLACK }));
      lamp.position.set(x + w / 2 - 0.2, h + 0.12, z - d / 2 + 0.2); sc.add(lamp);
      const l = ann(STATION_INFO[key][0]); l.position.set(x, h + 0.55, z); sc.add(l); this.labels.push(l);
      this.stations[key] = { mesh: m, lamp, label: l, intervals: [] };
    };
    box('printer_slot', 2.3, 2.1, 2.2, 0x3f5a7a); box('printer_tab', 2.3, 2.1, 2.2, 0x7d4f3a);
    for (const k of ['printer_slot', 'printer_tab']) {
      const [x, z] = P[k]; const win = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 0.9), new THREE.MeshStandardMaterial({ color: 0x0a0d10, emissive: 0x24361c, emissiveIntensity: 0.8 }));
      win.position.set(x + 1.16, 1.25, z); win.rotation.y = Math.PI / 2; sc.add(win);
    }
    const cam = (key) => {
      const [x, z] = P[key]; box(key, 0.35, 0.35, 2.4, 0x59636f);
      const arm = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 1.1), metal(0x59636f)); arm.position.set(x, 2.35, z + 0.45); sc.add(arm);
      const head = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.42, 0.55), metal(0x1d2127, { metalness: 0.6 })); head.position.set(x, 2.35, z + 0.95); sc.add(head);
      const lens = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.12, 24), new THREE.MeshStandardMaterial({ color: 0x0b0d10, emissive: C.accent, emissiveIntensity: 0.15 }));
      lens.position.set(x, 2.12, z + 0.95); sc.add(lens);
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.75, 2.0, 32, 1, true), new THREE.MeshBasicMaterial({ color: C.accent, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
      cone.position.set(x, 1.1, z + 0.45); sc.add(cone);
      Object.assign(this.stations[key], { lens, cone });
    };
    cam('phone'); cam('pi');
    box('caliper', 1.6, 1.3, 1.05, 0x66717e);
    this.jaws = [-1, 1].map((sgn) => { const j = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.7, 1.0), metal(0x9aa3ad, { metalness: 0.8, roughness: 0.3 })); j.position.set(P.caliper[0] + sgn * 0.3, 1.4, 0); sc.add(j); return j; });
    box('buffer', 1.9, 2.4, 0.35, 0x37414d); box('assembly', 2.0, 1.8, 1.25, 0x52687e); box('sorting', 1.6, 1.6, 0.85, 0x4a5867);
    box('ship', 2.8, 2.8, 0.22, 0x235c34); box('review', 2.4, 2.0, 0.95, 0x7a6418); box('rework', 2.0, 1.8, 0.95, 0x574c66); box('scrap', 2.8, 2.8, 0.22, 0x5e2a2a);
    box('phone_local', 0.35, 0.35, 1.6, 0x59636f); box('caliper_local', 1.4, 1.2, 0.9, 0x66717e);
    for (const k of ['caliper', 'phone', 'pi']) { const r = ann('', 'readout'); r.position.set(P[k][0], k === 'caliper' ? 2.3 : 3.1, P[k][1]); r.visible = false; sc.add(r); this.readouts[k] = r; }
    this.ring = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.035, 8, 48), new THREE.MeshStandardMaterial({ color: C.accent, emissive: C.accent, emissiveIntensity: 1.6 }));
    this.ring.rotation.x = Math.PI / 2; this.ring.visible = false; sc.add(this.ring);
    this.stationRing = new THREE.Mesh(new THREE.RingGeometry(1.7, 1.8, 64), new THREE.MeshBasicMaterial({ color: C.accent, side: THREE.DoubleSide }));
    this.stationRing.rotation.x = -Math.PI / 2; this.stationRing.visible = false; sc.add(this.stationRing);
  }
  setLabels(on) { for (const [k, s] of Object.entries(this.stations)) s.label.visible = on && !s.hiddenStation; }

  load(data, caughtIds = new Set()) {
    const sc = this.s.scene; this.parts.forEach((x) => sc.remove(x.m)); this.parts = []; this.data = data;
    const bins = { shipped: 0, scrap: 0 };
    for (const st of Object.values(this.stations)) st.intervals = [];
    for (const p of data.parts) {
      const kf = pathFor(p, p.fate === 'shipped' ? bins.shipped++ : p.fate === 'scrap' ? bins.scrap++ : 0);
      const mat = new THREE.MeshPhysicalMaterial({ color: p.kind === 'slot' ? C.slot : C.tab, roughness: 0.38, metalness: 0.05, clearcoat: 0.6, clearcoatRoughness: 0.3 });
      const m = new THREE.Mesh(this.partGeo[p.kind], mat); m.castShadow = true; m.visible = false; m.userData = { part: p.id }; sc.add(m);
      const review = p.events.filter((e) => e[0] === 'review').map((e) => [e[1], e[2]]);
      for (const [stn, a, b] of p.events) this.stations[stn]?.intervals.push([a, b, p]);
      const endT = kf[kf.length - 1][0];
      this.parts.push({ p, kf, m, review, endT, shipT: p.fate === 'shipped' ? endT : null, scrapT: p.fate === 'scrap' ? endT : null,
        caught: caughtIds.has(p.id), yaw: (hash(p.id) - 0.5) * 0.5 });
    }
    const local = data.parts.some((p) => p.events.some((e) => e[0].endsWith('_local')));
    for (const k of ['phone_local', 'caliper_local']) { const s = this.stations[k]; s.mesh.visible = s.lamp.visible = local; s.hiddenStation = !local; }
    this.T = Math.max(...this.parts.map((x) => x.endT)) + 5;
    this.t0 = Math.max(0, Math.min(...this.parts.map((x) => x.kf[0][0])) - 2);
  }

  update(t, dtReal, playing, truth) {
    if (!this.data) return { ship: 0, hold: 0, scrap: 0, esc: 0 };
    if (playing) this.beltTex.offset.x -= dtReal * 0.6;
    let ship = 0, hold = 0, scrap = 0, esc = 0; const shipped = new Set(); let selVisible = false;
    for (const x of this.parts) {
      const xy = at(x.kf, t); x.m.visible = !!xy; if (!xy) continue;
      const inReview = x.review.some(([a, b]) => t >= a && t <= b);
      const stacked = x.p.kind === 'tab' && x.shipT && t >= x.shipT;
      x.m.position.set(xy[0], 0.22 + (stacked ? 0.11 : 0) + xy[2], xy[1]); x.m.rotation.y = x.yaw;
      const mat = x.m.material; let col = x.p.kind === 'slot' ? C.slot : C.tab, em = BLACK, ei = 0;
      if (inReview) { col = C.review; em = C.review; ei = 0.35; }
      if (x.scrapT && t >= x.scrapT) col = C.scrap;
      if (x.caught && ((x.review.length && t >= x.review[0][0]) || (x.shipT && t >= x.shipT) || (x.scrapT && t >= x.scrapT))) { em = C.caught; ei = 0.7; }
      if (truth && x.p.escaped && x.shipT && t >= x.shipT) { col = C.escape; em = C.escape; ei = 0.9; }
      mat.color.copy(col); mat.emissive.copy(em); mat.emissiveIntensity = ei;
      if (x.review.length && t >= x.review[0][0]) hold++;
      if (x.scrapT && t >= x.scrapT) scrap++;
      if (x.shipT && t >= x.shipT && x.p.pair && !shipped.has(x.p.pair)) { shipped.add(x.p.pair); if (x.p.escaped) esc++; else ship++; }
      if (this.selected === x.p.id) { selVisible = true; this.ring.position.set(x.m.position.x, 0.08, x.m.position.z); }
    }
    this.ring.visible = selVisible;
    for (const [k, st] of Object.entries(this.stations)) {
      const cur = st.intervals.find(([a, b]) => t >= a && t <= b);
      const busyCol = k === 'review' ? C.review : C.accent;
      st.lamp.material.emissive.copy(cur ? busyCol : BLACK); st.lamp.material.emissiveIntensity = cur ? 2.2 : 0;
      st.lamp.material.color.copy(cur ? busyCol : LAMP_OFF);
      if (st.cone) { st.cone.material.opacity = cur ? 0.12 : 0; st.lens.material.emissiveIntensity = cur ? 2.0 : 0.15; }
      const r = this.readouts[k];
      if (r) {
        r.visible = !!cur;
        if (cur) {
          const p = cur[2];
          if (k === 'caliper') { r.element.textContent = `${fmt(p.measured_mm, 3)} mm`; r.element.style.background = ''; }
          else { const v = p.cams?.[k]; r.element.textContent = v === null || v === undefined ? '— missing' : v ? '⚑ flagged' : '✔ clear'; r.element.style.background = v ? css('--review') : (v === null ? css('--scrap') : ''); }
        }
      }
    }
    const cb = this.stations.caliper.intervals.find(([a, b]) => t >= a && t <= b);
    const gap = cb ? 0.17 : 0.3; this.jaws[0].position.x = P.caliper[0] - gap; this.jaws[1].position.x = P.caliper[0] + gap;
    return { ship, hold, scrap, esc };
  }

  pick(ev) {
    const rect = this.s.renderer.domElement.getBoundingClientRect();
    const nd = new THREE.Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    const rc = new THREE.Raycaster(); rc.setFromCamera(nd, this.s.camera);
    const hit = rc.intersectObjects(this.parts.filter((x) => x.m.visible).map((x) => x.m), false)[0];
    if (hit) return { type: 'part', id: hit.object.userData.part };
    const h2 = rc.intersectObjects(Object.values(this.stations).filter((s) => !s.hiddenStation).map((s) => s.mesh), false)[0];
    return h2 ? { type: 'station', id: h2.object.userData.station } : null;
  }
  select(sel) {
    this.selected = sel?.type === 'part' ? sel.id : null;
    Object.values(this.stations).forEach((s) => s.label.element.classList.remove('sel'));
    if (sel?.type === 'station') {
      const [x, z] = P[sel.id]; this.stationRing.position.set(x, 0.02, z); this.stationRing.visible = true;
      this.stations[sel.id].label.element.classList.add('sel');
    } else this.stationRing.visible = false;
  }
}

function pathFor(p, binIndex) {
  const kf = [], j = hash(p.id), jz = (j - 0.5) * 0.9;
  const pos = (k, dx = 0, dz = 0) => { const [x, z] = P[k] || P.buffer; return [x + dx, z + dz]; };
  const pr = p.kind === 'slot' ? 'printer_slot' : 'printer_tab';
  const first = p.events.length ? p.events[0][1] : p.print_t + 60;
  const out = Math.max(p.print_t, first - 25);
  kf.push([out, ...pos(pr, 1.7, jz * 0.8)]);
  let prevEnd = out + 2, prevKey = pr;
  kf.push([prevEnd, ...pos(pr, 1.7, jz * 0.8)]);
  for (const [station, start, end] of p.events) {
    const travel = Math.min(8, Math.max(0.5, start - prevEnd));
    const arrive = Math.max(prevEnd, Math.min(start, prevEnd + travel));
    kf.push([prevEnd, ...pos(prevKey, prevKey.startsWith('printer') ? 1.7 : 0, prevKey.startsWith('printer') ? jz * 0.8 : jz * 0.25)]);
    if (start - arrive > 1) kf.push([arrive, ...pos(station, -1.15, jz)], [start - 0.5, ...pos(station, -0.95, jz)]);
    kf.push([start, ...pos(station, 0, jz * 0.25)], [end, ...pos(station, 0, jz * 0.25)]);
    prevEnd = end; prevKey = station;
  }
  const last = kf[kf.length - 1][0];
  const binPos = (k) => { const [x, z] = P[k]; const i = binIndex; return [x - 1.05 + (i % 6) * 0.42, z - 1.05 + (Math.floor(i / 6) % 6) * 0.42]; };
  if (p.fate === 'shipped') kf.push([last + 4, ...binPos('ship')]);
  else if (p.fate === 'scrap') kf.push([last + 4, ...binPos('scrap')]);
  else kf.push([last + 4, ...pos('buffer', (j - 0.5) * 1.2, jz)]);
  return kf;
}
function at(kf, t) {
  if (t < kf[0][0]) return null;
  for (let i = 1; i < kf.length; i++) if (t <= kf[i][0]) {
    const [t0, x0, z0] = kf[i - 1], [t1, x1, z1] = kf[i]; const u = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
    const moving = Math.hypot(x1 - x0, z1 - z0) > 0.5;
    return [x0 + (x1 - x0) * u, z0 + (z1 - z0) * u, moving ? Math.sin(Math.PI * u) * 0.15 : 0];
  }
  const l = kf[kf.length - 1]; return [l[1], l[2], 0];
}

// ---------------------------------------------------------------- lab controller
const STORY = [
  ['Overview', 'One simulated shift of the Slot/Tab line. Each moving part is one simulated part from the discrete-event engine.', [-2, 23, 25.5], [-1.4, 0, -1.6]],
  ['Printers', 'Slots and tabs are printed in lots of 4. Width drift, warping and cracks are generated here; printers fail and get repaired (MTBF/MTTR).', [-19, 5, 7], [-14, 1, 0]],
  ['Two cameras', 'Phone and Pi cameras check the surface independently. The readout shows each result. A missing reading is never a "clear".', [-11, 4.5, 6], [-7, 1.5, 0]],
  ['Caliper', 'An operator measures the width. The calibrated policy turns the reading into a posterior. Click any part to see its evidence chain.', [-4, 3.5, 4.5], [-2.5, 1, 0]],
  ['Pairing and gate', 'Risk-optimised pairing picks partners (SciPy linear assignment). The pair gate still decides: P(unsafe) ≥ 1.32% means HOLD, whatever pairing saves.', [0, 6, 7], [2.5, 0.5, -0.5]],
  ['Review (HOLD)', 'Held parts go to review (45 s, shared operator). Holding everything looks "safe and cheap" on paper but cuts throughput by 82%.', [3, 6, 0], [3.5, 0.5, -5]],
  ['Shipped', 'Turn on ground truth: a red part is a shipped defect. In Compare mode, purple parts are defects the rule shipped and QualityRelay stopped.', [9, 6, 6], [11, 0, -2]],
];
const lab = { mode: 'single', views: [], runs: [], t: 0, T: 1, t0: 0, playing: true, speed: 60, sel: null, story: -1, caught: new Set() };

async function initLab() {
  const [sg, tg] = await Promise.all([loadSTL('slot_nominal_21p00.stl'), loadSTL('tab_nominal_20p00.stl')]);
  const prep = (g) => { const c = g.clone(); c.rotateX(-Math.PI / 2); c.center(); c.scale(0.016, 0.016, 0.016); return c; };
  const partGeo = { slot: prep(sg), tab: prep(tg) };
  lab.views = [new FactoryView($('#vpA'), partGeo), new FactoryView($('#vpB'), partGeo)];
  const sc = await api('/sim/scenarios');
  $('#scenario').innerHTML = ['single-site', 'multi-site'].map((g) => `<optgroup label="${g}">${sc.filter((s) => s.group === g).map((s) => `<option value="${s.sid}">${s.sid} · ${s.title}</option>`).join('')}</optgroup>`).join('');
  $$('#modeSeg button').forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
  $('#runBtn').onclick = run;
  $('#demoBtn').onclick = async () => { $('#scenario').value = 'F03'; $('#seed').value = 3; $('#npairs').value = 100; $('#policy').value = 'bayes'; $('#pairing').value = 'optimized'; $('#truth').checked = true; await run(); };
  $('#playBtn').onclick = togglePlay;
  $('#timeline').oninput = (e) => { lab.t = lab.t0 + (lab.T - lab.t0) * e.target.value / 1000; lab.playing = false; $('#playBtn').textContent = '▶'; };
  $('#speed').onchange = (e) => (lab.speed = +e.target.value);
  $('#labels').onchange = () => lab.views.forEach((v) => v.setLabels($('#labels').checked));
  $('#truth').onchange = () => renderInspector();
  $('#storyNext').onclick = () => story(lab.story + 1); $('#storyPrev').onclick = () => story(lab.story - 1);
  $('#toggleInspector').onclick = () => $('#studio').classList.toggle('noinsp');
  lab.views.forEach((v, i) => bindPicking(v, i));
  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'SELECT'].includes(document.activeElement?.tagName) || $('#view-lab').hidden) return;
    if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
    else if (e.key === 'l' || e.key === 'L') { $('#labels').checked = !$('#labels').checked; $('#labels').onchange(); }
    else if (e.key === 't' || e.key === 'T') { $('#truth').checked = !$('#truth').checked; renderInspector(); }
    else if (e.key === 'i' || e.key === 'I') $('#studio').classList.toggle('noinsp');
    else if (e.key === 'ArrowRight') story(lab.story + 1);
    else if (e.key === 'ArrowLeft') story(lab.story - 1);
  });
  let last = performance.now();
  const loop = (now) => {
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    if (!$('#view-lab').hidden) {
      if (lab.runs.length) {
        if (lab.playing) { lab.t += dt * lab.speed; if (lab.t > lab.T) lab.t = lab.t0; $('#timeline').value = Math.round(1000 * (lab.t - lab.t0) / Math.max(1, lab.T - lab.t0)); }
        $('#clock').textContent = mmss(lab.t);
        const truth = $('#truth').checked;
        lab.runs.forEach((r, i) => {
          const c = lab.views[i].update(lab.t, dt, lab.playing, truth);
          $(i ? '#countB' : '#countA').innerHTML = `<span><i>good</i><b>${c.ship}</b></span><span><i>held</i><b>${c.hold}</b></span><span><i>scrap</i><b>${c.scrap}</b></span><span><i>escaped</i><b style="color:var(--escape)">${truth ? c.esc : '—'}</b></span>`;
        });
      }
      lab.views.forEach((v, i) => { if (i === 0 || lab.mode === 'compare') v.s.render(); });
    }
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
  const q = new URLSearchParams(location.search);
  if (q.get('scenario')) $('#scenario').value = q.get('scenario');
  for (const k of ['policy', 'pairing']) if (q.get(k)) $(`#${k}`).value = q.get(k);
  if (q.get('seed')) $('#seed').value = q.get('seed'); if (q.get('pairs')) $('#npairs').value = q.get('pairs');
  if (q.get('mode') === 'compare') await setMode('compare'); else await run();
  lab.views.forEach((v) => v.s.flyTo(fitCam(v, STORY[0][2], STORY[0][3]), STORY[0][3], 2.6));
  if (q.get('select') === 'caught') { const id = [...lab.caught][0] || lab.runs.at(-1)?.parts.find((p) => p.pair)?.id; if (id) select({ type: 'part', id, side: lab.runs.length - 1 }); }
}

function bindPicking(v, side) {
  const el = v.s.renderer.domElement; let down = null;
  const tip = document.createElement('div'); tip.className = 'tip'; tip.hidden = true; document.body.appendChild(tip);
  el.addEventListener('pointerdown', (e) => (down = [e.clientX, e.clientY]));
  el.addEventListener('pointerup', (e) => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
    const hit = v.pick(e); select(hit ? { ...hit, side } : null);
  });
  let lastMove = 0;
  el.addEventListener('pointermove', (e) => {
    if (performance.now() - lastMove < 60) return; lastMove = performance.now();
    const hit = v.pick(e); el.style.cursor = hit ? 'pointer' : '';
    if (hit) { tip.hidden = false; tip.style.left = `${e.clientX + 12}px`; tip.style.top = `${e.clientY + 10}px`; tip.textContent = hit.type === 'part' ? hit.id : STATION_INFO[hit.id][0]; }
    else tip.hidden = true;
  });
  el.addEventListener('pointerleave', () => (tip.hidden = true));
}

// Narrow viewports (compare mode) need the camera further back to show the whole line.
function fitCam(v, cam, tgt) {
  const a = v.s.el.clientWidth / Math.max(1, v.s.el.clientHeight), f = Math.min(1.45, Math.max(1, 1.3 / a));
  return cam.map((c, i) => tgt[i] + (c - tgt[i]) * f);
}
function select(sel) { lab.sel = sel; lab.views.forEach((v) => v.select(sel)); renderInspector(); }
function togglePlay() { lab.playing = !lab.playing; $('#playBtn').textContent = lab.playing ? '❚❚' : '▶'; }
async function setMode(m) {
  lab.mode = m; $$('#modeSeg button').forEach((b) => b.classList.toggle('on', b.dataset.mode === m));
  $('#vpB').hidden = m !== 'compare'; $('#viewports').classList.toggle('compare', m === 'compare');
  $('#compareHint').hidden = m !== 'compare'; $('#policyLabel').textContent = m === 'compare' ? 'Right side: decision policy' : 'Decision policy';
  $('#labels').checked = m !== 'compare';  // two viewports: labels off by default (toggle with L)
  await run();
  lab.views.forEach((v) => v.s.flyTo(fitCam(v, STORY[0][2], STORY[0][3]), STORY[0][3], 1.2));
}
function story(i) {
  if (i < 0) i = 0; if (i >= STORY.length) i = 0;
  lab.story = i; const [title, text, cam, tgt] = STORY[i];
  $('#storyStep').textContent = `${i + 1} / ${STORY.length}`; $('#storyText').innerHTML = `<b>${title}.</b> ${text}`;
  $('#storyNext').textContent = i === STORY.length - 1 ? 'Restart ▶' : 'Next ▶';
  lab.views.forEach((v) => v.s.flyTo(fitCam(v, cam, tgt), tgt));
  if (i === STORY.length - 1) $('#truth').checked = true;
}

async function run() {
  const btn = $('#runBtn'); btn.disabled = true; $('#runStatus').textContent = 'Running the discrete-event engine…';
  const base = { scenario: $('#scenario').value || 'F01', seed: +$('#seed').value, n_pairs: +$('#npairs').value };
  const right = { ...base, policy: $('#policy').value, pairing: $('#pairing').value };
  const cfgs = lab.mode === 'compare' ? [{ ...base, policy: 'rules', pairing: 'fifo' }, right] : [right];
  try {
    const t0 = performance.now();
    lab.runs = await Promise.all(cfgs.map((c) => api('/sim/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(c) })));
    lab.caught = new Set();
    if (lab.runs.length === 2) {
      const escL = new Set(lab.runs[0].parts.filter((p) => p.escaped).map((p) => p.id));
      for (const p of lab.runs[1].parts) if (escL.has(p.id) && !p.escaped) lab.caught.add(p.id);
    }
    lab.runs.forEach((r, i) => lab.views[i].load(r, i === 1 ? lab.caught : new Set()));
    lab.views.forEach((v) => v.setLabels($('#labels').checked));
    const active = lab.views.slice(0, lab.runs.length);
    lab.T = Math.max(...active.map((v) => v.T)); lab.t0 = Math.min(...active.map((v) => v.t0)); lab.t = lab.t0;
    lab.playing = true; $('#playBtn').textContent = '❚❚';
    const name = (r) => (r.policy === 'rules' ? 'TODAY · rule' : r.policy === 'hold_all' ? 'HOLD ALL' : 'QUALITYRELAY');
    lab.runs.forEach((r, i) => {
      $(i ? '#titleB' : '#titleA').textContent = `${name(r)} · ${r.pairing === 'fifo' ? 'FIFO' : 'risk pairing'}`;
      $(i ? '#provB' : '#provA').textContent = `SIMULATED · ${r.scenario} · seed ${r.seed} · ${r.n_pairs} pairs · conservation ${r.kpis.conservation_ok ? '✔' : '✖'}`;
    });
    const r = lab.runs[lab.runs.length - 1];
    $('#context').textContent = `${r.scenario} · ${r.title} · seed ${r.seed} · ${r.n_pairs} pairs${lab.mode === 'compare' ? ' · compare' : ` · ${r.policy}+${r.pairing}`}`;
    $('#runStatus').textContent = `${lab.runs.length} run${lab.runs.length > 1 ? 's' : ''} computed in ${fmt(performance.now() - t0, 0)} ms`;
    renderMetrics(); select(null);
  } catch (e) { $('#runStatus').textContent = `Simulation API unavailable: ${e.message}`; }
  btn.disabled = false;
}

function renderMetrics() {
  const K = lab.runs.map((r) => r.kpis);
  const rows = [['good / hour', (k) => k.good_per_hour, 1, +1], ['shipped good', (k) => k.shipped_good, 0, +1], ['escaped', (k) => k.escaped, 0, -1],
    ['holds part / pair', (k) => k.part_holds + k.pair_holds, 0, -1], ['scrapped parts', (k) => k.scrapped_parts, 0, -1], ['mean cycle (min)', (k) => k.mean_cycle_s / 60, 1, -1]];
  $('#metrics').innerHTML = rows.map(([n, f, d, good]) => {
    if (K.length === 1) return `<div><small>${n}</small><b>${fmt(f(K[0]), d)}</b></div>`;
    const a = f(K[0]), b = f(K[1]), dlt = b - a, cls = Math.abs(dlt) < 1e-9 ? '' : (dlt * good > 0 ? 'up' : 'down');
    return `<div><small>${n}</small><b>${fmt(a, d)} → ${fmt(b, d)}</b><em class="${cls}">${Math.abs(dlt) < 1e-9 ? '±0' : sign(dlt, d)}</em></div>`;
  }).join('');
  if (K.length === 2) $('#metrics').insertAdjacentHTML('afterbegin', '<div class="lead">today →<br>QualityRelay</div>');
}

// ---------------------------------------------------------------- inspector
const findPart = (id, side) => lab.runs[side]?.parts.find((p) => p.id === id);
const findPair = (id, side) => lab.runs[side]?.pairs.find((q) => q.pair_id === id);
const camTxt = (v) => (v === null || v === undefined ? '<span class="badge hold">missing</span>' : v ? '<span class="badge hold">⚑ flagged</span>' : '<span class="badge ok">✔ clear</span>');
const STN = Object.fromEntries(Object.entries(STATION_INFO).map(([k, v]) => [k, v[0]]));

function partCard(p, side, truth) {
  const run = lab.runs[side], pair = p.pair ? findPair(p.pair, side) : null;
  const fate = p.fate === 'shipped' ? (truth && p.escaped ? '<span class="badge bad">shipped · DEFECT (truth)</span>' : '<span class="badge ok">shipped</span>')
    : p.fate === 'scrap' ? '<span class="badge mute">scrapped</span>' : '<span class="badge mute">unpaired at end of run</span>';
  const partner = pair ? (p.kind === 'slot' ? pair.tab : pair.slot) : null;
  let decision = '';
  if (pair) {
    const verdict = pair.decision === 'HOLD' ? '<span class="badge hold">HOLD</span>' : '<span class="badge ok">PASS_REVIEW</span>';
    let why;
    if (pair.reason === 'STALE_OR_MISSING_EVIDENCE') why = 'Supplier evidence arrived after the 120 s deadline. SAFE-MESH holds stale or missing evidence.';
    else if (run.policy === 'rules') why = `Rule: measured clearance <b>${fmt(pair.measured_clearance_mm, 3)} mm</b> ${pair.measured_clearance_mm >= 0.5 ? '≥' : '<'} 0.50 mm, and no camera flag on either part.`;
    else if (run.policy === 'hold_all') why = 'This policy sends every part to review first, then applies the rule.';
    else why = `P(unsafe) = 1 − (1−P<sub>surf,slot</sub>)(1−P<sub>surf,tab</sub>)(1−P<sub>dim</sub>) = <b>${pct(pair.p_unsafe, 3)}</b> ${pair.p_unsafe >= pair.threshold ? '≥' : '<'} threshold <b>${pct(pair.threshold, 2)}</b> (HOLD cost 2 / escape cost 150).`;
    decision = `<section><h4>Pair decision ${verdict}</h4><div class="kv">
      <span>partner</span><span class="link" data-part="${partner}" data-side="${side}">${partner}</span>
      <span>measured clearance</span><span>${fmt(pair.measured_clearance_mm, 3)} mm</span>
      <span>posterior clearance</span><span>${fmt(pair.posterior_clearance_mm, 3)} ± ${fmt(pair.posterior_clearance_sd, 3)}</span>
      <span>P(dimensional unsafe)</span><span>${pct(pair.p_dimensional, 3)}</span>
      <span>P(surface) slot / tab</span><span>${pct(pair.p_surface_slot, 3)} / ${pct(pair.p_surface_tab, 3)}</span>
      <span>P(unsafe)</span><span>${pct(pair.p_unsafe, 3)}</span>
      <span>fate</span><span>${pair.fate || '—'}</span></div><div class="why">${why}</div></section>`;
  }
  let prev = p.print_t;
  const tl = p.events.map(([s, a, b]) => { const w = Math.max(0, a - prev); prev = b; return `<li><span>${STN[s] || s}</span><span class="faint">${w > 1 ? `waited ${fmt(w, 0)} s` : ''}</span><span>${mmss(a)}–${mmss(b)}</span></li>`; }).join('');
  const truthSec = truth ? `<section><h4>Ground truth · evaluator only</h4><div class="kv">
      <span>true width</span><span>${fmt(p.width_mm, 3)} mm</span><span>crack</span><span>${p.crack ? 'yes' : 'no'}</span><span>warped</span><span>${p.warped ? 'yes' : 'no'}</span>
      ${pair ? `<span>true clearance</span><span>${fmt(pair.true_clearance_mm, 3)} mm</span><span>pair truly safe</span><span>${pair.truly_safe ? 'yes' : 'no'}</span>` : ''}</div></section>` : '';
  let caught = '';
  if (side === 1 && lab.caught.has(p.id)) {
    const how = p.fate === 'scrap' ? 'it was <b>scrapped</b> after review' : p.fate === 'shipped'
      ? (p.events.some((e) => e[0] === 'review') ? 'it was <b>held, reviewed</b>, and then shipped in a safe assembly' : `risk-based pairing gave it a different partner (<span class="link" data-part="${partner}" data-side="1">${partner}</span>), and the assembly was <b>safe</b>`)
      : 'it was <b>held back</b> and never shipped in a defective assembly';
    caught = `<div class="why" style="border-color:var(--caught)"><b>Caught:</b> on the left, the fixed rule shipped this part inside a defective assembly (ground truth). Here ${how}.</div>`;
  }
  return `<h2>${p.kind === 'slot' ? 'Slot' : 'Tab'} <span class="num">${p.id}</span></h2>
    <div class="sub">${p.lot} · printed ${mmss(p.print_t)}${lab.runs.length > 1 ? ` · ${side ? 'right' : 'left'} view` : ''}</div>
    ${fate}${caught}
    <section><h4>Evidence (what the system saw)</h4><div class="kv">
      ${Object.entries(p.cams || {}).map(([k, v]) => `<span>${STN[k] || k}</span><span>${camTxt(v)}</span>`).join('')}
      <span>caliper reading</span><span>${fmt(p.measured_mm, 3)} mm (σ ${fmt(p.caliper_sd, 2)})</span>
      <span>P(surface defect)</span><span>${p.surface_posterior === null ? '—' : pct(p.surface_posterior, 3)}</span>
      <span>expert review</span><span>${p.reviewed ? 'cleared' : p.events.some((e) => e[0] === 'review') ? 'yes' : 'no'}</span></div>
      <p class="faint small">Camera sensitivity/specificity come from a held-out calibration (${run.model.calibration_id}).</p></section>
    ${decision}
    <section><h4>Timeline</h4><ul class="tl">${tl || '<li><span>—</span></li>'}</ul></section>
    ${truthSec}`;
}
function stationCard(k, side) {
  const run = lab.runs[side], s = run?.stations[k], [name, desc] = STATION_INFO[k];
  return `<h2>${name}</h2><div class="sub">station · ${run.scenario} · ${run.policy}+${run.pairing}</div><p class="muted">${desc}</p>
    ${s ? `<section><h4>Load in this run</h4><div class="kv"><span>visits</span><span>${s.visits}</span><span>busy time</span><span>${fmt(s.busy_s / 60, 1)} min</span>
      <span>busy share of the run</span><span>${pct(s.busy_share, 0)}</span><span>mean service</span><span>${fmt(s.busy_s / Math.max(1, s.visits), 1)} s</span></div>
      <div class="bar"><i style="width:${Math.min(100, 100 * s.busy_share)}%"></i></div></section>` : '<section><p class="faint">No timed visits are recorded for this station in this run.</p></section>'}`;
}
function summaryCard() {
  if (!lab.runs.length) return '<p class="faint">Run a simulation.</p>';
  const r = lab.runs[lab.runs.length - 1];
  let html = `<h2>${r.scenario} · ${r.title}</h2><div class="sub">seed ${r.seed} · ${r.n_pairs} pairs · truth ${r.kpis.truth_sha256.slice(0, 12)}…</div>`;
  if (lab.runs.length === 2) {
    const ids = [...lab.caught];
    html += `<section><h4>Caught by QualityRelay</h4><p class="muted">The rule on the left shipped these parts inside defective assemblies (ground truth). On the right none of them ended up in a defective assembly: they were held, scrapped, or re-paired safely. Click one.</p>
      <div class="caughtlist">${ids.length ? ids.map((id) => `<span class="badge link" data-part="${id}" data-side="1">${id}</span>`).join('') : '<span class="faint">None in this run. Try F02 or F03, or 150 pairs.</span>'}</div></section>`;
  }
  html += `<section><h4>How to read this</h4><ul class="tl">
    <li><span>click a part</span><span class="faint">evidence chain behind its decision</span><span></span></li>
    <li><span>click a station</span><span class="faint">its load in this run</span><span></span></li>
    <li><span>keys</span><span class="faint"><kbd>space</kbd> play · <kbd>L</kbd> labels · <kbd>T</kbd> truth · <kbd>←</kbd><kbd>→</kbd> tour</span><span></span></li></ul></section>
    <section><h4>Provenance</h4><p class="faint small">SIMULATED. Toy part generator, illustrative station timings, held-out calibration ${r.model.calibration_id}. Not a factory measurement.</p></section>`;
  return html;
}
function renderInspector() {
  const truth = $('#truth').checked, sel = lab.sel; let html;
  if (sel?.type === 'part') {
    const side = Math.min(sel.side ?? 0, lab.runs.length - 1);
    const p = findPart(sel.id, side); html = p ? partCard(p, side, truth) : summaryCard(); $('#inspHint').textContent = 'part';
  } else if (sel?.type === 'station') { html = stationCard(sel.id, Math.min(sel.side ?? 0, lab.runs.length - 1)); $('#inspHint').textContent = 'station'; }
  else { html = summaryCard(); $('#inspHint').textContent = 'click a part or a station'; }
  $('#inspBody').innerHTML = html;
  $$('#inspBody [data-part]').forEach((el) => (el.onclick = () => select({ type: 'part', id: el.dataset.part, side: el.dataset.side !== undefined ? +el.dataset.side : 0 })));
}

// ---------------------------------------------------------------- parts page
async function initParts() {
  const cad = await api('/sim/cad');
  const s = makeStage($('#partCanvas'), { camPos: [60, 70, 95], bloom: false, labels: false });
  s.scene.fog = null;
  const grid = new THREE.GridHelper(240, 24, 0x262b32, 0x171a1f); grid.position.y = -12; s.scene.add(grid);
  let current = null; const show = (o) => { if (current) s.scene.remove(current); current = o; s.scene.add(o); };
  const rank = { slot: 0, tab: 1, bar: 2 }, sub = (f) => (f.includes('nominal') ? 0 : f.includes('good') ? 1 : 2);
  const parts = [...cad.catalogue].sort((a, b) => rank[a.kind] - rank[b.kind] || sub(a.file) - sub(b.file));
  const pretty = (c) => c.file.replace('.stl', '').replace(/_/g, ' ').replace(/(\d+)p(\d+)/, '$1.$2 mm');
  const list = $('#partList');
  const meshOf = (g, color) => { const m = new THREE.Mesh(g, new THREE.MeshPhysicalMaterial({ color, roughness: 0.4, clearcoat: 0.5 })); m.castShadow = true; return m; };
  async function single(c, btn) {
    $$('#partList button').forEach((b) => b.classList.toggle('on', b === btn));
    const g = await loadSTL(c.file); g.computeBoundingBox();
    const m = meshOf(g, c.kind === 'slot' ? 0x6f8aa6 : c.kind === 'tab' ? C.tab : 0x8a8f96); m.position.sub(g.boundingBox.getCenter(new THREE.Vector3()));
    const grp = new THREE.Group(); grp.add(m); grp.rotation.x = -Math.PI / 2; show(grp);
    $('#partLabel').innerHTML = `${pretty(c)} · ${c.kind === 'slot' ? 'opening' : 'width'} <b>${fmt(c.functional_width_mm, 2)} mm</b> · outer ${c.extents_mm.map((x) => fmt(x, 1)).join(' × ')} · rev ${c.revision}`;
  }
  parts.forEach((c, i) => {
    const b = document.createElement('button');
    b.innerHTML = `<span>${pretty(c)}<small>${c.kind} · ${c.watertight ? 'watertight' : 'open mesh'}</small></span><b>${fmt(c.functional_width_mm, 2)}</b>`;
    b.onclick = () => single(c, b); list.appendChild(b); if (i === 0) single(c, b);
  });
  const slots = parts.filter((c) => c.kind === 'slot'), tabs = parts.filter((c) => c.kind === 'tab');
  const opt = (c) => `<option value="${c.file}">${pretty(c)} (${fmt(c.functional_width_mm, 2)})</option>`;
  $('#fitSlot').innerHTML = slots.map(opt).join(''); $('#fitTab').innerHTML = tabs.map(opt).join('');
  async function fit() {
    const sc = slots.find((c) => c.file === $('#fitSlot').value), tc = tabs.find((c) => c.file === $('#fitTab').value);
    const [sg, tg] = await Promise.all([loadSTL(sc.file), loadSTL(tc.file)]); sg.computeBoundingBox(); tg.computeBoundingBox();
    const g = new THREE.Group(), sm = meshOf(sg, 0x6f8aa6), tm = meshOf(tg, C.tab), sb = sg.boundingBox, tb = tg.boundingBox;
    tm.position.set(sb.max.x - 24 - tb.min.x, (sb.min.y + sb.max.y) / 2 - (tb.min.y + tb.max.y) / 2, 0); g.add(sm, tm);
    const ctr = new THREE.Box3().setFromObject(g).getCenter(new THREE.Vector3()); g.children.forEach((m) => m.position.sub(ctr)); g.rotation.x = -Math.PI / 2; show(g);
    const clr = sc.functional_width_mm - tc.functional_width_mm, ok = clr >= 0.5;
    $('#fitVerdict').className = `verdict ${ok ? 'ok' : 'risk'}`;
    $('#fitVerdict').innerHTML = `${ok ? '✔' : '✖'} clearance <b>${fmt(clr, 2)} mm</b> (tolerance ≥ 0.50) → ${ok ? 'passes' : '<b>fails</b>'} the design check`;
    $('#partLabel').innerHTML = `Fit check · ${fmt(sc.functional_width_mm, 2)} − ${fmt(tc.functional_width_mm, 2)} = <b>${fmt(clr, 2)} mm</b> · CAD only`;
  }
  $('#fitSlot').value = slots.find((c) => c.file.includes('nominal'))?.file; $('#fitTab').value = tabs.find((c) => c.file.includes('nominal'))?.file;
  $('#fitSlot').onchange = fit; $('#fitTab').onchange = fit;
  $('#modeSingle').onclick = () => { $('#modeSingle').classList.add('on'); $('#modeFit').classList.remove('on'); $('#fitPick').classList.add('hidden'); list.classList.remove('hidden'); $('#partList button.on')?.click(); };
  $('#modeFit').onclick = () => { $('#modeFit').classList.add('on'); $('#modeSingle').classList.remove('on'); $('#fitPick').classList.remove('hidden'); list.classList.add('hidden'); fit(); };
  s.controls.autoRotate = true; s.controls.autoRotateSpeed = 0.8;
  (function loop() { if (!$('#view-parts').hidden) s.render(); requestAnimationFrame(loop); })();
}

// ---------------------------------------------------------------- results + science pages
const chip = (ok, yes, no) => `<span class="chip ${ok ? 'ok' : 'no'}">${ok ? '✔' : '✖'} ${ok ? yes : no}</span>`;
async function initResults() {
  const r = await api('/sim/results'), titles = Object.fromEntries((await api('/sim/scenarios')).map((s) => [s.sid, s.title]));
  const pv = r.factory.product_vs_today, ha = r.factory.hold_all;
  const warpParts = Object.values(r.warp).reduce((a, w) => a + w.parts, 0);
  $('#kpis').innerHTML = [['good', `${pv.filter((x) => x.safe).length} / ${pv.length}`, 'scenarios where QualityRelay shipped fewer defects'],
    ['warn', `${pv.filter((x) => x.throughput).length} / ${pv.length}`, 'of those also kept throughput: an honest trade-off'],
    ['', `${fmt(100 * (ha.hold_all.good_per_hour / ha.rules_fifo.good_per_hour - 1), 0)}%`, 'throughput if every part is held for review'],
    ['', `${(warpParts / 1e6).toFixed(0)}M`, 'parts in the NVIDIA Warp Monte Carlo']]
    .map(([c, a, b]) => `<div class="kpi ${c}"><strong>${a}</strong><span>${b}</span></div>`).join('');
  $('#resultsTable tbody').innerHTML = pv.map((x) => `<tr><td><span class="sid">${x.scenario}</span>${titles[x.scenario] || ''}</td>
    <td class="num">${sign(x.good_per_hour_diff)}</td><td class="num">${sign(x.escapes_diff, 2)}</td><td class="num">${sign(x.cost_per_good_diff, 2)}</td>
    <td>${chip(x.safe, 'safer', 'not shown')}</td><td>${chip(x.throughput, 'kept', 'lower')}</td><td>${chip(x.cheaper, 'cheaper', 'not shown')}</td>
    <td class="num">${r.factory.roi[x.scenario] ? fmt(100 * r.factory.roi[x.scenario].p_worse, 0) + '%' : '—'}</td></tr>`).join('');
  for (const fig of $$('.chart')) fig.innerHTML = await (await fetch(`/sim/charts/${fig.dataset.chart}.svg`)).text();
  const g = r.gate_a.summary, order = ['B0_rules', 'B1_single_agent_fixed', 'B2_full_information_upper_bound', 'B3_majority_vote', 'B5_structured_fixed', 'B6_single_agent_voi', 'B7_safe_mesh_voi', 'B7-cost_awareness'];
  const nice = { B0_rules: 'B0 fixed rule', B1_single_agent_fixed: 'B1 single agent, calibrated', B2_full_information_upper_bound: 'B2 upper bound (all captures)', B3_majority_vote: 'B3 majority vote',
    B5_structured_fixed: 'B5 structured requests', B6_single_agent_voi: 'B6 single agent + VOI', B7_safe_mesh_voi: 'B7 SAFE-MESH + VOI', 'B7-cost_awareness': 'B7 − cost awareness' };
  $('#gateTable tbody').innerHTML = order.map((k) => `<tr><td>${nice[k]}${k === 'B7_safe_mesh_voi' ? ' <span class="chip no">holds every part</span>' : ''}</td>
    <td class="num">${fmt(1000 * g[k].unsafe_pass_rate, 2)}</td><td class="num">${fmt(100 * g[k].released_good_rate, 1)}%</td><td class="num">${fmt(g[k].cost_per_unit, 2)}</td></tr>`).join('');
  $('#warpTable tbody').innerHTML = Object.entries(r.warp).map(([sid, w]) => `<tr><td><span class="sid">${sid}</span>${w.title}</td>
    <td class="num">${fmt(w.unsafe_per_1000.B0_rules, 2)}</td><td class="num">${fmt(w.unsafe_per_1000.B1_single_agent_fixed, 2)}</td>
    <td class="num">${sign((w.b1_minus_b0_ci[0] + w.b1_minus_b0_ci[1]) / 2, 2)} [${fmt(w.b1_minus_b0_ci[0], 2)}, ${fmt(w.b1_minus_b0_ci[1], 2)}]</td></tr>`).join('');
}

// ---------------------------------------------------------------- router + boot
const inited = {};
function route() {
  const v = (location.hash || '#lab').slice(1);
  const view = ['lab', 'parts', 'results', 'science', 'claims'].includes(v) ? v : 'lab';
  $$('.view').forEach((s) => (s.hidden = s.id !== `view-${view}`));
  $$('.tabs a').forEach((a) => a.classList.toggle('on', a.dataset.view === view));
  if (view === 'parts' && !inited.parts) { inited.parts = true; initParts().catch((e) => ($('#partLabel').textContent = e.message)); }
  if ((view === 'results' || view === 'science') && !inited.results) { inited.results = true; initResults().catch((e) => ($('#kpis').textContent = e.message)); }
}
window.addEventListener('hashchange', route);
route();
initLab().catch((e) => { $('#runStatus').textContent = `Lab failed to start: ${e.message}`; console.error(e); });
