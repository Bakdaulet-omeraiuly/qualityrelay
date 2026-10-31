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
// Conveyor speed in scene units per SIMULATED second (1 unit ≈ 0.25 m in this layout -> ~0.15 m/s).
const BELT_SPEED = 0.6;
const BELT_Y = 0.62;  // conveyor surface height
const LANE_STATIONS = new Set(['phone', 'pi', 'caliper']);
const laneKey = (st, line) => (LANE_STATIONS.has(st) ? `${st}_${line || 0}` : st);
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
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
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
  printer_slot: [-14, -2.6], printer_tab: [-14, 2.6], phone_0: [-8.5, -1], phone_1: [-8.5, 1], caliper_0: [-4.5, -1], caliper_1: [-4.5, 1],
  buffer: [0.6, 0], assembly: [4.5, 0], sorting: [7.5, 0], ship: [11.5, 0], review: [2.5, -6], rework: [6.5, -6], scrap: [11.5, -6],
  phone_local: [-5.5, 6], caliper_local: [-2.5, 6],
};
const STATION_INFO = {
  printer_slot: ['Slot printers', 'Print jobs of 4 parts (one lot). Width drift, warping and cracks are generated here; MTBF/MTTR failures.'],
  printer_tab: ['Tab printers', 'Print jobs of 4 parts (one lot). Kit-based CONWIP stops printing when the buffer is full.'],
  phone: ['iPhone camera', 'Surface check. A missing reading is never treated as "clear".'],
  caliper: ['Caliper', 'Measures width (σ 0.05 mm).'],
  phone_0: ['iPhone camera · slot lane', 'Surface check of every slot. A missing reading is never treated as "clear". Click "Open camera" to see its view or attach a real photo.'],
  phone_1: ['iPhone camera · tab lane', 'Surface check of every tab. A missing reading is never treated as "clear". Click "Open camera" to see its view or attach a real photo.'],
  caliper_0: ['Caliper · slot lane', 'Measures slot opening (σ 0.05 mm). One operator serves both calipers and also review/rework.'],
  caliper_1: ['Caliper · tab lane', 'Measures tab width (σ 0.05 mm). One operator serves both calipers and also review/rework.'],
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
    // ---- hall: concrete floor, back wall with windows, pillars
    const fc = document.createElement('canvas'); fc.width = fc.height = 512; const fg = fc.getContext('2d');
    fg.fillStyle = '#15191e'; fg.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 9000; i++) { const v = 18 + Math.random() * 16; fg.fillStyle = `rgba(${v},${v + 3},${v + 7},0.5)`; fg.fillRect(Math.random() * 512, Math.random() * 512, 2, 2); }
    fg.strokeStyle = 'rgba(0,0,0,0.35)'; fg.lineWidth = 2; fg.strokeRect(0, 0, 512, 512);
    const floorTex = new THREE.CanvasTexture(fc); floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping; floorTex.repeat.set(24, 18); floorTex.colorSpace = THREE.SRGBColorSpace;
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(120, 90), new THREE.MeshStandardMaterial({ map: floorTex, roughness: 0.85, metalness: 0.0, envMapIntensity: 0.25 }));
    floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; sc.add(floor);
    const pad = (x, z, w, d, c, o = 1) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshStandardMaterial({ color: c, roughness: 0.6, transparent: o < 1, opacity: o })); m.rotation.x = -Math.PI / 2; m.position.set(x, 0.006, z); m.receiveShadow = true; sc.add(m); };
    pad(-1.5, 0, 25, 3.2, 0x1d2a24, 0.8); pad(5.5, -6, 12.5, 4.2, 0x2a2414, 0.8); pad(-14, 0, 4.6, 8.8, 0x1b2230, 0.8);
    const dash = new THREE.MeshBasicMaterial({ color: 0xa88400 });
    for (const z of [-1.62, 1.62]) for (let x = -13.5; x < 13; x += 1.1) { const d = new THREE.Mesh(new THREE.PlaneGeometry(0.65, 0.08), dash); d.rotation.x = -Math.PI / 2; d.position.set(x, 0.012, z); sc.add(d); }
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(80, 6), metal(0x161b21, { roughness: 0.9 })); wall.position.set(0, 3, -13); wall.receiveShadow = true; sc.add(wall);
    const winMat = new THREE.MeshStandardMaterial({ color: 0x0b0f14, emissive: 0x2b3f55, emissiveIntensity: 0.55 });
    for (let x = -26; x <= 26; x += 4.4) { const w = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 1.6), winMat); w.position.set(x, 4.1, -12.95); sc.add(w); }
    for (let x = -24; x <= 24; x += 8) { const pl = new THREE.Mesh(new THREE.BoxGeometry(0.4, 6, 0.4), metal(0x343b45)); pl.position.set(x, 3, -12.7); pl.castShadow = true; sc.add(pl);
      const hz = new THREE.Mesh(new THREE.PlaneGeometry(0.55, 0.6), new THREE.MeshBasicMaterial({ color: 0xa88400 })); hz.position.set(x, 0.6, -12.49); sc.add(hz); }

    // ---- conveyor: frame, legs, instanced rollers, belt, drums, motor
    const alu = metal(0x8d96a0, { metalness: 0.75, roughness: 0.32 }), dark = metal(0x1f242b, { roughness: 0.6 });
    this.beltTexes = []; this.rollerXZ = [];
    const conveyor = (x0, x1, z, motorSide = -1) => {
      const L = x1 - x0, XC = (x0 + x1) / 2;
      const cv = document.createElement('canvas'); cv.width = 256; cv.height = 32; const g = cv.getContext('2d');
      g.fillStyle = '#1a1f25'; g.fillRect(0, 0, 256, 32); g.fillStyle = '#242a32'; for (let i = 0; i < 256; i += 16) g.fillRect(i, 0, 5, 32);
      const tex = new THREE.CanvasTexture(cv); tex.wrapS = THREE.RepeatWrapping; tex.repeat.set(L / 1.92, 1); tex.colorSpace = THREE.SRGBColorSpace; this.beltTexes.push(tex);
      const belt = new THREE.Mesh(new THREE.BoxGeometry(L, 0.04, 1.18), [dark, dark, new THREE.MeshStandardMaterial({ map: tex, roughness: 0.75 }), dark, dark, dark]);
      belt.position.set(XC, BELT_Y - 0.02, z); belt.receiveShadow = true; sc.add(belt);
      for (const dz of [-0.66, 0.66]) { const ch = new THREE.Mesh(new THREE.BoxGeometry(L, 0.2, 0.06), alu); ch.position.set(XC, BELT_Y - 0.06, z + dz); ch.castShadow = true; sc.add(ch); }
      for (let x = x0 + 0.4; x < x1; x += 2.3) {
        for (const dz of [-0.6, 0.6]) { const leg = new THREE.Mesh(new THREE.BoxGeometry(0.07, BELT_Y - 0.12, 0.07), alu); leg.position.set(x, (BELT_Y - 0.12) / 2, z + dz); leg.castShadow = true; sc.add(leg); }
        const cb = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 1.2), alu); cb.position.set(x, 0.12, z); sc.add(cb);
      }
      for (let x = x0 + 0.14; x < x1 - 0.1; x += 0.28) this.rollerXZ.push([x, z]);
      for (const x of [x0, x1]) { const dr = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 1.25, 20), alu); dr.rotation.x = Math.PI / 2; dr.position.set(x, BELT_Y - 0.08, z); sc.add(dr); }
      const motor = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.5, 20), metal(0x2f5f9e)); motor.rotation.x = Math.PI / 2; motor.position.set(x1 - 0.3, BELT_Y - 0.25, z + motorSide * 0.96); motor.castShadow = true; sc.add(motor);
      const gearbox = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.3, 0.26), dark); gearbox.position.set(x1 - 0.3, BELT_Y - 0.25, z + motorSide * 0.62); sc.add(gearbox);
    };
    conveyor(-12.6, -0.3, -1, -1); conveyor(-12.6, -0.3, 1, 1); conveyor(1.5, 10, 0, -1);
    const rollerGeo = new THREE.CylinderGeometry(0.055, 0.055, 1.3, 14); rollerGeo.rotateX(Math.PI / 2);
    this.rollers = new THREE.InstancedMesh(rollerGeo, metal(0xb8c0c8, { metalness: 0.9, roughness: 0.22 }), this.rollerXZ.length);
    this.rollerAngle = 0; this.rollerDummy = new THREE.Object3D(); sc.add(this.rollers); this.updateRollers();

    const lampAt = (x, y, z) => { const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 12), new THREE.MeshStandardMaterial({ color: LAMP_OFF, emissive: BLACK })); lamp.position.set(x, y, z); sc.add(lamp); return lamp; };
    const box = (key, w, d, h, color) => {
      const [x, z] = P[key];
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), metal(color)); m.position.set(x, h / 2, z);
      m.castShadow = m.receiveShadow = true; m.userData = { station: key }; sc.add(m);
      const lamp = lampAt(x + w / 2 - 0.2, h + 0.12, z - d / 2 + 0.2);
      const l = ann(STATION_INFO[key][0]); l.position.set(x, h + 0.55, z); sc.add(l); this.labels.push(l);
      this.stations[key] = { mesh: m, lamp, label: l, intervals: [] };
    };

    // ---- 3D printers (open frame): base, bed, posts, gantry + print head, part growing on the bed
    const printer = (key, kind) => {
      const [x, z] = P[key]; const grp = new THREE.Group(); grp.position.set(x, 0, z); sc.add(grp);
      const add = (geo, mat, px, py, pz) => { const m = new THREE.Mesh(geo, mat); m.position.set(px, py, pz); m.castShadow = m.receiveShadow = true; grp.add(m); return m; };
      add(new THREE.BoxGeometry(2.3, 0.7, 2.1), dark, 0, 0.35, 0);
      add(new THREE.BoxGeometry(2.25, 0.04, 0.12), new THREE.MeshStandardMaterial({ color: kind === 'slot' ? C.slot : C.tab, emissive: kind === 'slot' ? C.slot : C.tab, emissiveIntensity: 0.25 }), 0, 0.6, 1.06);
      for (const [px, pz] of [[-1.05, -0.95], [1.05, -0.95], [-1.05, 0.95], [1.05, 0.95]]) add(new THREE.BoxGeometry(0.08, 1.8, 0.08), alu, px, 1.6, pz);
      for (const pz of [-0.95, 0.95]) add(new THREE.BoxGeometry(2.18, 0.08, 0.08), alu, 0, 2.5, pz);
      for (const px of [-1.05, 1.05]) add(new THREE.BoxGeometry(0.08, 0.08, 1.98), alu, px, 2.5, 0);
      add(new THREE.BoxGeometry(1.6, 0.06, 1.5), metal(0x2c3138, { metalness: 0.5 }), 0, 0.78, 0);
      const gantry = add(new THREE.BoxGeometry(0.1, 0.1, 1.9), alu, 0, 1.55, 0);
      const head = add(new THREE.BoxGeometry(0.28, 0.32, 0.26), metal(0xe8eaed, { roughness: 0.4 }), 0, 1.4, 0);
      const nozzle = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.12, 12), new THREE.MeshStandardMaterial({ color: 0xffb347, emissive: 0xff7a00, emissiveIntensity: 0 }));
      nozzle.rotation.x = Math.PI; nozzle.position.set(0, -0.22, 0); head.add(nozzle);
      const wipMesh = new THREE.Mesh(this.partGeo[kind], new THREE.MeshPhysicalMaterial({ color: kind === 'slot' ? C.slot : C.tab, roughness: 0.5, transparent: true, opacity: 0.9 }));
      wipMesh.position.set(0, 0.81, 0); wipMesh.scale.set(1, 0.001, 1); wipMesh.visible = false; grp.add(wipMesh);
      const hit = new THREE.Mesh(new THREE.BoxGeometry(2.3, 2.6, 2.1), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }));
      hit.position.set(x, 1.3, z); hit.userData = { station: key }; sc.add(hit);
      const lamp = lampAt(x + 0.95, 2.62, z - 0.85);
      const l = ann(STATION_INFO[key][0]); l.position.set(x, 3.05, z); sc.add(l); this.labels.push(l);
      const r = ann('', 'readout'); r.position.set(x, 3.5, z); r.visible = false; sc.add(r);
      this.stations[key] = { mesh: hit, lamp, label: l, intervals: [], printer: { gantry, head, nozzle, wipMesh, readout: r, kind } };
    };
    printer('printer_slot', 'slot'); printer('printer_tab', 'tab');
    const iphone = (key) => {
      const [x, z] = P[key], side = Math.sign(z) || 1, y = 2.2;
      box(key, 0.12, 0.12, y + 0.25, 0x59636f);                     // post outside the lane
      this.stations[key].mesh.position.z = z + side * 0.95;
      this.stations[key].lamp.position.set(x, y + 0.42, z + side * 0.95); this.stations[key].label.position.set(x, y + 0.75, z + side * 0.95);
      const arm = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.08, 1.0), alu); arm.position.set(x, y + 0.2, z + side * 0.48); sc.add(arm);
      const body = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.04, 0.86), new THREE.MeshPhysicalMaterial({ color: 0x1b1d21, metalness: 0.6, roughness: 0.25, clearcoat: 1 }));
      body.position.set(x, y, z); body.castShadow = true; body.userData = { station: key }; sc.add(body);
      const bump = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.02, 0.2), metal(0x2a2d33)); bump.position.set(x - 0.08, y - 0.03, z - 0.26); sc.add(bump);
      const lenses = [];
      for (const [dx, dz] of [[-0.12, -0.31], [-0.04, -0.31], [-0.12, -0.21]]) {
        const l = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.03, 20), new THREE.MeshStandardMaterial({ color: 0x050608, emissive: C.accent, emissiveIntensity: 0.1 }));
        l.position.set(x + dx, y - 0.045, z + dz); sc.add(l); lenses.push(l);
      }
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.55, y - BELT_Y, 32, 1, true), new THREE.MeshBasicMaterial({ color: C.accent, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
      cone.position.set(x, (y + BELT_Y) / 2, z); sc.add(cone);
      Object.assign(this.stations[key], { lens: lenses[0], lenses, cone, camPos: [x - 0.1, y - 0.1, z - 0.26], camTarget: [x - 0.1, BELT_Y, z - 0.26] });
    };
    iphone('phone_0'); iphone('phone_1');
    this.jaws = {};
    for (const line of [0, 1]) {
      const key = `caliper_${line}`; box(key, 1.5, 1.3, 1.05, 0x66717e);
      this.jaws[line] = [-1, 1].map((sgn) => { const j = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.6, 0.9), metal(0x9aa3ad, { metalness: 0.8, roughness: 0.3 })); j.position.set(P[key][0] + sgn * 0.3, 1.35, P[key][1]); sc.add(j); return j; });
    }
    box('buffer', 1.6, 3.4, 0.7, 0x37414d); box('assembly', 2.0, 1.8, 1.25, 0x52687e); box('sorting', 1.6, 1.6, 0.85, 0x4a5867);
    // ---- robot arm at assembly (3 animated joints)
    { const base = new THREE.Group(); base.position.set(P.assembly[0], 0, -1.75); this.s.scene.add(base);
      const orange = metal(0xe07b1a, { roughness: 0.45 }), dk = metal(0x1f242b), al = metal(0x8d96a0, { metalness: 0.75, roughness: 0.32 });
      const pedestal = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.4, 0.5, 24), dk); pedestal.position.y = 0.25; pedestal.castShadow = true; base.add(pedestal);
      const yaw = new THREE.Group(); yaw.position.y = 0.5; base.add(yaw);
      const turret = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.28, 0.3, 24), orange); turret.position.y = 0.15; turret.castShadow = true; yaw.add(turret);
      const shoulder = new THREE.Group(); shoulder.position.y = 0.32; yaw.add(shoulder);
      const upper = new THREE.Mesh(new THREE.BoxGeometry(0.2, 1.1, 0.22), orange); upper.position.y = 0.55; upper.castShadow = true; shoulder.add(upper);
      const elbow = new THREE.Group(); elbow.position.y = 1.1; shoulder.add(elbow);
      const fore = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.9, 0.18), orange); fore.position.y = 0.45; fore.castShadow = true; elbow.add(fore);
      const wrist = new THREE.Group(); wrist.position.y = 0.9; elbow.add(wrist);
      const grip = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.12, 0.14), dk); grip.position.y = 0.06; wrist.add(grip);
      for (const sx of [-0.09, 0.09]) { const f = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.16, 0.08), al); f.position.set(sx, 0.18, 0); wrist.add(f); }
      this.robot = { yaw, shoulder, elbow }; }
    // ---- operators (hi-vis vest, helmet) at caliper, review and rework
    this.operators = [];
    for (const [ox, oz] of [[P.caliper_0[0] + 0.9, 0], [P.review[0], P.review[1] - 1.45], [P.rework[0], P.rework[1] - 1.35]]) {
      const o = new THREE.Group(); o.position.set(ox, 0, oz); o.scale.setScalar(1.25); this.s.scene.add(o);
      const legs = new THREE.Mesh(new THREE.CapsuleGeometry(0.16, 0.5, 4, 12), metal(0x2b3445)); legs.position.y = 0.45; o.add(legs);
      const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.21, 0.42, 4, 12), metal(0xd99a00, { roughness: 0.6 })); torso.position.y = 1.08; o.add(torso);
      const strip = new THREE.Mesh(new THREE.CylinderGeometry(0.215, 0.215, 0.05, 16), new THREE.MeshStandardMaterial({ color: 0xdddddd, emissive: 0x666666 })); strip.position.y = 1.0; o.add(strip);
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 12), metal(0xc49a78)); head.position.y = 1.58; o.add(head);
      const helmet = new THREE.Mesh(new THREE.SphereGeometry(0.165, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), metal(0xf2f2f2, { roughness: 0.35 })); helmet.position.y = 1.62; o.add(helmet);
      o.traverse((m) => { if (m.isMesh) m.castShadow = true; }); this.operators.push(o);
    }

    box('ship', 2.8, 2.8, 0.22, 0x235c34); box('review', 2.4, 2.0, 0.95, 0x7a6418); box('rework', 2.0, 1.8, 0.95, 0x574c66); box('scrap', 2.8, 2.8, 0.22, 0x5e2a2a);
    box('phone_local', 0.35, 0.35, 1.6, 0x59636f); box('caliper_local', 1.4, 1.2, 0.9, 0x66717e);
    for (const k of ['caliper_0', 'caliper_1', 'phone_0', 'phone_1']) { const r = ann('', 'readout'); r.position.set(P[k][0], k.startsWith('caliper') ? 2.2 : 3.4, P[k][1] + (k.startsWith('phone') ? Math.sign(P[k][1]) * 0.95 : 0)); r.visible = false; sc.add(r); this.readouts[k] = r; }
    this.ring = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.035, 8, 48), new THREE.MeshStandardMaterial({ color: C.accent, emissive: C.accent, emissiveIntensity: 1.6 }));
    this.ring.rotation.x = Math.PI / 2; this.ring.visible = false; sc.add(this.ring);
    this.stationRing = new THREE.Mesh(new THREE.RingGeometry(1.7, 1.8, 64), new THREE.MeshBasicMaterial({ color: C.accent, side: THREE.DoubleSide }));
    this.stationRing.rotation.x = -Math.PI / 2; this.stationRing.visible = false; sc.add(this.stationRing);
  }
  updateRollers() {
    const d = this.rollerDummy;
    this.rollerXZ.forEach(([x, z], i) => { d.position.set(x, BELT_Y - 0.085, z); d.rotation.set(0, 0, this.rollerAngle); d.updateMatrix(); this.rollers.setMatrixAt(i, d.matrix); });
    this.rollers.instanceMatrix.needsUpdate = true;
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
      for (const [stn, a, b] of p.events) this.stations[laneKey(stn, p.line)]?.intervals.push([a, b, p]);
      const endT = kf[kf.length - 1][0];
      this.parts.push({ p, kf, m, review, endT, shipT: p.fate === 'shipped' ? endT : null, scrapT: p.fate === 'scrap' ? endT : null,
        caught: caughtIds.has(p.id), yaw: (hash(p.id) - 0.5) * 0.5 });
    }
    for (const x of this.parts) {  // print jobs: from job start to the moment the part leaves the printer
      const k = x.p.kind === 'slot' ? 'printer_slot' : 'printer_tab';
      this.stations[k].intervals.push([x.p.print_t, x.kf[0][0], x.p]);
    }
    const local = data.parts.some((p) => p.events.some((e) => e[0].endsWith('_local')));
    for (const k of ['phone_local', 'caliper_local']) { const s = this.stations[k]; s.mesh.visible = s.lamp.visible = local; s.hiddenStation = !local; }
    this.T = Math.max(...this.parts.map((x) => x.endT)) + 5;
    this.t0 = Math.max(0, Math.min(...this.parts.map((x) => x.kf[0][0])) - 2);
  }

  update(t, dtReal, playing, truth) {  // eslint-disable-line
    if (!this.data) return { ship: 0, hold: 0, scrap: 0, esc: 0 };
    // belt texture: 12 repeats over 23 units -> 1 texture unit = 1.92 scene units
    if (playing) for (const tx of this.beltTexes) tx.offset.x -= (dtReal * lab.speed * BELT_SPEED) / 1.92;
    let ship = 0, hold = 0, scrap = 0, esc = 0; const shipped = new Set(); let selVisible = false;
    for (const x of this.parts) {
      const xy = at(x.kf, t); x.m.visible = !!xy; if (!xy) continue;
      const inReview = x.review.some(([a, b]) => t >= a && t <= b);
      const stacked = x.p.kind === 'tab' && x.shipT && t >= x.shipT;
      x.m.position.set(xy[0], heightAt(xy[0], xy[1]) + (stacked ? 0.11 : 0) + xy[2], xy[1]); x.m.rotation.y = x.yaw;
      const mat = x.m.material; let col = x.p.kind === 'slot' ? C.slot : C.tab, em = BLACK, ei = 0;
      if (inReview) { col = C.review; em = C.review; ei = 0.35; }
      if (x.scrapT && t >= x.scrapT) col = C.scrap;
      if (x.caught && ((x.review.length && t >= x.review[0][0]) || (x.shipT && t >= x.shipT) || (x.scrapT && t >= x.scrapT))) { em = C.caught; ei = 0.7; }
      if (truth && x.p.escaped && x.shipT && t >= x.shipT) { col = C.escape; em = C.escape; ei = 0.9; }
      mat.color.copy(col); mat.emissive.copy(em); mat.emissiveIntensity = ei;
      if (x.review.length && t >= x.review[0][0]) hold++;
      if (x.scrapT && t >= x.scrapT) scrap++;
      if (x.shipT && t >= x.shipT && x.p.pair && !shipped.has(x.p.pair)) { shipped.add(x.p.pair); if (x.p.escaped) esc++; else ship++; }
      if (this.selected === x.p.id) { selVisible = true; this.ring.position.set(x.m.position.x, x.m.position.y - 0.12, x.m.position.z); }
    }
    this.ring.visible = selVisible;
    for (const [k, st] of Object.entries(this.stations)) {
      const cur = st.intervals.find(([a, b]) => t >= a && t <= b);
      const busyCol = k === 'review' ? C.review : C.accent;
      st.lamp.material.emissive.copy(cur ? busyCol : BLACK); st.lamp.material.emissiveIntensity = cur ? 2.2 : 0;
      st.lamp.material.color.copy(cur ? busyCol : LAMP_OFF);
      if (st.cone) { st.cone.material.opacity = cur ? 0.12 : 0; for (const l of st.lenses || [st.lens]) l.material.emissiveIntensity = cur ? 2.0 : 0.1; }
      const r = this.readouts[k];
      if (r) {
        r.visible = !!cur;
        if (cur) {
          const p = cur[2];
          if (k.startsWith('caliper')) { r.element.textContent = `${fmt(p.measured_mm, 3)} mm`; r.element.style.background = ''; }
          else { const v = p.cams?.phone; r.element.textContent = v === null || v === undefined ? '— missing' : v ? '⚑ flagged' : '✔ clear'; r.element.style.background = v ? css('--review') : (v === null ? css('--scrap') : ''); }
        }
      }
    }
    if (playing) { this.rollerAngle -= (dtReal * lab.speed * BELT_SPEED) / 0.055; this.updateRollers(); }
    const now = performance.now() / 1000;
    for (const k of ['printer_slot', 'printer_tab']) {
      const st = this.stations[k], pr = st.printer, jobs = st.intervals.filter(([a, b]) => t >= a && t <= b);
      const on = jobs.length > 0;
      pr.gantry.position.x = on ? Math.sin(now * 2.1) * 0.6 : 0; pr.head.position.x = pr.gantry.position.x;
      pr.head.position.z = on ? Math.sin(now * 3.3) * 0.55 : 0; pr.nozzle.material.emissiveIntensity = on ? 2.4 : 0;
      pr.wipMesh.visible = on;
      if (on) { const [a, b] = jobs[0]; pr.wipMesh.scale.y = Math.max(0.02, Math.min(1, (t - a) / Math.max(1, b - a))); }
      const rep = jobs.find((j) => j[2].reprint_of);
      pr.readout.visible = !!rep;
      if (rep) { pr.readout.element.textContent = `↻ reprint ${rep[2].root_id || ''}`; pr.readout.element.style.background = css('--caught'); }
    }
    if (this.robot) {
      const busy = this.stations.assembly.intervals.some(([a, b]) => t >= a && t <= b);
      const ph = busy ? now * 2.4 : 0;
      this.robot.yaw.rotation.y = busy ? Math.sin(ph) * 1.1 : 0.4;
      this.robot.shoulder.rotation.z = busy ? 0.55 + Math.sin(ph * 2) * 0.25 : 0.2;
      this.robot.elbow.rotation.z = busy ? 1.1 + Math.cos(ph * 2) * 0.3 : 1.4;
    }
    const busyAt = (st) => st.intervals.some(([a, b]) => t >= a && t <= b);
    const lf = lab.liveFlash;
    if (lf && performance.now() < lf.until && this.stations[lf.key]) {   // physical event: flash the station
      const st = this.stations[lf.key]; st.lamp.material.color.copy(C.caught); st.lamp.material.emissive.copy(C.caught); st.lamp.material.emissiveIntensity = 3;
      const r = this.readouts[lf.key]; if (r) { r.visible = true; r.element.textContent = lf.text; r.element.style.background = css('--caught'); }
    }
    const opBusy = [busyAt(this.stations.caliper_0) || busyAt(this.stations.caliper_1), busyAt(this.stations.review), busyAt(this.stations.rework)];
    this.operators.forEach((o, i) => { o.position.y = opBusy[i] ? Math.abs(Math.sin(now * 4 + i)) * 0.03 : 0; o.rotation.x = opBusy[i] ? 0.12 : 0; });
    for (const line of [0, 1]) {
      const key = `caliper_${line}`, gap = busyAt(this.stations[key]) ? 0.16 : 0.3;
      this.jaws[line][0].position.x = P[key][0] - gap; this.jaws[line][1].position.x = P[key][0] + gap;
    }
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

// Height of a part's resting surface at (x, z): conveyor, buffer table, review/rework benches or floor pads.
function heightAt(x, z) {
  if (x > -12.8 && x < -0.2 && (Math.abs(z - 1) < 0.62 || Math.abs(z + 1) < 0.62)) return BELT_Y + 0.07;
  if (x > 1.3 && x < 10.2 && Math.abs(z) < 0.62) return BELT_Y + 0.07;
  if (Math.abs(x - P.buffer[0]) < 0.85 && Math.abs(z) < 1.75) return 0.76;
  if (z < -4.6 && x > 0.8 && x < 8.4) return 1.02;
  if (Math.abs(x - P.printer_slot[0] - 1.7) < 0.3) return 0.25;
  return 0.25;
}
function pathFor(p, binIndex) {
  const kf = [], j = hash(p.id), jz = (j - 0.5) * 0.6;
  const pos = (k, dx = 0, dz = 0) => { const [x, z] = P[laneKey(k, p.line)] || P.buffer; return [x + dx, z + dz]; };
  const pr = p.kind === 'slot' ? 'printer_slot' : 'printer_tab';
  const first = p.events.length ? p.events[0][1] : p.print_t + 60;
  const out = Math.max(p.print_t, first - 25);
  kf.push([out, ...pos(pr, 1.7, jz * 0.8)]);
  let prevEnd = out + 2, prevKey = pr;
  kf.push([prevEnd, ...pos(pr, 1.7, jz * 0.8)]);
  for (const [station, start, end] of p.events) {
    const [px, pz] = pos(prevKey), [sx, sz] = pos(station);
    const travel = Math.min(Math.max(0.5, start - prevEnd), Math.hypot(sx - px, sz - pz) / BELT_SPEED);
    const arrive = Math.max(prevEnd, Math.min(start, prevEnd + travel));
    kf.push([prevEnd, ...pos(prevKey, prevKey.startsWith('printer') ? 1.7 : 0, prevKey.startsWith('printer') ? jz * 0.8 : jz * 0.25)]);
    if (start - arrive > 1) kf.push([arrive, ...pos(station, -1.15, jz)], [start - 0.5, ...pos(station, -0.95, jz)]);
    kf.push([start, ...pos(station, 0, jz * 0.25)], [end, ...pos(station, 0, jz * 0.25)]);
    prevEnd = end; prevKey = station;
  }
  const last = kf[kf.length - 1][0];
  const binPos = (k) => { const [x, z] = P[k]; const i = binIndex; return [x - 1.05 + (i % 6) * 0.42, z - 1.05 + (Math.floor(i / 6) % 6) * 0.42]; };
  const [lx, lz] = pos(prevKey), toBin = (k) => Math.hypot(P[k][0] - lx, P[k][1] - lz) / BELT_SPEED;
  if (p.fate === 'shipped') kf.push([last + toBin('ship'), ...binPos('ship')]);
  else if (p.fate === 'scrap') kf.push([last + toBin('scrap'), ...binPos('scrap')]);
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
  ['Two lanes, iPhone cameras', 'Slots run on one lane, tabs on the other. An iPhone camera over each lane checks the surface; the readout shows its result. Click a camera and choose "Open camera" to see its view or attach a real photo.', [-11, 5, 7], [-8, 1.2, 0]],
  ['Calipers', 'One operator serves both calipers. The calibrated policy turns each reading into a posterior. Click any part to see its evidence chain.', [-6, 3.8, 5.5], [-4.5, 0.8, 0]],
  ['Pairing and gate', 'Risk-optimised pairing picks partners (SciPy linear assignment). The pair gate still decides: P(unsafe) ≥ 1.32% means HOLD, whatever pairing saves.', [0, 6, 7], [2.5, 0.5, -0.5]],
  ['Review (HOLD)', 'Held parts go to review (45 s, shared operator). Holding everything looks "safe and cheap" on paper but cuts throughput by 82%.', [3, 6, 0], [3.5, 0.5, -5]],
  ['Shipped', 'Turn on ground truth: a red part is a shipped defect. In Compare mode, purple parts are defects the rule shipped and QualityRelay stopped.', [9, 6, 6], [11, 0, -2]],
];
const lab = { mode: 'single', views: [], runs: [], t: 0, T: 1, t0: 0, playing: true, speed: 10, sel: null, story: -1, caught: new Set() };

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
  startLive();
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
      if (lab.camView && !$('#studio').classList.contains('noinsp')) {
        const cones = [...Object.values(lab.camView.view.stations).filter((s) => s.cone).map((s) => s.cone), lab.camView.view.stationRing, lab.camView.view.ring];
        const prev = cones.map((c) => c.visible); cones.forEach((c) => (c.visible = false));   // the camera must not see its own light cone
        lab.camView.renderer.render(lab.camView.view.s.scene, lab.camView.cam); cones.forEach((c, i) => (c.visible = prev[i]));
      }
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
  if (q.get('select')?.startsWith('phone_') || q.get('select')?.startsWith('caliper_')) select({ type: 'station', id: q.get('select'), side: 0 });
  if (q.get('part')) select({ type: 'part', id: q.get('part'), side: lab.runs.length - 1 });
  if (q.get('select') === 'caught') { const id = [...lab.caught][0] || lab.runs.at(-1)?.parts.find((p) => p.pair)?.id; if (id) select({ type: 'part', id, side: lab.runs.length - 1 }); }
}

