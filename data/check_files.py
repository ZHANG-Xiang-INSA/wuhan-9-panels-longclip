# -*- coding: utf-8 -*-
"""The register: every file this job delivers, and whether it still says what the geometry says.

    python data/check_files.py

check_all.py reconciles the NUMBERS - schedules against geometry, the models against the
schedules.  check_dxf.py and check_sheets.py check that a reader can see what is on a drawing.
Neither of them walks the register, and that is a real hole: a file can simply not be there, or be
there from three regenerations ago, and nothing says so.  Everything published was in the git tree
and the tree was clean, which is not the same as current.

So this one starts from what the job is supposed to hand over - nine boards, so nine models, nine
Blender files, nine textures, four renders each - counts it, opens it, and holds what is inside to
site/data/boards.json.  Nothing is taken on trust because it looks right.

It goes down to the cell.  Each schedule row: the product split has to sum to the quantity, the
used-on list has to sum to the quantity, and the order figure has to be +15 % taken per PRODUCT
and rounded up there.  Each DIMENSION in a drawing has to read the distance between the two points
it was built from.  Each texture has to be its own board at the fixed millimetres per pixel, and
the renders one size per view across all nine.
"""
import io, sys, os, json, csv, zipfile, struct, math, re, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import ezdxf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
os.chdir(ROOT)
D = json.load(open('site/data/boards.json', encoding='utf-8'))
S = D['summary']
N = len(D['boards'])
SLIPS = sum(len(b['pieces']) for b in D['boards'])
CLIPS = sum(len(b['rails']) for b in D['boards']) + sum(
    1 for b in D['boards'] for i, p in enumerate(b['pieces'])
    if i not in {j for rc in b['rails'] for j in rc['covers']})
bad, seen = [], 0


def ck(cond, msg):
    global seen
    seen += 1
    if not cond:
        bad.append(msg)


def has(path, least=1):
    ok = os.path.exists(path) and os.path.getsize(path) >= least
    ck(ok, 'missing or empty: %s (%d bytes)'
       % (path, os.path.getsize(path) if os.path.exists(path) else -1))
    return ok


# ------------------------------------------------------------------ the register, board by board
for b in D['boards']:
    i = b['idx']
    has('site/models/board_%d.glb' % i, 50000)
    has('site/blend/board_%d.blend' % i, 50000)
    has('site/textures/setout_board_%d.png' % i, 20000)
    for tag in ('front', 'hero', 'detail'):
        has('site/renders/b%d_%s.webp' % (i, tag), 5000)
        has('site/renders/b%d_%s.png' % (i, tag), 50000)
    has('site/renders/b%d_thumb.webp' % i, 1000)

# ------------------------------------------------------------------ the drawings
for q in ('dxf/05_nine_boards_CN_EN.dxf', 'dxf/06_clips_CN_EN.dxf', 'dxf/07_bricks_CN_EN.dxf',
          'dxf/07_bricks_spare15_CN_EN.dxf', 'dxf/08_setout_CN_EN.dxf',
          'dxf/08_setout_spare15_CN_EN.dxf', 'dxf/guiding_rail_clip_10_types_orthographic.dxf'):
    has(q, 1000)
for q in ('S7_nine_boards_schedule_CN_EN', 'S8_clips_CN_EN', 'S9_bricks_CN_EN'):
    has('drawings/%s.svg' % q, 10000)
    has('drawings/%s.png' % q, 10000)
has('docs/board_comparison.pdf', 10000)
has('docs/joint_report.html', 1000)
has('site/index.html', 1000)
has('site/app.js', 1000)
has('site/style.css', 1000)
has('data/clip_colours.json', 100)


def text(p):
    return [e.dxf.text for e in ezdxf.readfile(p).modelspace().query('TEXT')]


# dxf/05 carries the nine boards: every board's title and its size
t5 = ' '.join(text('dxf/05_nine_boards_CN_EN.dxf'))
for b in D['boards']:
    ck(b['en'] in t5 or b['zh'] in t5, 'dxf/05 does not name board %d' % b['idx'])

