/* v2 — the assembly page.
 *
 * The page at / is a catalogue: nine boards, their schedules, the drawings to download.  This one
 * has a single job instead, which the catalogue only ever states in numbers - HOW THE BOARD GOES
 * TOGETHER.  So the whole of it is two ideas:
 *
 *   the stage    scroll drives an exploded view.  The slips lift off, the clips are left standing
 *                on the backing with their 2654 drill marks, and the clip legend isolates one
 *                length at a time.  Nothing here is a video: it is the same GLB the catalogue
 *                loads, taken apart by moving its meshes.
 *
 *   the drawing  the setting-out, drawn from the same boards.json, with the schedule beside it.
 *                Hover a slip and the row it is ordered on lights up; hover a row and every slip
 *                it covers lights up.  That correspondence is the thing this job has spent its
 *                whole life checking, and until now it was only ever a number in two tables.
 *
 * It reads ../data/boards.json and ../models/*.glb.  It writes nothing and shares no file with
 * the catalogue, so the two can be changed independently.
 */
import * as THREE from 'three';
import { GLTFLoader } from '../vendor/GLTFLoader.js';
import { RoomEnvironment } from '../vendor/RoomEnvironment.js';
import { OrbitControls } from '../vendor/OrbitControls.js';
import { EffectComposer } from './vendor/EffectComposer.js';
import { RenderPass } from './vendor/RenderPass.js';
import { UnrealBloomPass } from './vendor/UnrealBloomPass.js';
import { OutputPass } from './vendor/OutputPass.js';

const $ = s => document.querySelector(s);
const D = await (await fetch('../data/boards.json')).json();
const CC = D.summary.clip_colours || {};
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------------------------------------------------------------- language */
let lang = (localStorage.getItem('w9lang') || (navigator.language || '').slice(0, 2)) === 'en'
  ? 'en' : 'zh';
const T = {
  zh: {
    back: '目录', code: '武汉摄影展板　装配',
    s_plan: '图纸会跟着指针走',
    s_csched: '卡扣明细 CLIP SCHEDULE',
    s_sched: '砖片明细 BRICK SCHEDULE',
    s_swap: '成品面 ⇄ 背板放线',
    s_pick: '换一块板',
    scrub: n => `砖片抬起 ${n}%`,
    steps: ['装好', '抬起砖片', '只剩卡扣'],
    f_w: '板长 mm', f_h: '板宽 mm', f_j: '灰缝 mm', f_s: '砖片', f_c: '卡扣', f_d: '钻孔',
    author_n: '张祥 Xiang ZHANG', author_r: '产品开发工程师 Product Development Engineer',
    of: '共', row: (c, s, q) => `${c}　${s}　×${q}`
  },
  en: {
    back: 'Catalogue', code: 'WUHAN BOARDS — ASSEMBLY',
    s_plan: 'The drawing follows the pointer',
    s_csched: 'CLIP SCHEDULE',
    s_sched: 'BRICK SCHEDULE',
    s_swap: 'FINISHED FACE ⇄ SETTING OUT',
    s_pick: 'ANOTHER BOARD',
    scrub: n => `SLIPS LIFTED ${n}%`,
    steps: ['ASSEMBLED', 'SLIPS LIFTED', 'CLIPS ONLY'],
    f_w: 'board length', f_h: 'board width', f_j: 'joint', f_s: 'slips', f_c: 'clips', f_d: 'drill marks',
    author_n: 'Xiang ZHANG', author_r: 'Product Development Engineer',
    of: 'of', row: (c, s, q) => `${c}　${s}　×${q}`
  }
};
const t = k => T[lang][k];

function paint() {
  document.documentElement.lang = lang === 'zh' ? 'zh' : 'en';
  $('#lang').textContent = lang === 'zh' ? 'EN' : '中文';
  document.querySelectorAll('[data-t]').forEach(el => {
    const v = t(el.dataset.t);
    if (typeof v === 'string') el.textContent = v;
  });
  document.querySelectorAll('#steps button').forEach(bt => {
    bt.textContent = t('steps')[+bt.dataset.si];
  });
  drawBoard();
}
$('#lang').onclick = () => {
  lang = lang === 'zh' ? 'en' : 'zh';
  localStorage.setItem('w9lang', lang);
  paint();
};

/* ---------------------------------------------------------------- which board */
let bi = 0;
const board = () => D.boards[bi];

