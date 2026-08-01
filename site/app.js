import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';
import {RoomEnvironment} from './vendor/RoomEnvironment.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const D = await (await fetch('data/boards.json')).json();
const {boards, clipgeo, profile: P, slip: SLIP} = D;
const LEGOUT = (P.flat - SLIP[1]) / 2;      // 1.5, how far a leg stands outside the slip face
const byIdx = Object.fromEntries(boards.map(b => [b.idx, b]));

const INK = '#1d1d1b', MUT = '#7d7a72', LINE = '#d3ccbd';
// R50 blue, the longer rails green, the bespoke pockets rust: three families, three colours
const CLIP_COL = c => c === 'R50' ? '#2f6ea8' : /^R\d/.test(c) ? '#1f7a5a' : '#b4491f';

/* =====================================================================
   language
   ===================================================================== */
const T = {
  zh: {
    code: '武汉摄影展板　九块', nav_boards: '选板', nav_model: '模型', nav_bricks: '砖型',
    nav_clips: '卡扣', nav_shots: '渲染', nav_draw: '图纸', nav_files: '文件', lang: 'EN',
    s_boards: '九块板', s_boards_p: '点任一块，下面的模型与全部表格都会跟着换。',
    bc_size: '板面', bc_types: '砖型', bc_pcs: '砖片',
    th_for: '属于', dl_all: '打包下载全部内容',
    v_exp: '分解',
    loading: '载入模型', board: '板', of: ' / 九',
    hint: '<b>拖动</b> 旋转　<b>Ctrl + 滚轮</b> 缩放　点击任一砖片或卡扣',
    h_view: '视角', h_colour: '配色', h_layers: '图层', h_lift: '抬起砖片', h_zoom: '缩放',
    z_fit: '复位',
    q_exact_s: '按图施工的净数量', q_spare_s: '订货量，含损耗',
    v_hero: '立体', v_front: '正视', v_rake: '掠光',
    m_real: '真实', m_type: '砖型', m_clip: '卡扣',
    l_slips: '砖片', l_clips: '卡扣', l_mortar: '砂浆', l_board: '背板',
    // 粗面 / 细面, the same two words the drawings use.  The site said 毛面 / 光面, so one finish
    // had two names depending on which document the reader had in front of them.
    wall: '墙面', floor: '地面', raw: '粗面', sleek: '细面',
    st_size: '板面 mm', st_slips: '砖片', st_types: '砖型', st_clips: '卡扣', st_ctypes: '卡扣型',
    s_bricks: '砖型表', s_bricks_p: '每一型画在同一比例的整砖虚影上。点一行可在上方模型中单独亮出该型。',
    th_code: '代号', th_kind: '类别', th_size: '外廓 mm', th_area: '面积 mm²',
    th_qty: '数量', th_desc: '说明',
    k_whole: '整砖', k_std: '标准件', k_cut: '切砖',
    d_whole: l => `整砖片，${l} mm`,
    d_std: l => `标准件，${l} mm`,
    d_cut: (n, l, w, h) => `切割件，${n} 边 ${l} mm，外接框 ${w} × ${h}`,
    note_cut: n => `虚线是未切的 ${SLIP[0]} × ${SLIP[1]} 整砖。这块板有 ${n} 片切砖。`,
    note_nocut: `虚线是未切的 ${SLIP[0]} × ${SLIP[1]} 整砖。这块板全部使用整砖，无需切割。`,
    s_clips: '卡扣表',
    s_clips_p: `板厚 ${P.sheet}，立边 ${P.leg} 高，${P.lip} mm 唇边内折 ${P.angle}°，全场一致。导轨卡扣平板 ${P.flat} 宽、开口收至 ${P.mouth}；包边卡扣随砖片外形走，没有固定宽度。`,
    v_plan: '平面', v_sect: '断面', v_blank: '展开料',
    d_fit: '适宽', d_dl: '下载原图', open_svg: '点击打开矢量图，可放大滚动',
    cap_plan: '阴影为唇边折过来压住砖片的部分',
    cap_sect: '箭头为折弯方向：向内',
    cap_blank: '折边为展平状态，箭头为折向',
    cap_brk: '断开画法：两端为实长，中间等断面省略',
    blank_note: b => `展开料 ${b} 宽`,
    brk_note: (L, n, d) => `全长 ${L} mm，${n} 个 Ø${d} 固定孔；`+`图为断开画法，中间等断面已省略，两端按实长绘制。`,
    fold_note: (f, t, w) => `折边一律<b>向内折回</b>压住砖片：` +
      [f ? `${f} 条整边折起` : '', t ? `${t} 条仅在中部折一个 ${w} mm 宽小卡扣` : '']
        .filter(Boolean).join('，') + '。',
    s_shots: '渲染', s_shots_p: '三张同一套灯光。点击看大图。',
    sh_front: '正视', sh_hero: '立体', sh_detail: '掠光局部',
    sh_front_s: '板面正投影', sh_hero_s: '整板三维', sh_detail_s: '620 mm 局部',
    s_draw: '图纸', s_draw_p: '九块板共用三张总图：S7 排布与砖型表、S8 卡扣详图、S9 砖片下料图。点击看大图，原稿在文件区；背板放线图为 1:1 的 dxf/08，无预览图，同样在文件区下载。',
    sheet7: '九板排布与砖型表', sheet8: '卡扣详图', sheet9: '砖片下料图',
    no_gl: '这台设备的浏览器没有可用的 WebGL，三维查看器无法运行，上面显示的是这块板的渲染图。'
         + '页面其余部分（排布、砖型与卡扣明细、图纸、下载）不受影响。'
         + '换一个较新的浏览器，或在电脑上打开，即可使用三维。',
    nav_sum: '汇总',
    s_sum: '九块板汇总',
    s_sum_p: '九块板合起来的下料表。砖型按尺寸归并，同一尺寸在各板上编号不同也只算一种。',
    q_exact: '实际用量', q_spare: '备料 +15%',
    sum_bricks: '砖片', sum_clips: '卡扣',
    th_used: '用于', th_total: '合计', th_prod: '砖类型',
    note_exact: (b, c) => `实际用量：砖片 ${b} 片，卡扣 ${c} 个。${prodNote()}${longNote()}`,
    note_spare: (b, c) => `含 15% 备料，按（型号 × 砖类型）逐项向上取整（下单最小单位）：砖片 ${b} 片，卡扣 ${c} 个。两者不再一一对应，因为一根长卡扣覆盖整排砖。`,
    g_shape: '按形状', g_type: '按型号', g_prod: '按砖类型',
    g_board: '按板号', g_board_l: '板',
    note_board: '　按板分组只给出净用量：备料按砖类型下单，不按板分摊。',
    s_files: '文件', s_files_p: '每块板的模型与渲染单独列出，图纸与数据九块板共用。',
    th_file: '文件', th_what: '内容', th_size2: '大小', dl: '下载',
    foot1: '武汉摄影展板　砖片 215 × 65 × 20',
    f_glb: n => `第 ${n} 块板的三维模型`,
    f_blend: n => `第 ${n} 块板的 Blender 文件，砂浆可用小眼睛开关`,
    f_front: n => `第 ${n} 块板 正视渲染`, f_hero: n => `第 ${n} 块板 立体渲染`,
    f_detail: n => `第 ${n} 块板 掠光局部`,
    f_dxf1: '九板排布图 DXF', f_dxf2: '卡扣详图 DXF', f_dxf3: '砖片下料图 DXF', f_dxf4: '背板放线图 DXF',
    f_dxf3s: '砖片下料图 DXF（备料 +15%）',
    f_dxf4s: '背板放线图 DXF（备料 +15%，排布不变）',
    f_bcsv: '砖片明细表 CSV（形状 / 砖类型 / 板号 三种分组）',
    f_ccsv: '卡扣明细表 CSV（型号 / 砖类型 / 板号 三种分组）',
    f_s7svg: 'S7 九板排布与砖型表 SVG', f_s7png: 'S7 同上 PNG',
    f_s8svg: 'S8 卡扣详图 SVG', f_s8png: 'S8 同上 PNG',
    f_s9svg: 'S9 砖片下料图 SVG', f_s9png: 'S9 同上 PNG',
    f_cmp: '原始要求与最终设计对照 PDF',
    f_json: '全部几何的来源',
    i_size: '外廓', i_area: '面积', i_qty: '数量', i_note: '说明',
    i_sect: '断面', i_mouth: '开口', i_sheet: '板厚',
    foot2: (b) => `第 ${b.idx} 块　${b.pieces.length} 片　${b.types.length} 砖型　${b.clips.length} 卡扣型`
  },
  en: {
    code: 'WUHAN PHOTOGRAPHY BOARDS   NINE', nav_boards: 'Boards', nav_model: 'Model',
    nav_bricks: 'Bricks',
    s_boards: 'The nine boards',
    s_boards_p: 'Pick any one. The model below and every table on the page follow it.',
    bc_size: 'board', bc_types: 'types', bc_pcs: 'slips',
    th_for: 'For', dl_all: 'Download everything as one zip',
    v_exp: 'Exploded',
    nav_clips: 'Clips', nav_shots: 'Renders', nav_draw: 'Drawings', nav_files: 'Files',
    lang: '中文', loading: 'LOADING MODEL', board: 'Board', of: ' / 9',
    hint: '<b>drag</b> to orbit　<b>ctrl + scroll</b> to zoom　click any slip or clip',
    h_view: 'View', h_colour: 'Colour', h_layers: 'Layers', h_lift: 'Lift the slips off',
    h_zoom: 'Zoom', z_fit: 'Fit',
    q_exact_s: 'net, exactly as drawn', q_spare_s: 'what to order, breakage allowed for',
    v_hero: 'Hero', v_front: 'Front', v_rake: 'Raking',
    m_real: 'Real', m_type: 'Brick type', m_clip: 'Clip type',
    l_slips: 'Slips', l_clips: 'Clips', l_mortar: 'Mortar', l_board: 'Backing',
    wall: 'Wall', floor: 'Floor', raw: 'Raw', sleek: 'Sleek',
    st_size: 'board mm', st_slips: 'slips', st_types: 'types', st_clips: 'clips',
    st_ctypes: 'clip types',
    s_bricks: 'Brick schedule',
    s_bricks_p: 'Each type is drawn against a ghost of the uncut slip at one scale. Click a row to isolate it in the model.',
    th_code: 'Code', th_kind: 'Kind', th_size: 'Bounding mm', th_area: 'Area mm²',
    th_qty: 'Qty', th_desc: 'Description',
    k_whole: 'whole', k_std: 'standard', k_cut: 'cut',
    d_whole: l => `Whole slip, ${l} mm`,
    d_std: l => `Standard, ${l} mm`,
    d_cut: (n, l, w, h) => `Cut, ${n} sides ${l} mm, bbox ${w} × ${h}`,
    note_cut: n => `The dashed outline is the uncut ${SLIP[0]} × ${SLIP[1]} slip. This board has ${n} cut pieces.`,
    note_nocut: `The dashed outline is the uncut ${SLIP[0]} × ${SLIP[1]} slip. This board is laid entirely in whole slips.`,
    s_clips: 'Clip schedule',
    s_clips_p: `Sheet ${P.sheet}, legs ${P.leg}, ${P.lip} mm lip folded ${P.angle}° inward, the same throughout. The rail clip is ${P.flat} across with a ${P.mouth} mouth; a pocket follows the piece and has no set width.`,
    v_plan: 'Plan', v_sect: 'Section', v_blank: 'Blank',
    d_fit: 'Fit width', d_dl: 'Download', open_svg: 'click for the vector sheet, zoom and scroll',
    cap_plan: 'shaded = the lip folded back over the slip',
    cap_sect: 'arrow = the fold direction: inward',
    cap_blank: 'flaps shown unfolded; arrow = which way they fold',
    cap_brk: 'broken view: both ends to length, the identical middle omitted',
    blank_note: b => `blank ${b} across`,
    brk_note: (L, n, d) => `${L} mm overall, ${n} off Ø${d} fixing holes. `+`Drawn broken: both ends are to length and the identical middle is omitted.`,
    fold_note: (f, t, w) => `Every fold hooks <b>INWARD</b>, back over the slip: ` +
      [f ? `${f} full-length lip${f > 1 ? 's' : ''}` : '',
       t ? `${t} edge${t > 1 ? 's' : ''} folded only as a ${w} mm wide tab at the middle` : '']
        .filter(Boolean).join(', ') + '.',
    s_shots: 'Renders', s_shots_p: 'Three views, one lighting set-up. Click to enlarge.',
    sh_front: 'Front', sh_hero: 'Hero', sh_detail: 'Raking',
    sh_front_s: 'elevation', sh_hero_s: 'whole board', sh_detail_s: '620 mm detail',
    s_draw: 'Drawings', s_draw_p: 'Three sheets cover all nine boards: S7 layouts and brick schedule, S8 clip details, S9 brick cutting. Click to enlarge; originals are under Files. The setting-out for the backing board is dxf/08, drawn 1:1 with no preview, and is under Files too.',
    sheet7: 'Boards and brick schedule', sheet8: 'Clip details',
    sheet9: 'Brick slips, cutting drawing',
    no_gl: 'This browser has no working WebGL, so the 3D viewer cannot run and the picture above '
         + 'is a render of this board. Everything else on the page - the layouts, the brick and '
         + 'clip schedules, the drawings and the downloads - is unaffected. Open it in a newer '
         + 'browser, or on a computer, for the 3D.',
    nav_sum: 'Summary',
    s_sum: 'All nine boards',
    s_sum_p: 'The cutting list for the nine boards together. Brick types are grouped by size, so one size is one row however the boards number it.',
    q_exact: 'As built', q_spare: 'With 15% spare',
    sum_bricks: 'Bricks', sum_clips: 'Clips',
    th_used: 'Used on', th_total: 'Total', th_prod: 'Product',
    note_exact: (b, c) => `As built: ${b} slips, ${c} clips.${prodNote()}${longNote()}`,
    note_spare: (b, c) => `With 15% spare, rounded up per (type × product) - the cell an order line is placed against: ${b} slips, ${c} clips. The two no longer match one for one, because a long clip covers a whole run of slips.`,
    g_shape: 'By shape', g_type: 'By type', g_prod: 'By product',
    g_board: 'By board', g_board_l: 'Board',
    note_board: '  Grouped by board the figure is net only: spare is ordered per product, not apportioned board by board.',
    s_files: 'Files', s_files_p: 'Each board has its own model and renders; the drawings and the data cover all nine.',
    th_file: 'File', th_what: 'What it is', th_size2: 'Size', dl: 'Download',
    foot1: 'Wuhan photography boards   slip 215 × 65 × 20',
    f_glb: n => `Board ${n}, the model in this viewer`,
    f_blend: n => `Board ${n}, Blender file, mortar on its own collection`,
    f_front: n => `Board ${n} front elevation`, f_hero: n => `Board ${n} hero render`,
    f_detail: n => `Board ${n} raking detail`,
    f_dxf1: 'Boards, DXF', f_dxf2: 'Clip details, DXF', f_dxf3: 'Brick slips, DXF', f_dxf4: 'Setting out on the board, DXF',
    f_dxf3s: 'Brick slips, DXF (order quantities +15%)',
    f_dxf4s: 'Setting out, DXF (order quantities +15%, layout unchanged)',
    f_bcsv: 'Brick schedule, CSV (by shape / product / board)',
    f_ccsv: 'Clip schedule, CSV (by type / product / board)',
    f_s7svg: 'S7 boards and brick schedule, SVG', f_s7png: 'S7 as above, PNG',
    f_s8svg: 'S8 clip details, SVG', f_s8png: 'S8 as above, PNG',
    f_s9svg: 'S9 brick slips, SVG', f_s9png: 'S9 as above, PNG',
    f_cmp: 'Requirement against final design, PDF',
    f_json: 'The geometry everything is generated from',
    i_size: 'bounding', i_area: 'area', i_qty: 'qty', i_note: 'note',
    i_sect: 'section', i_mouth: 'mouth', i_sheet: 'sheet',
    foot2: (b) => `Board ${b.idx}   ${b.pieces.length} slips   ${b.types.length} types   ${b.clips.length} clip types`
  }
};
let lang = localStorage.getItem('wuhan-lang') || 'en';
const t = k => T[lang][k];