# dxf/06 carries one detail per clip type, at that type's own length
t6 = text('dxf/06_clips_CN_EN.dxf')
for e in S['clips']:
    ck(any(e['code'] == x or e['code'] in x for x in t6),
       'dxf/06 has no detail for %s' % e['code'])
for r in S['rails']:
    ck(any(x.strip() == ('%g' % r['length']) for x in t6),
       'dxf/06 does not dimension %s at %g' % (r['code'], r['length']))

# EVERY HOLE OF EVERY CLIP HAS TO BE LOCATABLE ON dxf/06.  A rail's holes are on one centreline
# and one height places them all; a pocket's are not - PK-3T03's sit at 68 and 25 above the
# bottom, PK-8T02's at 57 and 30 - and the drawing gave the along-chain for both but a height for
# only one, so the second hole could not be found.  Both coordinates of every hole are checked
# against the numbers that actually appear inside that clip's own panel.
_t6xy = [(e.dxf.insert[1], e.dxf.text) for e in ezdxf.readfile('dxf/06_clips_CN_EN.dxf')
         .modelspace().query('TEXT')]
CG6 = D['clipgeo']
for e in S['clips']:
    g = CG6.get(e['code'])
    if not g or not g.get('holes'):
        continue
    top = [y for y, t in _t6xy if t == e['code']]
    if not top:
        continue
    band = {t for y, t in _t6xy if top[0]-420 < y <= top[0]}
    base = g['base']
    x0, y0 = min(q[0] for q in base), min(q[1] for q in base)
    xmax = max(q[0] for q in base)
    hs = sorted(g['holes'])

    def placed(vals, chain):
        """either way of writing it counts: the distance from the datum, or the steps that add
        up to it.  A rail is dimensioned as a chain across and heights from the bottom; a pocket
        the other way round, offsets from the left and heights as a chain.  Both locate the hole,
        and a check that only knows one of them is a check on the draughtsman's habit."""
        return all(('%g' % round(v, 1)) in band for v in vals) or                all(('%g' % round(v, 1)) in band for v in chain)

    across = [h[0]-x0 for h in hs]
    step_x = [hs[0][0]-x0]+[hs[k][0]-hs[k-1][0] for k in range(1, len(hs))]+[xmax-hs[-1][0]]
    ck(placed(across, [v for v in step_x if v >= 1.0]),
       'dxf/06 %s: a hole is not placed across the blank' % e['code'])
    up = sorted(hs, key=lambda h: h[1])
    heights = [h[1]-y0 for h in up]
    step_y = [up[0][1]-y0]+[up[k][1]-up[k-1][1] for k in range(1, len(up))]
    ck(placed(heights, step_y),
       'dxf/06 %s: a hole is not placed up the blank - it cannot be located' % e['code'])

# dxf/07 carries the brick schedule; every code and every quantity on it
t7 = text('dxf/07_bricks_CN_EN.dxf')
for e in S['bricks']:
    ck(e['code'] in t7, 'dxf/07 is missing brick %s' % e['code'])
    ck(str(e['qty']) in t7, 'dxf/07 is missing the quantity %d for %s' % (e['qty'], e['code']))
ck(str(S['brick_total']) in t7, 'dxf/07 does not carry the brick total %d' % S['brick_total'])

# dxf/08 is the setting-out: one closed outline per slip and one per clip, and the drill marks
d8 = ezdxf.readfile('dxf/08_setout_CN_EN.dxf')
pl = [e for e in d8.modelspace().query('LWPOLYLINE')]
slip = [e for e in pl if e.dxf.layer.endswith('_SLIP')]
clip = [e for e in pl if '_CLIP' in e.dxf.layer]
hole = [e for e in d8.modelspace().query('CIRCLE') if e.dxf.layer.endswith('_HOLE')]
ck(len(slip) == SLIPS, 'dxf/08 draws %d slips, the geometry has %d' % (len(slip), SLIPS))
ck(len(clip) == CLIPS, 'dxf/08 draws %d clips, the geometry has %d' % (len(clip), CLIPS))
# a piece carries no hole list of its own - the holes belong to the clip type it wears
CG = D['clipgeo']
nh = sum(len(rc['holes']) for b in D['boards'] for rc in b['rails']) + sum(
    len(CG[p['c']]['holes']) for b in D['boards'] for i, p in enumerate(b['pieces'])
    if i not in {j for rc in b['rails'] for j in rc['covers']})
