// QualityRelay 18.1 website: 3D factory replay, STL parts viewer, results. Everything shown is SIMULATED.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { STLLoader } from 'three/addons/STLLoader.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/CSS2DRenderer.js';

const $ = (s) => document.querySelector(s);
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const COL = { slot: css('--slot'), tab: css('--tab'), review: css('--review'), scrap: css('--scrap'), escape: css('--escape'), accent: css('--accent') };
const fmt = (x, d = 1) => (x === null || x === undefined || Number.isNaN(+x)) ? '—' : (+x).toFixed(d);
const sign = (x, d = 1) => (x > 0 ? '+' : '') + fmt(x, d);
const api = async (url, opts) => { const r = await fetch(url, opts); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); };

// ---------- shared three.js scaffolding ----------
function makeStage(el, { camPos = [0, 14, 18], target = [0, 0, 0], labels = false } = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(el.clientWidth, el.clientHeight);
  renderer.shadowMap.enabled = true;
  el.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.1, 2000);
  camera.position.set(...camPos);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(...target); controls.enableDamping = true; controls.update();
  scene.add(new THREE.HemisphereLight(0xdfeaff, 0x2a3038, 1.6)); scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const sun = new THREE.DirectionalLight(0xffffff, 2.0); sun.position.set(8, 18, 10); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30 });
  scene.add(sun);
  let labelRenderer = null;
  if (labels) {
    labelRenderer = new CSS2DRenderer(); labelRenderer.setSize(el.clientWidth, el.clientHeight);
    Object.assign(labelRenderer.domElement.style, { position: 'absolute', top: '0', left: '0', pointerEvents: 'none' });
    el.appendChild(labelRenderer.domElement);
  }
  new ResizeObserver(() => {
    const w = el.clientWidth, h = el.clientHeight; if (!w || !h) return;
    renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); labelRenderer?.setSize(w, h);
  }).observe(el);
  return { renderer, scene, camera, controls, labelRenderer, render() { controls.update(); renderer.render(scene, camera); labelRenderer?.render(scene, camera); } };
}

function label(text, cls = 'label3d') {
  const d = document.createElement('div'); d.className = cls; d.textContent = text; return new CSS2DObject(d);
}

// ---------- STL catalogue ----------
const loader = new STLLoader();
const geomCache = new Map();
function loadSTL(name) {
  if (!geomCache.has(name)) geomCache.set(name, new Promise((res, rej) => loader.load(`/sim/stl/${name}`, (g) => { g.computeVertexNormals(); res(g); }, undefined, rej)));
  return geomCache.get(name);
}
const metal = (color, opts = {}) => new THREE.MeshStandardMaterial({ color, metalness: 0.15, roughness: 0.55, ...opts });

function fitMeshes(slotG, tabG) {
  // STL axes: x = length (60), y = width, z = thickness. Slot opening is open at +x, 48 mm deep.
  const g = new THREE.Group();
  const slot = new THREE.Mesh(slotG, metal(0x6f8aa6)); slot.castShadow = slot.receiveShadow = true;
  slotG.computeBoundingBox(); tabG.computeBoundingBox();
  const sb = slotG.boundingBox, tb = tabG.boundingBox;
  const tab = new THREE.Mesh(tabG, metal(new THREE.Color(COL.tab)));
  tab.castShadow = true;
  const slotMidY = (sb.min.y + sb.max.y) / 2, tabMidY = (tb.min.y + tb.max.y) / 2;
  tab.position.set(sb.max.x - 24 - tb.min.x, slotMidY - tabMidY, 0);  // inserted 24 mm into the opening
  g.add(slot, tab);
  const box = new THREE.Box3().setFromObject(g); const c = box.getCenter(new THREE.Vector3());
  g.children.forEach((m) => m.position.sub(c));
  g.rotation.x = -Math.PI / 2;
  return g;
}

// ---------- hero: rotating fit ----------
async function hero(cad) {
  const s = makeStage($('#heroCanvas'), { camPos: [70, 80, 110] });
  s.controls.autoRotate = true; s.controls.autoRotateSpeed = 1.2; s.controls.enableZoom = false;
  const slotN = cad.catalogue.find((c) => c.file.startsWith('slot_nominal')), tabN = cad.catalogue.find((c) => c.file.startsWith('tab_nominal'));
  const [sg, tg] = await Promise.all([loadSTL(slotN.file), loadSTL(tabN.file)]);
  s.scene.add(fitMeshes(sg, tg));
  const grid = new THREE.GridHelper(220, 22, 0x2a333f, 0x1a2029); grid.position.y = -10; s.scene.add(grid);
  $('#heroClear').textContent = `${fmt(cad.nominal.design_clearance_mm, 1)} mm (${fmt(cad.nominal.slot_opening_mm, 1)} − ${fmt(cad.nominal.tab_width_mm, 1)})`;
  (function loop() { s.render(); requestAnimationFrame(loop); })();
}