/* =====================================================================
   procedural fired clay, generated once
   ===================================================================== */
const TILE = 0.25, N = 768, L0 = 0.75, KCOL = 0.105;

const TEX = (() => {
  const hash = (x, y, s) => {
    let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(s, 2147483647);
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
  };
  const wrap = (v, p) => ((v % p) + p) % p;
  const vn = (x, y, per, s) => {
    const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = hash(wrap(xi, per), wrap(yi, per), s), b = hash(wrap(xi + 1, per), wrap(yi, per), s);
    const c = hash(wrap(xi, per), wrap(yi + 1, per), s), d = hash(wrap(xi + 1, per), wrap(yi + 1, per), s);
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
  };
  const fbm = (x, y, per, s, oct) => {
    let tt = 0, amp = 1, f = 1, nm = 0;
    for (let i = 0; i < oct; i++) {
      tt += amp * vn(x * f, y * f, per * f, s + i); nm += amp; amp *= 0.5; f *= 2;
    }
    return tt / nm;
  };
  const PM = Math.round(26 * TILE), PG = Math.round(300 * TILE), PK = Math.round(780 * TILE);
  const H = new Float32Array(N * N);
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const u = x / N, v = y / N;
      const m = fbm(u * PM, v * PM, PM, 11, 3);
      const g = fbm(u * PG, v * PG, PG, 27, 2);
      const f = vn(u * PG * 3.6, v * PG * 3.6, Math.round(PG * 3.6), 53);
      const k = vn(u * PK, v * PK, PK, 71);
      H[y * N + x] = 0.30 * m + 0.34 * g + 0.26 * (k > 0.86 ? (k - 0.86) / 0.14 : 0) + 0.10 * f;
    }
  }
  let mu = 0; for (let i = 0; i < H.length; i++) mu += H[i];
  mu /= H.length;
  let sd = 0; for (let i = 0; i < H.length; i++) sd += (H[i] - mu) ** 2;
  sd = Math.sqrt(sd / H.length) || 1;
  for (let i = 0; i < H.length; i++) H[i] = Math.max(0, Math.min(1, 0.5 + (H[i] - mu) / (4 * sd)));

  const at = (x, y) => H[wrap(y, N) * N + wrap(x, N)];
  const enc = c => c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
  const cv = fn => {
    const c = document.createElement('canvas'); c.width = c.height = N;
    const g2 = c.getContext('2d'), im = g2.createImageData(N, N), d = im.data;
    for (let y = 0; y < N; y++) {
      for (let x = 0; x < N; x++) {
        const i = (y * N + x) * 4, o = fn(x, y);
        d[i] = o[0]; d[i + 1] = o[1]; d[i + 2] = o[2]; d[i + 3] = 255;
      }
    }
    g2.putImageData(im, 0, 0); return c;
  };
  const mk = c => {
    const x = new THREE.CanvasTexture(c);
    x.wrapS = x.wrapT = THREE.RepeatWrapping;
    x.repeat.set(1 / TILE, 1 / TILE);
    return x;
  };
  const albedo = mk(cv((x, y) => {
    const v = Math.round(255 * enc(Math.min(1, L0 * (1 + KCOL * 2 * (at(x, y) - 0.5)))));
    return [v, v, v];
  }));
  albedo.colorSpace = THREE.SRGBColorSpace;
  const rough = mk(cv((x, y) => {
    const v = Math.round(255 * (0.87 + 0.06 * (0.5 - at(x, y)) * 2));
    return [v, v, v];
  }));
  const normal = mk(cv((x, y) => {
    const dx = at(x + 1, y) - at(x - 1, y), dy = at(x, y + 1) - at(x, y - 1);
    const S = 4.0, l = Math.hypot(-dx * S, -dy * S, 1);
    return [Math.round((-dx * S / l * 0.5 + 0.5) * 255),
            Math.round((-dy * S / l * 0.5 + 0.5) * 255),
            Math.round((1 / l * 0.5 + 0.5) * 255)];
  }));
  return {albedo, rough, normal};
})();

/* =====================================================================
   renderer
   ===================================================================== */
const canvas = $('#gl');
// The viewer is ONE section of this page, and it used to be able to take the whole page with it.
// three r180 is WebGL2-only, so on a phone without it - an older Android GPU, a webview on a
// driver blacklist, an iOS context lost under memory pressure - this line threw, and because it
// runs at module level the throw stopped everything after it: the i18n pass, the board cards,
// every schedule and the files table. The page went from 4802 characters to 58 and read as simply
// broken. Nothing below the model needs a GPU, so a failure here now costs the viewer and nothing
// else; the stage keeps the still render it already shows before you interact with it.
let renderer = null;
try {
  renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true});
} catch (e) {
  renderer = null;
}
const GL = !!renderer;
if (GL) {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
}

const scene = new THREE.Scene();
if (GL) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
}
scene.environmentIntensity = 0.30;

const key = new THREE.DirectionalLight(0xffffff, 2.55 / L0 * 0.42);
key.position.set(-0.42, 0.72, 0.55).multiplyScalar(10);
const fill = new THREE.DirectionalLight(0xffffff, 0.77 / L0 * 0.42);
fill.position.set(0.78, 0.38, 0.50).multiplyScalar(10);
scene.add(key, fill, new THREE.HemisphereLight(0xffffff, 0xd8d2c4, 0.42 / L0));