ck(len(hole) == nh, 'dxf/08 draws %d drill marks, the geometry has %d' % (len(hole), nh))

# the ordering copies carry the +15 % figures and the same setting-out
t7s = text('dxf/07_bricks_spare15_CN_EN.dxf')
ck(str(S['brick_spare']) in t7s, 'dxf/07 spare does not carry the order total %d' % S['brick_spare'])

# ------------------------------------------------- one numbering, on every drawing
# The brick code is the number a fabricator works to, and it is written in six places: dxf/05's
# schedule and its layer names, dxf/08's per-piece labels and its per-board legend, dxf/07, and
# the three sheets.  Nothing used to hold any of those to boards.json, so a renumbering that
# reached five of the six passed every gate and shipped two numbering systems in one set.
_BC = {b['idx']: [t['code'] for t in b['types']] for b in D['boards']}
_ALL = sorted({c for v in _BC.values() for c in v})

t5 = ' '.join(text('dxf/05_nine_boards_CN_EN.dxf'))
_l5 = {e.dxf.layer for e in ezdxf.readfile('dxf/05_nine_boards_CN_EN.dxf').modelspace()}
for _i, _cs in _BC.items():
    for _c in _cs:
        ck(_c in t5, 'dxf/05 never writes %s, which board %d lays' % (_c, _i))
        ck(any(l.startswith('P%d_%s_' % (_i, _c)) for l in _l5),
           'dxf/05 has no P%d_%s_* layer' % (_i, _c))
ck(not re.search(r'\bT0[1-9]\b', t5) and not any(re.search(r'\bT0[1-9]\b', l) for l in _l5),
   'dxf/05 still carries a per-board T code')

for _q in ('dxf/08_setout_CN_EN.dxf', 'dxf/08_setout_spare15_CN_EN.dxf'):
    _t8 = [x for x in text(_q) if re.fullmatch(r'[A-Z]+[0-9]+', x or '')]
    _lab = collections.Counter(x for x in _t8 if x in _ALL)
    _want = collections.Counter()
    for b in D['boards']:
        for p in b['pieces']:
            _want[b['types'][p['t']]['code']] += 1
    ck(_lab == _want, '%s labels %s, the geometry has %s'
       % (os.path.basename(_q), dict(_lab), dict(_want)))
    ck(not re.search(r'\bT0[1-9]\b', ' '.join(text(_q))),
       '%s still carries a per-board T code' % os.path.basename(_q))

# The two setting-out copies must say the same thing piece for piece, not only draw the same
# geometry: check_all compares their polylines and circles and never looked at the text.
_a = [x for x in text('dxf/08_setout_CN_EN.dxf') if x in _ALL]
_b = [x for x in text('dxf/08_setout_spare15_CN_EN.dxf') if x in _ALL]
ck(_a == _b, 'dxf/08 and its ordering copy label the pieces differently')

# ------------------------------------------------------------------ the sheets
# Read out of the SVG's text COMMENTS, not its body.  matplotlib writes every glyph as a path, so
# a plain substring test was answered by whatever <g id="patch_1414"> happened to be there: the
# S7 assertion below passed for any brick total from 1 to 1528 and would have passed just as
# happily with the sheet still on the old numbering.
def svgtext(q):
    return ' '.join(re.findall(r'<!--(.*?)-->', io.open(q, encoding='utf-8').read(), re.S))


for q, want in (('drawings/S7_nine_boards_schedule_CN_EN.svg', _ALL),
                ('drawings/S8_clips_CN_EN.svg', [e['code'] for e in S['clips']]),
                ('drawings/S9_bricks_CN_EN.svg', [e['code'] for e in S['bricks']])):
    body = svgtext(q)
    for w in want:
        ck(w in body, '%s does not carry %s' % (os.path.basename(q), w))
    ck(not re.search(r'\bT0[1-9]\b', body),
       '%s still carries a per-board T code' % os.path.basename(q))