// ---------- parts viewer ----------
async function partsViewer(cad) {
  const s = makeStage($('#partCanvas'), { camPos: [60, 70, 95] });
  const grid = new THREE.GridHelper(240, 24, 0x2a333f, 0x1a2029); grid.position.y = -12; s.scene.add(grid);
  let current = null;
  const show = (obj) => { if (current) s.scene.remove(current); current = obj; s.scene.add(obj); };
  const rank = { slot: 0, tab: 1, bar: 2 }, sub = (f) => (f.includes('nominal') ? 0 : f.includes('good') ? 1 : 2);
  const parts = [...cad.catalogue].sort((a, b) => rank[a.kind] - rank[b.kind] || sub(a.file) - sub(b.file));
  const list = $('#partList');
  const pretty = (c) => c.file.replace('.stl', '').replace(/_/g, ' ').replace(/(\d+)p(\d+)/, '$1.$2 mm');
  async function single(c, btn) {
    list.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b === btn));
    const g = await loadSTL(c.file);
    const m = new THREE.Mesh(g, metal(c.kind === 'slot' ? 0x6f8aa6 : c.kind === 'tab' ? new THREE.Color(COL.tab) : 0x8a8f96));
    m.castShadow = true; g.computeBoundingBox(); const ctr = g.boundingBox.getCenter(new THREE.Vector3());
    m.position.sub(ctr); const grp = new THREE.Group(); grp.add(m); grp.rotation.x = -Math.PI / 2; show(grp);
    const what = c.kind === 'slot' ? 'slot opening' : c.kind === 'tab' ? 'tab width' : 'bar width';
    $('#partLabel').innerHTML = `${pretty(c)} · ${what} <b>${fmt(c.functional_width_mm, 2)} mm</b> measured from mesh · outer ${c.extents_mm.map((x) => fmt(x, 1)).join(' × ')} mm · rev <b>${c.revision}</b>`;
  }
  parts.forEach((c, i) => {
    const b = document.createElement('button');
    b.innerHTML = `<span>${pretty(c)}<small>${c.kind} · ${c.watertight ? 'watertight' : 'open mesh'}</small></span><b>${fmt(c.functional_width_mm, 2)}</b>`;
    b.onclick = () => single(c, b); list.appendChild(b); if (i === 0) single(c, b);
  });
  const slots = parts.filter((c) => c.kind === 'slot'), tabs = parts.filter((c) => c.kind === 'tab');
  const opt = (c) => `<option value="${c.file}">${pretty(c)} (${fmt(c.functional_width_mm, 2)})</option>`;
  $('#fitSlot').innerHTML = slots.map(opt).join(''); $('#fitTab').innerHTML = tabs.map(opt).join('');
  $('#fitSlot').value = slots.find((c) => c.file.includes('nominal'))?.file; $('#fitTab').value = tabs.find((c) => c.file.includes('nominal'))?.file;
  async function fit() {
    const sc = slots.find((c) => c.file === $('#fitSlot').value), tc = tabs.find((c) => c.file === $('#fitTab').value);
    const [sg, tg] = await Promise.all([loadSTL(sc.file), loadSTL(tc.file)]);
    show(fitMeshes(sg, tg));
    const clr = sc.functional_width_mm - tc.functional_width_mm, ok = clr >= 0.5;
    $('#fitVerdict').className = `verdict ${ok ? 'ok' : 'risk'}`;
    $('#fitVerdict').innerHTML = `${ok ? '✔' : '✖'} clearance <b>${fmt(clr, 2)} mm</b>, tolerance ≥ 0.50 mm → ${ok ? 'passes the design check' : '<b>fails</b> the design check'}`;
    $('#partLabel').innerHTML = `Fit check · slot ${fmt(sc.functional_width_mm, 2)} mm − tab ${fmt(tc.functional_width_mm, 2)} mm = <b>${fmt(clr, 2)} mm</b> · CAD only, not a physical measurement`;
  }
  $('#fitSlot').onchange = fit; $('#fitTab').onchange = fit;
  $('#modeSingle').onclick = () => { $('#modeSingle').classList.add('on'); $('#modeFit').classList.remove('on'); $('#fitPick').classList.add('hidden'); list.classList.remove('hidden'); list.querySelector('button.on')?.click(); };
  $('#modeFit').onclick = () => { $('#modeFit').classList.add('on'); $('#modeSingle').classList.remove('on'); $('#fitPick').classList.remove('hidden'); list.classList.add('hidden'); fit(); };
  (function loop() { s.render(); requestAnimationFrame(loop); })();
}

