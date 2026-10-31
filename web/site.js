// QualityRelay Studio (18.1). WEB-01: three separated views, each with its own source tier.
//   #physical  Live Physical Inspection         hardware ledger only (PHYSICAL_CAPTURE / VERIFIED_PHYSICAL)
//   #sim/...   Digital Factory Simulation       SIMULATED
//   #agents/.. Agent Collaboration & Benchmark  TEST_FIXTURE trace + SIMULATED benchmark
// Nothing from one family is drawn inside another: physical events never animate the simulated line.
import * as THREE from 'three';
import CameraControls from 'camera-controls';
CameraControls.install({ THREE });  // yomotsu/camera-controls: smooth orbit / truck / dolly, the de-facto three.js camera rig
import { STLLoader } from 'three/addons/STLLoader.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/CSS2DRenderer.js';
import { RoomEnvironment } from 'three/addons/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/EffectComposer.js';
import { RenderPass } from 'three/addons/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/OutputPass.js';
import { GTAOPass } from 'three/addons/GTAOPass.js';
import { SMAAPass } from 'three/addons/SMAAPass.js';
import { RGBELoader } from 'three/addons/RGBELoader.js';
let ptModule = null;  // three-gpu-pathtracer, loaded on first Photo mode

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
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const ctx = { physical: 'hardware ledger', sim: '—', agents: '—', claims: '' };  // app-bar context line, per family
const hash = (s) => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return (h >>> 0) / 4294967295; };
// Conveyor speed in scene units per SIMULATED second (1 unit ≈ 0.25 m in this layout -> ~0.15 m/s).
const BELT_SPEED = 0.6;
const BELT_Y = 0.62;  // conveyor surface height
const Y_AXIS = new THREE.Vector3(0, 1, 0);
const QUEUE_GAP = 1.3;  // centre spacing of queued parts: an assembled pair is 72 mm = 1.15 units, plus a visible gap
// Tab centre relative to slot centre when assembled: +12 mm along the part (0.016 scene units per mm).
const ASSEMBLED_TAB_OFFSET = new THREE.Vector3(12.3 * 0.016, -0.002, 0);  // 0.3 mm air gap + tiny drop: no coincident faces (z-fighting)
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
// FDM look: 0.2 mm layer lines as a bump map. UV v = height in layers (8 layers per texture tile),
// computed in mm before scaling, so the line pitch is the true layer height.
const LAYER_MM = 0.2, LAYERS_PER_TILE = 8;
const addLayerUV = (g) => {
  const pos = g.attributes.position, uv = new Float32Array(pos.count * 2);
  for (let i = 0; i < pos.count; i++) { uv[2 * i] = (pos.getX(i) + pos.getZ(i)) / 4; uv[2 * i + 1] = pos.getY(i) / (LAYER_MM * LAYERS_PER_TILE); }
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
};
const layerBump = (() => {
  const c = document.createElement('canvas'); c.width = 4; c.height = 64; const g = c.getContext('2d');
  for (let y = 0; y < 64; y++) { const v = Math.round(128 + 110 * Math.pow(Math.abs(Math.sin((Math.PI * y * LAYERS_PER_TILE) / 64)), 0.6)); g.fillStyle = `rgb(${v},${v},${v})`; g.fillRect(0, y, 4, 1); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
})();
// Matte PLA: no clearcoat, slight sheen from the layer ridges.
const plaMat = (color, o = {}) => new THREE.MeshPhysicalMaterial({ color, roughness: 0.5, metalness: 0, bumpMap: layerBump, bumpScale: 0.6, sheen: 0.25, sheenRoughness: 0.6, ...o });
const metal = (color, o = {}) => new THREE.MeshStandardMaterial({ color, metalness: 0.2, roughness: 0.55, envMapIntensity: 0.45, ...o });

// ---------------------------------------------------------------- render quality
// ?quality=low (or the toggle) drops ambient occlusion, SMAA and the HDRI for slow laptops.
const QUALITY = (() => { const q = new URLSearchParams(location.search).get('quality') || localStorage.getItem('qr_quality'); return q === 'low' ? 'low' : 'high'; })();
// Real warehouse lighting (Poly Haven CC0 HDRI), shared by every stage; falls back to RoomEnvironment.
let hdrPromise = null;
const loadHDR = () => (hdrPromise ??= new Promise((res) => new RGBELoader().load('/sim/hdri/warehouse.hdr', res, undefined, () => res(null))));

// Photo mode traces a flattened copy of what is visible: one mesh per material group and per instance,
// plain PBR materials (colour, map, roughness, metalness, emission). The path tracer mis-assigns
// materials on multi-material and instanced meshes, so it never sees those directly.
function flattenForTrace(src) {
  const out = new THREE.Scene(); src.updateMatrixWorld(true);
  const simple = new Map();
  const toStd = (m) => {
    if (!simple.has(m)) simple.set(m, new THREE.MeshStandardMaterial({
      color: m.color?.clone() ?? new THREE.Color(0xffffff), map: m.map ?? null,
      roughness: m.roughness ?? 0.8, metalness: m.metalness ?? 0, roughnessMap: m.roughnessMap ?? null,
      emissive: m.isMeshBasicMaterial ? m.color.clone().multiplyScalar(0.15) : (m.emissive?.clone() ?? new THREE.Color(0)),
      emissiveIntensity: m.emissiveIntensity ?? 1, transparent: m.transparent, opacity: m.opacity, side: m.side }));
    return simple.get(m);
  };
  src.traverseVisible((o) => {
    if (o.isLight && (o.isDirectionalLight || o.isPointLight || o.isSpotLight)) { const l = o.clone(); l.matrixAutoUpdate = false; l.matrix.copy(o.matrixWorld); if (o.target) { l.target = o.target.clone(); out.add(l.target); l.target.position.setFromMatrixPosition(o.target.matrixWorld); } out.add(l); return; }
    if (!o.isMesh || o.isCSS2DObject) return;
    const base = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone();
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const groups = Array.isArray(o.material) && o.geometry.groups.length ? o.geometry.groups : [{ start: 0, count: Infinity, materialIndex: 0 }];
    const mtx = o.isInstancedMesh ? Array.from({ length: o.count }, (_, i) => { const m = new THREE.Matrix4(); o.getMatrixAt(i, m); return m.premultiply(o.matrixWorld); }) : [o.matrixWorld];
    for (const g of groups) {
      const mat = mats[g.materialIndex]; if (!mat || mat.visible === false) continue;
      const geo = new THREE.BufferGeometry(); const n = base.attributes.position.count, a = g.start, b = Math.min(n, a + g.count);
      for (const [k, at] of Object.entries(base.attributes)) geo.setAttribute(k, new THREE.BufferAttribute(at.array.slice(a * at.itemSize, b * at.itemSize), at.itemSize, at.normalized));
      if (!geo.attributes.normal) geo.computeVertexNormals();
      for (const m of mtx) { const mesh = new THREE.Mesh(geo, toStd(mat)); mesh.matrixAutoUpdate = false; mesh.matrix.copy(m); mesh.matrixWorld.copy(m); out.add(mesh); }
    }
  });
  return out;
}

// ---------------------------------------------------------------- renderer stage (env light + AO + bloom + labels)
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
  let hdrEquirect = null;
  if (QUALITY === 'high') loadHDR().then((hdr) => { if (hdr) { hdr.mapping = THREE.EquirectangularReflectionMapping; hdrEquirect = hdr; scene.environment = pmrem.fromEquirectangular(hdr).texture; scene.environmentIntensity = 0.8; } });
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 400);
  camera.position.set(...camPos);
  const controls = new CameraControls(camera, renderer.domElement);
  controls.setLookAt(...camPos, ...target, false);
  Object.assign(controls, { smoothTime: 0.22, draggingSmoothTime: 0.1, dollyToCursor: true, dollySpeed: 0.8 });
  const clock = new THREE.Clock(); let autoRotate = false;
  controls.addEventListener('controlstart', () => (autoRotate = false));
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(10, 22, 12); key.castShadow = true;
  const sm = QUALITY === 'high' ? 4096 : 1024;
  key.shadow.mapSize.set(sm, sm); Object.assign(key.shadow.camera, { left: -24, right: 24, top: 16, bottom: -16, near: 4, far: 60 });
  key.shadow.bias = -0.0003; key.shadow.normalBias = 0.02; key.shadow.radius = 3;
  scene.add(key, new THREE.HemisphereLight(0xbfd4ff, 0x15181d, 0.35));
  let composer = null;
  if (bloom) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    if (QUALITY === 'high') {
      // Ground-contact shading: radius in scene units (1 unit ≈ 0.25 m), so ~10 cm.
      const ao = new GTAOPass(scene, camera, 512, 512, undefined, { radius: 0.4, distanceExponent: 1.5, thickness: 1, scale: 1, samples: 16 });
      ao.blendIntensity = 0.9; composer.addPass(ao);
    }
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(256, 256), 0.5, 0.4, 0.92));
    composer.addPass(new OutputPass());
    if (QUALITY === 'high') composer.addPass(new SMAAPass(256, 256));  // composer bypasses the canvas MSAA
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
  let tween = null, tracer = null;
  return {
    el, renderer, scene, camera, controls, labelRenderer,
    set autoRotate(on) { autoRotate = on; },
    target() { return controls.getTarget(new THREE.Vector3()); },
    get tracer() { return tracer; },
    // Photo mode: progressive path tracing of the same scene (three-gpu-pathtracer). Fog is dropped
    // (unsupported); the environment is the raw warehouse HDRI so light bounces come from a real room.
    async photo(on) {
      if (on && !tracer) {
        // r160 scenes lack background/environmentRotation (added in r162); the path tracer reads them.
        for (const k of ['backgroundRotation', 'environmentRotation']) if (!(k in THREE.Scene.prototype)) Object.defineProperty(THREE.Scene.prototype, k, { get() { return (this[`_${k}`] ??= new THREE.Euler()); }, configurable: true });
        ptModule ??= await import('three-gpu-pathtracer');
        const hdr = hdrEquirect || await loadHDR();
        if (hdr) hdr.mapping = THREE.EquirectangularReflectionMapping;
        const flat = flattenForTrace(scene);
        flat.background = scene.background; flat.environment = hdr || scene.environment; flat.environmentIntensity = 1.1;
        tracer = new ptModule.WebGLPathTracer(renderer);
        // Show the normal render until 8 samples exist, then fade the traced image in (no raw noise on screen).
        // Trace at CSS-pixel resolution: on Retina this is ~4x faster per sample.
        Object.assign(tracer, { minSamples: 8, renderDelay: 0, fadeDuration: 700, filterGlossyFactor: 0.5, dynamicLowRes: false, rasterizeScene: true,
          renderScale: 1 / Math.min(window.devicePixelRatio || 1, 2) });
        tracer.bounces = 6; tracer.tiles.set(2, 2);
        tracer.setScene(flat, camera);
        this._camM = camera.matrixWorld.clone();
        if (labelRenderer) labelRenderer.domElement.style.visibility = 'hidden';
      } else if (!on && tracer) {
        const t = tracer; tracer = null;
        try { t.dispose(); } catch (e) { /* r160 lacks some internals the tracer frees; nothing else to release */ }
        if (labelRenderer) labelRenderer.domElement.style.visibility = '';
      }
    },
    snapshot() { if (tracer) tracer.renderSample(); else if (composer) composer.render(); else renderer.render(scene, camera); return renderer.domElement.toDataURL('image/png'); },
    move(right, forward) { const k = controls.distance * 0.08; controls.truck(right * k, 0, true); controls.forward(forward * k, true); },
    zoomBy(f) { controls.dollyTo(THREE.MathUtils.clamp(controls.distance * f, controls.minDistance, controls.maxDistance), true); },
    focus(point, dist = 4.5) {  // keep the viewing direction, move in on a point
      const d = camera.position.clone().sub(this.target()).setLength(dist);
      if (d.y < dist * 0.45) d.y = dist * 0.45;
      const p = point.clone().add(d); controls.setLookAt(p.x, p.y, p.z, point.x, point.y, point.z, true);
    },
    flyTo(pos, tgt) { controls.setLookAt(...pos, ...tgt, true); },
    render() {
      const dt = clock.getDelta();
      if (autoRotate) controls.azimuthAngle += dt * 0.25;
      controls.update(dt);
      if (tracer) {
        camera.updateMatrixWorld();
        if (!camera.matrixWorld.equals(this._camM)) { this._camM.copy(camera.matrixWorld); tracer.updateCamera(); }  // restart only when the view really moved
        tracer.renderSample(); return;
      }
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
    // camera-controls defaults: left-drag turn, right-drag / two fingers move, wheel / pinch zoom (to the cursor)
    Object.assign(this.s.controls, { maxPolarAngle: Math.PI / 2.1, minDistance: 2.2, maxDistance: 60 });
    this.s.controls.setBoundary(new THREE.Box3(new THREE.Vector3(-20, 0, -11), new THREE.Vector3(15, 3, 9)));  // the orbit centre stays in the hall
    this.parts = []; this.stations = {}; this.labels = []; this.readouts = {}; this.selected = null; this.data = null;
    this.build();
  }
  build() {
    const sc = this.s.scene;
    // ---- hall: concrete floor, back wall with windows, pillars
    const fc = document.createElement('canvas'); fc.width = fc.height = 512; const fg = fc.getContext('2d');
    fg.fillStyle = '#23282e'; fg.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 40; i++) { const r = 40 + Math.random() * 120, x = Math.random() * 512, y = Math.random() * 512, gr = fg.createRadialGradient(x, y, 0, x, y, r); const v = 30 + Math.random() * 14;
      gr.addColorStop(0, `rgba(${v},${v + 2},${v + 5},0.12)`); gr.addColorStop(1, 'rgba(0,0,0,0)'); fg.fillStyle = gr; fg.fillRect(0, 0, 512, 512); }
    for (let i = 0; i < 9000; i++) { const v = 26 + Math.random() * 18; fg.fillStyle = `rgba(${v},${v + 3},${v + 7},0.45)`; fg.fillRect(Math.random() * 512, Math.random() * 512, 2, 2); }
    fg.strokeStyle = 'rgba(0,0,0,0.35)'; fg.lineWidth = 2; fg.strokeRect(0, 0, 512, 512);
    const floorTex = new THREE.CanvasTexture(fc); floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping; floorTex.repeat.set(24, 18); floorTex.colorSpace = THREE.SRGBColorSpace;
    // roughness varies (worn vs. polished patches) so the HDRI gives soft, uneven reflections like sealed concrete
    const rc = document.createElement('canvas'); rc.width = rc.height = 256; const rg = rc.getContext('2d'); rg.fillStyle = '#d2d2d2'; rg.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 30; i++) { const x = Math.random() * 256, y = Math.random() * 256, r = 20 + Math.random() * 70, gr = rg.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, 'rgba(165,165,165,0.5)'); gr.addColorStop(1, 'rgba(165,165,165,0)'); rg.fillStyle = gr; rg.fillRect(0, 0, 256, 256); }
    const roughTex = new THREE.CanvasTexture(rc); roughTex.wrapS = roughTex.wrapT = THREE.RepeatWrapping; roughTex.repeat.set(12, 9);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(120, 90), new THREE.MeshStandardMaterial({ map: floorTex, roughness: 1, roughnessMap: roughTex, metalness: 0.0, envMapIntensity: 0.45 }));
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
      const wipMesh = new THREE.Mesh(this.partGeo[kind], plaMat(kind === 'slot' ? C.slot : C.tab, { transparent: true, opacity: 0.9 }));
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
    // bin places are given in order of arrival, so piles fill bottom-up (a pair = one place)
    const arrival = new Map();
    for (const p of data.parts) if (p.fate === 'shipped' || p.fate === 'scrap') {
      const key = p.fate === 'shipped' ? `s:${p.pair || p.id}` : `x:${p.id}`, tEnd = pathFor(p, 0).at(-1)[0];
      arrival.set(key, Math.min(arrival.get(key) ?? Infinity, tEnd));
    }
    const rank = (prefix) => new Map([...arrival].filter(([k]) => k.startsWith(prefix)).sort((a, b) => a[1] - b[1]).map(([k], i) => [k, i]));
    const shipRank = rank('s:'), scrapRank = rank('x:');
    for (const st of Object.values(this.stations)) st.intervals = [];
    for (const p of data.parts) {
      const bi = p.fate === 'shipped' ? shipRank.get(`s:${p.pair || p.id}`) : p.fate === 'scrap' ? scrapRank.get(`x:${p.id}`) : 0;
      const kf = pathFor(p, bi);
      const mat = plaMat(p.kind === 'slot' ? C.slot : C.tab);
      const m = new THREE.Mesh(this.partGeo[p.kind], mat); m.castShadow = true; m.visible = false; m.userData = { part: p.id }; sc.add(m);
      const review = p.events.filter((e) => e[0] === 'review').map((e) => [e[1], e[2]]);
      for (const [stn, a, b] of p.events) this.stations[laneKey(stn, p.line)]?.intervals.push([a, b, p]);
      const endT = kf[kf.length - 1][0];
      this.parts.push({ p, kf, m, review, endT, shipT: p.fate === 'shipped' ? endT : null, scrapT: p.fate === 'scrap' ? endT : null,
        caught: caughtIds.has(p.id), yaw: (hash(p.id) - 0.5) * 0.12, bin: bi,
        asmT: p.events.find((e) => e[0] === 'assembly')?.[1] ?? null });
    }
    this.slotByPair = new Map(this.parts.filter((x) => x.p.kind === 'slot' && x.p.pair).map((x) => [x.p.pair, x]));  // p.pair is the pair id
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
    // pass 1: where the event log puts each part
    let live = [];
    for (const x of this.parts) {
      x.xy = at(x.kf, t); x.m.visible = !!x.xy; if (!x.xy) continue;
      x.inBin = (x.shipT && t >= x.shipT) || (x.scrapT && t >= x.scrapT); x.stack = 0;
    }
    for (const x of this.parts) {  // after every part has its xy for this frame
      if (!x.xy) continue;
      x.riding = x.p.kind === 'tab' && x.asmT !== null && t >= x.asmT && !x.inBin && !!this.slotByPair.get(x.p.pair)?.xy;  // assembled: tab sits in its slot
      if (!x.inBin && !x.riding) live.push(x);
    }
    // pass 2: parts are solid. Anything that would overlap a part ahead of it on the line waits behind it
    // (queue), ordered by position along the flow (+x). Display only: event times are untouched.
    const placed = [], bx = P.buffer[0];
    const resting = live.filter((x) => Math.abs(x.xy[0] - bx) < 0.85 && Math.abs(x.xy[1]) < 1.75 && !x.xy[2]).sort((a, b) => a.kf[0][0] - b.kf[0][0]);
    let rackN = 0;
    // rack sits on the upstream half of the buffer table so the assembly belt (from x = 1.3) stays clear
    const rack = (x) => { const i = rackN++; x.xy = [bx - 0.3, -1.5 + (i % 6) * 0.6, 0]; x.stack = Math.floor(i / 6); x.w = x.p.kind === 'slot' ? 0.6 : 0.4; placed.push(x); };
    resting.forEach(rack);
    live = live.filter((x) => !resting.includes(x));
    live.sort((a, b) => b.xy[0] - a.xy[0] || a.p.print_t - b.p.print_t);
    for (const x of live) {
      const w = x.p.kind === 'slot' ? 0.6 : 0.4;  // footprint width + margin for the small yaw
      // queue up to 3 places back; a longer queue (e.g. a full buffer) is piled up in place instead,
      // so parts never get pushed through printers or walls
      x.stack = 0; let pushes = 0, racked = false;
      for (let k = 0; k < 40; k++) {
        // 1e-6 slack: a part just pushed to exactly GAP behind another must not count as touching it again
        const hit = placed.find((o) => o.stack === x.stack && Math.abs(o.xy[0] - x.xy[0]) < QUEUE_GAP - 1e-6 && Math.abs(o.xy[1] - x.xy[1]) < (w + o.w) / 2);
        if (!hit) break;
        const back = hit.xy[0] - QUEUE_GAP;
        // only queue backwards while staying on the same surface (belt / table); never drop a part onto the floor
        if (x.stack === 0 && pushes < 3 && Math.abs(heightAt(back, x.xy[1]) - heightAt(x.xy[0], x.xy[1])) < 0.01) { x.xy = [back, x.xy[1], 0, x.xy[3]]; pushes++; }  // keeps its carried height
        else if (x.xy[0] > bx && x.xy[0] < P.assembly[0] && Math.abs(x.xy[1]) < 0.7) { rack(x); racked = true; break; }  // the assembly queue backs up into the buffer rack
        else { x.xy = [hit.xy[0], hit.xy[1], hit.xy[2], hit.xy[3]]; x.stack = hit.stack + 1; }  // ride on top, including the part's hop
      }
      if (!racked) { x.w = w; placed.push(x); }
    }
    // all slots first, so an assembled tab always follows its slot's position from this frame
    for (const x of [...this.parts.filter((q) => q.p.kind !== 'tab'), ...this.parts.filter((q) => q.p.kind === 'tab')]) {
      if (!x.xy) continue;
      const xy = x.xy;
      const inReview = x.review.some(([a, b]) => t >= a && t <= b);
      const toBin = (x.shipT || x.scrapT) && t >= x.kf[x.kf.length - 2][0];  // final move into the bin: aim at its layer
      const layer = toBin ? Math.floor(x.bin / 8) * 0.1 : 0;
      const slotOf = x.p.kind === 'tab' && x.p.pair && (x.riding || (x.shipT && t >= x.shipT)) ? this.slotByPair.get(x.p.pair) : null;
      if (slotOf && slotOf.m.visible) {
        // assembled: the tab sits in the slot channel, pushed to the closed base (CAD: tab x 12..72 mm in a 0..60 mm slot)
        x.m.rotation.y = slotOf.m.rotation.y;
        x.m.position.copy(ASSEMBLED_TAB_OFFSET).applyAxisAngle(Y_AXIS, slotOf.m.rotation.y).add(slotOf.m.position);
      } else {
        x.m.position.set(xy[0], (xy[3] ?? heightAt(xy[0], xy[1])) + layer + (x.stack || 0) * 0.1 + xy[2], xy[1]); x.m.rotation.y = x.inBin ? 0 : x.yaw;
      }
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
  // waiting spot just before a station, pulled in until it is on the station's own surface (belt / table), never the floor
  const onSurface = (k, dx, dz) => { const [sx, sz] = pos(k), h = heightAt(sx, sz); let f = 1;
    while (f > 0.05 && Math.abs(heightAt(sx + dx * f, sz + dz * f) - h) > 0.01) f *= 0.8;
    return [sx + dx * f, sz + dz * f]; };
  const pr = p.kind === 'slot' ? 'printer_slot' : 'printer_tab';
  const first = p.events.length ? p.events[0][1] : p.print_t + 60;
  const out = Math.max(p.print_t, first - 25);
  // printed part is handed from the printer straight onto the start of its lane belt (never the floor)
  const laneZ = (P[laneKey('phone', p.line)] || P.phone_0)[1], beltStart = [-12.2, laneZ + jz * 0.25];
  kf.push([out, ...beltStart]);
  let prevEnd = out + 2, prevKey = pr;
  kf.push([prevEnd, ...beltStart]);
  for (const [station, start, end] of p.events) {
    const [px, pz] = prevKey === pr ? beltStart : pos(prevKey), [sx, sz] = pos(station);
    const travel = Math.min(Math.max(0.5, start - prevEnd), Math.hypot(sx - px, sz - pz) / BELT_SPEED);
    const arrive = Math.max(prevEnd, Math.min(start, prevEnd + travel));
    kf.push([prevEnd, ...(prevKey === pr ? beltStart : pos(prevKey, 0, jz * 0.25))]);
    if (start - arrive > 1) kf.push([arrive, ...onSurface(station, -1.15, jz)], [start - 0.5, ...onSurface(station, -0.95, jz)]);
    kf.push([start, ...pos(station, 0, jz * 0.25)], [end, ...pos(station, 0, jz * 0.25)]);
    prevEnd = end; prevKey = station;
  }
  const last = kf[kf.length - 1][0];
  // bins hold a 2 x 4 grid per layer; parts are 0.96 x 0.53 (slot) / 0.32 (tab) scene units, so cells never overlap
  const binPos = (k) => { const [x, z] = P[k]; const c = binIndex % 8; return [x - 0.7 + (c % 2) * 1.25, z - 0.9 + Math.floor(c / 2) * 0.6]; };
  const [lx, lz] = pos(prevKey), toBin = (k) => Math.hypot(P[k][0] - lx, P[k][1] - lz) / BELT_SPEED;
  // the 4th value is the arc height of that move: parts are lifted over the pile, never through it
  if (p.fate === 'shipped') kf.push([last + toBin('ship'), ...binPos('ship'), 1.4]);
  else if (p.fate === 'scrap') kf.push([last + toBin('scrap'), ...binPos('scrap'), 1.0]);
  else kf.push([last + 4, ...pos('buffer', (j - 0.5) * 1.2, jz)]);
  return kf;
}
function at(kf, t) {
  if (t < kf[0][0]) return null;
  for (let i = 1; i < kf.length; i++) if (t <= kf[i][0]) {
    const [t0, x0, z0] = kf[i - 1], [t1, x1, z1] = kf[i]; const u = t1 > t0 ? (t - t0) / (t1 - t0) : 1;
    const moving = Math.hypot(x1 - x0, z1 - z0) > 0.5;
    // while moving between two surfaces the part is carried at a height blended between them, so it
    // never dips to the floor over a gap (4th value: surface height)
    const x = x0 + (x1 - x0) * u, z = z0 + (z1 - z0) * u;
    return [x, z, moving ? Math.sin(Math.PI * u) * (kf[i][3] ?? 0.15) : 0, moving ? heightAt(x0, z0) + (heightAt(x1, z1) - heightAt(x0, z0)) * u : heightAt(x, z)];
  }
  const l = kf[kf.length - 1]; return [l[1], l[2], 0, heightAt(l[1], l[2])];
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
  const prep = (g) => { const c = g.clone(); c.rotateX(-Math.PI / 2); c.center(); addLayerUV(c); c.scale(0.016, 0.016, 0.016); return c; };
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
  $('#truth').onchange = () => { renderInspector(); renderAgents(true); };
  $$('.rtabs button').forEach((b) => (b.onclick = () => setRTab(b.dataset.rtab)));
  $('#storyNext').onclick = () => story(lab.story + 1); $('#storyPrev').onclick = () => story(lab.story - 1);
  $('#toggleInspector').onclick = () => $('#studio').classList.toggle('noinsp');
  lab.views.forEach((v, i) => { bindPicking(v, i); viewControls(v); });
  // Compare mode: the other camera follows the one being moved, so the two lines stay comparable
  let leader = 0;
  lab.views.forEach((v, i) => {
    v.s.controls.addEventListener('controlstart', () => (leader = i));
    v.s.controls.addEventListener('update', () => {
      if (lab.mode !== 'compare' || leader !== i) return;
      const o = lab.views[1 - i].s, p = v.s.camera.position, t = v.s.target();
      o.controls.setLookAt(p.x, p.y, p.z, t.x, t.y, t.z, false);
    });
  });
  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'SELECT'].includes(document.activeElement?.tagName) || $('#view-lab').hidden) return;
    if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
    else if (e.key === 'l' || e.key === 'L') { $('#labels').checked = !$('#labels').checked; $('#labels').onchange(); }
    else if (e.key === 't' || e.key === 'T') { $('#truth').checked = !$('#truth').checked; renderInspector(); }
    else if (e.key === 'i' || e.key === 'I') $('#studio').classList.toggle('noinsp');
    else if ('wasdWASD'.includes(e.key) && e.key.length === 1) {  // WASD: move over the floor
      const k = { w: [0, 1], s: [0, -1], a: [-1, 0], d: [1, 0] }[e.key.toLowerCase()];
      lab.views.forEach((v) => v.s.move(...k));
    }
    else if (e.key === '+' || e.key === '=') lab.views.forEach((v) => v.s.zoomBy(0.7));
    else if (e.key === '-' || e.key === '_') lab.views.forEach((v) => v.s.zoomBy(1.4));
    else if (e.key === '0') lab.views.forEach(resetView);
    else if ((e.key === 'f' || e.key === 'F') && lab.sel) lab.views.forEach((v) => focusOn(v, lab.sel));
    else if (e.key === 'ArrowRight') story(lab.story + 1);
    else if (e.key === 'ArrowLeft') story(lab.story - 1);
  });
  let last = performance.now();
  const loop = (now) => {
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    if (!$('#view-lab').hidden) {
      if (lab.runs.length) {
        if (lab.views[0]?.s.tracer && lab.playing) { lab.playing = false; $('#playBtn').textContent = '▶'; }  // Photo mode freezes the line
        if (lab.playing) { lab.t += dt * lab.speed; if (lab.t > lab.T) lab.t = lab.t0; $('#timeline').value = Math.round(1000 * (lab.t - lab.t0) / Math.max(1, lab.T - lab.t0)); }
        $('#clock').textContent = mmss(lab.t);
        const truth = $('#truth').checked;
        lab.runs.forEach((r, i) => {
          const c = lab.views[i].update(lab.t, dt, lab.playing, truth);
          $(i ? '#countB' : '#countA').innerHTML = `<span><i>good</i><b>${c.ship}</b></span><span><i>held</i><b>${c.hold}</b></span><span><i>scrap</i><b>${c.scrap}</b></span><span><i>escaped</i><b style="color:var(--escape)">${truth ? c.esc : '—'}</b></span>`;
        });
      }
      lab.views.forEach((v, i) => { if (i === 0 || lab.mode === 'compare') v.s.render(); });
      renderAgents(false);
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
  if (q.get('debug') === '1') window.__qrLab = lab;  // test hook (overlap check)
  if (q.get('photo') === '1') setTimeout(() => $('#photoBtn')?.click(), 3200);  // URL preset: open in Photo mode
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
    feed.insertAdjacentHTML('afterbegin', `<div><b>UNVERIFIED</b><span>${esc(e.station_id)} · ${esc(e.lane)} · ${esc(e.specimen_id)} · ${esc(e.value ?? '')} · declared ${esc(e.source_tier)}</span></div>`);
    while (feed.children.length > 12) feed.lastChild.remove();
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
  el.addEventListener('dblclick', (e) => {  // double-click: fly to the part/station; on empty floor: back to the overview
    const hit = v.pick(e);
    if (hit) { select({ ...hit, side }); focusOn(v, hit); } else resetView(v);
  });
}
function objPoint(v, sel) {
  if (sel?.type === 'part') { const x = v.parts.find((q) => q.p.id === sel.id); return x?.m.visible ? x.m.position.clone() : null; }
  if (sel?.type === 'station') { const st = v.stations[sel.id]; return st ? st.mesh.getWorldPosition(new THREE.Vector3()) : null; }
  return null;
}
function focusOn(v, sel) { const pt = objPoint(v, sel); if (pt) v.s.focus(pt, sel.type === 'part' ? 2.6 : 5); }
function resetView(v) { v.s.flyTo(fitCam(v, STORY[0][2], STORY[0][3]), STORY[0][3], 0.9); }
function viewControls(v) {
  const box = document.createElement('div'); box.className = 'viewctl';
  box.innerHTML = `<button data-a="in" title="Zoom in (+)">+</button><button data-a="out" title="Zoom out (−)">−</button>
    <button data-a="focus" title="Fly to the selected part or station (F)">◎</button><button data-a="reset" title="Whole line (0 or double-click empty floor)">⤢</button>`;
  box.onclick = (e) => { const a = e.target.dataset.a; if (!a) return;
    if (a === 'in') v.s.zoomBy(0.7); else if (a === 'out') v.s.zoomBy(1.4); else if (a === 'reset') resetView(v);
    else if (a === 'focus' && lab.sel) focusOn(v, lab.sel); };
  const hint = document.createElement('div'); hint.className = 'viewhint';
  hint.innerHTML = 'drag: turn · right-drag: move<br>scroll / pinch: zoom to cursor<br>WASD: move · double-click: fly to';
  v.s.el.append(box, hint);
  setTimeout(() => hint.classList.add('gone'), 9000);  // shown once at start, then out of the way
  box.onmouseenter = () => hint.classList.remove('gone'); box.onmouseleave = () => hint.classList.add('gone');
}

// Narrow viewports (compare mode) need the camera further back to show the whole line.
function fitCam(v, cam, tgt) {
  const a = v.s.el.clientWidth / Math.max(1, v.s.el.clientHeight), f = Math.min(1.45, Math.max(1, 1.3 / a));
  return cam.map((c, i) => tgt[i] + (c - tgt[i]) * f);
}
function select(sel) { lab.sel = sel; lab.views.forEach((v) => v.select(sel)); renderInspector(); if (sel) setRTab('insp'); }
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
  if (lab.views[0]?.s.tracer) await exitPhoto();
  const btn = $('#runBtn'); btn.disabled = true; $('#runStatus').textContent = 'Running the discrete-event engine…';
  const base = { scenario: $('#scenario').value || 'F01', seed: +$('#seed').value, n_pairs: +$('#npairs').value };
  const right = { ...base, policy: $('#policy').value, pairing: $('#pairing').value };
  const cfgs = lab.mode === 'compare' ? [{ ...base, policy: 'rules', pairing: 'fifo' }, right] : [right];
  try {
    const t0 = performance.now();
    lab.runs = await Promise.all(cfgs.map((c) => api('/sim/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(c) })));
    lab.caught = new Set(); agState.side = null; setTimeout(() => renderAgents(true), 0);
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
    ctx.sim = `${r.scenario} · ${r.title} · seed ${r.seed} · ${r.n_pairs} pairs${lab.mode === 'compare' ? ' · compare' : ` · ${r.policy}+${r.pairing}`}`; setContext('sim');
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
      <label>Specimen ID<input id="camSpec" type="text" list="specIds" placeholder="e.g. S-GOOD-01" maxlength="40" style="display:block;width:100%;margin-top:4px;background:var(--panel2);color:var(--text);border:1px solid var(--border2);border-radius:6px;padding:6px 8px"></label></div>
    <datalist id="specIds">${['S-GOOD', 'S-NOM', 'S-RISK', 'S-DEF', 'T-GOOD', 'T-NOM', 'T-RISK', 'T-DEF'].map((x) => `<option value="${x}-01">`).join('')}</datalist>
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
  return `${location.origin}/?${q}#sim`;
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
    <li><span>keys</span><span class="faint"><kbd>space</kbd> play · <kbd>L</kbd> labels · <kbd>T</kbd> truth · <kbd>←</kbd><kbd>→</kbd> tour · <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> move · <kbd>+</kbd><kbd>−</kbd> zoom · <kbd>F</kbd> fly to selection · <kbd>0</kbd> whole line</span><span></span></li></ul></section>
    <section><h4>Provenance</h4><p class="faint small">SIMULATED. Toy part generator, illustrative station timings, held-out calibration ${r.model.calibration_id}. Not a factory measurement.
      This 3D Lab runs two lanes with one iPhone camera each (cameras: ${(r.cameras || []).join(', ')}) and reprints confirmed defects. The pre-registered results in the Results tab used phone + Pi cameras without reprint.</p></section>`;
  return html;
}
function renderInspector() {
  const truth = $('#truth').checked, sel = lab.sel; let html;
  if (sel?.type === 'part') {
    const side = Math.min(sel.side ?? 0, lab.runs.length - 1);
    const p = findPart(sel.id, side); html = p ? partCard(p, side, truth) + agentConversation(lab.runs[side], p) : summaryCard(); $('#inspHint').textContent = '· part';
  } else if (sel?.type === 'station') { html = stationCard(sel.id, Math.min(sel.side ?? 0, lab.runs.length - 1)); $('#inspHint').textContent = '· station'; }
  else { html = summaryCard(); $('#inspHint').textContent = ''; }
  stopCamera(); lab.camView = null;
  $('#inspBody').innerHTML = html;
  if (sel?.type === 'station' && sel.id.startsWith('phone_')) bindCameraPanel(sel.id, Math.min(sel.side ?? 0, lab.runs.length - 1));
  $$('#inspBody [data-part]').forEach((el) => (el.onclick = () => select({ type: 'part', id: el.dataset.part, side: el.dataset.side !== undefined ? +el.dataset.side : 0 })));
}

// ---------------------------------------------------------------- agents: live analytics (right dock)
// Every number here is computed from the agents' own messages up to the playback time.
// Ground truth (escapes) is shown only with the "Ground truth" layer on. SIMULATED.
const AG_NODES = { vision: [56, 24], governance: [170, 24], cost: [284, 24], assembly: [170, 95], metrology: [56, 166], process: [170, 166], learning: [284, 166] };
const AG_NAME = { vision: 'Vision', metrology: 'Metrology', assembly: 'Assembly', process: 'Process', cost: 'Cost', learning: 'Learning', governance: 'Safety' };
const AG_COL = { pass: '#76b900', released: '#199e70', rework: '#9085e9', scrap: '#6b727c', pending: '#e0b000', hold: '#e0b000' };
const REASON = {
  DIMENSIONAL_RISK: 'Clearance risk', SURFACE_RISK_SLOT: 'Slot surface', SURFACE_RISK_TAB: 'Tab surface', SURFACE_RISK: 'Surface (camera)',
  STALE_OR_MISSING_EVIDENCE: 'Missing / late evidence', UNVERIFIED_EVIDENCE: 'Evidence failed VERIFY', RULE_CLEARANCE: 'Rule: clearance < 0.5', RULE_ANY_FLAG_OR_MISSING: 'Rule: camera flag',
  HOLD_ALL_POLICY: 'Hold-all policy', RULE_CLEARANCE_AFTER_REVIEW: 'Rule after review',
};
const agState = { last: 0, side: null, tab: 'agents' };
const agRun = () => { const i = agState.side ?? lab.runs.length - 1; return lab.runs[i]; };
const shortId = (id) => String(id).replace(/^P-/, '').replace(/([ST])-\d+-0*(\d+)/g, '$1$2');
const lastIdx = (msgs, t) => { let lo = 0, hi = msgs.length; while (lo < hi) { const m = (lo + hi) >> 1; if (msgs[m][0] <= t) lo = m + 1; else hi = m; } return lo; };

function setRTab(tab) {
  agState.tab = tab;
  $$('.rtabs button').forEach((b) => b.classList.toggle('on', b.dataset.rtab === tab));
  $('#agentsBody').hidden = tab !== 'agents'; $('#inspBody').hidden = tab !== 'insp';
  if (tab === 'agents') renderAgents(true);
}

function agentsAt(run, t) {
  const A = run.agents, msgs = A.messages, n = lastIdx(msgs, t);
  const edges = {}, sent = {}, reasons = {}, pairDec = {}, pairOut = {}, partOut = {};
  let partHolds = 0, bytes = 0, alarms = [], proposals = 0;
  const proto = { requests: 0, responses: 0, proposals: 0, out: {}, ver: {} };
  for (let i = 0; i < n; i++) {
    const [mt, kind, from, to, cas, body, b] = msgs[i];
    bytes += b; sent[from] = (sent[from] || 0) + 1;
    if (from !== to) { const k = `${from}>${to}`; edges[k] = (edges[k] || 0) + 1; }
    if (kind === 'DECISION') {
      if (body.stage === 'pair') pairDec[cas] = body;
      if (body.decision === 'HOLD') { const r = A.decisions[cas]?.reason || body.reason; reasons[r] = (reasons[r] || 0) + 1; if (body.stage === 'part') partHolds++; }
    } else if (kind === 'REVIEW_OUTCOME' && to === 'learning') {
      if (String(cas).startsWith('P-')) pairOut[cas] = body.outcome; else partOut[cas] = body.outcome;
    } else if (kind === 'EVIDENCE_RESPONSE' && body.protocol === 'PeerBus') {
      proto.responses++; proto.out[body.outcome] = (proto.out[body.outcome] || 0) + 1;
      for (const x of body.summaries || []) proto.ver[x.verification_status] = (proto.ver[x.verification_status] || 0) + 1;
    } else if (kind === 'REQUEST_EVIDENCE' && body.protocol === 'PeerBus') proto.requests++;
    else if (kind === 'DECISION_PROPOSAL') proto.proposals++;
    else if (kind === 'ALARM') alarms.push([mt, body]);
    else if (kind === 'PROPOSE_RECALIBRATION') proposals++;
  }
  const decided = Object.keys(pairDec), pass = decided.filter((k) => pairDec[k].decision === 'PASS').length;
  const mix = { pass, released: 0, rework: 0, scrap: 0, pending: 0 };
  for (const k of decided) if (pairDec[k].decision === 'HOLD') {
    const o = pairOut[k]; if (o === 'released') mix.released++; else if (o === 'rework') mix.rework++; else if (o === 'split_scrap') mix.scrap++; else mix.pending++;
  }
  const truthEsc = run.pairs.filter((p) => p.escaped && p.shipped_s !== null && p.shipped_s !== undefined && p.shipped_s <= t).length;
  // Learning: share of surface holds the expert confirmed vs the share the Vision agent predicted
  let flagged = 0, confirmed = 0, predicted = 0;
  for (const [pid, o] of Object.entries(partOut)) { flagged++; if (o === 'scrapped') confirmed++; predicted += A.decisions[pid]?.p || 0; }
  return { proto, n, edges, sent, reasons, decided: decided.length, mix, partHolds, bytes, alarms, proposals, truthEsc, flagged, confirmed,
    predicted: flagged ? predicted / flagged : null, recent: msgs.slice(Math.max(0, n - 60), n) };
}

function agNet(run, s, t) {
  const maxE = Math.max(1, ...Object.values(s.edges)), win = Math.max(2, lab.speed * 0.8);
  const recentAlarm = s.alarms.length && t - s.alarms[s.alarms.length - 1][0] < 120;
  let svg = '';
  for (const [k, c] of Object.entries(s.edges)) {
    const [a, b] = k.split('>'); if (!AG_NODES[a] || !AG_NODES[b]) continue;
    const [x1, y1] = AG_NODES[a], [x2, y2] = AG_NODES[b];
    svg += `<line class="edge" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke-width="${(1 + 4 * Math.sqrt(c / maxE)).toFixed(2)}"><title>${AG_NAME[a]} → ${AG_NAME[b]}: ${c} messages</title></line>`;
  }
  let pulses = 0;
  for (let i = s.recent.length - 1; i >= 0 && pulses < 28; i--) {
    const [mt, kind, a, b] = s.recent[i]; if (a === b || t - mt > win || !AG_NODES[a] || !AG_NODES[b]) continue;
    const u = Math.min(1, (t - mt) / win), [x1, y1] = AG_NODES[a], [x2, y2] = AG_NODES[b];
    const col = kind === 'ALARM' ? 'var(--escape)' : kind === 'DECISION' ? 'var(--review)' : '#e8eaed';
    svg += `<circle class="pulse" cx="${(x1 + (x2 - x1) * u).toFixed(1)}" cy="${(y1 + (y2 - y1) * u).toFixed(1)}" r="3.2" fill="${col}" opacity="${(1 - u * 0.6).toFixed(2)}"/>`;
    pulses++;
  }
  for (const [id, [x, y]] of Object.entries(AG_NODES)) {
    const cls = ['node', s.sent[id] ? 'active' : '', id === 'process' && recentAlarm ? 'alarm' : '', id === 'learning' && s.proposals ? 'prop' : ''].join(' ');
    const r = run.agents.roster[id]; if (!r) continue;
    svg += `<g class="${cls}" transform="translate(${x - 50},${y - 18})"><title>${r.name}${r.role ? ` = adilnurgg role ${r.role}` : ''}: ${r.what} (${r.inside}, no LLM)</title>
      <rect width="100" height="36" rx="8"/><text x="10" y="15">${AG_NAME[id]}</text><text class="sub" x="10" y="28">${s.sent[id] || 0} sent</text>
      <text class="sub" x="92" y="15" text-anchor="end">${r.inside === 'statistic' ? 'stat' : 'rule'}</text></g>`;
  }
  return `<svg class="ag-net" viewBox="0 0 340 190" role="img" aria-label="Messages between the six agents">${svg}</svg>`;
}

function agSpc(run, t) {
  const A = run.agents, cfg = A.spc, msgs = A.messages, n = lastIdx(msgs, t);
  const t0 = lab.t0, T = Math.max(lab.T, t0 + 1), W = 340, H = 64, pad = 22;
  const out = [];
  for (const kind of ['slot', 'tab']) {
    const pts = [], al = [];
    for (let i = 0; i < n; i++) {
      const m = msgs[i];
      if (m[1] === 'MEASUREMENT' && m[5].kind === kind) { const d = m[5].reading_mm - cfg.nominal_mm[kind] - m[5].offset_mm; pts.push([m[0], d, cfg.sigma_mm[m[5].site] || 0.06]); }
      else if (m[1] === 'ALARM' && m[5].kind === kind) al.push(m[0]);
    }
    const sig = pts.length ? pts.reduce((a, p) => a + p[2], 0) / pts.length : 0.06, lim = 3 * sig, Y = Math.max(0.3, lim * 1.35);
    const x = (tt) => pad + (W - pad - 4) * (tt - t0) / (T - t0), y = (d) => H / 2 - (H / 2 - 6) * Math.max(-1, Math.min(1, d / Y));
    let g = `<rect class="band" x="${pad}" y="${y(lim)}" width="${W - pad - 4}" height="${y(-lim) - y(lim)}"/>
      <line class="lim" x1="${pad}" x2="${W - 4}" y1="${y(lim)}" y2="${y(lim)}"/><line class="lim" x1="${pad}" x2="${W - 4}" y1="${y(-lim)}" y2="${y(-lim)}"/>
      <line class="ctr" x1="${pad}" x2="${W - 4}" y1="${y(0)}" y2="${y(0)}"/>
      <text x="2" y="${y(lim) + 3}">+3σ</text><text x="2" y="${y(-lim) + 3}">−3σ</text><text x="${W - 4}" y="10" text-anchor="end">${kind} width − nominal (mm)</text>`;
    const col = kind === 'slot' ? 'var(--slot)' : 'var(--tab)';
    for (const [tt, d] of pts) g += `<circle cx="${x(tt).toFixed(1)}" cy="${y(d).toFixed(1)}" r="1.9" fill="${Math.abs(d) > lim ? 'var(--escape)' : col}" opacity=".9"/>`;
    for (const tt of al) g += `<line x1="${x(tt)}" x2="${x(tt)}" y1="4" y2="${H - 4}" stroke="var(--escape)" stroke-width="1.5"><title>CUSUM alarm</title></line>`;
    out.push(`<svg class="ag-spc" viewBox="0 0 ${W} ${H}" role="img" aria-label="${kind} control chart">${g}</svg>`);
  }
  return out.join('');
}

const fmtT = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
function agLine(m) {
  const [mt, kind, from, to, cas, b] = m, id = shortId(cas);
  let k = kind.replace('_', ' ').toLowerCase(), cls = '', txt;
  if (kind === 'DECISION') { cls = b.decision === 'HOLD' ? 'hold' : 'pass'; k = b.decision; txt = `<b>${AG_NAME[from]}</b> → ${AG_NAME[to]}: ${id} ${b.decision === 'HOLD' ? `held (${REASON[b.reason] || b.reason})` : 'released'}`; }
  else if (kind === 'REQUEST_EVIDENCE') txt = `<b>${AG_NAME[from]}</b> asks ${AG_NAME[to]} for ${(b.requested_kind || '').replace('_', ' ').toLowerCase()} of ${id} <span class="faint">· signed</span>`;
  else if (kind === 'EVIDENCE_RESPONSE') {
    const x = (b.summaries || [])[0] || {}, ok = b.outcome === 'GRANTED';
    cls = ok ? '' : 'alarm'; k = ok ? 'verified' : b.outcome;
    txt = `<b>${AG_NAME[from]}</b> → ${AG_NAME[to]}: ${id} ${x.kind === 'CALIPER' ? `${(x.payload?.measurement_mm ?? 0).toFixed(3)} mm` : x.verdict || ''} <span class="faint">· ${b.outcome}${x.verification_status ? ' / ' + x.verification_status : ''}</span>`;
  }
  else if (kind === 'HYPOTHESIS_UPDATE') txt = `<b>Assembly</b> belief for ${shortId(b.part)}: P(surface) ${(100 * b.p_surface).toFixed(2)}%, width ${b.mean_mm.toFixed(3)} ± ${b.sd_mm.toFixed(3)} mm`;
  else if (kind === 'DECISION_PROPOSAL') { cls = b.state === 'HOLD' ? 'hold' : 'pass'; k = 'proposal'; txt = `<b>Assembly</b> → Safety: ${id} ${b.state} <span class="faint">· signed</span>`; }
  else if (kind === 'DECISION_REQUEST') txt = `<b>${AG_NAME[from]}</b> → Cost: ${id} ${b.p_unsafe !== undefined ? `P(unsafe) ${(100 * b.p_unsafe).toFixed(2)}%` : b.p_surface !== null && b.p_surface !== undefined ? `P(surface) ${(100 * b.p_surface).toFixed(2)}%` : 'rule check'}`;
  else if (kind === 'MEASUREMENT') txt = `<b>Metrology</b> → Process: ${id} ${b.reading_mm.toFixed(3)} mm`;
  else if (kind === 'ALARM') { cls = 'alarm'; txt = `<b>Process</b>: CUSUM alarm, ${b.kind} printer ${b.direction} (${b.site})`; }
  else if (kind === 'PROPOSE_SETPOINT') txt = `<b>Process</b> proposes ${b.kind} offset ${b.offset_mm > 0 ? '+' : ''}${b.offset_mm.toFixed(3)} mm`;
  else if (kind === 'REVIEW_OUTCOME') txt = `<b>${AG_NAME[from]}</b> → ${AG_NAME[to]}: expert ${String(b.outcome || 'cleared').replace('_', ' ')} ${id}`;
  else if (kind === 'PROPOSE_RECALIBRATION') { cls = 'alarm'; txt = `<b>Learning</b> proposes camera recalibration`; }
  else if (kind === 'SHIPPED') txt = `<b>Assembly</b> → Learning: ${id} shipped`;
  else txt = `<b>${AG_NAME[from] || from}</b>: ${kind.toLowerCase()} ${id}`;
  return `<li><span class="t">${fmtT(mt)}</span><span><span class="k ${cls}">${k}</span>${txt}</span></li>`;
}

function renderAgents(force) {
  const el = $('#agentsBody'); if (!el || el.hidden) return;
  const now = performance.now(); if (!force && now - agState.last < 220) return; agState.last = now;
  const run = agRun();
  if (!run) { el.innerHTML = '<p class="faint">Run a simulation.</p>'; return; }
  if (!run.agents) { el.innerHTML = '<p class="faint">This run was made without agents.</p>'; return; }
  const s = agentsAt(run, lab.t), A = run.agents, truth = $('#truth').checked, ck = A.check;
  const tot = Math.max(1, s.decided), mixKeys = ['pass', 'released', 'rework', 'scrap', 'pending'];
  const mixLbl = { pass: 'released first pass', released: 'held → released', rework: 'held → reworked', scrap: 'held → scrapped / split', pending: 'held, in review' };
  const rs = Object.entries(s.reasons).sort((a, b) => b[1] - a[1]), rmax = Math.max(1, ...rs.map((r) => r[1])), rsum = rs.reduce((a, r) => a + r[1], 0);
  let cum = 0;
  const side = lab.runs.length === 2 ? `<div class="seg mini" style="margin-bottom:8px">${lab.runs.map((r, i) => `<button class="${(agState.side ?? lab.runs.length - 1) === i ? 'on' : ''}" data-agside="${i}">${i === 0 ? 'Today · rule' : 'QualityRelay'}</button>`).join('')}</div>` : '';
  let calib = '<span class="faint">Waits for at least 5 expert-reviewed surface holds.</span>';
  if (s.flagged >= 5) {
    const k = s.confirmed, n = s.flagged, z = 1.96, p = k / n, d = 1 + z * z / n, c = (p + z * z / (2 * n)) / d, h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d;
    const lo = Math.max(0, c - h), hi = Math.min(1, c + h), ok = s.predicted >= lo && s.predicted <= hi, X = (v) => 8 + 324 * v;
    calib = `<svg class="ag-spc" viewBox="0 0 340 34" role="img" aria-label="calibration check"><line class="ctr" x1="8" x2="332" y1="17" y2="17"/>
      <line x1="${X(lo)}" x2="${X(hi)}" y1="17" y2="17" stroke="var(--muted)" stroke-width="4" stroke-linecap="round"/>
      <circle cx="${X(p)}" cy="17" r="4" fill="var(--text)"/><path d="M${X(s.predicted)} 8 l5 9 -5 9 -5 -9z" fill="var(--review)"/>
      <text x="8" y="32">0%</text><text x="332" y="32" text-anchor="end">100%</text></svg>
      <div>Expert confirmed <b>${k}/${n}</b> surface holds (${(100 * p).toFixed(0)}%, 95% CI ${(100 * lo).toFixed(0)}–${(100 * hi).toFixed(0)}%); Vision predicted <b>${(100 * s.predicted).toFixed(0)}%</b> ◆.
      ${ok ? 'Consistent with the camera calibration.' : '<b style="color:#f0c64a">Outside the interval: Learning proposes recalibration (proposal only).</b>'}</div>`;
  }
  el.innerHTML = `${side}
    <div class="ag-head"><h2>Agents deciding this run</h2><span class="chk ${ck.identical ? 'ok' : 'bad'}" title="${ck.note}">${ck.identical ? '✓' : '✗'} ${ck.equal}/${ck.pairs} decisions = reference</span></div>
    <div class="faint small" style="margin:-4px 0 10px">Cost agent: ${A.policy_inside}. Code, not LLMs. SIMULATED.</div>
    <div class="ag-kpis">
      <div class="ag-kpi"><b>${s.decided}</b><span>pairs decided</span></div>
      <div class="ag-kpi"><b>${s.decided ? Math.round(100 * s.mix.pass / tot) : 0}%</b><span>first-pass release</span></div>
      <div class="ag-kpi"><b>${s.decided - s.mix.pass + s.partHolds}</b><span>holds</span></div>
      <div class="ag-kpi"><b style="color:${truth && s.truthEsc ? 'var(--escape)' : ''}">${truth ? s.truthEsc : '—'}</b><span>escaped ${truth ? '(truth)' : '(turn on T)'}</span></div>
      <div class="ag-kpi"><b>${s.decided ? (s.n / s.decided).toFixed(1) : '0'}</b><span>messages / pair</span></div>
      <div class="ag-kpi"><b>${s.decided ? (s.bytes / s.decided / 1024).toFixed(2) : '0'}<small style="font-size:11px"> KB</small></b><span>data / pair</span></div>
    </div>
    <div class="ag-sec"><h4>Who talks to whom <em>${s.n} messages</em></h4>${agNet(run, s, lab.t)}</div>
    <div class="ag-sec"><h4>Protocol · adilnurgg's PeerBus <em>role-signed</em></h4>
      <div class="ag-roster">
        <span>evidence requests (ACL checked)</span><span>${s.proto.requests}</span>
        <span>granted / refused</span><span>${s.proto.out.GRANTED || 0} / ${s.proto.responses - (s.proto.out.GRANTED || 0)}</span>
        <span>VERIFY ok · forged · stale · dup</span><span>${s.proto.ver.VERIFIED || 0} · ${s.proto.ver.BAD_SIGNATURE || 0} · ${s.proto.ver.STALE_EVIDENCE || 0} · ${s.proto.ver.DUPLICATE_SOURCE || 0}</span>
        <span>decision proposals → safety_governance</span><span>${s.proto.proposals}</span>
      </div>
      <div class="faint small" style="margin-top:6px">Roles: ${Object.entries(A.roster).filter(([, r]) => r.role).map(([k, r]) => `${AG_NAME[k]} = <code>${r.role}</code>`).join(', ')}.</div></div>
    <div class="ag-sec"><h4>Pair decisions <em>${s.decided}</em></h4>
      <div class="ag-bar">${mixKeys.filter((k) => s.mix[k]).map((k) => `<i style="width:${(100 * s.mix[k] / tot).toFixed(2)}%;background:${AG_COL[k]}" title="${mixLbl[k]}: ${s.mix[k]}"></i>`).join('')}</div>
      <div class="ag-leg">${mixKeys.map((k) => `<span><i style="background:${AG_COL[k]}"></i>${mixLbl[k]} <b class="num">${s.mix[k]}</b></span>`).join('')}</div></div>
    <div class="ag-sec"><h4>Why parts are held <em>Pareto</em></h4>
      ${rs.length ? `<div class="ag-pareto">${rs.map(([r, c]) => { cum += c; return `<span class="lbl" title="${r}">${REASON[r] || r}</span><span class="trk"><i style="width:${(100 * c / rmax).toFixed(1)}%"></i></span><span class="v">${c} <span class="faint">${Math.round(100 * cum / rsum)}%</span></span>`; }).join('')}</div>` : '<span class="faint small">No holds yet.</span>'}</div>
    <div class="ag-sec"><h4>Process agent · control charts <em>${s.alarms.length} alarm${s.alarms.length === 1 ? '' : 's'}</em></h4>${agSpc(run, lab.t)}</div>
    <div class="ag-sec"><h4>Learning agent · calibration check</h4><div class="ag-cal">${calib}</div></div>
    <div class="ag-sec"><h4>Live log</h4><ul class="ag-log">${s.recent.filter((m) => m[2] !== m[3] || m[1] === 'PROPOSE_SETPOINT').slice(-9).reverse().map(agLine).join('') || '<li class="faint">Waiting for the first part.</li>'}</ul></div>`;
  $$('[data-agside]', el).forEach((b) => (b.onclick = () => { agState.side = +b.dataset.agside; renderAgents(true); }));
}

function agentConversation(run, p) {
  const A = run?.agents; if (!A) return '';
  const msgs = A.messages.filter((m) => m[4] === p.id || (p.pair && m[4] === p.pair) || m[5]?.part === p.id);
  if (!msgs.length) return '';
  return `<section><h4>Agent conversation · ${msgs.length} messages</h4><ul class="ag-log ag-conv">${msgs.slice(0, 24).map(agLine).join('')}</ul></section>`;
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
  s.autoRotate = true;
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

// ---------------------------------------------------------------- live physical inspection (hardware ledger only)
const ago = (t) => { if (!t) return '—'; const d = Date.now() / 1000 - t; return d < 90 ? `${Math.round(d)} s ago` : d < 5400 ? `${Math.round(d / 60)} min ago` : new Date(t * 1000).toLocaleString(); };
const tierChip = (t) => t === 'VERIFIED_PHYSICAL' ? '<span class="chip ok">VERIFIED_PHYSICAL</span>' : t === 'PHYSICAL_CAPTURE' ? '<span class="chip phys">PHYSICAL_CAPTURE</span>' : `<span class="chip no">${esc(t)}</span>`;
const GT_CLASS = { CONFIRMED: 'ok', DISPUTED: 'no', AWAITING_GROUND_TRUTH: 'hold' };
const gtChip = (s) => `<span class="chip ${GT_CLASS[s] || 'mute'}">${esc(s)}</span>`;
const physValue = (v) => v.measurement_mm !== undefined ? `${fmt(v.measurement_mm, 3)} ± ${fmt(v.uncertainty_mm, 3)} ${esc(v.unit || 'mm')}`
  : v.bin !== undefined ? `bin ${esc(v.bin)}` : v.temperature_c !== undefined ? `${fmt(v.temperature_c, 1)} °C` : '—';
async function refreshPhysical() {
  const [st, ev] = await Promise.all([api('/physical/status'), api('/physical/events?limit=100')]);
  const a = st.actuation, verified = ev.tiers.VERIFIED_PHYSICAL || 0;
  const act = a.estop ? ['warn', 'E-STOP', 'software E-stop latched'] : !a.hardware_enabled ? ['', 'OFF', 'actuator hardware disabled · default HOLD']
    : a.armed ? ['warn', 'ARMED', `armed by ${esc(a.armed_by)} · ${a.in_flight.length} in flight`] : ['', 'DISARMED', 'hardware enabled, not armed · default HOLD'];
  $('#physKpis').innerHTML = [['', `${st.ledger_events}`, `records in the hardware ledger (${st.hardware_ledger})`],
    [verified ? 'good' : '', `${verified}`, `of the ${ev.count} shown are VERIFIED_PHYSICAL (ground truth recorded)`],
    ['', `${st.hardware_stations_provisioned.length}`, `stations provisioned: ${esc(st.hardware_stations_provisioned.join(', ') || 'none')}`],
    [act[0], act[1], `sorter: ${act[2]}`]].map(([c, x, y]) => `<div class="kpi ${c}"><strong>${x}</strong><span>${y}</span></div>`).join('');
  $('#physTable tbody').innerHTML = ev.events.map((e) => `<tr><td class="faint">${ago(e.observed_at)}</td><td class="num">${esc(e.event_id)}</td><td>${esc(e.specimen_id)}</td>
    <td>${esc(e.station_id)}</td><td>${esc(e.kind)}</td><td class="num">${physValue(e.values)}</td><td>${tierChip(e.source_tier)}</td>
    <td>${gtChip(e.verification_status)}</td><td>${e.station_authenticated ? '<span class="chip ok">✔ envelope</span>' : `<span class="chip no" title="${esc(e.candidate_problems.join('; '))}">✖ none</span>`}</td></tr>`).join('');
  $('#physEmpty').hidden = ev.events.length > 0;
  $('#routeTable tbody').innerHTML = ev.routes.map((r) => `<tr><td class="num">${esc(r.action_id)}</td><td>${esc(r.kind)}</td><td>${esc(r.specimen_id ?? '')}</td>
    <td>${esc(r.bin ?? r.actual_bin ?? '')}</td><td class="num">${esc(r.sensor_event_id ?? '')}</td></tr>`).join('');
  $('#routeEmpty').hidden = ev.routes.length > 0;
  $('#physUpdated').textContent = `updated ${new Date().toLocaleTimeString()}`;
  ctx.physical = `hardware ledger · ${st.ledger_events} records · ${verified} verified`; setContext('physical');
}
function initPhysical() {
  const tick = () => { if (!$('#view-physical').hidden) refreshPhysical().catch((e) => ($('#physUpdated').textContent = e.message)); };
  $('#physRefresh').onclick = tick; setInterval(tick, 5000);
  startLive();
}

// ---------------------------------------------------------------- agent collaboration (TEST_FIXTURE trace)
const ROLE = { quality_inspector: 'Quality', metrology_engineer: 'Metrology', additive_manufacturing_expert: 'Pi / AM', design_geometry: 'CAD',
  assembly_engineer: 'Assembly', safety_governance: 'Safety', inspection_planner: 'Planner' };
const role = (r) => ROLE[r] || r || '';
const stateChip = (s) => `<span class="chip ${s === 'PASS_REVIEW' ? 'ok' : s === 'HOLD' ? 'hold' : 'no'}">${esc(s)}</span>`;
function traceRow(e) {
  const b = e.body || {}, who = e.type === 'MESSAGE' ? `${role(e.sender_role)}${e.recipient_role && e.recipient_role !== e.sender_role ? ` → ${role(e.recipient_role)}` : ''}` : e.type;
  let what = '', right = '', bad = false;
  if (e.type === 'MESSAGE') {
    if (!e.signature_valid) { what = `${e.kind} rejected: bad sender signature`; bad = true; }
    else if (e.kind === 'FIND_MISSING_EVIDENCE') what = `missing ${(b.missing || []).join(', ') || 'nothing'}`;
    else if (e.kind === 'REQUEST_EVIDENCE') { what = `REQUEST ${b.requested_kind} · ${b.reason_code}`; right = `max $${b.max_cost}`; }
    else if (e.kind === 'EVIDENCE_RESPONSE') { what = `${b.outcome} ${(b.summaries || []).map((x) => `${x.event_id} (source_root ${x.source_root})`).join(', ') || b.reason || ''}`; right = `$${b.cost_charged}`; bad = b.outcome !== 'GRANTED'; }
    else if (e.kind === 'HYPOTHESIS_UPDATE') { what = `belief ${fmt(b.belief_before, 3)} → ${fmt(b.belief_after, 3)}`; right = String(b.note || '').slice(0, 60); }
    else if (e.kind === 'PROPOSE_INSPECTION') { what = `next: ${b.chosen}`; right = `NetVOI ${sign(b.net_voi, 3)}`; }
    else if (e.kind === 'DECISION_PROPOSAL') { what = `${b.state} ${(b.reasons || []).join(', ')} · without requests: ${b.control_state}`; right = b.decision_changed ? 'changed' : 'unchanged'; }
    else what = e.kind;
  } else if (e.type === 'VERIFY') { what = `${e.event_id}: ${e.outcome}${e.note ? ` (${e.note})` : ''}`; bad = e.outcome !== 'VERIFIED'; }
  else if (e.type === 'LLM_CALL') { what = `${e.provider}:${e.model} round ${e.round}`; right = `${e.prompt_tokens}+${e.completion_tokens} tok · ${e.cost_usd == null ? 'unpriced' : '$' + fmt(e.cost_usd, 5)}`; }
  else { what = e.reason || e.detail || ''; bad = e.type === 'ERROR' || e.type === 'PROPOSAL_REJECTED'; }
  return `<li class="${bad ? 'bad' : ''}"><span>${e.seq}</span><span>${esc(who)}</span><span>${esc(what)}</span><span>${esc(right)}</span></li>`;
}
async function runCollective() {
  const btn = $('#colRun'); btn.disabled = true; $('#colStatus').textContent = 'running…';
  try {
    const r = await api('/research/collective/run', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario: $('#colScenario').value, request_cost: +$('#colCost').value, budget: +$('#colBudget').value, planner: $('#colPlanner').value }) });
    const c = await api(`/research/collective/runs/${encodeURIComponent(r.run_id)}/traces/${encodeURIComponent(r.case_id)}`);
    const reasons = (d) => esc((d.reasons || []).join(', ') || 'no reasons');
    $('#colKpis').innerHTML = [[stateChip(c.decision.state), `with peer requests · ${reasons(c.decision)}`],
      [stateChip(c.control_decision.state), `control, requests disabled · ${reasons(c.control_decision)}`],
      [`${c.independent_sources_before} → ${c.independent_sources_after}`, 'independent source_roots held by the requester'],
      [`$${fmt(c.cost_charged, 2)}`, `charged for ${c.requests} request(s): ${esc(Object.entries(c.request_outcomes).map(([k, v]) => `${k} ${v}`).join(', ') || 'none')}`]]
      .map(([a, b]) => `<div class="kpi"><strong>${a}</strong><span>${b}</span></div>`).join('');
    $('#colBelief').innerHTML = c.belief_path.map((s) => `<li><span>${esc(s.step)}</span><span class="small muted">${esc(s.note || '')}</span><span>${fmt(s.belief, 3)}</span>
      <div class="bar"><i style="width:${Math.min(100, 100 * s.belief)}%"></i></div></li>`).join('');
    $('#colCriteria').innerHTML = Object.entries(c.criteria).map(([k, v]) => chip(v, k.replaceAll('_', ' '), k.replaceAll('_', ' '))).join('');
    const p = c.proposal;
    $('#colProposal').innerHTML = `<p><b>${esc(p.chosen)}</b> · NetVOI ${sign(p.net_voi, 3)} · <span class="faint">${esc(p.likelihood_source)}</span></p>
      <table><thead><tr><th>Candidate</th><th class="num">Exp. loss</th><th class="num">Cost</th><th class="num">NetVOI</th></tr></thead><tbody>${(p.candidates || []).map((x) =>
      `<tr><td>${esc(x.name)}</td><td class="num">${fmt(x.expected_loss, 3)}</td><td class="num">${fmt(x.inspection_cost, 2)}</td><td class="num">${sign(x.net_voi, 3)}</td></tr>`).join('')}</tbody></table>`;
    $('#colTrace').innerHTML = c.trace.entries.map(traceRow).join('');
    const url = `/research/collective/runs/${encodeURIComponent(r.run_id)}/traces/${encodeURIComponent(r.case_id)}`;
    $('#colRunId').innerHTML = `${esc(r.run_id)} · ${esc(c.origin)} · planner ${esc(r.planner?.planner || r.planner?.provider || $('#colPlanner').value)} · <a href="${url}" target="_blank">JSON trace</a>`;
    ctx.agents = `${c.origin} · ${$('#colScenario').value} · ${c.decision.state}`; setContext('agents');
    const stateChanged = c.decision.state !== c.control_decision.state;  // decision_changed also counts a change of reasons alone
    $('#colStatus').textContent = !c.decision_changed ? 'Same decision and reasons as the control run.'
      : stateChanged ? `Peer evidence changed the decision: ${c.control_decision.state} → ${c.decision.state}.` : `Same state (${c.decision.state}) as the control run, but for different reasons.`;
  } catch (e) { $('#colStatus').textContent = e.message; }
  btn.disabled = false;
}
async function initAgents() {
  const [sc, llm] = await Promise.all([api('/research/collective/scenarios'), api('/integrations/llm')]);
  $('#colScenario').innerHTML = Object.keys(sc.scenarios).map((k) => `<option value="${esc(k)}"${k === 'pi_suspect' ? ' selected' : ''}>${esc(k)}</option>`).join('');
  const hint = () => ($('#colScenarioHint').textContent = sc.scenarios[$('#colScenario').value]);
  $('#colScenario').onchange = hint; hint();
  for (const [name, st] of Object.entries(llm.providers))  // unconfigured providers stay visible but unselectable: no fake AI output
    $('#colPlanner').insertAdjacentHTML('beforeend', `<option value="${esc(name)}"${['NOT_CONFIGURED', 'ERROR'].includes(st.state) ? ' disabled' : ''}>LLM: ${esc(name)} (${esc(st.state)})</option>`);
  $('#llmStatus').innerHTML = Object.entries(llm.providers).map(([n, st]) => `<div class="kv"><span>${esc(n)}</span><span>${esc(st.state)}${st.entitlement ? ` · entitlement ${esc(st.entitlement.state)}` : ''}</span></div>`).join('')
    + `<p class="faint small" style="margin:8px 0 0">${esc(llm.decision_authority)}</p>`;
  $('#colRun').onclick = runCollective;
  await runCollective();
}

// ---------------------------------------------------------------- physical bench: manual caliper calibration (HyorinmaruK data)
async function initBench() {
  const d = await api('/sim/physical/summary');
  if (d.status === 'NOT_AVAILABLE') { $('#physCal').innerHTML = `No measurements yet. ${d.hint}.`; return; }
  const c = d.calibration, f = c.fits;
  $('#physCal').innerHTML = `<div class="kv"><span>files</span><span>${d.files.join(', ')}</span><span>status</span><span>${c.status}</span>
    <span>caliper repeatability σ</span><span>${c.caliper_repeatability_sd_mm ?? '—'} mm</span>
    ${Object.entries(f).map(([k, v]) => `<span>${k} bias / scatter</span><span>${sign(v.bias_mm, 3)} / ${fmt(v.width_sd_mm, 3)} mm (${v.n_specimens} parts)</span>`).join('')}</div>
    <p class="faint small">${c.note}</p>`;
  $('#physSpec tbody').innerHTML = c.specimens.map((s) => `<tr><td class="num">${s.specimen_id}</td><td>${s.manual_id || '—'}</td><td class="num">${s.n}</td><td class="num">${fmt(s.mean_mm, 3)}</td>
    <td class="num">${s.nominal_mm ?? '—'}</td><td class="num">${s.deviation_mm === null ? '—' : sign(s.deviation_mm, 3)}</td><td class="num">${fmt(s.spread_mm, 3)}</td></tr>`).join('');
  $('#physPhoto tbody').innerHTML = d.photo_vs_caliper.length ? d.photo_vs_caliper.map((r) => `<tr><td class="num">${r.specimen_id}</td><td>${r.file}</td><td class="num">${fmt(r.photo_mm, 3)}</td>
    <td class="num">${fmt(r.caliper_mm, 3)}</td><td class="num">${sign(r.photo_minus_caliper_mm, 3)}</td><td class="num">${fmt(r.photo_px_per_mm, 1)}</td></tr>`).join('')
    : '<tr><td colspan="6" class="faint">No photos with a matching specimen ID yet.</td></tr>';
}

let exitPhoto = async () => {};
{ const btn = $('#photoBtn'), save = $('#photoSave'), st = $('#photoStatus'); let on = false, tick = null;
  if (btn) btn.onclick = async () => {
    const v = lab.views[0]; if (!v) return;
    on = !on; btn.textContent = on ? 'Exit photo mode' : 'Photo mode'; save.disabled = !on;
    if (on) { lab.playing = false; $('#playBtn').textContent = '▶'; st.textContent = 'Building the path-tracing scene…';
      try { await v.s.photo(true); } catch (e) { st.textContent = `Photo mode unavailable: ${e.message}`; console.error("PHOTO", e.stack); on = false; btn.textContent = 'Photo mode'; save.disabled = true; return; }
      tick = setInterval(() => { const t = v.s.tracer; if (t) st.textContent = t.isCompiling ? 'Compiling the path tracer…' : t.samples < 8 ? `Warming up (${Math.floor(t.samples)}/8 samples)…` : `${Math.floor(t.samples)} samples · path traced, SIMULATED scene (left view). Sharper the longer you wait; dragging restarts.`; }, 500);
    } else { clearInterval(tick); await v.s.photo(false); st.textContent = ''; }
  };
  exitPhoto = async () => { if (on) await btn.onclick(); };
  if (save) save.onclick = () => { const a = document.createElement('a'); a.href = lab.views[0].s.snapshot(); a.download = 'qualityrelay_photo_SIMULATED.png'; a.click(); };
}
{ const hq = $('#hq'); if (hq) { hq.checked = QUALITY === 'high';
  hq.addEventListener('change', () => { localStorage.setItem('qr_quality', hq.checked ? 'high' : 'low'); const u = new URL(location.href); u.searchParams.delete('quality'); location.href = u.href; }); } }

// ---------------------------------------------------------------- router + boot
// family -> sub-views and the one tier badge shown for the whole screen. Families never share a screen.
const FAMILY = {
  physical: { views: { '': 'physical', bench: 'bench' }, tier: 'PHYSICAL', title: 'Hardware ledger only. Each row carries its own tier: PHYSICAL_CAPTURE until a recorded ground-truth check makes it VERIFIED_PHYSICAL.' },
  sim: { views: { '': 'lab', parts: 'parts', results: 'results' }, tier: 'SIMULATED', title: 'Every number here comes from simulation, not from a factory.' },
  agents: { views: { '': 'agents', benchmark: 'science' }, tier: 'TEST_FIXTURE · SIMULATED', title: 'Collaboration runs on fixture evidence; the benchmark runs on simulated lots. Neither is a physical measurement.' },
  claims: { views: { '': 'claims' }, tier: 'CLAIMS', title: 'What the evidence does and does not support.' },
};
const LEGACY = { lab: 'sim', parts: 'sim/parts', results: 'sim/results', science: 'agents/benchmark' };  // pre-WEB-01 links keep working
function setContext(fam) { if (document.body.dataset.family === fam) $('#context').textContent = ctx[fam]; }
const inited = {};
function route() {
  let h = (location.hash || '#physical').slice(1);
  if (LEGACY[h]) { h = LEGACY[h]; history.replaceState(null, '', `${location.pathname}${location.search}#${h}`); }
  let [fam, sub = ''] = h.split('/');
  if (!FAMILY[fam]) [fam, sub] = ['physical', ''];
  const F = FAMILY[fam], view = F.views[sub] || F.views[''];
  document.body.dataset.family = fam;
  document.body.classList.toggle('hassub', !!$(`#subnav-${fam}`));
  $$('.subnav').forEach((n) => (n.hidden = n.id !== `subnav-${fam}`));
  $$('.subnav a').forEach((a) => a.classList.toggle('on', a.dataset.view === view));
  $$('.view').forEach((s) => (s.hidden = s.id !== `view-${view}`));
  $$('.tabs a').forEach((a) => a.classList.toggle('on', a.dataset.family === fam));
  Object.assign($('#tier'), { textContent: F.tier, title: F.title });
  $('#toggleInspector').hidden = view !== 'lab';
  setContext(fam);
  if (view === 'physical') { if (!inited.physical) { inited.physical = true; initPhysical(); } refreshPhysical().catch((e) => ($('#physUpdated').textContent = e.message)); }
  if (view === 'agents' && !inited.agents) { inited.agents = true; initAgents().catch((e) => ($('#colStatus').textContent = e.message)); }
  if (view === 'parts' && !inited.parts) { inited.parts = true; initParts().catch((e) => ($('#partLabel').textContent = e.message)); }
  if (view === 'bench' && !inited.bench) { inited.bench = true; initBench().catch((e) => ($('#physCal').textContent = e.message)); }
  if ((view === 'results' || view === 'science') && !inited.results) { inited.results = true; initResults().catch((e) => ($('#kpis').textContent = e.message)); }
  if (view === 'lab' && !inited.lab) {  // lazy: the 3D stage must be visible to size and frame its cameras
    inited.lab = true; initLab().catch((e) => { $('#runStatus').textContent = `Lab failed to start: ${e.message}`; console.error(e); });
  }
}
window.addEventListener('hashchange', route);
route();