/* the pieces a rail covers, and the clip each piece wears, worked out once per board */
function coverage(b) {
  const cov = new Set();
  b.rails.forEach(r => r.covers.forEach(i => cov.add(i)));
  return cov;
}

/* the catalogue code a board-local brick type is ordered under */
const BCODE = new Map();
D.summary.bricks.forEach(e => e.use.forEach(u => BCODE.set(u.board + '/' + u.code, e.code)));
const BRICK = new Map(D.summary.bricks.map(e => [e.code, e]));
const CLIP = new Map(D.summary.clips.map(e => [e.code, e]));
const PRODOF = {};
D.boards.forEach(b => { PRODOF[b.idx] = b.product; });
const up15 = n => Math.ceil(n * 1.15);

/* +15 % is taken per (code x product) and rounded up THERE, because a product is what a purchase
   line is; rounding the code's total instead is a different number.  The bricks carry theirs in
   the data already; a clip's is derived the same way from where it is used. */
function clipSpare(e) {
  const per = {};
  (e.use || []).forEach(u => { const k = PRODOF[u.board] || ''; per[k] = (per[k] || 0) + u.qty; });
  return Object.values(per).reduce((s2, v) => s2 + up15(v), 0);
}

/* ================================================================ THE STAGE */
const cv = $('#gl');
const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.25;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e0f11);
const camera = new THREE.PerspectiveCamera(34, 1, 0.05, 60);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.05).texture;
// 0.26, the same figure the page at / uses.  A room environment at full strength is a white box
// on every side, and the slips came out of it white however far the exposure was pulled down -
// taking the exposure down only took the metal with them.  The environment is the light to cut.
scene.environmentIntensity = 0.26;

const key = new THREE.DirectionalLight(0xfff0dd, 1.45);
key.position.set(-1.4, 2.2, 1.7);
scene.add(key);
const rim = new THREE.DirectionalLight(0xbcd4ff, 0.55);
rim.position.set(1.9, 0.9, -1.6);
scene.add(rim);
scene.add(new THREE.AmbientLight(0xffffff, 0.06));

// The clay colour lives in a texture the page at / builds at run time; the GLB carries the shape
// and no brick colour at all, so the slips arrive white and stay white.  It is put back here.
const CLAY = new THREE.Color(0xc7936a);

// Bloom, and gently.  The clips are the only bright metal in the frame, so a low threshold picks
// them out on their own without the backing board fogging up behind them.
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.28, 0.45, 0.95);
composer.addPass(bloom);
composer.addPass(new OutputPass());

let root = null, slipGroup = null, clipMeshes = [], brickMeshes = [], mortar = null, backing = null;
const loader = new GLTFLoader();

const controls = new OrbitControls(camera, cv);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.rotateSpeed = 0.55;
controls.minDistance = 0.6;
controls.maxDistance = 6;
controls.maxPolarAngle = Math.PI * 0.49;      // never under the board
controls.target.set(0, 0, 0);

// The wheel belongs to the page.  OrbitControls takes it for zoom and swallows it, and over a
// canvas that fills the screen that means the page stops scrolling and the explode never runs.
// Zoom is moved onto ctrl + wheel (pinch on a trackpad sends the same thing) and the plain wheel
// is left alone.
controls.enableZoom = false;
cv.addEventListener('wheel', e => {
  if (!(e.ctrlKey || e.metaKey)) return;
  e.preventDefault();
  const d = camera.position.clone().sub(controls.target);
  const L = d.length() * Math.exp(e.deltaY * 0.0015);
  camera.position.copy(controls.target)
    .add(d.setLength(Math.min(controls.maxDistance, Math.max(controls.minDistance, L))));
}, { passive: false });

let ballR = 1;
// the distance at which a sphere of ballR fits the shorter of the two field angles
function frame() {
  const v = THREE.MathUtils.degToRad(camera.fov) * 0.5;
  const half = Math.min(v, Math.atan(Math.tan(v) * camera.aspect));
  const d = (ballR / Math.sin(half)) * 1.06;
  camera.position.set(0, 0, 0)
    .add(new THREE.Vector3(0.10, 0.60, 0.79).normalize().multiplyScalar(d));
  controls.update();
}

function fit() {
  const w = cv.clientWidth, h = cv.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
  composer.setSize(w, h);
  bloom.resolution.set(w, h);
}