// ---------- 3D factory ----------
const P = {  // station layout (x, z)
  printer_slot: [-14, -2.6], printer_tab: [-14, 2.6], phone: [-8.5, 0], pi: [-5.5, 0], caliper: [-2.5, 0],
  buffer: [1, 0], assembly: [4.5, 0], sorting: [7.5, 0], ship: [11.5, 0], review: [2.5, -6], rework: [6.5, -6], scrap: [11.5, -6],
  phone_local: [-5.5, 6], caliper_local: [-2.5, 6],
};
function factoryScene() {
  const s = makeStage($('#factoryCanvas'), { camPos: [-1, 13.5, 14.5], target: [-1.2, 0, -1.2], labels: true });
  s.controls.maxPolarAngle = Math.PI / 2.15; s.controls.minDistance = 8; s.controls.maxDistance = 60;
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(160, 120), new THREE.MeshStandardMaterial({ color: 0x18202a, roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; s.scene.add(floor);
  const grid = new THREE.GridHelper(80, 80, 0x2a3440, 0x1f2731); grid.position.y = 0.01; s.scene.add(grid);
  const belt = new THREE.Mesh(new THREE.BoxGeometry(23, 0.12, 1.3), new THREE.MeshStandardMaterial({ color: 0x232b35, roughness: 0.6 }));
  belt.position.set(-1.5, 0.06, 0); belt.receiveShadow = true; s.scene.add(belt);
  const stations = {};
  const st = (key, name, w, d, h, color, lift = 0.7) => {
    const [x, z] = P[key];
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), metal(color, { roughness: 0.45 }));
    m.position.set(x, h / 2, z); m.castShadow = m.receiveShadow = true; s.scene.add(m);
    const l = label(name); l.position.set(x, h + lift, z); s.scene.add(l); stations[key] = [m, l]; return m;
  };
  st('printer_slot', 'Slot printers', 2.2, 2, 2.2, 0x4a6788); st('printer_tab', 'Tab printers', 2.2, 2, 2.2, 0x8a5a44);
  const cam = (key, name) => { const [x, z] = P[key]; st(key, name, 0.5, 0.5, 2.6, 0x5d6878, 1.0);
    const head = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.5, 0.6), metal(0x22272e)); head.position.set(x, 2.7, z + 0.2); s.scene.add(head);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.04, 8, 20), new THREE.MeshBasicMaterial({ color: new THREE.Color(COL.accent) }));
    ring.position.set(x, 2.7, z + 0.52); s.scene.add(ring); };
  cam('phone', 'Phone camera'); cam('pi', 'Pi camera');
  st('caliper', 'Caliper + operator', 1.6, 1.4, 1.1, 0x66727f, 1.6); st('buffer', 'Pairing buffer', 1.8, 2.4, 0.4, 0x3c4754, 0.6);
  st('assembly', 'Assembly', 2, 1.8, 1.2, 0x5a6d80, 1.5); st('sorting', 'Sorter', 1.6, 1.6, 0.9, 0x4f5d6c, 0.6);
  st('ship', 'Shipped', 2.6, 2.6, 0.25, 0x2f6b3f); st('review', 'Review (HOLD)', 2.4, 2, 0.9, 0x8a7420);
  st('rework', 'Rework', 2, 1.8, 0.9, 0x5e536b); st('scrap', 'Scrap', 2.6, 2.6, 0.25, 0x6b3434);
  st('phone_local', 'Assembly-site camera', 0.5, 0.5, 1.6, 0x5d6878); st('caliper_local', 'Assembly-site caliper', 1.4, 1.2, 0.9, 0x66727f);
  s.stations = stations;
  return s;
}

const fs = { stage: null, parts: [], meshes: [], t: 0, T: 1, playing: true, speed: 60, data: null };
const geoS = new THREE.BoxGeometry(0.8, 0.4, 0.55), geoT = new THREE.BoxGeometry(0.72, 0.32, 0.44);
const hash = (s) => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return (h >>> 0) / 4294967295; };