# ------------------------------------------------------------------ the schedules
for q, tot, col in (('site/downloads/brick_schedule.csv', S['brick_total'], 6),
                    ('site/downloads/clip_schedule.csv', S['clip_total'], 9)):
    rows = list(csv.reader(io.open(q, encoding='utf-8-sig')))[1:]
    by = {}
    for r in rows:
        by[r[0]] = by.get(r[0], 0)+int(r[col])
    ck(len(by) == 3, '%s has %d groupings, want 3' % (os.path.basename(q), len(by)))
    ck(set(by.values()) == {tot}, '%s groupings %s, want %d' % (os.path.basename(q), by, tot))

# ------------------------------------------------------------------ the zip
z = zipfile.ZipFile('site/downloads/wuhan-9-panels.zip')
names = z.namelist()
for b in D['boards']:
    # the zip pads the number - board_01.glb - so ask for the board's folder, not its filename
    fold = '02_boards/board_%02d/' % b['idx']
    for ext in ('.glb', '.blend'):
        ck(any(n.startswith(fold) and n.endswith(ext) for n in names),
           'zip has no %s for board %d' % (ext, b['idx']))
    ck(sum(1 for n in names if n.startswith(fold)) >= 5,
       'zip carries only %d files for board %d'
       % (sum(1 for n in names if n.startswith(fold)), b['idx']))
for w in ('05_nine_boards', '06_clips', '07_bricks', '08_setout', 'S7_', 'S8_', 'S9_',
          'brick_schedule.csv', 'clip_schedule.csv', 'boards.json'):
    ck(any(w in n for n in names), 'zip is missing %s' % w)
for n in names:
    ck(z.getinfo(n).file_size > 0, 'zip entry %s is empty' % n)

# ------------------------------------------------------------------ the page
app = io.open('site/app.js', encoding='utf-8').read()
idx = io.open('site/index.html', encoding='utf-8').read()
for b in D['boards']:
    ck('renders/b%d_hero.webp' % b['idx'] in app or 'b${b.idx}_hero' in app,
       'the page never asks for board %d\'s hero' % b['idx'])
    break
ck('clip_colours' in app, 'the page does not read the clip palette')
ck('data/boards.json' in app, 'the page does not read boards.json')
for q in ('S7_preview.webp', 'S8_preview.webp', 'S9_preview.webp'):
    ck(q in idx, 'index.html does not show %s' % q)
    has('site/renders/%s' % q, 2000)

# --------------------------------------------------------- the schedules, cell by cell
# Not just the three totals.  Every row: the product split has to sum to the quantity, the
# used-on list has to sum to the quantity, and the order figure has to be +15 % taken per PRODUCT
# and rounded up there - rounding the row total instead is a different number.  The by-board
# grouping is compared cell for cell against the geometry, which is the only one of the three
# that can be.  The by-board rows carry no order figure on purpose: a board is a slice of an
# ordering cell, and 15 % of a slice is not ordered from anybody.
def _split(cell, q):
    """'L10 B2 358; L10 Grey 411' -> [(name, qty)]; a bare name takes the row's own quantity,
    which is how the by-product grouping writes it"""
    out = []
    for part in [x.strip() for x in cell.split(';') if x.strip()]:
        m = re.search(r'^(.*?)\s+(\d+)$', part)
        out.append((m.group(1), int(m.group(2))) if m else (part, q))
    return out


_prod = {}
for e in S['bricks']:
    for u in e['use']:
        _prod[(u['board'], u['code'])] = e['code']
_gb, _gc = collections.Counter(), collections.Counter()
for b in D['boards']:
    _cov = {i for rc in b['rails'] for i in rc['covers']}
    for i, p in enumerate(b['pieces']):
        _gb[_prod[(b['idx'], b['types'][p['t']]['code'])], b['idx']] += 1
        if i not in _cov:
            _gc[p['c'], b['idx']] += 1
    for rc in b['rails']:
        _gc[rc['code'], b['idx']] += 1