let loadSeq = 0;
async function loadBoard(i) {
  const b = D.boards[i];
  // The old board is torn down AFTER the new one has arrived, and a load that has been overtaken
  // drops what it fetched.  Tearing down first and awaiting meant two quick clicks on the chips
  // left the slower board in the scene for good - and it kept the brickwork the fade could no
  // longer reach, so CLIPS ONLY showed a raft of slips over two backings.
  const seq = ++loadSeq;
  const g = await loader.loadAsync(`../models/board_${b.idx}.glb`);
  if (seq !== loadSeq) return;
  if (root) { scene.remove(root); root.traverse(o => { if (o.isMesh) o.geometry.dispose(); }); }
  root = g.scene;
  slipGroup = new THREE.Group();
  clipMeshes = [];
  mortar = backing = null;
  // WHAT THE NODES ARE ACTUALLY CALLED.  glTF names a node after the Blender OBJECT, not its
  // mesh, and build_blender9 calls the objects CLIP_R700 and backing_1 / backing_2 - the backing
  // is two primitives, the board colour and the setting-out texture.  Matching on the mesh name
  // ('R700') found nothing, so every clip was lifted along with the slips and the legend could
  // isolate none of them.
  const parts = [];
  root.traverse(o => { if (o.isMesh) parts.push(o); });
  parts.forEach(o => {
    const n = o.name || '';
    if (n.startsWith('backing')) { backing = backing || o; o.userData.fixed = true; }
    else if (n === 'MORTAR') { mortar = o; }
    else if (n.startsWith('CLIP_') && CC[n.slice(5)]) {
      o.userData.code = n.slice(5);
      o.userData.fixed = true;
      clipMeshes.push(o);
    } else o.userData.slip = true;
  });
  // The slips are re-parented so one group carries the lift; the clips and the board stay put.
  // The mortar goes up with them: it is the joint BETWEEN the slips, and it used to be cut at a
  // fixed point in the run instead, so half way through the lift the brickwork lost its joints
  // and became a raft of loose slips with daylight between them.
  parts.forEach(o => { if (o.userData.slip) slipGroup.add(o); });
  if (mortar) slipGroup.add(mortar);
  root.add(slipGroup);
  scene.add(root);
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const mid = box.getCenter(new THREE.Vector3());
  root.position.sub(mid);
  // Framed off the bounding sphere and off whichever of the two field angles is the narrower, so
  // a tall window frames the board the same as a wide one.  Set by eye against a half-size it
  // guessed at, the board ran off three sides of the screen.
  ballR = size.length() * 0.5;
  controls.target.set(0, 0, 0);
  controls.minDistance = ballR * 0.55;
  controls.maxDistance = ballR * 5;
  // the backing carries the setting-out texture, which is nearly white and swamps everything in
  // front of it once there is a bloom; on this page it is taken down to a stage grey
  root.traverse(o => {
    if (!o.isMesh || !o.material) return;
    if ((o.name || '').startsWith('backing')) {
      o.material = o.material.clone();
      o.material.color = new THREE.Color(0x3a3d42);
      if (o.material.map) o.material.map = null;
      o.material.roughness = 0.92;
      o.material.metalness = 0;
    } else if (!(o.name || '').startsWith('CLIP_')) {
      // slips and mortar: fired clay, matt, and nothing like a mirror
      o.material = o.material.clone();
      o.material.color = o === mortar ? new THREE.Color(0x9a958c) : CLAY.clone();
      o.material.roughness = 0.88;
      o.material.metalness = 0;
      // Transparency is declared here, once, and never flipped again.  It is part of three's
      // program cache key, so setting it during the fade needs material.needsUpdate - and doing
      // that on the crossing still churned a recompile every frame.  Declared up front, the fade
      // is one number.  depthWrite stays on while it is solid, so nothing sorts differently.
      o.material.transparent = true;
      // and front faces only, because a slip is a closed box.  The GLB marks every brick material
      // double-sided, and three draws a double-sided TRANSPARENT mesh twice a frame - back faces,
      // then front - flipping material.side and re-flagging needsUpdate each time
      // (three.module.js: 'material.transparent === true && material.side === DoubleSide').  That
      // is two extra draws and two program look-ups per mesh per frame for a solid that has no
      // inside to see.
      o.material.side = THREE.FrontSide;
    }
  });
  brickMeshes = [];
  slipGroup.traverse(o => { if (o.isMesh) brickMeshes.push(o); });
  fit();
  frame();
  // Where the page is scrolled to, not zero.  Changing board at the far end of the run put the
  // new board back together while the page was still at the bottom of the stage: the scrub read
  // 0 % against a scroll of 100 %, and the next nudge of the wheel snapped it back.
  explode(REDUCED ? 0.55 : progress());
}