function pathFor(p, binIndex) {
  const kf = []; const j = hash(p.id), jz = (j - 0.5) * 0.9;
  const pos = (k, dx = 0, dz = 0) => { const [x, z] = P[k] || P.buffer; return [x + dx, z + dz]; };
  const pr = p.kind === 'slot' ? 'printer_slot' : 'printer_tab';
  // the part appears at the printer's output side when its print job finishes
  const first = p.events.length ? p.events[0][1] : p.print_t + 60;
  const out = Math.max(p.print_t, first - 25);
  kf.push([out, ...pos(pr, 1.6, jz * 0.8)]);
  let prevEnd = out + 2, prevKey = pr;
  kf.push([prevEnd, ...pos(pr, 1.6, jz * 0.8)]);
  for (const [station, start, end] of p.events) {
    const travel = Math.min(8, Math.max(0.5, start - prevEnd));
    const arrive = Math.max(prevEnd, Math.min(start, prevEnd + travel));
    kf.push([prevEnd, ...pos(prevKey, prevKey.startsWith('printer') ? 1.6 : 0, prevKey.startsWith('printer') ? jz * 0.8 : jz * 0.25)]);
    if (start - arrive > 1) kf.push([arrive, ...pos(station, -1.1, jz)], [start - 0.5, ...pos(station, -0.9, jz)]);
    kf.push([start, ...pos(station, 0, jz * 0.25)], [end, ...pos(station, 0, jz * 0.25)]);
    prevEnd = end; prevKey = station;
  }
  const last = kf[kf.length - 1][0];
  const binPos = (k) => { const [x, z] = P[k]; const i = binIndex; return [x - 1 + (i % 6) * 0.4, z - 1 + (Math.floor(i / 6) % 6) * 0.4]; };
  if (p.fate === 'shipped') kf.push([last + 4, ...binPos('ship')]);
  else if (p.fate === 'scrap') kf.push([last + 4, ...binPos('scrap')]);
  else kf.push([last + 4, ...pos('buffer', (j - 0.5) * 1.2, jz)]);
  return kf;
}
function at(kf, t) {
  if (t < kf[0][0]) return null;
  for (let i = 1; i < kf.length; i++) if (t <= kf[i][0]) {
    const [t0, x0, z0] = kf[i - 1], [t1, x1, z1] = kf[i]; const u = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
    return [x0 + (x1 - x0) * u, z0 + (z1 - z0) * u];
  }
  const l = kf[kf.length - 1]; return [l[1], l[2]];
}