function startLive() {
  if (!window.EventSource || new URLSearchParams(location.search).get('nolive')) return;  // nolive=1: screenshots / offline demos
  const es = new EventSource('/sim/live/stream');
  es.onopen = () => ($('#liveState').textContent = 'connected');
  es.onerror = () => ($('#liveState').textContent = 'offline');
  es.onmessage = (m) => {
    const e = JSON.parse(m.data), feed = $('#liveFeed');
    if (feed.classList.contains('faint')) { feed.classList.remove('faint'); feed.innerHTML = ''; }
    feed.insertAdjacentHTML('afterbegin', `<div><b>LIVE</b><span>${e.station_id} · ${e.lane} · ${e.specimen_id} · ${e.value ?? ''} · ${e.source_tier}${e.verified ? '' : ' · unverified'}</span></div>`);
    while (feed.children.length > 6) feed.lastChild.remove();
    const key = e.station_id === 'phone' || e.station_id === 'caliper' ? `${e.station_id}_${e.lane === 'tab' ? 1 : 0}` : e.station_id === 'assembly' ? 'assembly' : null;
    if (key) lab.liveFlash = { key, until: performance.now() + 2500, text: `LIVE ${e.value ?? ''}` };
    $('#liveState').textContent = `${e.seq} events`;
  };
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
    ${p.reprint_of ? `<div class="why" style="border-color:var(--caught)"><b>↻ Reprint</b> of <span class="link" data-part="${p.reprint_of}" data-side="${side}">${p.reprint_of}</span>: the defective original was scrapped and this part was printed again from the nominal CAD model (printer re-zeroed). It went through the full inspection again.</div>` : ''}
    ${p.reprinted_as ? `<div class="why"><b>Defect confirmed → reprinted</b> as <span class="link" data-part="${p.reprinted_as}" data-side="${side}">${p.reprinted_as}</span>.</div>` : ''}
    <section><h4>Evidence (what the system saw)</h4><div class="kv">
      ${Object.entries(p.cams || {}).map(([k, v]) => `<span>${STN[k] || k} · ${p.kind} lane</span><span>${camTxt(v)}</span>`).join('')}
      <span>caliper reading</span><span>${fmt(p.measured_mm, 3)} mm (σ ${fmt(p.caliper_sd, 2)})</span>
      <span>P(surface defect)</span><span>${p.surface_posterior === null ? '—' : pct(p.surface_posterior, 3)}</span>
      <span>expert review</span><span>${p.reviewed ? 'cleared' : p.events.some((e) => e[0] === 'review') ? 'yes' : 'no'}</span></div>
      <p class="faint small">Camera sensitivity/specificity come from a held-out calibration (${run.model.calibration_id}).</p></section>
    ${decision}
    <section><h4>Plain-language explanation <span class="badge mute">template · no LLM</span></h4><p class="explain">${explain(p, pair, run, truth)}</p></section>
    <section><h4>Timeline</h4><ul class="tl">${tl || '<li><span>—</span></li>'}</ul></section>
    ${truthSec}
    <section><h4>Part passport (QR)</h4><div style="display:flex;gap:12px;align-items:center"><div class="qr">${passportQR(p.id)}</div>
      <p class="faint small">Scan to reopen this exact part and its evidence chain. Phones on the same network need the server started with <code>--host 0.0.0.0</code>.</p></div></section>`;
}
function cameraSection(k) {
  return `<section><h4>Camera · ${k === 'phone_0' ? 'slot' : 'tab'} lane</h4>
    <div class="camview" id="camView"><span class="corner tl faint">SIMULATED VIEW</span></div>
    <div class="row2" style="margin-top:8px"><button class="ghost" id="camDevice">📷 Open device camera</button>
      <label class="ghost filebtn">⬆ Upload photo<input type="file" accept="image/*" capture="environment" id="camFile" hidden></label></div>
    <video id="camVideo" class="camimg" playsinline muted hidden></video><img id="camPhoto" class="camimg" alt="captured photo" hidden>
    <div class="row2" style="margin-top:8px">
      <label>Purpose<select id="camPurpose"><option value="training">training photo (model)</option><option value="measurement">measurement / reference</option></select></label>
      <label>Specimen ID<input id="camSpec" type="text" placeholder="e.g. P07" maxlength="40" style="display:block;width:100%;margin-top:4px;background:var(--panel2);color:var(--text);border:1px solid var(--border2);border-radius:6px;padding:6px 8px"></label></div>
    <div class="row2">
      <label>Label<select id="camLabel"><option value="inbox">label later</option><option value="good">good part</option><option value="defect">defective part</option></select></label>
      <label>Defect type<select id="camDefect" disabled><option value="">—</option>${['warp', 'stringing', 'chip', 'hole', 'crack', 'layer_shift', 'under_extrusion', 'wrong_size', 'other'].map((d) => `<option>${d}</option>`).join('')}</select></label></div>
    <div class="row2"><label>Caliper reading, mm (optional)<input id="camCal" type="number" step="0.01" min="0" max="99"></label>
      <button class="primary" id="camSave" disabled style="align-self:end;margin-bottom:10px">Save + NVIDIA check</button></div>
    <p class="faint small">Training photos: marker in the same corner every time, turn good parts a little between shots, mix part types. Measurement photos: part placed the same way against the marker; add the caliper reading. See PHOTO_CAPTURE_GUIDE.md.</p>
    <div id="camResult" class="faint small" style="margin-top:8px">The photo is saved as PHYSICAL_CAPTURE training data (data/prints/…). The NVIDIA anomaly model scores it once it has been trained on real photos.</div></section>
    <section><h4>Visual inspection <span class="badge mute">candidates · review required</span></h4>
      <p class="faint small">Uses the open-source inspection pack: image-quality gate, photo-vs-reference difference after ArUco registration, heatmap, candidate boxes, and Roboflow prediction boxes. Results are UNVERIFIED_VISUAL_CANDIDATE and never pass or reject a part.</p>
      <div class="row2"><button class="ghost" id="visRef" disabled>★ Set as GOOD reference</button><button class="ghost" id="visCmp" disabled>⇄ Compare with reference</button></div>
      <details style="margin-top:8px"><summary class="faint small">Model output (Roboflow prediction JSON)</summary>
        <textarea id="visRf" rows="4" style="width:100%;margin-top:6px;background:var(--panel2);color:var(--text);border:1px solid var(--border2);border-radius:6px;font:11px var(--mono)" placeholder='{"predictions":[{"x":120,"y":80,"width":30,"height":20,"confidence":0.7,"class":"crack"}]}'></textarea>
        <button class="ghost" id="visRfBtn" disabled style="width:100%">Draw model boxes</button></details>
      <div id="visOut" class="small" style="margin-top:8px"></div></section>`;
}
function passportURL(id) {
  const r = lab.runs.at(-1); const q = new URLSearchParams({ scenario: r.scenario, seed: r.seed, pairs: r.n_pairs, policy: r.policy, pairing: r.pairing, part: id });
  if (lab.mode === 'compare') q.set('mode', 'compare');
  return `${location.origin}/?${q}#lab`;
}
function passportQR(id) {
  if (typeof qrcode !== 'function') return '<span class="faint">QR library missing</span>';
  const q = qrcode(0, 'M'); q.addData(passportURL(id)); q.make(); return q.createSvgTag({ cellSize: 3, margin: 2, scalable: true });
}
// I7: deterministic, evidence-grounded explanation (no LLM key configured; nothing is invented)
function explain(p, pair, run, truth) {
  const kind = p.kind === 'slot' ? 'slot' : 'tab', nominal = p.kind === 'slot' ? 21.0 : 20.0, out = [];
  out.push(`This ${kind} (${p.id}) was printed in ${p.lot.split(':').pop()} at ${mmss(p.print_t)}${p.reprint_of ? `, as a reprint of ${p.reprint_of}` : ''}.`);
  const cam = p.cams?.phone;
  out.push(cam === null || cam === undefined ? 'The iPhone camera produced no reading, so the surface counts as not checked, never as clear.'
    : cam ? 'The iPhone camera flagged a possible surface defect, so the part went to expert review.' : 'The iPhone camera saw no surface defect.');
  out.push(`The caliper measured ${fmt(p.measured_mm, 3)} mm (${sign(p.measured_mm - nominal, 3)} mm from the ${nominal.toFixed(1)} mm CAD nominal).`);
  if (pair) {
    if (pair.reason === 'STALE_OR_MISSING_EVIDENCE') out.push('Its pair was held because supplier evidence arrived after the deadline.');
    else if (run.policy === 'rules') out.push(`Paired with ${p.kind === 'slot' ? pair.tab : pair.slot}, the measured clearance was ${fmt(pair.measured_clearance_mm, 3)} mm, so the rule said ${pair.decision === 'HOLD' ? 'HOLD (below 0.50 mm or a camera flag)' : 'PASS'}.`);
    else out.push(`Paired with ${p.kind === 'slot' ? pair.tab : pair.slot}, the estimated clearance was ${fmt(pair.posterior_clearance_mm, 3)} ± ${fmt(pair.posterior_clearance_sd, 3)} mm. The chance the pair is unsafe came out at ${pct(pair.p_unsafe, 3)}, ${pair.p_unsafe >= pair.threshold ? 'above' : 'below'} the ${pct(pair.threshold, 2)} break-even, so it was ${pair.decision === 'HOLD' ? 'held for review' : 'passed for assembly'}.`);
  }
  out.push(p.fate === 'shipped' ? 'It was assembled and shipped.' : p.fate === 'scrap' ? `It was scrapped after review${p.reprinted_as ? ` and reprinted as ${p.reprinted_as}` : ''}.` : 'It was still waiting for a partner when the run ended.');
  if (truth && pair) out.push(`Ground truth (evaluator only): the pair was ${pair.truly_safe ? 'safe' : 'unsafe'}, so the decision was ${(pair.decision === 'HOLD') !== pair.truly_safe ? 'right' : (pair.decision === 'HOLD' ? 'cautious (a false hold)' : 'wrong (an escape)')}.`);
  return out.join(' ');
}
function stationCard(k, side) {
  const run = lab.runs[side], s = run?.stations[k], [name, desc] = STATION_INFO[k];
  return `<h2>${name}</h2><div class="sub">station · ${run.scenario} · ${run.policy}+${run.pairing}</div><p class="muted">${desc}</p>
    ${s ? `<section><h4>Load in this run</h4><div class="kv"><span>visits</span><span>${s.visits}</span><span>busy time</span><span>${fmt(s.busy_s / 60, 1)} min</span>
      <span>busy share of the run</span><span>${pct(s.busy_share, 0)}</span><span>mean service</span><span>${fmt(s.busy_s / Math.max(1, s.visits), 1)} s</span></div>
      <div class="bar"><i style="width:${Math.min(100, 100 * s.busy_share)}%"></i></div></section>` : '<section><p class="faint">No timed visits are recorded for this station in this run.</p></section>'}
    ${k.startsWith('phone_') ? cameraSection(k) : ''}`;
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
    <section><h4>Provenance</h4><p class="faint small">SIMULATED. Toy part generator, illustrative station timings, held-out calibration ${r.model.calibration_id}. Not a factory measurement.
      This 3D Lab runs two lanes with one iPhone camera each (cameras: ${(r.cameras || []).join(', ')}) and reprints confirmed defects. The pre-registered results in the Results tab used phone + Pi cameras without reprint.</p></section>`;
  return html;
}
function renderInspector() {
  const truth = $('#truth').checked, sel = lab.sel; let html;
  if (sel?.type === 'part') {
    const side = Math.min(sel.side ?? 0, lab.runs.length - 1);
    const p = findPart(sel.id, side); html = p ? partCard(p, side, truth) : summaryCard(); $('#inspHint').textContent = 'part';
  } else if (sel?.type === 'station') { html = stationCard(sel.id, Math.min(sel.side ?? 0, lab.runs.length - 1)); $('#inspHint').textContent = 'station'; }
  else { html = summaryCard(); $('#inspHint').textContent = 'click a part or a station'; }
  stopCamera(); lab.camView = null;
  $('#inspBody').innerHTML = html;
  if (sel?.type === 'station' && sel.id.startsWith('phone_')) bindCameraPanel(sel.id, Math.min(sel.side ?? 0, lab.runs.length - 1));
  $$('#inspBody [data-part]').forEach((el) => (el.onclick = () => select({ type: 'part', id: el.dataset.part, side: el.dataset.side !== undefined ? +el.dataset.side : 0 })));
}

// ---------------------------------------------------------------- camera panel
let camStream = null, camRenderer = null;
function stopCamera() { camStream?.getTracks().forEach((t) => t.stop()); camStream = null; }
function bindCameraPanel(k, side) {
  const view = lab.views[side], st = view.stations[k];
  const el = $('#camView');
  if (!camRenderer) { camRenderer = new THREE.WebGLRenderer({ antialias: true }); camRenderer.setPixelRatio(Math.min(devicePixelRatio, 2)); camRenderer.toneMapping = THREE.ACESFilmicToneMapping; }
  camRenderer.setSize(el.clientWidth, el.clientHeight); el.prepend(camRenderer.domElement);
  const cam = new THREE.PerspectiveCamera(58, el.clientWidth / el.clientHeight, 0.02, 60);
  cam.up.set(0, 0, -1); cam.position.set(...st.camPos); cam.lookAt(...st.camTarget);
  lab.camView = { view, cam, renderer: camRenderer };
  let photo = null;
  const setPhoto = (dataUrl) => { photo = dataUrl; $('#camPhoto').src = dataUrl; $('#camPhoto').hidden = false; $('#camVideo').hidden = true; $('#camSave').disabled = false;
    for (const id of ['#visRef', '#visCmp', '#visRfBtn']) $(id).disabled = false; inspect('quality'); };
  const lane = k === 'phone_0' ? 'slot' : 'tab';
  const inspect = async (action) => {
    const out = $('#visOut'); out.innerHTML = '<span class="faint">Running…</span>';
    try {
      const r = await api('/sim/vision/inspect', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lane, action, image_b64: photo, roboflow_json: action === 'roboflow' ? $('#visRf').value : null }) });
      const q = r.quality, rep = r.report;
      let html = `<div class="kv"><span>image quality</span><span>${q.warnings.length ? `<span class="badge hold">${q.warnings.join(', ')}</span>` : '<span class="badge ok">usable</span>'}</span>
        <span>sharpness (Laplacian var.)</span><span>${fmt(q.blur_laplacian_variance, 0)}</span>`;
      if (r.registration) html += `<span>registration</span><span>${r.registration.status === 'REGISTERED' ? 'ArUco ✔' : r.registration.status}</span>`;
      if (rep) html += `<span>candidate regions</span><span>${rep.regions.length}</span><span>decision</span><span><span class="badge hold">${rep.decision}</span></span>`;
      html += '</div>';
      if (r.reference_saved) html += `<div class="why">GOOD reference saved for the ${lane} lane (registered to the marker frame).</div><img class="camimg" src="${r.preview}" alt="reference">`;
      if (r.heatmap) html += `<div class="row2" style="margin-top:6px"><figure style="margin:0"><img class="camimg" src="${r.heatmap}" alt="difference heatmap"><figcaption class="faint small">difference heatmap</figcaption></figure><figure style="margin:0"><img class="camimg" src="${r.boxes}" alt="candidate boxes"><figcaption class="faint small">candidate boxes</figcaption></figure></div>`;
      else if (r.boxes) html += `<img class="camimg" src="${r.boxes}" alt="model boxes"><p class="faint small">Model boxes: untrusted predictions; check the model's licence and weights.</p>`;
      if (rep) html += `<p class="faint small">${rep.claim_boundary} ${rep.warnings.join(' · ')}</p>`;
      html += `<p class="faint small">Anomaly heatmap (STFPM / Anomalib): ${r.anomaly_model.status}.</p>`;
      out.innerHTML = html;
    } catch (err) { out.innerHTML = `<span class="faint">${err.message.includes('409') ? 'No GOOD reference for this lane yet: set one first.' : err.message.includes('422') ? 'Needs the printed ArUco marker in the photo (or valid Roboflow JSON).' : err.message}</span>`; }
  };
  $('#visRef').onclick = () => inspect('set_reference'); $('#visCmp').onclick = () => inspect('compare'); $('#visRfBtn').onclick = () => inspect('roboflow');
  $('#camFile').onchange = (e) => { const f = e.target.files?.[0]; if (!f) return; const r = new FileReader(); r.onload = () => setPhoto(r.result); r.readAsDataURL(f); };
  $('#camDevice').onclick = async () => {
    if (camStream) {   // second click = capture a frame
      const v = $('#camVideo'), c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight;
      c.getContext('2d').drawImage(v, 0, 0); setPhoto(c.toDataURL('image/jpeg', 0.92)); stopCamera(); $('#camDevice').textContent = '📷 Open device camera'; return;
    }
    try {
      camStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 } } });
      const v = $('#camVideo'); v.srcObject = camStream; v.hidden = false; $('#camPhoto').hidden = true; await v.play();
      $('#camDevice').textContent = '⏺ Capture photo';
    } catch (err) { $('#camResult').textContent = `Camera unavailable: ${err.message}. Use "Upload photo" instead.`; }
  };
  $('#camLabel').onchange = () => { $('#camDefect').disabled = $('#camLabel').value !== 'defect'; if ($('#camDefect').disabled) $('#camDefect').value = ''; };
  $('#camSave').onclick = async () => {
    $('#camSave').disabled = true; $('#camResult').textContent = 'Saving…';
    try {
      const r = await api('/sim/vision/capture', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lane: k === 'phone_0' ? 'slot' : 'tab', label: $('#camLabel').value, image_b64: photo, purpose: $('#camPurpose').value,
          specimen_id: $('#camSpec').value.trim() || null, defect_type: $('#camDefect').value || null,
          caliper_mm: $('#camCal').value ? +$('#camCal').value : null }) });
      const n = r.nvidia_anomaly, c = r.dataset_counts;
      const ms = r.measurement || {};
      const meas = ms.status === 'MEASURED' ? `<span>width from photo</span><span>${ms.kind === 'slot_opening' ? 'slot opening' : 'tab width'} <b>${fmt(ms.width_mm, 3)} mm</b></span><span>photo resolution</span><span>${fmt(ms.photo_px_per_mm, 1)} px/mm${ms.photo_px_per_mm < 15 ? ' (low: move closer)' : ''}</span>`
        : `<span>width from photo</span><span class="faint">${ms.status || '—'}: put the ArUco sheet next to the part</span>`;
      const cal = r.photo_minus_caliper_mm !== null && r.photo_minus_caliper_mm !== undefined ? `<span>photo − caliper</span><span><b>${sign(r.photo_minus_caliper_mm, 3)} mm</b></span>` : '';
      $('#camResult').innerHTML = `<div class="kv">${meas}${cal}<span>saved</span><span>${r.saved.split('/').slice(-2).join('/')}</span><span>size</span><span>${r.width} × ${r.height}</span>
        <span>tier</span><span>${r.source_tier}</span><span>dataset</span><span>good ${c.good} · defect ${c.defect} · inbox ${c.inbox}</span></div>
        <div class="why"><b>NVIDIA anomaly model: ${n.status}.</b> ${n.reason} ${n.ready_to_train ? '<b>Enough photos to train now:</b>' : `Need ≥ ${n.need.good} good and ≥ ${n.need.defect} defect photos, then:`} <code>${n.train_command}</code></div>`;
      try {
        const sg = await api('/sim/vision/suggest?limit=3');
        if (sg.suggestions.length) $('#camResult').insertAdjacentHTML('beforeend', `<div class="why"><b>Label next (most informative first):</b><br>${sg.suggestions.map((x) => `${x.file}: ${x.reason}`).join('<br>')}</div>`);
      } catch { /* suggestions are optional */ }
    } catch (err) { $('#camResult').textContent = err.message.includes('422') ? 'Not saved: a defective training photo needs a defect type; specimen ID may use letters, digits, - and _ only.' : `Save failed: ${err.message}`; }
    $('#camSave').disabled = false;
  };
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