/* how far through the stage the page is scrolled, which is what says where the explode is */
function progress() {
  const el = $('#stage');
  const travel = el.offsetHeight - innerHeight;
  return travel > 0 ? Math.max(0, Math.min(1, (scrollY - el.offsetTop) / travel)) : 0;
}

/* The exploded view.  0 = assembled; half way = the brickwork lifted clear of the board, joints
   and all; 1 = the brickwork gone and the clips left standing on the backing with their drill
   marks, which is the only state that shows all of them at once. */
function explode(k) {
  if (!root) return;
  const e = k * k * (3 - 2 * k);                 // smoothstep, so the ends settle
  if (slipGroup) slipGroup.position.y = e * 0.42;
  // The brickwork clears away over 0.58 to 0.80, because CLIPS ONLY has to mean only the clips and
  // the board they are fixed to - and it has to be gone by the point the button that says so
  // lights up, which is k = 0.8.
  const a = 1 - Math.max(0, Math.min(1, (k - 0.58) / 0.22));
  brickMeshes.forEach(m => {
    m.visible = a > 0.02;
    const mt = m.material;
    if (!mt) return;
    mt.opacity = a;
    mt.depthWrite = a > 0.999;
  });
  const tilt = -0.14 + e * 0.10;
  root.rotation.x = tilt;
  root.rotation.y = -0.22 + e * 0.30;
  clipMeshes.forEach(m => {
    const mt = m.material;
    if (mt && mt.emissive) {
      mt.emissive.set(new THREE.Color(CC[m.userData.code]?.metal || '#8b939c'));
      // Gently.  The rails cover 68 of every 75 mm of this board, so once the brickwork is out of
      // the way they are the whole picture - lit to 0.6 they flattened into one orange sheet with
      // the drill marks lost in it.
      mt.emissiveIntensity = 0.04 + e * 0.22;
    }
  });
  $('#scrubi').style.width = (k * 100).toFixed(1) + '%';
  $('#scrubtxt').textContent = t('scrub')(Math.round(k * 100));
  document.querySelectorAll('#steps button').forEach(bt => {
    bt.classList.toggle('on', Math.abs(+bt.dataset.p - k) < 0.2);
  });
}

/* The stage had one control and it was the page scroll, which is a fair way to travel through the
   explode and a poor way to stop anywhere in particular.  The three states it passes through are
   on buttons now, and the bar under them takes a drag.  Both of them move the page rather than the
   model, so the scroll position stays the one thing that says where the explode is. */
let seek = p => explode(p);
(function stageControl() {
  $('#steps').innerHTML = [0, 1, 2]
    .map(i => `<button data-si="${i}" data-p="${i / 2}"></button>`).join('');
  $('#steps').querySelectorAll('button').forEach(bt => { bt.onclick = () => seek(+bt.dataset.p); });
  const bar = $('#scrubbar');
  const at = x => {
    const r = bar.getBoundingClientRect();
    seek(Math.max(0, Math.min(1, (x - r.left) / r.width)));
  };
  let down = false;
  // seek first, capture second: a capture that is refused must not cost the click its position
  bar.addEventListener('pointerdown', e => {
    down = true;
    at(e.clientX);
    try { bar.setPointerCapture(e.pointerId); } catch (_) { /* no pointer to capture */ }
  });
  bar.addEventListener('pointermove', e => { if (down) at(e.clientX); });
  bar.addEventListener('pointerup', () => { down = false; });
})();

let isolate = null;
function applyIsolate() {
  clipMeshes.forEach(m => { m.visible = !isolate || m.userData.code === isolate; });
  document.querySelectorAll('#legend li').forEach(li => {
    li.classList.toggle('on', isolate === li.dataset.code);
  });
  document.querySelectorAll('#pan .clip').forEach(el => {
    const on = !isolate || el.dataset.code === isolate;
    el.classList.toggle('dim', !on);
    el.classList.toggle('hi', !!isolate && on);
  });
  document.querySelectorAll('#pan .hole').forEach(el => {
    el.classList.toggle('dim', !!isolate && el.dataset.code !== isolate);
  });
  document.querySelectorAll('#csched tr[data-clip]').forEach(tr => {
    tr.classList.toggle('on', isolate === tr.dataset.clip);
  });
  document.querySelector('#plan').classList.toggle('iso', !!isolate);
}