function loadRun(data) {
  const s = fs.stage; fs.meshes.forEach((m) => s.scene.remove(m)); fs.meshes = [];
  const counters = { shipped: 0, scrap: 0 };
  fs.parts = data.parts.map((p) => {
    const bin = p.fate === 'shipped' ? counters.shipped++ : p.fate === 'scrap' ? counters.scrap++ : 0;
    const kf = pathFor(p, bin);
    const mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(p.kind === 'slot' ? COL.slot : COL.tab), roughness: 0.45, metalness: 0.1, emissive: 0x000000 });
    const m = new THREE.Mesh(p.kind === 'slot' ? geoS : geoT, mat); m.castShadow = true; m.visible = false; s.scene.add(m); fs.meshes.push(m);
    const review = p.events.filter((e) => e[0] === 'review').map((e) => [e[1], e[2]]);
    const endT = kf[kf.length - 1][0];
    return { p, kf, m, review, endT, shipT: p.fate === 'shipped' ? endT : null, scrapT: p.fate === 'scrap' ? endT : null };
  });
  fs.T = Math.max(...fs.parts.map((x) => x.endT)) + 5; fs.t0 = Math.max(0, Math.min(...fs.parts.map((x) => x.kf[0][0])) - 2); fs.t = fs.t0; fs.data = data;
  const local = data.parts.some((p) => p.events.some((e) => e[0].endsWith('_local')));
  for (const k of ['phone_local', 'caliper_local']) s.stations[k].forEach((o) => { o.visible = local; if (o.element) o.element.style.display = local ? '' : 'none'; });
  const k = data.kpis;
  $('#runKpis').innerHTML = [['good / hour', fmt(k.good_per_hour, 1)], ['shipped good', `${k.shipped_good} / ${k.shipped}`], ['escaped', k.escaped],
    ['holds (part / pair)', `${k.part_holds} / ${k.pair_holds}`], ['scrapped parts', k.scrapped_parts], ['mean cycle', `${fmt(k.mean_cycle_s / 60, 1)} min`]]
    .map(([a, b]) => `<div><small>${a}</small><b>${b}</b></div>`).join('');
}
function frame(dt) {
  if (!fs.data) return;
  if (fs.playing) { fs.t += dt * fs.speed; if (fs.t > fs.T) fs.t = fs.t0 || 0; $('#timeline').value = Math.round(1000 * fs.t / fs.T); }
  const t = fs.t, truth = $('#truth').checked; let ship = 0, hold = 0, scrap = 0, esc = 0;
  const pairsShipped = new Set();
  for (const x of fs.parts) {
    const xy = at(x.kf, t); x.m.visible = !!xy; if (!xy) continue;
    const inReview = x.review.some(([a, b]) => t >= a && t <= b);
    const y = 0.4 + (x.p.kind === 'tab' && x.p.fate === 'shipped' && x.shipT && t >= x.shipT ? 0.36 : 0);
    x.m.position.set(xy[0], y, xy[1]);
    let color = x.p.kind === 'slot' ? COL.slot : COL.tab, emissive = 0x000000;
    if (inReview) { color = COL.review; emissive = 0x3a2e00; }
    if (x.scrapT && t >= x.scrapT) color = COL.scrap;
    if (truth && x.p.escaped && x.shipT && t >= x.shipT) { color = COL.escape; emissive = 0x400000; }
    x.m.material.color.set(color); x.m.material.emissive.set(emissive);
    if (x.review.length && t >= x.review[0][0]) hold++;
    if (x.scrapT && t >= x.scrapT) scrap++;
    if (x.shipT && t >= x.shipT && x.p.pair && !pairsShipped.has(x.p.pair)) { pairsShipped.add(x.p.pair); if (x.p.escaped) esc++; else ship++; }
  }
  const mm = Math.floor(t / 60), ss = Math.floor(t % 60);
  $('#clock').textContent = `${mm}:${String(ss).padStart(2, '0')}`; $('#cShip').textContent = ship; $('#cHold').textContent = hold;
  $('#cScrap').textContent = scrap; $('#cEsc').textContent = truth ? esc : '—';
}

