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
    scrub: n => `滚动 = 爆炸行程　·　砖片抬起 ${n}%`,
    f_w: '板宽 mm', f_h: '板高 mm', f_j: '灰缝 mm', f_s: '砖片', f_c: '卡扣', f_d: '钻孔',
    foot: '几何、图纸、模型与本页由 data/ 下的脚本从同一份数据生成。',
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
    scrub: n => `SCROLL = EXPLODE　·　slips lifted ${n}%`,
    f_w: 'board w', f_h: 'board h', f_j: 'joint', f_s: 'slips', f_c: 'clips', f_d: 'drill marks',
    foot: 'The geometry, the drawings, the models and this page are generated from one set of data by the scripts under data/.',
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
// 0.62, not 1.05.  Three lights, a room environment and a bloom on top of a backing board that is
// nearly white came out as a white sheet with the board somewhere inside it.
renderer.toneMappingExposure = 0.62;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e0f11);
const camera = new THREE.PerspectiveCamera(34, 1, 0.05, 60);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.05).texture;

const key = new THREE.DirectionalLight(0xfff0dd, 1.5);
key.position.set(-1.4, 2.2, 1.7);
scene.add(key);
const rim = new THREE.DirectionalLight(0xbcd4ff, 0.8);
rim.position.set(1.9, 0.9, -1.6);
scene.add(rim);
scene.add(new THREE.AmbientLight(0xffffff, 0.12));

// Bloom, and gently.  The clips are the only bright metal in the frame, so a low threshold picks
// them out on their own without the backing board fogging up behind them.
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.28, 0.45, 0.95);
composer.addPass(bloom);
composer.addPass(new OutputPass());

let root = null, slipGroup = null, clipMeshes = [], mortar = null, backing = null;
const loader = new GLTFLoader();

const controls = new OrbitControls(camera, cv);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.rotateSpeed = 0.55;
controls.minDistance = 0.6;
controls.maxDistance = 6;
controls.maxPolarAngle = Math.PI * 0.49;      // never under the board
controls.target.set(0, 0, 0);

function fit() {
  const w = cv.clientWidth, h = cv.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
  composer.setSize(w, h);
  bloom.resolution.set(w, h);
}

async function loadBoard(i) {
  const b = D.boards[i];
  if (root) { scene.remove(root); root.traverse(o => { if (o.isMesh) o.geometry.dispose(); }); }
  const g = await loader.loadAsync(`../models/board_${b.idx}.glb`);
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
  // the slips are re-parented so one group carries the lift; the clips and the board stay put
  parts.forEach(o => { if (o.userData.slip) slipGroup.add(o); });
  root.add(slipGroup);
  scene.add(root);
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const mid = box.getCenter(new THREE.Vector3());
  root.position.sub(mid);
  const r = Math.max(size.x, size.z) * 0.5;
  camera.position.set(r * 0.55, r * 1.75, r * 2.05);
  controls.target.set(0, 0, 0);
  controls.minDistance = r * 1.1;
  controls.maxDistance = r * 6;
  controls.update();
  // the backing carries the setting-out texture, which is nearly white and swamps everything in
  // front of it once there is a bloom; on this page it is taken down to a stage grey
  if (backing) {
    root.traverse(o => {
      if (o.isMesh && (o.name || '').startsWith('backing') && o.material) {
        o.material = o.material.clone();
        o.material.color = new THREE.Color(0x3a3d42);
        if (o.material.map) o.material.map = null;
        o.material.roughness = 0.92;
        o.material.metalness = 0;
      }
    });
  }
  fit();
  explode(0);
}

/* the exploded view.  0 = assembled, 1 = the slips clear of the board and the mortar gone, which
   is the only state in which the clips and their drill marks are all visible at once. */
function explode(k) {
  if (!root) return;
  const e = k * k * (3 - 2 * k);                 // smoothstep, so the ends settle
  if (slipGroup) slipGroup.position.y = e * 0.42;
  if (mortar) { mortar.visible = e < 0.55; mortar.position.y = e * 0.42; }
  const tilt = -0.30 + e * 0.16;
  root.rotation.x = tilt;
  root.rotation.y = -0.22 + e * 0.30;
  clipMeshes.forEach(m => {
    const mt = m.material;
    if (mt && mt.emissive) {
      mt.emissive.set(new THREE.Color(CC[m.userData.code]?.metal || '#8b939c'));
      mt.emissiveIntensity = 0.05 + e * 0.55;
    }
  });
  $('#scrubi').style.width = (k * 100).toFixed(1) + '%';
  $('#scrubtxt').textContent = t('scrub')(Math.round(k * 100));
}

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
  stats: () => ({
    triangles: renderer.info.render.triangles,
    calls: renderer.info.render.calls,
    slips: slipGroup ? slipGroup.children.length : 0,
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
  $('#swapA').src = `../renders/b${b.idx}_front.webp`;
  $('#swapB').src = `../textures/setout_board_${b.idx}.png`;
  $('#swap').style.aspectRatio = `${b.w} / ${b.h}`;
  $('#chips').innerHTML = D.boards.map((x, i) =>
    `<button class="chip${i === bi ? ' on' : ''}" data-i="${i}">${String(x.idx).padStart(2, '0')}</button>`).join('');
  $('#chips').querySelectorAll('.chip').forEach(c => {
    c.onclick = () => { bi = +c.dataset.i; isolate = null; paint(); loadBoard(bi); };
  });
  applyIsolate();
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