function tick() {
  controls.update();
  composer.render();
  requestAnimationFrame(tick);
}

// A handle for checking, not for the page.  A WebGL canvas cannot be read back after it has been
// composited - readPixels on the default buffer returns zeros whether the frame drew a board or
// nothing at all - so what actually got drawn is exposed instead: the triangle count per frame,
// and what the loader found in the GLB.
window.__v2 = {
  // what the slips actually come out as.  The scene is re-rendered into an offscreen target,
  // which unlike the default buffer can be read back, and the middle of the frame is averaged.
  sample: () => {
    const rt = new THREE.WebGLRenderTarget(160, 160, { type: THREE.UnsignedByteType });
    const old = renderer.getRenderTarget();
    renderer.setRenderTarget(rt);
    renderer.render(scene, camera);
    const px = new Uint8Array(160 * 160 * 4);
    renderer.readRenderTargetPixels(rt, 0, 0, 160, 160, px);
    renderer.setRenderTarget(old);
    rt.dispose();
    let r = 0, g = 0, b = 0, n = 0, white = 0;
    for (let i = 0; i < px.length; i += 4) {
      if (px[i] + px[i + 1] + px[i + 2] < 40) continue;        // the black backdrop
      r += px[i]; g += px[i + 1]; b += px[i + 2]; n++;
      if (px[i] > 235 && px[i + 1] > 235 && px[i + 2] > 235) white++;
    }
    return n ? { r: Math.round(r / n), g: Math.round(g / n), b: Math.round(b / n),
                 lit: n, whitePct: +(100 * white / n).toFixed(1) } : { lit: 0 };
  },
  scene: () => {
    const out = [];
    root && root.traverse(o => {
      if (!o.isMesh || !o.visible) return;
      const bb = new THREE.Box3().setFromObject(o);
      out.push({ n: o.name, col: '#' + o.material.color.getHexString(),
                 min: bb.min.toArray().map(v => +v.toFixed(2)),
                 max: bb.max.toArray().map(v => +v.toFixed(2)) });
    });
    return { cam: camera.position.toArray().map(v => +v.toFixed(2)),
             rot: root ? [+root.rotation.x.toFixed(3), +root.rotation.y.toFixed(3)] : null,
             meshes: out };
  },
  stats: () => ({
    bricks: brickMeshes.map(m => ({ n: m.name, on: m.visible, o: +(m.material.opacity).toFixed(3),
                                    clear: m.material.transparent, ver: m.material.version })),
    mortarInLift: !!mortar && mortar.parent === slipGroup,
    dist: +camera.position.distanceTo(controls.target).toFixed(4),
    triangles: renderer.info.render.triangles,
    calls: renderer.info.render.calls,
    slips: slipGroup ? slipGroup.children.filter(o => o !== mortar).length : 0,
    clips: clipMeshes.length,
    codes: clipMeshes.map(m => m.userData.code).filter((v, i, a2) => a2.indexOf(v) === i),
    lift: slipGroup ? +slipGroup.position.y.toFixed(4) : null
  })
};
addEventListener('resize', fit);

/* ================================================================ THE DRAWING */
const NS = 'http://www.w3.org/2000/svg';

/** the rotation and translation that carries polygon src onto dst */
function rigid(src, dst) {
  const n = Math.min(src.length, dst.length);
  const cs = [0, 0], cd = [0, 0];
  src.forEach(q => { cs[0] += q[0] / src.length; cs[1] += q[1] / src.length; });
  dst.forEach(q => { cd[0] += q[0] / dst.length; cd[1] += q[1] / dst.length; });
  let nu = 0, de = 0;
  for (let i = 0; i < n; i++) {
    nu += (src[i][0] - cs[0]) * (dst[i][1] - cd[1]) - (src[i][1] - cs[1]) * (dst[i][0] - cd[0]);
    de += (src[i][0] - cs[0]) * (dst[i][0] - cd[0]) + (src[i][1] - cs[1]) * (dst[i][1] - cd[1]);
  }
  const th = Math.atan2(nu, de), co = Math.cos(th), si = Math.sin(th);
  return p => [cd[0] + (p[0] - cs[0]) * co - (p[1] - cs[1]) * si,
               cd[1] + (p[0] - cs[0]) * si + (p[1] - cs[1]) * co];
}
let hot = null;                                   // the brick code under the pointer