// Blender's camera.angle spans the longer sensor axis, so the hero's 30 deg is horizontal on a
// 3:2 frame and 20.3 deg vertical.  three's fov is vertical, so this is what matches the still.
const camera = new THREE.PerspectiveCamera(20.3, 1, 0.02, 200);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.08;
controls.rotateSpeed = 0.85; controls.zoomSpeed = 0.9; controls.panSpeed = 0.7;
// The page owns the wheel.  With OrbitControls holding it, a scroll anywhere over the stage zoomed
// the model instead of moving the page, and the stage is tall, so there was no way past the hero
// without hunting for a gap.  Zoom is on ctrl or cmd + wheel, which is also what maps and CAD do.
// Zoom stays off the WHEEL, which the page owns, but a phone has no wheel and pinch is THE
// gesture: with enableZoom false a two-finger pinch on the canvas did nothing at all, and
// touch-action:none meant it did not zoom the page either, so there was no way to get closer
// except the small +/- buttons.  Zoom is enabled and the wheel is taken back below.
controls.enableZoom = true;
controls.minPolarAngle = 0; controls.maxPolarAngle = Math.PI;   // let it go right round the back
// Zoom has to be on for pinch and off for a plain wheel, and OrbitControls has one flag for both.
// So the flag is dropped for exactly the length of one wheel dispatch: this runs in the capture
// phase, OrbitControls' own listener on this same element then reads false and returns without
// preventDefault - leaving the page free to scroll - and the flag is back before anything else
// happens.  stopImmediatePropagation would have done it too, but it silences EVERY other wheel
// listener on the canvas, which is more than this needs to say.
canvas.addEventListener('wheel', e => {
  if (e.ctrlKey || e.metaKey) return;
  controls.enableZoom = false;
  setTimeout(() => { controls.enableZoom = true; }, 0);
}, {capture: true, passive: true});
canvas.addEventListener('wheel', e => {
  if (!(e.ctrlKey || e.metaKey)) return;
  e.preventDefault();
  const k = Math.pow(0.94, -Math.sign(e.deltaY));
  const off = camera.position.clone().sub(controls.target);
  const d = Math.min(Math.max(off.length()*k, controls.minDistance), controls.maxDistance);
  camera.position.copy(controls.target).add(off.setLength(d));
}, {passive: false});
// exposed so the check harness can prove ctrl+wheel is what moves the camera
window.__camDist = () => camera.position.distanceTo(controls.target);
window.__camPos = () => ({x: camera.position.x, y: camera.position.y, z: camera.position.z});

// build_blender9.py exports yup, which leaves the board lying flat: the face normal (Blender +Z)
// comes in as three +Y and the board's own up (Blender +Y) as three -Z.  The obvious fix was to
// point camera.up at the board's up, and that is what caused the drag to fight back: OrbitControls
// builds its spherical frame from object.up ONCE, in its constructor, and camera.up was being set
// afterwards.  The control was orbiting about world +Y while the camera was rolled to -Z, so a
// horizontal drag came out as a mixture of azimuth and polar - pull left, turn right - and near
// the mismatched poles it stalled altogether.
//
// So do not rewrite the camera.  Stand the MODEL up instead: a quarter turn about X puts the
// board's up on world +Y and its face on +Z, which is the orientation every 3D viewer assumes,
// and the default camera.up then needs no help.
const MODEL_TILT = Math.PI/2;
const OUT = new THREE.Vector3(0, 0, 1);
const UP = new THREE.Vector3(0, 1, 0);
const SIDE = new THREE.Vector3(1, 0, 0);

const VIEWS = {
  hero:  {v: [0.90, -0.26, 0.36], z: 1.18, still: true},
  front: {v: [1.00, -0.05, 0.00], z: 1.14},
  // a real grazing shot: almost along the face, so the 20 mm relief and the joint shadows read
  rake:  {v: [0.26, -0.34, 0.90], z: 0.72},
  // the assembly, with the slips lifted off the clips that hold them.  The old fourth view sat 20
  // degrees from raking and handed the reader the same picture twice; a plain back view is worse
  // still, because the backing board is in the way of everything worth seeing.
  exp:   {v: [0.66, -0.52, 0.54], z: 1.30, lift: 62}
};
const LEDE = 0.28;
const lede_f = () => innerWidth < 980 ? 0 : LEDE;

/* =====================================================================
   materials
   ===================================================================== */
const cache = new Map(), matCache = new Map();
function clayMat(hex, vc) {
  const k = 'c' + hex + vc;
  if (!matCache.has(k)) {
    const m = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(hex), roughness: 0.87, metalness: 0, specularIntensity: 0.32,
      vertexColors: vc, map: TEX.albedo, roughnessMap: TEX.rough, normalMap: TEX.normal});
    m.normalScale.set(0.6, 0.6);
    matCache.set(k, m);
  }
  return matCache.get(k);
}
function metalMat(hex, rough) {
  const k = 'm' + hex + rough;
  if (!matCache.has(k)) {
    matCache.set(k, new THREE.MeshStandardMaterial({
      color: new THREE.Color(hex), roughness: rough, metalness: 0.9}));
  }
  return matCache.get(k);
}
const MAT_GHOST = new THREE.MeshStandardMaterial({
  color: new THREE.Color('#b9ab97'), roughness: 0.95, transparent: true, opacity: 0.16,
  depthWrite: false});
const MAT_DIM = new THREE.MeshStandardMaterial({color: new THREE.Color('#d5cfc2'), roughness: 0.96});

/* =====================================================================
   loading
   ===================================================================== */
const loadEl = $('#load'), barI = $('#bar2i'), stage = $('#model'), still = $('#still');
const loader = new GLTFLoader();

function load(idx) {
  if (cache.has(idx)) return cache.get(idx);
  const p = loader.loadAsync(`models/board_${idx}.glb`, e => {
    if (e.lengthComputable) barI.style.width = (e.loaded / e.total * 100) + '%';
  }).then(g => prep(g.scene, idx));
  cache.set(idx, p);
  return p;
}

function prep(root, idx) {
  const b = byIdx[idx];
  const codes = new Set(b.clips.map(c => c.code));
  const slips = [], clips = [];
  const backing = [];
  let mortar = null;
  root.traverse(o => {
    if (!o.isMesh) return;
    const n = o.name.replace(/^CLIP_/, '').replace(/\.\d+$/, '');
    const m = /^T(\d+)_/.exec(o.name);
    if (m) { o.userData = {kind: 'slip', ti: +m[1] - 1}; slips.push(o); }
    else if (codes.has(n) || /^(RC-|PK-)/.test(n)) { o.userData = {kind: 'clip', code: n}; clips.push(o); }
    // the mortar has to be picked off before the fall-through, or it lands in `backing` and the
    // two fight over one slot: whichever the traverse reached last would be the only one drawn
    else if (n === 'MORTAR') { o.userData = {kind: 'mortar'}; mortar = o; }
    // a LIST, not one mesh. The backing carries two materials - the setting-out on the face
    // the slips sit on, plain board everywhere else - and glTF splits a mesh with two materials
    // into two primitives, which arrive here as two meshes. Keeping only the last one left the
    // other permanently visible when the board layer was switched off.
    else { o.userData = {kind: 'board'}; backing.push(o); }
  });
  root.rotation.x = MODEL_TILT;
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  const centre = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const corners = [];
  for (const x of [box.min.x, box.max.x])
    for (const y of [box.min.y, box.max.y])
      for (const z of [box.min.z, box.max.z]) corners.push(new THREE.Vector3(x, y, z));
  return {root, slips, clips, backing, mortar, centre, corners, span: Math.max(size.x, size.y)};
}

/* =====================================================================
   framing

   The lede owns a band down the left on a wide stage.  The board is kept clear of it with
   camera.setViewOffset, which shifts the frustum and leaves the orbit centre on the board.  An
   earlier version slid controls.target sideways instead, so the model swung about a point off
   its own face and dragging felt wrong.
   ===================================================================== */
function dirOf(k) {
  const [a, u, s] = VIEWS[k].v;
  return new THREE.Vector3().addScaledVector(OUT, a).addScaledVector(UP, u)
    .addScaledVector(SIDE, s).normalize();
}
function applyOffset() {
  const f = lede_f(), w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  if (!f) camera.clearViewOffset();
  else camera.setViewOffset(w, h, -f * w / 2, 0, w, h);
}
function allowed(k) {
  const f = lede_f(), cw = canvas.clientWidth, ch = canvas.clientHeight;
  if (!VIEWS[k].still) return [1 - f, 1];
  const iw = still.naturalWidth || 3, ih = still.naturalHeight || 2;
  const s = Math.min(cw * (1 - f) / iw, ch / ih);
  return [iw * s / cw, ih * s / ch];
}
function fitR(dir, k) {
  const [ax, ay] = allowed(k);
  const f = lede_f();
  let R = cur.span * 3;
  for (let i = 0; i < 10; i++) {
    camera.position.copy(cur.centre).addScaledVector(dir, R);
    camera.lookAt(cur.centre);
    camera.updateMatrixWorld(true); camera.updateProjectionMatrix();
    camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    let m = 0;
    for (const p of cur.corners) {
      const v = p.clone().project(camera);
      // the view offset already shifts x, so measure the board against the band it sits in
      m = Math.max(m, Math.abs(v.x - f) / ax, Math.abs(v.y) / ay);
    }
    if (Math.abs(m - 1) < 0.002) break;
    R *= Math.max(0.25, m);
  }
  return R;
}
let anim = null;
const ease = k => k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
function goto(k, ms = 850) {
  applyOffset();
  const dir = dirOf(k);
  const target = cur.centre.clone().addScaledVector(dir, fitR(dir, k) * VIEWS[k].z);
  if (!ms) {
    camera.position.copy(target); controls.target.copy(cur.centre); controls.update();
    return;
  }
  const p0 = camera.position.clone(), t0 = controls.target.clone(), t1 = performance.now() + ms;
  anim = () => {
    const e = ease(Math.max(0, Math.min(1, 1 - (t1 - performance.now()) / ms)));
    camera.position.lerpVectors(p0, target, e);
    controls.target.lerpVectors(t0, cur.centre, e);
    if (e >= 1) anim = null;
  };
}

/* =====================================================================
   state
   ===================================================================== */
let cur = null, board = null;
let mode = 'real', isolate = null, explode = 0, exWant = 0, live = false;
// The view, the colour mode and the layer chips belong to the reader, not to the board.  They
// survived a board change already; what did not was the picture: show() dropped back to the
// still, and the still is always the plain hero render, so somebody who had asked for clips
// only was handed a picture of slips and reasonably concluded the setting had been lost.
let view = 'hero', engaged = false, isoClip = null;
// mortar on by default: the board as it is actually finished.  Turning it off is the way to
// look at the bare brickwork and at the clips behind it.
const layer = {slips: true, clips: true, mortar: true, board: true};