async function runSim() {
  const btn = $('#runBtn'); btn.disabled = true; $('#runStatus').textContent = 'Running the discrete-event engine…';
  try {
    const body = { scenario: $('#scenario').value, policy: $('#policy').value, pairing: $('#pairing').value, seed: +$('#seed').value, n_pairs: +$('#npairs').value };
    const t0 = performance.now(); const d = await api('/sim/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    loadRun(d); fs.playing = true; $('#playBtn').textContent = '❚❚';
    $('#runStatus').innerHTML = `${d.scenario} · ${d.title} · ${d.parts.length} parts · computed in ${fmt(performance.now() - t0, 0)} ms · conservation ${d.kpis.conservation_ok ? '✔' : '✖'} · <b>SIMULATED</b>`;
  } catch (e) { $('#runStatus').textContent = `Simulation API unavailable (${e.message}). Start: uvicorn qualityrelay17.api:app`; }
  btn.disabled = false;
}

async function factory() {
  fs.stage = factoryScene();
  const sc = await api('/sim/scenarios');
  $('#scenario').innerHTML = ['single-site', 'multi-site'].map((g) => `<optgroup label="${g}">${sc.filter((s) => s.group === g).map((s) => `<option value="${s.sid}">${s.sid} · ${s.title}</option>`).join('')}</optgroup>`).join('');
  $('#runBtn').onclick = runSim;
  $('#playBtn').onclick = () => { fs.playing = !fs.playing; $('#playBtn').textContent = fs.playing ? '❚❚' : '▶'; };
  $('#timeline').oninput = (e) => { fs.t = fs.T * e.target.value / 1000; fs.playing = false; $('#playBtn').textContent = '▶'; };
  $('#speed').onchange = (e) => { fs.speed = +e.target.value; };
  let last = performance.now();
  (function loop(now) { const dt = Math.min(0.1, (now - last) / 1000); last = now; frame(dt); fs.stage.render(); requestAnimationFrame(loop); })(last);
  runSim();
}

// ---------- results ----------
const chip = (ok, yes, no) => `<span class="chip ${ok ? 'ok' : 'no'}">${ok ? '✔' : '✖'} ${ok ? yes : no}</span>`;
async function results() {
  const r = await api('/sim/results');
  const pv = r.factory.product_vs_today, titles = Object.fromEntries((await api('/sim/scenarios')).map((s) => [s.sid, s.title]));
  const safer = pv.filter((x) => x.safe).length, kept = pv.filter((x) => x.throughput).length;
  const warpParts = Object.values(r.warp).reduce((a, w) => a + w.parts, 0);
  const ha = r.factory.hold_all, haDrop = 100 * (ha.hold_all.good_per_hour / ha.rules_fifo.good_per_hour - 1);
  $('#heroKpis').innerHTML = [
    ['good', `${safer} / ${pv.length}`, 'scenarios where QualityRelay shipped fewer defects'],
    ['warn', `${kept} / ${pv.length}`, 'of those also kept throughput (honest trade-off)'],
    ['', `${fmt(haDrop, 0)}%`, 'throughput if every part is held for review'],
    ['', `${(warpParts / 1e6).toFixed(0)}M`, 'parts in the NVIDIA Warp Monte Carlo'],
  ].map(([c, a, b]) => `<div class="kpi ${c}"><strong>${a}</strong><span>${b}</span></div>`).join('');
  $('#resultsTable tbody').innerHTML = pv.map((x) => {
    const roi = r.factory.roi[x.scenario];
    return `<tr><td><span class="sid">${x.scenario}</span>${titles[x.scenario] || ''}</td><td class="num">${sign(x.good_per_hour_diff)}</td>
      <td class="num">${sign(x.escapes_diff, 2)}</td><td class="num">${sign(x.cost_per_good_diff, 2)}</td>
      <td>${chip(x.safe, 'safer', 'not shown')}</td><td>${chip(x.throughput, 'kept', 'lower')}</td><td>${chip(x.cheaper, 'cheaper', 'not shown')}</td>
      <td class="num">${roi ? fmt(100 * roi.p_worse, 0) + '%' : '—'}</td></tr>`;
  }).join('');
  for (const fig of document.querySelectorAll('.chart')) {
    const svg = await (await fetch(`/sim/charts/${fig.dataset.chart}.svg`)).text(); fig.innerHTML = svg;
  }
  const g = r.gate_a.summary, order = ['B0_rules', 'B1_single_agent_fixed', 'B2_full_information_upper_bound', 'B3_majority_vote', 'B5_structured_fixed', 'B6_single_agent_voi', 'B7_safe_mesh_voi', 'B7-cost_awareness'];
  const nice = { B0_rules: 'B0 fixed rule', B1_single_agent_fixed: 'B1 single agent, calibrated', B2_full_information_upper_bound: 'B2 upper bound (all captures)', B3_majority_vote: 'B3 majority vote',
    B5_structured_fixed: 'B5 structured requests', B6_single_agent_voi: 'B6 single agent + VOI', B7_safe_mesh_voi: 'B7 SAFE-MESH + VOI', 'B7-cost_awareness': 'B7 − cost awareness' };
  $('#gateTable tbody').innerHTML = order.map((k) => `<tr><td>${nice[k]}${k === 'B7_safe_mesh_voi' ? ' <span class="chip no">holds every part</span>' : ''}</td>
    <td class="num">${fmt(1000 * g[k].unsafe_pass_rate, 2)}</td><td class="num">${fmt(100 * g[k].released_good_rate, 1)}%</td><td class="num">${fmt(g[k].cost_per_unit, 2)}</td></tr>`).join('');
  $('#warpTable tbody').innerHTML = Object.entries(r.warp).map(([sid, w]) => `<tr><td><span class="sid">${sid}</span>${w.title}</td>
    <td class="num">${fmt(w.unsafe_per_1000.B0_rules, 2)}</td><td class="num">${fmt(w.unsafe_per_1000.B1_single_agent_fixed, 2)}</td>
    <td class="num">${sign((w.b1_minus_b0_ci[0] + w.b1_minus_b0_ci[1]) / 2, 2)} [${fmt(w.b1_minus_b0_ci[0], 2)}, ${fmt(w.b1_minus_b0_ci[1], 2)}]</td></tr>`).join('');
}

// ---------- boot ----------
(async () => {
  try {
    const cad = await api('/sim/cad');
    hero(cad); partsViewer(cad);
  } catch (e) { $('#partLabel').textContent = `CAD API unavailable: ${e.message}`; }
  factory().catch((e) => { $('#runStatus').textContent = `Factory API unavailable: ${e.message}`; });
  results().catch((e) => { $('#heroKpis').innerHTML = `<div class="kpi"><span>Results API unavailable: ${e.message}</span></div>`; });
})();