function drawBoard() {
  const b = board();
  $('#bidx').textContent = String(b.idx).padStart(2, '0');
  $('#btitle').textContent = lang === 'zh' ? b.zh : b.en;
  $('#bsub').textContent = `${b.w} × ${b.h}　·　${b.joint} mm`;

  const cov = coverage(b);
  const nClip = b.rails.length + b.pieces.filter((p, i) => !cov.has(i)).length;
  const nHole = b.rails.reduce((s, r) => s + r.holes.length, 0)
    + b.pieces.filter((p, i) => !cov.has(i))
      .reduce((s, p) => s + (D.clipgeo[p.c]?.holes?.length || 0), 0);
  $('#figs').innerHTML = [
    [b.w, 'f_w'], [b.h, 'f_h'], [b.joint, 'f_j'],
    [b.pieces.length, 'f_s'], [nClip, 'f_c'], [nHole, 'f_d']
  ].map(([v, k]) => `<div><b>${v}</b><span>${t(k)}</span></div>`).join('');

  // legend: only the clip types this board actually carries
  const used = new Map();
  b.rails.forEach(r => used.set(r.code, (used.get(r.code) || 0) + 1));
  b.pieces.forEach((p, i) => { if (!cov.has(i)) used.set(p.c, (used.get(p.c) || 0) + 1); });
  const ord = ['R1000', 'R700', 'R300', 'R100', 'R50', 'PK-3T03', 'PK-8T02'];
  $('#legend').innerHTML = [...used.entries()]
    .sort((a, c) => ord.indexOf(a[0]) - ord.indexOf(c[0]))
    .map(([c, n]) => `<li data-code="${c}"><i style="background:${CC[c]?.line || '#888'};
      box-shadow:0 0 9px ${CC[c]?.line || '#888'}"></i>${c}<em>×${n}</em></li>`)
    .join('');
  $('#legend').querySelectorAll('li').forEach(li => {
    li.onclick = () => { isolate = isolate === li.dataset.code ? null : li.dataset.code; applyIsolate(); };
  });

  drawPlan(b, cov);
  drawSched(b);
  drawFace(b);
  $('#swapB').src = `../textures/setout_board_${b.idx}.png`;
  // the drawing and the wipe are the same board seen twice, so they are given the same box
  $('#swap').style.aspectRatio = $('#panwrap').style.aspectRatio = `${b.w} / ${b.h}`;
  $('#chips').innerHTML = D.boards.map((x, i) =>
    `<button class="chip${i === bi ? ' on' : ''}" data-i="${i}">${String(x.idx).padStart(2, '0')}</button>`).join('');
  $('#chips').querySelectorAll('.chip').forEach(c => {
    c.onclick = () => { bi = +c.dataset.i; isolate = null; paint(); loadBoard(bi); };
  });
  applyIsolate();
}

/* The finished face for the wipe, drawn rather than photographed.  b*_front.webp is a 29 mm lens
   looking slightly down at the board, so its outline is a trapezoid sitting inside a margin; the
   setting-out texture is the board itself, dead on.  Wiping between the two never lined up, and no
   amount of cropping makes a perspective view register with an orthographic one.  Both halves are
   now the same rectangle off the same coordinates, so a course on the left is the course on the
   right.  What shows between the slips is the joint. */
function drawFace(b) {
  const cvs = $('#swapA'), S = Math.min(2, 1500 / b.w);
  cvs.width = Math.round(b.w * S);
  cvs.height = Math.round(b.h * S);
  const g = cvs.getContext('2d');
  g.fillStyle = '#a29c92';
  g.fillRect(0, 0, cvs.width, cvs.height);
  g.setTransform(S, 0, 0, -S, 0, cvs.height);      // the board's own frame, y up
  b.pieces.forEach((p, i) => {
    let h = (i * 2654 + b.idx * 977) & 0xffff;
    h ^= h >> 5;
    const v = (h % 21) - 10;                       // clay is not one colour
    g.fillStyle = `rgb(${186 + v},${143 + v},${103 + v})`;
    g.beginPath();
    p.p.forEach((q, k) => (k ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1])));
    g.closePath();
    g.fill();
  });
  g.setTransform(1, 0, 0, 1, 0, 0);
}