function paint() {
  if (!cur) return;
  const col = board.colour;
  for (const o of cur.slips) {
    const ty = board.types[o.userData.ti] || {};
    const dim = isolate !== null && o.userData.ti !== isolate;
    if (mode === 'clip') o.material = MAT_GHOST;
    else if (dim) o.material = MAT_DIM;
    else if (mode === 'type') o.material = clayMat(ty.colour || '#b0aca4', true);
    else o.material = clayMat(ty.kind === 'CUT' ? col.dark : col.brick, true);
    o.visible = layer.slips;
  }
  for (const o of cur.clips) {
    const c = o.userData.code;
    const dimc = isoClip !== null && c !== isoClip;
    o.material = dimc ? MAT_DIM
      : (mode === 'clip' || mode === 'type')
        ? metalMat(CLIP_COL(c), 0.45)
        : metalMat(c === 'R50' ? '#8b939c' : '#bd7048', c === 'R50' ? 0.42 : 0.36);
    o.visible = layer.clips;
  }
  if (cur.mortar) {
    cur.mortar.material = clayMat(col.mortar, false);
    cur.mortar.visible = layer.mortar;
  }
  // The backing keeps the materials that came in the GLB. They carry the setting-out texture -
  // every slip's outline, its clip's tray, the fixing holes and a code inside each - and replacing
  // them with a plain clay colour, which is what used to happen here, wiped all of that the moment
  // the board was drawn.
  for (const o of cur.backing) o.visible = layer.board;
}
const OUT_LOCAL = new THREE.Vector3(0, 1, 0);   // the face normal inside the untilted model
function applyExplode() {
  for (const o of cur.slips) {
    const home = o.userData.home || (o.userData.home = o.position.clone());
    o.position.copy(home).addScaledVector(OUT_LOCAL, explode);
  }
}

/* =====================================================================
   board switching
   ===================================================================== */
async function show(idx, first) {
  board = byIdx[idx];
  $$('.bcard').forEach(p => p.classList.toggle('on', +p.dataset.i === idx));
  still.src = `renders/b${idx}_hero.webp`;
  if (!engaged) { stage.classList.remove('live'); live = false; }
  isolate = null; isoClip = null; exWant = 0; explode = 0;
  $('#ex').value = 0; $('#exv').textContent = '0 mm';
  $('#insp').classList.remove('show');
  $$('#views button').forEach(x => x.classList.toggle('on', x.dataset.v === view));
  lede(); sections();
  if (location.hash !== '#b' + idx) history.replaceState(null, '', '#b' + idx);

  // Without a context there is nothing to put the model in, so the megabytes are not fetched
  // either: the stage keeps the still render of this board and the rest of the page carries on.
  if (!GL) { loadEl.classList.add('gone'); return; }

  if (!first) loadEl.classList.remove('gone');
  barI.style.width = cache.has(idx) ? '100%' : '0%';
  const m = await load(idx);
  if (board.idx !== idx) return;
  if (cur) scene.remove(cur.root);
  cur = m;
  scene.add(cur.root);
  controls.minDistance = cur.span * 0.16;
  controls.maxDistance = cur.span * 6;
  for (const o of cur.slips) o.userData.home = null;
  applyExplode(); paint(); resize();
  lastLede = lede_f();
  goto(view, 0);
  loadEl.classList.add('gone');
}

function goLive() { if (!live && GL) { live = true; stage.classList.add('live'); } }
['pointerdown', 'wheel', 'touchstart'].forEach(e =>
  stage.addEventListener(e, goLive, {passive: true}));

/* =====================================================================
   lede
   ===================================================================== */
function lede() {
  const b = board;
  $('#bno').textContent = String(b.idx).padStart(2, '0');
  $('#bof').textContent = t('of');
  const zh = b.zh, en = b.en;
  const s = lang === 'zh' ? zh : en;
  const br = lang === 'zh' ? s.indexOf('，') : s.indexOf(',');
  $('#btitle').innerHTML = br < 0 ? s : `${s.slice(0, br)}<br><em>${s.slice(br + 1).trim()}</em>`;
  $('#bsub').textContent =
    `${b.use === 'Wall' ? t('wall') : t('floor')} · ${b.finish === 'Raw' ? t('raw') : t('sleek')}`;
  const nClip = b.clips.reduce((s2, c) => s2 + c.qty, 0);
  $('#bstats').innerHTML = [
    [`${b.w} × ${b.h}`, t('st_size')],
    [b.pieces.length, t('st_slips')],
    [b.types.length, t('st_types')],
    [`${nClip}`, t('st_clips')],
    [b.clips.length, t('st_ctypes')]
  ].map(([a, c]) => `<div class="stat"><b data-to="${a}">${a}</b><span>${c}</span></div>`).join('');
  $$('#bstats .stat b').forEach(el => countUp(el, el.dataset.to));
  $('#foot2').textContent = t('foot2')(b);
}

/* =====================================================================
   brick glyphs
   ===================================================================== */
function outlineOf(ti) { return outlineIn(board, ti); }
function outlineIn(bd, ti) {
  const pc = bd.pieces.find(p => p.t === ti);
  if (!pc) return null;
  const q = pc.p, n = q.length;
  let bi = 0, bl = -1;
  for (let i = 0; i < n; i++) {
    const d = (q[(i + 1) % n][0] - q[i][0]) ** 2 + (q[(i + 1) % n][1] - q[i][1]) ** 2;
    if (d > bl) { bl = d; bi = i; }
  }
  const th = -Math.atan2(q[(bi + 1) % n][1] - q[bi][1], q[(bi + 1) % n][0] - q[bi][0]);
  const c = Math.cos(th), s = Math.sin(th);
  const r = q.map(p => [p[0] * c - p[1] * s, p[0] * s + p[1] * c]);
  const mx = Math.min(...r.map(p => p[0])), my = Math.min(...r.map(p => p[1]));
  return r.map(p => [p[0] - mx, p[1] - my]);
}
function glyph(pts, fill) {
  const w = 104, h = 36, GS = 88 / SLIP[0];
  const oy = h / 2 + SLIP[1] * GS / 2, ox = (w - SLIP[0] * GS) / 2;
  const d = pts.map(p => `${(ox + p[0] * GS).toFixed(1)},${(oy - p[1] * GS).toFixed(1)}`).join(' ');
  return `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true">
    <rect x="${ox}" y="${(oy - SLIP[1] * GS).toFixed(1)}" width="${(SLIP[0] * GS).toFixed(1)}"
      height="${(SLIP[1] * GS).toFixed(1)}" fill="none" stroke="${LINE}" stroke-width=".75"
      stroke-dasharray="3 2"/>
    <polygon points="${d}" fill="${fill}" fill-opacity=".85" stroke="${INK}" stroke-width="1"/></svg>`;
}

/* =====================================================================
   clip views: plan, section, developed blank

   lipped[i] is the edge poly[i-1] -> poly[i], the convention clips9_build writes and every
   drawing reads.  The blank is the tray plus a leg+lip flap turned out along each lipped RUN,
   with the fold line at the leg; on the rail that comes to 10+15+68+15+10 = 118 across, which is
   the figure on the DXF.  The earlier version drew the plan again in dashed line and called it a
   blank, which showed nothing.

   A run is not always the whole edge.  Where two lipped edges meet, both returns fold inward and
   collide in the corner, so PK-8T02 - three lipped edges on one triangle - carries a tab_w tab at
   the middle of each edge instead of a full lip.  lipRuns is the same rule as clips9.lip_runs,
   and the plan, the blank and the 3D model all read it, so none of them can disagree about where
   the metal is.
   ===================================================================== */
function lipRuns(a, b, lipped, tab, tabW) {
  if (!lipped) return [];
  const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
  if (!tab || L <= tabW) return [[0, L]];
  return [[(L - tabW) / 2, (L + tabW) / 2]];
}

function edgePts(a, b, t0, t1) {
  const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const ux = (b[0] - a[0]) / L, uy = (b[1] - a[1]) / L;
  return [[a[0] + ux * t0, a[1] + uy * t0], [a[0] + ux * t1, a[1] + uy * t1]];
}

/* A rail 1000 long and 68 across, scaled to fit a card, is a seven-pixel hairline: the plan and the
   blank are drawn but there is nothing in them to see, which is why the long clip's card read as a
   note with no drawing under it.  Anything longer than six times its own width is therefore drawn
   BROKEN - KEEP mm off each end at a scale that can be read, the identical middle left out between
   two break lines, which is what any drawing of a long section does.  KEEP is 210 so both end
   holes and one full 125 pitch fall inside the kept part.

   breakParts returns the same {base, lipped, tabs, holes} shape the whole-part path uses, so the
   plan and the blank draw one part or two without knowing which case they are in. */
const BRK_KEEP = 210, BRK_GAP = 60;

function breakParts(g) {
  const W = g.bw, H = g.bh, shift = W - (2 * BRK_KEEP + BRK_GAP);
  const rect = (x0, x1) => [[x0, 0], [x1, 0], [x1, H], [x0, H]];
  // lipped[i] is the edge poly[i-1] -> poly[i]: the two long edges carry the legs, the two ends
  // and the two cut faces at the break do not
  const lip = [false, true, false, true];
  return [
    {base: rect(0, BRK_KEEP), lipped: lip, tabs: [],
     holes: g.holes.filter(h => h[0] <= BRK_KEEP + 0.01), cut: [false, false, true, false]},
    {base: rect(BRK_KEEP + BRK_GAP, 2 * BRK_KEEP + BRK_GAP), lipped: lip, tabs: [],
     holes: g.holes.filter(h => h[0] >= W - BRK_KEEP - 0.01).map(h => [h[0] - shift, h[1]]),
     cut: [true, false, false, false]},
  ];
}