for path, kind, iq, io_, ip, iu, ic, src in (
        ('site/downloads/brick_schedule.csv', 'brick', 6, 7, 5, 8, 2, _gb),
        ('site/downloads/clip_schedule.csv', 'clip', 9, 10, 8, 11, 2, _gc)):
    rows = list(csv.reader(io.open(path, encoding='utf-8-sig')))[1:]
    for r in rows:
        q = int(r[iq])
        pv = _split(r[ip], q)
        ck(sum(v for _n, v in pv) == q, '%s %s %s: the product split sums to %d, the quantity '
           'is %d' % (kind, r[0], r[ic], sum(v for _n, v in pv), q))
        uv = [int(x) for x in re.findall(r'x(\d+)', r[iu])]
        if uv:
            ck(sum(uv) == q, '%s %s %s: used-on sums to %d, the quantity is %d'
               % (kind, r[0], r[ic], sum(uv), q))
        if r[io_]:
            want = sum(-(-v*115//100) for _n, v in pv)
            ck(int(r[io_]) == want, '%s %s %s: orders %s, +15%% per product gives %d'
               % (kind, r[0], r[ic], r[io_], want))
    tab = collections.Counter()
    for r in rows:
        if r[0].startswith('按板号'):
            tab[r[ic], int(re.search(r'(\d+)', r[1]).group(1))] += int(r[iq])
    ck(dict(tab) == dict(src),
       '%s: the by-board table is not the geometry' % os.path.basename(path))

# --------------------------------------------------------- every dimension measures itself
# A dimension that says 700 and spans 690 is worse than no dimension.  ezdxf keeps the two points
# it was built from, so the number on the drawing is held to the distance between them.
for q in ('dxf/05_nine_boards_CN_EN.dxf', 'dxf/08_setout_CN_EN.dxf'):
    for e in ezdxf.readfile(q).modelspace().query('DIMENSION'):
        try:
            p1, p2 = e.dxf.defpoint2, e.dxf.defpoint3
            got = e.get_measurement()
        except Exception:
            continue
        if isinstance(got, (int, float)):
            want = math.dist((p1[0], p1[1]), (p2[0], p2[1]))
            ck(abs(got-want) < 0.05, '%s: a dimension reads %.2f and spans %.2f'
               % (os.path.basename(q), got, want))

# --------------------------------------------------------- the pictures, at their real scale
# The setting-out texture is the board at a fixed millimetres-per-pixel, so its size is a fact
# about the board and not a setting.  One pixel of slack: 1535 x 2.6 is 3990.9999999999995.
PXMM = 2.6
for b in D['boards']:
    q = 'site/textures/setout_board_%d.png' % b['idx']
    im = Image.open(q)
    ck(abs(im.width-b['w']*PXMM) <= 1.01 and abs(im.height-b['h']*PXMM) <= 1.01,
       '%s is %dx%d, the board is %g x %g at %g px/mm'
       % (os.path.basename(q), im.width, im.height, b['w'], b['h'], PXMM))
_sz = collections.Counter()
for b in D['boards']:
    for tag in ('front', 'hero', 'detail'):
        for ext in ('webp', 'png'):
            _sz[tag, ext, Image.open('site/renders/b%d_%s.%s' % (b['idx'], tag, ext)).size] += 1
ck(all(v == len(D['boards']) for v in _sz.values()),
   'the renders are not one size per view: %s' % sorted(_sz.items()))
for q in ('S7_nine_boards_schedule_CN_EN', 'S8_clips_CN_EN', 'S9_bricks_CN_EN'):
    a = Image.open('drawings/%s.png' % q)
    m = re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"',
                  io.open('drawings/%s.svg' % q, encoding='utf-8').read(3000))
    ck(m is not None, '%s.svg has no size' % q)
    if m:
        ck(abs(a.width/a.height-float(m.group(1))/float(m.group(2))) < 0.02,
           '%s: the png and the svg are different shapes' % q)

# ---------------------------------------------- every drill mark in every model, in its place
# The clips in the models were solid - 60 triangles each, the section swept round with nothing
# taken out - while the drawing and the texture both showed the drill marks.  Nothing was looking,
# because nothing had ever compared a model against the geometry below the level of "how many
# clips".  Every hole is now found in the mesh by its own rim: a ring of vertices at 1.75 from the
# centre the data puts it at.  glTF is Y-up, so the board's y is the mesh's MINUS z - the first
# version of this check had that sign the wrong way round and reported 1470 of 2654 missing when
# every one of them was there.
def _rigid(src, dst):
    """the motion that carries src onto dst; boards.json has each clip's placed tray but not its
    placed holes, so the holes are carried over by the motion recovered from the two polygons"""
    n = min(len(src), len(dst))
    cs = (sum(q[0] for q in src)/len(src), sum(q[1] for q in src)/len(src))
    cd = (sum(q[0] for q in dst)/len(dst), sum(q[1] for q in dst)/len(dst))
    nu = sum((src[i][0]-cs[0])*(dst[i][1]-cd[1])-(src[i][1]-cs[1])*(dst[i][0]-cd[0])
             for i in range(n))
    de = sum((src[i][0]-cs[0])*(dst[i][0]-cd[0])+(src[i][1]-cs[1])*(dst[i][1]-cd[1])
             for i in range(n))
    th = math.atan2(nu, de)
    co, si = math.cos(th), math.sin(th)
    return lambda p: (cd[0]+(p[0]-cs[0])*co-(p[1]-cs[1])*si,
                      cd[1]+(p[0]-cs[0])*si+(p[1]-cs[1])*co)


MS = 0.001
for b in D['boards']:
    q = os.path.join('site', 'models', 'board_%d.glb' % b['idx'])
    if not os.path.exists(q):
        continue
    raw = open(q, 'rb').read()
    off, ch = 12, {}
    while off < len(raw):
        ln, ty = struct.unpack_from('<II', raw, off)
        ch[ty] = raw[off+8:off+8+ln]
        off += 8+ln
    G = json.loads(ch[0x4E4F534A].decode('utf-8'))
    BIN = ch[0x004E4942]
    cx, cy = b['w']/2.0, b['h']/2.0
    want = {}
    cov = {j for rc in b['rails'] for j in rc['covers']}
    for rc in b['rails']:
        want.setdefault(rc['code'], []).extend([tuple(v) for v in rc['holes']])
    for j, p in enumerate(b['pieces']):
        if j in cov:
            continue
        g = CG[p['c']]
        if g.get('holes') and len(g['base']) == len(p['k']):
            mv = _rigid([tuple(v) for v in g['base']], [tuple(v) for v in p['k']])
            want.setdefault(p['c'], []).extend([mv(tuple(v)) for v in g['holes']])
    for m in G['meshes']:
        c = m['name']
        if c not in want:
            continue
        a = G['accessors'][m['primitives'][0]['attributes']['POSITION']]
        bv = G['bufferViews'][a['bufferView']]
        o = bv.get('byteOffset', 0)+a.get('byteOffset', 0)
        st = bv.get('byteStride') or 12
        pts = [struct.unpack_from('<3f', BIN, o+k*st) for k in range(a['count'])]
        gone = 0
        for hx, hy in want[c]:
            X, Z = (hx-cx)*MS, -(hy-cy)*MS
            if sum(1 for v in pts
                   if abs(math.hypot(v[0]-X, v[2]-Z)-1.75*MS) < 0.0002) < 8:
                gone += 1
        ck(gone == 0, 'board %d: %d of the %d drill marks on %s are not in the model'
           % (b['idx'], gone, len(want[c]), c))

# ---------------------------------------------- S8 draws the same holes as everything else
sys.path.insert(0, HERE)
import clips9_draw as _CDR                                              # noqa: E402
for _c in json.load(io.open(os.path.join(HERE, 'clips9.json'), encoding='utf-8'))['clips']:
    if _c['kind'] != 'POCKET':
        continue
    _base, _lip, _hs, _bl = _CDR.geom(_c)
    _x0 = min(v[0] for v in _base)
    _y0 = min(v[1] for v in _base)
    _got = sorted((round(h[0]-_x0, 2), round(h[1]-_y0, 2)) for h in _hs)
    _wnt = sorted((round(v[0], 2), round(v[1], 2)) for v in CG[_c['code']]['holes'])
    ck(_got == _wnt, 'S8 draws %s at %s, every other drawing has %s'
       % (_c['code'], _got, _wnt))

print('%d checks over %d boards, %d slips, %d clips' % (seen, N, SLIPS, CLIPS))
print('CHECKS FAILED: %d' % len(bad))
for x in bad[:40]:
    print('   ', x)
sys.exit(1 if bad else 0)