function drawPlan(b, cov) {
  const svg = $('#pan');
  svg.setAttribute('viewBox', `0 0 ${b.w} ${b.h}`);
  svg.innerHTML = '';
  const g = document.createElementNS(NS, 'g');
  // the drawing is built the way the board is: y up, so it is flipped into SVG's y-down frame
  g.setAttribute('transform', `translate(0,${b.h}) scale(1,-1)`);
  svg.appendChild(g);

  b.pieces.forEach((p, i) => {
    const el = document.createElementNS(NS, 'polygon');
    el.setAttribute('points', p.p.map(q => q.join(',')).join(' '));
    el.setAttribute('class', 'slip');
    const code = BCODE.get(b.idx + '/' + b.types[p.t].code);
    el.dataset.code = code;
    el.dataset.i = i;
    g.appendChild(el);
  });
  const clipPoly = (k, code) => {
    const el = document.createElementNS(NS, 'polygon');
    el.setAttribute('points', k.map(q => q.join(',')).join(' '));
    el.setAttribute('class', 'clip');
    el.setAttribute('stroke', CC[code]?.line || '#888');
    el.dataset.code = code;
    g.appendChild(el);
  };
  b.rails.forEach(r => {
    clipPoly(r.k, r.code);
    r.holes.forEach(h => {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', h[0]); c.setAttribute('cy', h[1]); c.setAttribute('r', 1.75);
      c.setAttribute('class', 'hole');
      g.appendChild(c);
    });
  });
  // A clip that sits on one slip carries its type's holes, and boards.json stores those against
  // the blank's own corner - so they are carried onto the slip by the motion that put the tray
  // there, the same recovery setout9 does for dxf/08.  Left out, the plan drew 238 of board 1's
  // 280 drill marks and the count under the stage disagreed with the drawing beside it.
  b.pieces.forEach((p, i) => {
    if (cov.has(i) || !p.k) return;
    clipPoly(p.k, p.c);
    const geo = D.clipgeo[p.c];
    if (!geo || !geo.holes || geo.base.length !== p.k.length) return;
    const mv = rigid(geo.base, p.k);
    geo.holes.forEach(h => {
      const q = mv(h);
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', q[0]); c.setAttribute('cy', q[1]); c.setAttribute('r', 1.75);
      c.setAttribute('class', 'hole');
      g.appendChild(c);
    });
  });

  svg.onpointermove = ev => {
    const el = ev.target.closest ? ev.target.closest('.slip') : null;
    setHot(el ? el.dataset.code : null);
  };
  svg.onpointerleave = () => setHot(null);
}

function setHot(code) {
  if (hot === code) return;
  hot = code;
  document.querySelectorAll('#pan .slip').forEach(el => {
    el.classList.toggle('on', !!code && el.dataset.code === code);
    el.classList.toggle('dim', !!code && el.dataset.code !== code);
  });
  // a slip is picked out by taking the whole rest of the drawing down, clips and drill marks
  // included - leaving them at full weight left the picked slip inside the same thicket of lines
  if (!isolate) {
    document.querySelectorAll('#pan .clip, #pan .hole')
      .forEach(el => el.classList.toggle('dim', !!code));
  }
  document.querySelectorAll('#sched tr').forEach(tr => {
    tr.classList.toggle('on', !!code && tr.dataset.code === code);
  });
  const e = code && BRICK.get(code);
  $('#pick').textContent = e
    ? t('row')(e.code, e.dims ? `${e.dims[0]} × ${e.dims[1]}` : '', e.qty)
    : '';
}