function clipViews(code) {
  const g = clipgeo[code];
  if (!g) return '';
  const col = CLIP_COL(code);
  const pad = 7;
  const tabW = g.tab_w || P.tab_w;
  const brk = g.bw > 6 * g.bh;
  const parts = brk ? breakParts(g)
    : [{base: g.base, lipped: g.lipped, tabs: g.tabs || [], holes: g.holes, cut: []}];
  const VW = brk ? 2 * BRK_KEEP + BRK_GAP : g.bw;      // the width actually drawn
  const runsOf = (p, i) => lipRuns(p.base[(i - 1 + p.base.length) % p.base.length], p.base[i],
                                   p.lipped[i], p.tabs[i], tabW);

  const pts = (p, S, ox, oy, H) =>
    p.map(q => `${(ox + q[0] * S).toFixed(1)},${(oy + (H - q[1]) * S).toFixed(1)}`).join(' ');

  // ---- plan.  The fold marks used to be bare lines lying on the tray edge, which says where the
  // metal is but nothing about which way it goes; the client read the card as folding outward.
  // Each run now also carries the hook tip, drawn tip_in INSIDE the tray, and a hatch joining the
  // two - the plan of the metal that stands over the slip.  This is what the DXF top view shows.
  const S1 = 108 / Math.max(VW, g.bh);
  // 26, not 20.  The value sits below the dimension line and a 9 px glyph has a descender: at
  // 20 the whole row of figures hung past the bottom of the viewBox and was clipped away.
  const dimH = brk ? 26 : 0;
  const vb1 = `0 0 ${(VW * S1 + pad * 2).toFixed(1)} ${(g.bh * S1 + pad * 2 + dimH).toFixed(1)}`;
  const M1 = q => `${(pad + q[0] * S1).toFixed(1)},${(pad + (g.bh - q[1]) * S1).toFixed(1)}`;
  const body1 = parts.map(part => {
    const m = part.base.length;
    const lips = part.base.map((q, i) => {
      const a = part.base[(i - 1 + m) % m];
      const dx = q[0] - a[0], dy = q[1] - a[1], L = Math.hypot(dx, dy) || 1;
      const ix = -dy / L, iy = dx / L;                   // inward normal of a CCW tray
      return runsOf(part, i).map(([t0, t1]) => {
        const [p0, p1] = edgePts(a, q, t0, t1);
        const k0 = [p0[0] + ix * P.tip_in, p0[1] + iy * P.tip_in];
        const k1 = [p1[0] + ix * P.tip_in, p1[1] + iy * P.tip_in];
        return `<polygon points="${[p0, p1, k1, k0].map(M1).join(' ')}" fill="${col}"
          fill-opacity=".28" stroke="none"/>
        <line x1="${M1(p0).split(',')[0]}" y1="${M1(p0).split(',')[1]}"
          x2="${M1(p1).split(',')[0]}" y2="${M1(p1).split(',')[1]}"
          stroke="${col}" stroke-width="3.2" stroke-linecap="butt"/>
        <line x1="${M1(k0).split(',')[0]}" y1="${M1(k0).split(',')[1]}"
          x2="${M1(k1).split(',')[0]}" y2="${M1(k1).split(',')[1]}"
          stroke="${col}" stroke-width="1.1" stroke-dasharray="3 2"/>`;
      }).join('');
    }).join('');
    const holes = part.holes.map(h => `<circle cx="${(pad + h[0] * S1).toFixed(1)}"
      cy="${(pad + (g.bh - h[1]) * S1).toFixed(1)}" r="${Math.max(1.6, P.hole / 2 * S1).toFixed(1)}"
      fill="#fff" stroke="${MUT}" stroke-width=".9"/>`).join('');
    // the face at a break is not an end of the part, so it is drawn as a break line, not an edge
    const cutX = part.cut.map((c, i) => c ? part.base[i][0] : null).filter(v => v !== null);
    const zig = cutX.map(x => {
      const X = pad + x * S1, y0 = pad, y1 = pad + g.bh * S1, k = (y1 - y0) / 6;
      const w = 3.4;
      let d = `M${X.toFixed(1)},${y0.toFixed(1)}`;
      for (let j = 1; j <= 6; j++) {
        d += ` L${(X + (j % 2 ? w : -w)).toFixed(1)},${(y0 + k * (j - 0.5)).toFixed(1)}`;
      }
      return `<path d="${d} L${X.toFixed(1)},${y1.toFixed(1)}" fill="none" stroke="${INK}"
        stroke-width="1.1"/>`;
    }).join('');
    return `<polygon points="${pts(part.base, S1, pad, pad, g.bh)}" fill="#efece6"
      stroke="${INK}" stroke-width="1.1"/>${lips}${holes}${zig}`;
  }).join('');
  // On a broken view the drawn length is not the real one, so the real one is dimensioned: the end
  // margin, one pitch, and the overall figure across the break.
  let dims1 = '';
  if (brk) {
    const yd = pad + g.bh * S1 + 12, h0 = g.holes[0][0], h1 = g.holes[1][0];
    const tick = x => `<line x1="${(pad + x * S1).toFixed(1)}" y1="${(yd - 4).toFixed(1)}"
      x2="${(pad + x * S1).toFixed(1)}" y2="${(yd + 4).toFixed(1)}" stroke="${MUT}"
      stroke-width=".8"/>`;
    const lab = (x, s) => `<text x="${(pad + x * S1).toFixed(1)}" y="${(yd + 11).toFixed(1)}"
      font-size="9" text-anchor="middle" fill="${MUT}">${s}</text>`;
    dims1 = `<line x1="${pad}" y1="${yd.toFixed(1)}" x2="${(pad + VW * S1).toFixed(1)}"
      y2="${yd.toFixed(1)}" stroke="${MUT}" stroke-width=".8"/>
      ${tick(0)}${tick(h0)}${tick(h1)}${tick(VW)}
      ${lab(h0 / 2, Math.round(h0))}${lab((h0 + h1) / 2, Math.round(h1 - h0))}
      ${lab((h1 + VW) / 2, Math.round(g.bw))}`;
  }
  const plan = `<svg viewBox="${vb1}">${body1}${dims1}</svg>`;

  // ---- section, drawn in its own frame so the 20 deep slip is not clipped off the top
  const F = P.flat, LG = P.leg, TI = P.tip_in, TU = P.tip_up, ST = SLIP[2];
  const topY = Math.max(LG, ST) + 6, s2 = 108 / F;
  const w2 = F * s2 + pad * 2, h2 = topY * s2 + pad * 2;
  const my = y => (pad + (topY - y) * s2).toFixed(1);
  const mx = x => (pad + x * s2).toFixed(1);
  // A pocket has no 68 flat and no mouth - it follows the piece, so its width is whatever the plan
  // shows and changes edge to edge.  Drawing the rail's M profile on a pocket card described a
  // part that does not exist.  What the two share is the edge, so a pocket gets one leg and its
  // return lip, with the slip against it, and an arrow on the lip so the direction is not left to
  // be inferred: the tip comes back over the slip, and that interference is the whole retention.
  // by kind, not by code: the long clip is the same M profile as R50 and only its length differs,
  // and testing for 'R50' drew it with the pocket's half section - a part that does not exist
  const isRail = g.kind === 'RAIL';
  const prof = isRail
    ? [[TI, TU], [0, LG], [0, 0], [F, 0], [F, LG], [F - TI, TU]]
    : [[TI, TU], [0, LG], [0, 0], [F / 2, 0]];
  const sx = isRail ? (F - SLIP[1]) / 2 : LEGOUT;
  const sw = isRail ? SLIP[1] : F / 2 - LEGOUT;
  const sect = `<svg viewBox="0 0 ${w2.toFixed(1)} ${h2.toFixed(1)}">
    <defs><marker id="ah${code.replace(/\W/g, '')}" viewBox="0 0 8 8" refX="7" refY="4"
      markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L8 4 L0 8 z"
      fill="${col}"/></marker></defs>
    <rect x="${mx(sx)}" y="${my(ST)}" width="${(sw * s2).toFixed(1)}"
      height="${(ST * s2).toFixed(1)}" fill="#c09070" fill-opacity=".5" stroke="${INK}"
      stroke-width=".7"/>
    <polyline points="${prof.map(q => `${mx(q[0])},${my(q[1])}`).join(' ')}" fill="none"
      stroke="${col}" stroke-width="2.4" stroke-linejoin="miter"/>
    <line x1="${mx(0)}" y1="${my(LG + 5.5)}" x2="${mx(TI + 2.6)}" y2="${my(LG + 5.5)}"
      stroke="${col}" stroke-width="1.1" marker-end="url(#ah${code.replace(/\W/g, '')})"/>
    ${isRail ? `<line x1="${mx(F)}" y1="${my(LG + 5.5)}" x2="${mx(F - TI - 2.6)}"
      y2="${my(LG + 5.5)}" stroke="${col}" stroke-width="1.1"
      marker-end="url(#ah${code.replace(/\W/g, '')})"/>` : ''}</svg>`;

  // ---- developed blank: tray plus a flap on every lipped run
  const fl = LG + P.lip;
  const flaps = [];
  let bx0 = 0, by0 = 0, bx1 = VW, by1 = g.bh;
  for (const part of parts) {
    const m = part.base.length;
    for (let i = 0; i < m; i++) {
      const a = part.base[(i - 1 + m) % m], b = part.base[i];
      const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
      const nx = dy / L, ny = -dx / L;                  // outward normal of a CCW tray
      for (const [t0, t1] of runsOf(part, i)) {
        const [p0, p1] = edgePts(a, b, t0, t1);
        const q = [p0, p1, [p1[0] + nx * fl, p1[1] + ny * fl], [p0[0] + nx * fl, p0[1] + ny * fl]];
        const fold = [[p0[0] + nx * LG, p0[1] + ny * LG], [p1[0] + nx * LG, p1[1] + ny * LG]];
        flaps.push({q, fold});
        for (const p of q) {
          bx0 = Math.min(bx0, p[0]); by0 = Math.min(by0, p[1]);
          bx1 = Math.max(bx1, p[0]); by1 = Math.max(by1, p[1]);
        }
      }
    }
  }
  const bw = bx1 - bx0, bh = by1 - by0;
  const S3 = 108 / Math.max(bw, bh);
  const ox3 = pad - bx0 * S3, oy3 = pad + by1 * S3;
  const mp = q => `${(ox3 + q[0] * S3).toFixed(1)},${(oy3 - q[1] * S3).toFixed(1)}`;
  // An unfolded flap drawn outside the tray, unlabelled, reads as a flap that folds outward - and
  // that is exactly how this card was read.  Each flap now carries an arrow back toward the tray.
  const aid = 'fa' + code.replace(/\W/g, '');
  const arrows = flaps.map(f => {
    const m = [(f.q[0][0] + f.q[1][0]) / 2, (f.q[0][1] + f.q[1][1]) / 2];
    const v = [f.q[3][0] - f.q[0][0], f.q[3][1] - f.q[0][1]];
    const a = [m[0] + v[0] * 0.9, m[1] + v[1] * 0.9], b = [m[0] + v[0] * 0.18, m[1] + v[1] * 0.18];
    return `<line x1="${mp(a).split(',')[0]}" y1="${mp(a).split(',')[1]}"
      x2="${mp(b).split(',')[0]}" y2="${mp(b).split(',')[1]}" stroke="${col}" stroke-width="1.3"
      marker-end="url(#${aid})"/>`;
  }).join('');
  const blank = `<svg viewBox="0 0 ${(bw * S3 + pad * 2).toFixed(1)} ${(bh * S3 + pad * 2).toFixed(1)}">
    <defs><marker id="${aid}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="4.5"
      markerHeight="4.5" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="${col}"/></marker></defs>
    ${flaps.map(f => `<polygon points="${f.q.map(mp).join(' ')}" fill="#f6efe9"
      stroke="${MUT}" stroke-width="1"/>`).join('')}
    ${parts.map(part => `<polygon points="${part.base.map(mp).join(' ')}" fill="#efece6"
      stroke="${INK}" stroke-width="1.1"/>`).join('')}
    ${flaps.map(f => `<line x1="${mp(f.fold[0]).split(',')[0]}" y1="${mp(f.fold[0]).split(',')[1]}"
      x2="${mp(f.fold[1]).split(',')[0]}" y2="${mp(f.fold[1]).split(',')[1]}"
      stroke="${col}" stroke-width=".9" stroke-dasharray="4 2.5"/>`).join('')}
    ${arrows}
    ${parts.flatMap(part => part.holes).map(h => `<circle cx="${mp(h).split(',')[0]}"
      cy="${mp(h).split(',')[1]}" r="${Math.max(1.5, P.hole / 2 * S3).toFixed(1)}" fill="#fff"
      stroke="${MUT}" stroke-width=".9"/>`).join('')}</svg>`;

  const tabs = g.tabs || [];
  const across = isRail ? `${P.lip}+${P.leg}+${P.flat}+${P.leg}+${P.lip} = ${(P.flat + 2 * (P.leg + P.lip)).toFixed(0)}`
    : `${Math.round(bw)} × ${Math.round(bh)}`;
  const nfull = g.lipped.filter((v, i) => v && !tabs[i]).length;
  const ntab = g.lipped.filter((v, i) => v && tabs[i]).length;
  return `<div class="cviews">
    <div class="cview">${plan}<h5>${t('v_plan')}</h5>
      <i>${brk ? t('cap_brk') : t('cap_plan')}</i></div>
    <div class="cview">${sect}<h5>${t('v_sect')}</h5><i>${t('cap_sect')}</i></div>
    <div class="cview">${blank}<h5>${t('v_blank')}</h5>
      <i>${brk ? t('cap_brk') : t('cap_blank')}</i></div>
  </div><p class="cdim">${t('fold_note')(nfull, ntab, tabW)}<br>${t('blank_note')(across)}${
    brk ? `<br>${t('brk_note')(g.bw, g.holes.length, P.hole)}` : ''}</p>`;
}