function drawSched(b) {
  const cov = coverage(b);

  const perB = new Map();
  b.pieces.forEach(p => {
    const c = BCODE.get(b.idx + '/' + b.types[p.t].code);
    perB.set(c, (perB.get(c) || 0) + 1);
  });
  $('#sched').innerHTML = head(lang === 'zh' ? 'mm' : 'mm')
    + [...perB.entries()].sort((x, y) => y[1] - x[1]).map(([c, n]) => {
      const e = BRICK.get(c);
      return `<tr data-code="${c}"><td>${c}</td>
        <td>${e.dims ? e.dims[0] + ' × ' + e.dims[1] : ''}</td>
        <td class="n">${n}</td><td class="n">${e.qty}</td><td class="n or">${e.spare}</td></tr>`;
    }).join('');
  $('#sched').querySelectorAll('tr[data-code]').forEach(tr => {
    tr.onpointerenter = () => setHot(tr.dataset.code);
    tr.onpointerleave = () => setHot(null);
  });

  const perC = new Map();
  b.rails.forEach(r => perC.set(r.code, (perC.get(r.code) || 0) + 1));
  b.pieces.forEach((p, i) => { if (!cov.has(i)) perC.set(p.c, (perC.get(p.c) || 0) + 1); });
  const ord = ['R1000', 'R700', 'R300', 'R100', 'R50', 'PK-3T03', 'PK-8T02'];
  $('#csched').innerHTML = head(lang === 'zh' ? '长度' : 'length')
    + [...perC.entries()].sort((x, y) => ord.indexOf(x[0]) - ord.indexOf(y[0])).map(([c, n]) => {
      const e = CLIP.get(c) || { qty: 0 };
      return `<tr data-clip="${c}">
        <td><i class="sw" style="background:${CC[c]?.line || '#888'}"></i>${c}</td>
        <td>${e.length ? e.length + ' mm' : (lang === 'zh' ? '随砖形' : 'follows piece')}</td>
        <td class="n">${n}</td><td class="n">${e.qty}</td>
        <td class="n or">${clipSpare(e)}</td></tr>`;
    }).join('');
  $('#csched').querySelectorAll('tr[data-clip]').forEach(tr => {
    tr.onpointerenter = () => { isolate = tr.dataset.clip; applyIsolate(); };
    tr.onpointerleave = () => { isolate = null; applyIsolate(); };
    tr.onclick = () => { isolate = isolate === tr.dataset.clip ? null : tr.dataset.clip; applyIsolate(); };
  });
}

function head(mid) {
  const zh = lang === 'zh';
  return `<tr><th>${zh ? '件号' : 'CODE'}</th><th>${mid}</th>
    <th class="n">${zh ? '本板' : 'here'}</th><th class="n">${zh ? '全场' : 'all nine'}</th>
    <th class="n or">${zh ? '备料 +15%' : '+15% order'}</th></tr>`;
}

/* ---------------------------------------------------------------- the wipe */
(function swap() {
  const el = $('#swap'), b = $('#swapB'), h = $('#handle');
  // CLIP-PATH, not a box of its own width.  The setting-out was in a narrower box with an image
  // sized to itself, so the two halves were at different scales and the seam sat wherever that
  // box happened to end - half the board was brick and half was backing, and the handle never
  // reached either edge.  Both images now fill the same box and the top one is cut, so the seam
  // is a straight line through one picture and it goes edge to edge.
  const set = x => {
    const r = el.getBoundingClientRect();
    const p = Math.max(0, Math.min(100, ((x - r.left) / r.width) * 100));
    b.style.clipPath = `inset(0 0 0 ${p}%)`;
    h.style.left = p + '%';
  };
  let down = false;
  el.addEventListener('pointerdown', e => { down = true; el.setPointerCapture(e.pointerId); set(e.clientX); });
  el.addEventListener('pointermove', e => { if (down) set(e.clientX); });
  el.addEventListener('pointerup', () => { down = false; });
  set(el.getBoundingClientRect().left + el.getBoundingClientRect().width * 0.5);
})();

/* ---------------------------------------------------------------- motion */
paint();
await loadBoard(0);
tick();

if (!REDUCED) {
  const lenis = new Lenis({ lerp: 0.11, wheelMultiplier: 0.9 });
  const raf = time => { lenis.raf(time); requestAnimationFrame(raf); };
  requestAnimationFrame(raf);
  gsap.registerPlugin(ScrollTrigger);
  lenis.on('scroll', ScrollTrigger.update);

  ScrollTrigger.create({
    trigger: '#stage',
    start: 'top top',
    end: 'bottom bottom',
    scrub: 0.6,
    onUpdate: s => explode(s.progress)
  });
  seek = p => {
    const el = $('#stage');
    lenis.scrollTo(el.offsetTop + p * (el.offsetHeight - innerHeight), { duration: 0.85 });
  };
  gsap.from('.ttl h1', {
    scrollTrigger: { trigger: '#stage', start: 'top top' },
    yPercent: 24, opacity: 0, duration: 0.9, ease: 'power3.out'
  });
  gsap.from('#plan .head > *', {
    scrollTrigger: { trigger: '#plan', start: 'top 78%' },
    y: 22, opacity: 0, duration: 0.7, stagger: 0.09, ease: 'power2.out'
  });
  gsap.from('.chip', {
    scrollTrigger: { trigger: '#boards', start: 'top 85%' },
    y: 14, opacity: 0, duration: 0.45, stagger: 0.03, ease: 'power2.out'
  });
} else {
  explode(0.55);
}