/* =====================================================================
   sections
   ===================================================================== */
/* type.desc in boards.json carries both languages on one line, which is what the DXF and the
   printed schedule want - one row, two readers.  On the page it made the English table read half
   in Chinese, so the description is built here from the same fields in whichever language is on. */
function kindOf(ty) {
  return ty.kind === 'CUT' ? t('k_cut') : ty.kind === 'STD' ? t('k_std') : t('k_whole');
}

function describe(ty) {
  if (ty.kind === 'CUT') {
    return t('d_cut')(ty.nsides, ty.label, ty.dims[0], ty.dims[1]);
  }
  return (ty.kind === 'STD' ? t('d_std') : t('d_whole'))(ty.label);
}

function sections() {
  const b = board;
  $('#brickrows').innerHTML = b.types.map((ty, i) => {
    const o = outlineOf(i);
    return `<tr data-t="${i}">
      <td class="gly">${o ? glyph(o, ty.colour) : ''}</td>
      <td class="tid"><span class="swatch" style="background:${ty.colour}"></span>${ty.code}</td>
      <td class="kind">${kindOf(ty)}</td>
      <td class="num">${ty.dims[0]} × ${ty.dims[1]}</td>
      <td class="num">${ty.area.toLocaleString()}</td>
      <td class="qty">${ty.qty}</td>
      <td class="ds">${describe(ty)}</td>
    </tr>`;
  }).join('');
  $$('#brickrows tr').forEach(el => el.onclick = () => {
    const i = +el.dataset.t;
    isolate = isolate === i ? null : i;
    $$('#brickrows tr').forEach(x => x.classList.toggle('sel', +x.dataset.t === isolate));
    if (isolate !== null) {
      goLive();
      if (mode === 'clip') setMode('real');
      $('#model').scrollIntoView({behavior: 'smooth'});
    }
    paint();
  });
  const nCut = b.types.filter(x => x.kind === 'CUT').reduce((s, x) => s + x.qty, 0);
  $('#bricknote').textContent = nCut ? t('note_cut')(nCut) : t('note_nocut');

  $('#clipcards').innerHTML = b.clips.map(c => `
    <div class="clipcard" data-c="${c.code}">
      <header><b>${c.code}</b>
        <span class="tag" style="color:${CLIP_COL(c.code)}">${lang === 'zh' ? c.zh : c.en}</span>
        <span class="q">× ${c.qty}</span></header>
      ${clipViews(c.code)}
      <div class="cnote">${lang === 'zh' ? c.note_zh : c.note_en}</div>
    </div>`).join('');
  $$('#clipcards .clipcard').forEach(el => el.onclick = () => {
    const code = el.dataset.c;
    const sel = isoClip === code ? null : code;
    isoClip = sel;
    $$('#clipcards .clipcard').forEach(x => x.classList.toggle('sel', x.dataset.c === sel));
    engaged = true;
    goLive();
    if (sel) {
      setMode('clip');
      // the mortar is solid and fills the joint to the backing, so it has to come off too or
      // the clip the reader just asked to see is buried in it
      layer.slips = false; layer.clips = true; layer.mortar = false; layer.board = true;
      syncChips();
      if (view === 'hero' || view === 'front') { view = 'exp'; }
      $$('#views button').forEach(x => x.classList.toggle('on', x.dataset.v === view));
      goto(view);
    }
    paint();
    $('#model').scrollIntoView({behavior: 'smooth', block: 'start'});
  });

  $('#shotgrid').innerHTML = [
    ['front', t('sh_front'), t('sh_front_s')],
    ['hero', t('sh_hero'), t('sh_hero_s')],
    ['detail', t('sh_detail'), t('sh_detail_s')]
  ].map(([tag, ti, s]) => `
    <figure class="plate" data-lb="renders/b${b.idx}_${tag}.png">
      <img src="renders/b${b.idx}_${tag}.webp" alt="${ti}" loading="lazy">
      <figcaption class="pcap"><b>${ti}</b><span>${s}</span></figcaption>
    </figure>`).join('');
  bindLb();
  summary();
  files();
  watchRise();
}

/* =====================================================================
   all-board summary

   The one table somebody ordering material can work from.  It cannot sum the per-board schedules by
   code, because T-codes restart on every board: board 3's T04 and board 8's T04 are different cut
   shapes that happen to share a number.  data/boards.json therefore carries a `summary` block built
   by site_export.py, which groups types on size using the same key panels9_types uses, so a type is
   one row here however many boards lay it and however they number it.
   ===================================================================== */
let spare = false;
const withSpare = n => Math.ceil(n * 1.15);

function sumGlyph(e) {
  const u = e.use[0], bd = byIdx[u.board];
  if (!bd) return '';
  const ti = bd.types.findIndex(t => t.code === u.code);
  if (ti < 0) return '';
  const o = outlineIn(bd, ti);
  return o ? glyph(o, bd.types[ti].colour) : '';
}

function prodNote() {
  const P = (D.summary || {}).products || [];
  if (!P.length) return '';
  const f = x => spare ? `${x.product} ${x.spare}` : `${x.product} ${x.qty}`;
  const zh = lang === 'zh';
  return (zh ? '　按砖类型：' : '  By product: ') + P.map(f).join(zh ? '，' : ', ') + (zh ? '。' : '.');
}

function longNote() {
  // The one searched length is gone: the shop works to a stock family, so a continuous run is
  // made up of several of these end to end.  Each carries its own hole positions, taken from the
  // supplier's drawing, so there is no one pitch to quote.
  const R = (D.summary || {}).rails || [];
  if (!R.length) return '';
  const g = D.summary.rail_gap, e = D.summary.rail_end_max;
  const list = R.map(r => `${r.code} ${r.length} × ${r.qty}`).join(lang === 'zh' ? '，' : ', ');
  return lang === 'zh'
    ? `　整排导轨：${list}；相邻两根间隔 ${g}，每排两端最多空出 ${e}。`
    : `  Rails on a run: ${list}; ${g} apart, at most ${e} left open at each end of a run.`;
}

/* ---------------------------------------------------------------------
   Grouping.  The catalogue is one set of numbers and three ways of reading it: by what is made
   (shape, or clip type), by what is ordered (product), and by what is delivered to a board.
   Nothing is recounted between them - each view sums the same cells - so the foot total is
   identical in all three, and assertGroups() says so out loud in the console if it ever is not.

   THE ORDERING CELL IS (type, product).  Spare is 15 % rounded UP, and rounding has to happen
   somewhere definite: round per shape and the split by product orders fractions of a brick, round
   per board and the same brick is rounded up nine times over.  A product is what a purchase order
   line is, so that is the cell.  Which is why the board view cannot carry a spare figure: a board
   is a slice of a cell, not a cell, and 15 % of a slice is not ordered from anybody.  The toggle
   is disabled there rather than shown with a number nobody would place an order against.
   --------------------------------------------------------------------- */
let bgroup = 'shape', cgroup = 'type';
const PRODOF = {};
boards.forEach(b => { PRODOF[b.idx] = b.product; });
const PRODS = () => ((D.summary || {}).products || []).map(x => x.product);

// clips broken to the same (code, product) cell the bricks already use
function clipCells(e) {
  const per = {};
  (e.use || []).forEach(u => {
    const p = PRODOF[u.board] || '';
    per[p] = (per[p] || 0) + u.qty;
  });
  return Object.keys(per).sort().map(p => ({product: p, qty: per[p], spare: withSpare(per[p])}));
}

function brickGroups() {
  const S = D.summary, q = e => spare ? e.spare : e.qty;
  const row = (e, qty, prod, used) => ({
    html: `<td class="gly">${sumGlyph(e)}</td><td class="tid">${e.code}</td>
      <td class="kind">${kindOf(e)}</td><td class="num">${e.dims[0]} × ${e.dims[1]}</td>
      <td class="ds">${prod}</td><td class="qty">${qty}</td><td class="ds">${used}</td>`,
    qty,
  });
  if (bgroup === 'shape') {
    return [{rows: S.bricks.map(e => row(e, q(e),
      (e.products || []).map(x => x.product).join('　'),
      e.use.map(u => `${u.board}·${u.code}`).join('　')))}];
  }
  if (bgroup === 'product') {
    return PRODS().map(p => ({
      label: p,
      rows: S.bricks.filter(e => (e.products || []).some(x => x.product === p)).map(e => {
        const c = e.products.find(x => x.product === p);
        return row(e, spare ? c.spare : c.qty, p,
                   e.use.filter(u => PRODOF[u.board] === p)
                        .map(u => `${u.board}·${u.code}`).join('　'));
      }),
    }));
  }
  return boards.map(b => ({
    label: `${t('g_board_l')} ${b.idx}　${b.product}`,
    rows: S.bricks.filter(e => e.use.some(u => u.board === b.idx)).map(e => {
      const u = e.use.find(x => x.board === b.idx);
      return row(e, u.qty, b.product, `${b.idx}·${u.code}`);
    }),
  }));
}

function clipGroups() {
  const S = D.summary;
  const desc = e => `${lang === 'zh' ? e.zh : e.en}${
    e.length ? ` · ${e.length} mm · ${e.holes}×⌀3.5 @${e.pitch}` : ''}`;
  const row = (e, qty, used) => ({
    html: `<td class="tid">${e.code}</td><td class="kind">${desc(e)}</td>
      <td class="qty">${qty}</td><td class="ds">${used}</td>`,
    qty,
  });
  if (cgroup === 'type') {
    return [{rows: S.clips.map(e => {
      const cells = clipCells(e);
      return row(e, spare ? cells.reduce((s, c) => s + c.spare, 0) : e.qty,
                 e.use.map(u => u.board).join('　'));
    })}];
  }
  if (cgroup === 'product') {
    return PRODS().map(p => ({
      label: p,
      rows: S.clips.map(e => [e, clipCells(e).find(c => c.product === p)])
        .filter(([, c]) => c)
        .map(([e, c]) => row(e, spare ? c.spare : c.qty,
                             e.use.filter(u => PRODOF[u.board] === p)
                                  .map(u => u.board).join('　'))),
    })).filter(g => g.rows.length);
  }
  return boards.map(b => ({
    label: `${t('g_board_l')} ${b.idx}　${b.product}`,
    rows: S.clips.map(e => [e, (e.use || []).find(u => u.board === b.idx)])
      .filter(([, u]) => u)
      .map(([e, u]) => row(e, u.qty, `${b.idx}`)),
  }));
}

function paintGroups(el, groups, span) {
  el.innerHTML = groups.map(g => {
    const sub = g.rows.reduce((s, r) => s + r.qty, 0);
    const head = g.label
      ? `<tr class="grp"><td colspan="${span}">${g.label}<span class="gq">${sub}</span></td></tr>`
      : '';
    return head + g.rows.map(r => `<tr>${r.html}</tr>`).join('');
  }).join('');
  return groups.reduce((s, g) => s + g.rows.reduce((a, r) => a + r.qty, 0), 0);
}

function summary() {
  const S = D.summary;
  if (!S) return;
  // the board view is a slice of an ordering cell, so it can only show the net figure
  const noSpare = bgroup === 'board' || cgroup === 'board';
  if (noSpare && spare) setSpare(false);
  $$('#bgroup button, #cgroup button').forEach(b => b.classList
    .toggle('on', b.dataset.g === (b.parentNode.id === 'bgroup' ? bgroup : cgroup)));
  $$('#spare button').forEach(b => { b.disabled = noSpare && b.dataset.s === 'spare'; });

  const bt = paintGroups($('#sumbricks'), brickGroups(), 7);
  const ct = paintGroups($('#sumclips'), clipGroups(), 4);
  $('#sumbtot').textContent = bt;
  $('#sumctot').textContent = ct;
  $('#sumnote').textContent = t(spare ? 'note_spare' : 'note_exact')(bt, ct)
    + (noSpare ? t('note_board') : '');
}

function setSpare(on) {
  spare = on;
  $$('#spare button').forEach(x => x.classList.toggle('on', (x.dataset.s === 'spare') === on));
  $('#summary').classList.toggle('sparing', on);
}

$$('#spare button').forEach(b => b.onclick = () => {
  setSpare(b.dataset.s === 'spare');
  summary();
});
$$('#bgroup button').forEach(b => b.onclick = () => { bgroup = b.dataset.g; summary(); });
$$('#cgroup button').forEach(b => b.onclick = () => { cgroup = b.dataset.g; summary(); });

/* Regrouping must never change a total.  Checked here rather than trusted, because the failure
   this guards against - a shape counted under two products, a board missing from a use list -
   looks entirely plausible on the page. */
function assertGroups() {
  const S = D.summary;
  if (!S) return;
  const was = [bgroup, cgroup, spare];
  const tot = (gs) => gs.reduce((s, g) => s + g.rows.reduce((a, r) => a + r.qty, 0), 0);
  const out = [];
  for (const sp of [false, true]) {
    spare = sp;
    const bs = ['shape', 'product'].concat(sp ? [] : ['board'])
      .map(g => { bgroup = g; return tot(brickGroups()); });
    const cs = ['type', 'product'].concat(sp ? [] : ['board'])
      .map(g => { cgroup = g; return tot(clipGroups()); });
    if (new Set(bs).size > 1) out.push(`bricks ${sp ? 'spare' : 'exact'}: ${bs.join(' / ')}`);
    if (new Set(cs).size > 1) out.push(`clips ${sp ? 'spare' : 'exact'}: ${cs.join(' / ')}`);
  }
  [bgroup, cgroup, spare] = was;
  if (out.length) console.error('summary groupings disagree -', out.join('; '));
}
assertGroups();

// The wheel belongs to the page, so zooming needs a control of its own rather than a modifier
// nobody will discover.
function zoomBy(k) {
  const off = camera.position.clone().sub(controls.target);
  const d = Math.min(Math.max(off.length()*k, controls.minDistance), controls.maxDistance);
  camera.position.copy(controls.target).add(off.setLength(d));
  goLive();
}
$$('#zoom button').forEach(b => b.onclick = () => {
  const z = b.dataset.z;
  if (z === 'fit') { engaged = true; goto(view); return; }
  zoomBy(z === 'in' ? 0.82 : 1.22);
});

async function files() {
  const b = board;
  const nn = String(b.idx).padStart(2, '0');
  const all = lang === 'zh' ? '九块板共用' : 'all nine';
  const F = [
    [`models/board_${b.idx}.glb`, t('f_glb')(b.idx), nn],
    [`blend/board_${b.idx}.blend`, t('f_blend')(b.idx), nn],
    [`renders/b${b.idx}_front.png`, t('f_front')(b.idx), nn],
    [`renders/b${b.idx}_hero.png`, t('f_hero')(b.idx), nn],
    [`renders/b${b.idx}_detail.png`, t('f_detail')(b.idx), nn],
    ['downloads/05_nine_boards_CN_EN.dxf', t('f_dxf1'), all],
    ['downloads/06_clips_CN_EN.dxf', t('f_dxf2'), all],
    ['downloads/S7_nine_boards_schedule_CN_EN.svg', t('f_s7svg'), all],
    ['downloads/S7_nine_boards_schedule_CN_EN.png', t('f_s7png'), all],
    ['downloads/S8_clips_CN_EN.svg', t('f_s8svg'), all],
    ['downloads/S8_clips_CN_EN.png', t('f_s8png'), all],
    ['downloads/07_bricks_CN_EN.dxf', t('f_dxf3'), all],
    ['downloads/S9_bricks_CN_EN.svg', t('f_s9svg'), all],
    ['downloads/S9_bricks_CN_EN.png', t('f_s9png'), all],
    ['downloads/08_setout_CN_EN.dxf', t('f_dxf4'), all],
    ['downloads/07_bricks_spare15_CN_EN.dxf', t('f_dxf3s'), all],
    ['downloads/08_setout_spare15_CN_EN.dxf', t('f_dxf4s'), all],
    ['downloads/brick_schedule.csv', t('f_bcsv'), all],
    ['downloads/clip_schedule.csv', t('f_ccsv'), all],
    ['downloads/board_comparison.pdf', t('f_cmp'), all],
    ['data/boards.json', t('f_json'), all]
  ];
  $('#dlrows').innerHTML = (await Promise.all(F.map(async ([href, what, who]) => {
    return `<tr><td class="who">${who}</td><td class="f">${href.split('/').pop()}</td>
      <td>${what}</td>
      <td class="sz">${await size(href)}</td>
      <td class="go"><a href="${href}" download>${t('dl')}</a></td></tr>`;
  }))).join('');
  $('#dlsize').textContent = await size('downloads/wuhan-9-panels.zip');
}

async function size(href) {
  try {
    const r = await fetch(href, {method: 'HEAD'});
    const n = +r.headers.get('content-length');
    if (n) return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.round(n / 1024) + ' KB';
  } catch (e) { /* no headers over file:// */ }
  return '';
}

/* =====================================================================
   picking
   ===================================================================== */
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
const insp = $('#insp');
const row = (k, v) => `<dt>${k}</dt><dd>${v}</dd>`;
let down = null;
canvas.addEventListener('pointerdown', e => down = [e.clientX, e.clientY]);
canvas.addEventListener('pointerup', e => {
  if (!down || !cur || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
  const r = canvas.getBoundingClientRect();
  ndc.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1);
  ray.setFromCamera(ndc, camera);
  const hits = ray.intersectObjects([...cur.slips, ...cur.clips].filter(o => o.visible), false);
  if (!hits.length) { insp.classList.remove('show'); return; }
  const u = hits[0].object.userData;
  if (u.kind === 'slip') {
    const ty = board.types[u.ti];
    $('#ins-id').textContent = ty.code;
    $('#ins-sub').textContent = kindOf(ty);
    $('#ins-dl').innerHTML =
      row(t('i_size'), `${ty.dims[0]} × ${ty.dims[1]} mm`) +
      row(t('i_area'), `${ty.area.toLocaleString()} mm²`) +
      row(t('i_qty'), `× ${ty.qty}`) + row(t('i_note'), ty.label);
  } else {
    const c = board.clips.find(x => x.code === u.code) || {};
    $('#ins-id').textContent = u.code;
    $('#ins-sub').textContent = lang === 'zh' ? (c.zh || '') : (c.en || '');
    $('#ins-dl').innerHTML =
      row(t('i_sect'), `${P.flat} / ${P.leg} / ${P.lip} @ ${P.angle}°`) +
      row(t('i_mouth'), `${P.mouth} mm`) + row(t('i_sheet'), `${P.sheet} mm`) +
      row(t('i_qty'), `× ${c.qty ?? '—'}`);
  }
  insp.classList.add('show');
});

/* =====================================================================
   controls
   ===================================================================== */
function setMode(m) {
  mode = m;
  $$('#modes button').forEach(x => x.classList.toggle('on', x.dataset.m === m));
  if (m === 'clip') isolate = null;
  $$('#brickrows tr').forEach(x => x.classList.toggle('sel', +x.dataset.t === isolate));
  paint();
}
$$('#views button').forEach(b => b.onclick = () => {
  $$('#views button').forEach(x => x.classList.toggle('on', x === b));
  view = b.dataset.v; engaged = true;
  const L = VIEWS[view].lift;
  if (L !== undefined) { $('#ex').value = L; $('#ex').dispatchEvent(new Event('input')); }
  goLive(); goto(view);
});
$$('#modes button').forEach(b => b.onclick = () => { engaged = true; goLive(); setMode(b.dataset.m); });
function syncChips() {
  $$('#layers .chip').forEach(x => x.classList.toggle('on', layer[x.dataset.l]));
}
$$('#layers .chip').forEach(b => b.onclick = () => {
  engaged = true;
  layer[b.dataset.l] = !layer[b.dataset.l];
  b.classList.toggle('on', layer[b.dataset.l]);
  goLive(); paint();
});
$('#ex').oninput = e => {
  exWant = (+e.target.value) / 100 * 0.22;
  $('#exv').textContent = Math.round(exWant * 1000) + ' mm';
  goLive();
};

function paintStatic() {
  document.documentElement.lang = lang;
  $$('[data-t]').forEach(el => {
    const v = T[lang][el.dataset.t];
    if (typeof v === 'string') el.innerHTML = v;
  });
  $$('#lang button').forEach(b => b.classList.toggle('on', b.dataset.lang === lang));
}
function boardCards() {
  $('#boardgrid').innerHTML = boards.map(b => `
    <button class="bcard${b.idx === (board && board.idx) ? ' on' : ''}" data-i="${b.idx}" type="button">
      <img src="renders/b${b.idx}_thumb.webp" alt="" loading="lazy">
      <span class="bno">${String(b.idx).padStart(2, '0')}</span>
      <span class="bnm">${lang === 'zh' ? b.zh : b.en}</span>
      <span class="bmeta">${b.w} × ${b.h} · ${b.pieces.length} ${t('bc_pcs')} · ${b.types.length} ${t('bc_types')}</span>
    </button>`).join('');
  $$('.bcard').forEach(p => p.onclick = () => {
    show(+p.dataset.i);
    $('#model').scrollIntoView({behavior: 'smooth', block: 'start'});
  });
}
$('#lang').onclick = e => {
  const b = e.target.closest('button');
  if (!b || b.dataset.lang === lang) return;
  lang = b.dataset.lang;
  localStorage.setItem('wuhan-lang', lang);
  paintStatic(); lede(); sections();
  boardCards();
};

addEventListener('keydown', e => {
  if (e.target.matches('input')) return;
  if (e.key === 'Escape') { closeDoc(); insp.classList.remove('show'); return; }
  // arrows belong to whatever is in front.  With the drawing viewer open they were still
  // switching the board behind it, which fetched another GLB the reader could not see.
  if (document.getElementById('lb').classList.contains('on')) return;
  const i = boards.findIndex(b => b.idx === board.idx);
  if (e.key === 'ArrowRight') show(boards[(i + 1) % boards.length].idx);
  if (e.key === 'ArrowLeft') show(boards[(i + boards.length - 1) % boards.length].idx);
});
addEventListener('hashchange', () => {
  const m = /^#b(\d)$/.exec(location.hash);
  if (m && byIdx[+m[1]] && board.idx !== +m[1]) show(+m[1]);
});

/* =====================================================================
   the drawing viewer

   S7 is 4620 x 10340.  Fitting that to a screen shows it at about 7 %, which is why every
   dimension on it was unreadable, and the thing being fitted was a 804 x 1800 thumbnail, so
   zooming the browser only made the blur bigger.  The sheets now open as SVG - the same file the
   downloads serve - at a size you choose, in a pane you scroll.
   ===================================================================== */
const lb = $('#lb'), lbimg = $('#lbimg'), lbpane = $('#lbpane');
let lbScale = 1, lbNat = [0, 0];

function lbApply(keepCentre) {
  if (!lbNat[0]) return;
  const cx = (lbpane.scrollLeft + lbpane.clientWidth / 2) / Math.max(1, lbimg.offsetWidth);
  const cy = (lbpane.scrollTop + lbpane.clientHeight / 2) / Math.max(1, lbimg.offsetHeight);
  lbimg.style.width = Math.round(lbNat[0] * lbScale) + 'px';
  if (keepCentre) {
    lbpane.scrollLeft = cx * lbimg.offsetWidth - lbpane.clientWidth / 2;
    lbpane.scrollTop = cy * lbimg.offsetHeight - lbpane.clientHeight / 2;
  }
}

function lbSet(v, keepCentre) {
  lbScale = Math.min(8, Math.max(0.05, v));
  lbApply(keepCentre);
  const p = $('#lbpct');
  if (p) p.textContent = Math.round(lbScale * 100) + '%';
}

function lbFitW() {
  lbSet(lbNat[0] ? (lbpane.clientWidth - 34) / lbNat[0] : 1, false);
  lbpane.scrollTop = 0;
}

function openDoc(href, name) {
  lbNat = [0, 0];
  lbimg.removeAttribute('style');
  lbimg.src = href;
  $('#lbt').textContent = name || href.split('/').pop();
  $('#lbdl').href = href;
  $('#lbdl').setAttribute('download', name || '');
  lb.classList.add('on');
  document.body.style.overflow = 'hidden';   // or a wheel over the toolbar scrolls the page behind
  $('#lb .x').focus();
  const ready = () => {
    // an SVG reports its own intrinsic size; fall back to the box the browser gave it
    lbNat = [lbimg.naturalWidth || lbimg.offsetWidth, lbimg.naturalHeight || lbimg.offsetHeight];
    // Open at 1:1, not fitted.  S7 is 2016 x 4512: fitting it to a 1400 pane puts the schedule
    // text at 68 % and fitting the height would put it at 18 %, which is the whole complaint -
    // showing all of it at once is exactly what makes it unreadable.  It opens readable and you
    // scroll, and Fit is one button away for anyone who wants the overview.
    lbSet(1, false);
    lbpane.scrollTop = 0;
    lbpane.scrollLeft = Math.max(0, (lbimg.offsetWidth - lbpane.clientWidth) / 2);
  };
  if (lbimg.complete && lbimg.naturalWidth) ready();
  else lbimg.onload = ready;
}

function bindLb() {
  $$('[data-lb]').forEach(el => {
    el.onclick = () => openDoc(el.dataset.lb, el.dataset.name);
    // a drawing you can only reach with a mouse is a drawing half the readers cannot open
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.onkeydown = e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); el.click(); }
    };
  });
}
$$('#lb .lbz button').forEach(b => b.onclick = e => {
  e.stopPropagation();
  const z = b.dataset.z;
  if (z === 'fit') return lbFitW();
  if (z === 'one') return lbSet(1, true);
  lbSet(lbScale * (z === 'in' ? 1.4 : 1 / 1.4), true);
});
function closeDoc() {
  if (!lb.classList.contains('on')) return;
  lb.classList.remove('on');
  document.body.style.overflow = '';
}
$('#lb .x').onclick = closeDoc;
lb.onclick = e => { if (e.target === lb) closeDoc(); };
lbimg.ondblclick = () => (lbScale > 0.99 ? lbFitW() : lbSet(1, true));
lbpane.addEventListener('wheel', e => {
  if (!e.ctrlKey && !e.metaKey) return;          // plain wheel scrolls the sheet, as it should
  e.preventDefault();
  lbSet(lbScale * (e.deltaY < 0 ? 1.12 : 1 / 1.12), true);
}, {passive: false});

// drag to pan.  Scrollbars alone are not a way to read a 2016 x 4512 drawing: you want to grab it
// and push it about, the way every other drawing viewer works.
let drag = null;
lbpane.addEventListener('pointerdown', e => {
  if (e.button !== 0) return;
  drag = {x: e.clientX, y: e.clientY, l: lbpane.scrollLeft, t: lbpane.scrollTop};
  lbpane.setPointerCapture(e.pointerId);
  lbpane.classList.add('grab');
});
lbpane.addEventListener('pointermove', e => {
  if (!drag) return;
  lbpane.scrollLeft = drag.l - (e.clientX - drag.x);
  lbpane.scrollTop = drag.t - (e.clientY - drag.y);
});
for (const ev of ['pointerup', 'pointercancel'])
  lbpane.addEventListener(ev, () => { drag = null; lbpane.classList.remove('grab'); });

addEventListener('keydown', e => {
  if (!lb.classList.contains('on')) return;
  const step = e.shiftKey ? 400 : 120;
  const k = {ArrowDown: [0, step], ArrowUp: [0, -step], ArrowRight: [step, 0],
             ArrowLeft: [-step, 0], PageDown: [0, lbpane.clientHeight * 0.9],
             PageUp: [0, -lbpane.clientHeight * 0.9]}[e.key];
  if (k) { lbpane.scrollBy(k[0], k[1]); e.preventDefault(); return; }
  if (e.key === 'Home') { lbpane.scrollTop = 0; e.preventDefault(); }
  if (e.key === 'End') { lbpane.scrollTop = lbpane.scrollHeight; e.preventDefault(); }
  if (e.key === '+' || e.key === '=') { lbSet(lbScale * 1.4, true); e.preventDefault(); }
  if (e.key === '-') { lbSet(lbScale / 1.4, true); e.preventDefault(); }
  if (e.key === '0') { lbFitW(); e.preventDefault(); }
});
addEventListener('resize', () => { if (lb.classList.contains('on') && lbScale < 0.2) lbFitW(); });

/* =====================================================================
   loop
   ===================================================================== */
function resize() {
  if (!GL) return;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  const r = renderer.getPixelRatio();
  if (canvas.width !== Math.round(w * r) || canvas.height !== Math.round(h * r)) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    applyOffset();
  }
}
// A phone fires resize whenever the URL bar slides, and taking the camera back mid-drag is worse
// than a slightly loose fit, so refit only while the poster is up or when the lede band changes.
let lastLede = null, rt = null;
addEventListener('resize', () => {
  resize();
  clearTimeout(rt);
  rt = setTimeout(() => {
    if (!cur) return;
    const f = lede_f();
    if (!live || f !== lastLede) {
      lastLede = f;
      goto(view, 0);
    }
  }, 160);
});
let vis = true;
new IntersectionObserver(es => vis = es[0].isIntersecting, {threshold: 0}).observe(canvas);
if (GL) renderer.setAnimationLoop(() => {
  if (!vis || !cur) return;
  resize();
  if (anim) anim();
  if (Math.abs(exWant - explode) > 1e-5) {
    explode += (exWant - explode) * 0.16;
    if (Math.abs(exWant - explode) < 1e-5) explode = exWant;
    applyExplode();
  }
  controls.update();
  renderer.render(scene, camera);
});

/* =====================================================================
   motion
   ===================================================================== */
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

// Sections rise into place once, the first time they are reached.  An observer rather than a scroll
// handler, because the page already runs a render loop and a scroll listener would fight it.
const rise = new IntersectionObserver((es, ob) => {
  for (const e of es) {
    if (!e.isIntersecting) continue;
    e.target.classList.add('in');
    ob.unobserve(e.target);
  }
}, {rootMargin: '0px 0px -12% 0px'});
function watchRise() {
  if (REDUCED) return;
  $$('section .shead, .bcard, .clipcard, .plate, .sumcol, .allbtn, #files .tscroll')
    .forEach((el, i) => {
      if (el.dataset.rise) return;
      el.dataset.rise = '1';
      el.classList.add('rise');
      el.style.transitionDelay = Math.min(i, 8)*38 + 'ms';
      rise.observe(el);
    });
}

// the cursor's position on a card, for the light that follows it
addEventListener('pointermove', e => {
  const c = e.target.closest && e.target.closest('.bcard');
  if (!c) return;
  const r = c.getBoundingClientRect();
  c.style.setProperty('--mx', (e.clientX-r.left) + 'px');
  c.style.setProperty('--my', (e.clientY-r.top) + 'px');
}, {passive: true});

// The hero figures change with the board, so they count rather than cut.  Short enough to read as
// a transition and not as a slot machine.
function countUp(el, to) {
  const n = +String(to).replace(/[^\d.]/g, '');
  if (REDUCED || !isFinite(n) || n < 12) { el.textContent = to; return; }
  const t0 = performance.now(), dur = 460, pre = String(to).replace(/[\d.]+$/, '');
  const step = now => {
    const p = Math.min(1, (now-t0)/dur), e = 1-Math.pow(1-p, 3);
    el.textContent = pre + Math.round(n*e);
    if (p < 1) requestAnimationFrame(step); else el.textContent = to;
  };
  requestAnimationFrame(step);
}

paintStatic();
const first = /^#b(\d)$/.exec(location.hash);
boardCards();
await show(first && byIdx[+first[1]] ? +first[1] : 1, true);

// Say why the viewer is a picture rather than leaving somebody poking at a still that will not
// turn.  Everything else on the page is unaffected and needs no explaining.
if (!GL) {
  const n = document.createElement('p');
  n.className = 'nogl';
  n.dataset.t = 'no_gl';                 // so the language switch translates it like everything else
  n.innerHTML = T[lang].no_gl;
  stage.appendChild(n);
  document.body.classList.add('no-gl');   // distinct from the <p class=nogl> note
}
document.body.classList.add('ready');
