# -*- coding: utf-8 -*-
"""One command that reconciles every deliverable against the geometry.

    python data/check_all.py

The counts appear in nine places - boards.json, four DXFs and their two ordering copies, three
sheets, two CSVs, the zip and the page - and each is generated from the one before it.  That is
the right arrangement and it still lets a number go stale, because a generator that is not re-run
keeps writing yesterday's figure and nothing complains.  This asks the geometry itself and holds
everything else to it.

What is checked:

  HOLDING     every slip held by exactly one clip, no slip held twice, none left out
  SCHEDULE    the clip schedule equals the clips actually drawn
  LONG CLIP   length, hole count, pitch and end margins on every one of them, and that no board
              with a joint too small to take one carries one
  CLASH       no two clip trays overlap, by separating axis
  SPARE       +15 % rounded up per (type x product), and the totals that follow from it
  ORDER COPY  the +15 % DXFs carry the ordering figures, and 08's geometry is board-for-board
              identical to the net copy - a setting-out drawing is where things go, and the
              ordering copy must not move anything
  COLOUR      one colour per clip type and no two alike, honoured by dxf/08's layers and by the
              material on every clip mesh in every model
  SERVED      site/downloads is the same DRAWING as the master (a DXF is not reproducible byte
              for byte); the SVGs, which are, are compared byte for byte
  CSV         the three groupings in each schedule sum to the same total, and the spec columns
              carry the family's real lengths and hole counts
  MODEL       every GLB holds as many clips as the schedule says, per board and per code

Run data/check_dxf.py and data/check_sheets.py alongside it for the drawing-quality half:
this file checks the numbers, those two check that a reader can see them.
"""
import io, sys, os, json, math, csv, itertools, hashlib, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import ezdxf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
os.chdir(ROOT)
D = json.load(open('site/data/boards.json', encoding='utf-8'))
S = D['summary']
RAILS = {r['code']: r for r in S['rails']}
GAP, END_MAX = S['rail_gap'], S['rail_end_max']
FLAT, SLIP_W = 68.0, 65.0
bad = []


def ck(cond, msg):
    if not cond:
        bad.append(msg)


# ---------------------------------------------------------------- holding and schedule
cnt = {}
for b in D['boards']:
    for rc in b['rails']:
        cnt[rc['code']] = cnt.get(rc['code'], 0)+1
    covered = {i for rc in b['rails'] for i in rc['covers']}
    for i, p in enumerate(b['pieces']):
        if i not in covered:
            cnt[p['c']] = cnt.get(p['c'], 0)+1
ck(cnt == {e['code']: e['qty'] for e in S['clips']},
   'clip schedule %s != clips drawn %s' % ({e['code']: e['qty'] for e in S['clips']}, cnt))
ck(sum(len(b['pieces']) for b in D['boards']) == S['brick_total'], 'brick total')
ck(sum(e['qty'] for e in S['bricks']) == S['brick_total'], 'brick catalogue total')
ck(sum(e['qty'] for e in S['clips']) == S['clip_total'], 'clip catalogue total')
for b in D['boards']:
    cov = set()
    for lc in b['rails']:
        cov.update(lc['covers'])
    # A slip may sit on more than one rail and often does - board 1's fourth slip carries the end
    # of one R700, an R100 and an R50 - so what has to hold is that every slip is either on a rail
    # or has a clip of its own, not that it is on exactly one.
    own = {i for i in range(len(b['pieces'])) if i not in cov}
    ck(own | cov == set(range(len(b['pieces']))),
       'board %d: %d own + %d covered != %d pieces' % (b['idx'], len(own), len(cov),
                                                       len(b['pieces'])))
    onrails = {lc['code'] for lc in b['rails']}
    for i in cov:
        ck(b['pieces'][i]['c'] in onrails, 'board %d: piece %d is covered but reads %s'
           % (b['idx'], i, b['pieces'][i]['c']))

# ---------------------------------------------------------------- the rails
# Every rail is one of the supplier's lengths, drawn at that length, with that length's holes.
for b in D['boards']:
    ck(not (b['joint'] <= FLAT-SLIP_W+1e-9 and b['rails']),
       'board %d has a %g joint and %d rails' % (b['idx'], b['joint'], len(b['rails'])))
    for rc in b['rails']:
        spec = RAILS.get(rc['code'])
        ck(spec is not None, 'board %d: rail %s is not on the schedule' % (b['idx'], rc['code']))
        if not spec:
            continue
        k = rc['k']
        e = sorted(math.dist(k[i-1], k[i]) for i in range(4))
        # sorted against sorted: an R50 tray is 68 x 50, so its LONGEST edge is the flat and its
        # shortest is the length - the other way round from every other rail
        want = sorted((spec['length'], FLAT))
        ck(abs(e[0]-want[0]) < 0.05 and abs(e[3]-want[1]) < 0.05,
           'board %d %s is %.1f x %.1f' % (b['idx'], rc['code'], e[3], e[0]))
        ck(len(rc['holes']) == len(spec['holes']),
           'board %d %s has %d holes, the drawing says %d'
           % (b['idx'], rc['code'], len(rc['holes']), len(spec['holes'])))
        hs = sorted(rc['holes'])
        d = [math.dist(hs[i], hs[i+1]) for i in range(len(hs)-1)]
        want = [spec['holes'][i+1]-spec['holes'][i] for i in range(len(spec['holes'])-1)]
        ck(len(d) == len(want) and all(abs(a-c) < 0.05 for a, c in zip(d, want)),
           'board %d %s hole spacing %s, the drawing says %s' % (b['idx'], rc['code'], d, want))

# ------------------------------------------------------- how the rails sit on their run
# Read off the exported geometry, not off rails9: the packer saying it obeyed its own rules is
# not evidence.  Every run is rebuilt from the trays and the slips as they were written out.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import runs9                                                        # noqa: E402
GRIP = 50.0

for b in D['boards']:
    if not b['rails']:
        continue
    for r in runs9.runs(b):
        u, s0, L = r['u'], r['s0'], r['length']
        alng = lambda q: q[0]*u[0]+q[1]*u[1]-s0
        mine = []
        for rc in b['rails']:
            e = [alng(q) for q in rc['k']]
            lo, hi = min(e), max(e)
            v = r['v']
            off = sum(q[0]*v[0]+q[1]*v[1] for q in rc['k'])/4.0
            if -1e-6 <= lo and hi <= L+1e-6 and abs(off-r['t']) < 1e-6:
                mine.append((lo, hi))
        if not mine:
            continue
        mine.sort()
        # Two kinds of run, and each is held to its own rule.  A run of nothing but part slips -
        # board 4's four border courses, 104 stacked on 104 - gets one R50 on the MIDDLE of each
        # slip and deliberately leaves its ends open; anything else is FILLED, both end clips
        # flush with the ends of the course.  Which one this is, is read off the geometry.
        span = [(min(min(q[0]*u[0]+q[1]*u[1]-s0 for q in p['p']),
                     max(q[0]*u[0]+q[1]*u[1]-s0 for q in p['p'])),
                 max(q[0]*u[0]+q[1]*u[1]-s0 for q in p['p'])) for p in r['pieces']]
        part = all(hi-lo <= 120.0+1e-9 for lo, hi in span)
        if part:
            ck(len(mine) == len(span),
               'board %d: a run of %d part slips carries %d clips'
               % (b['idx'], len(span), len(mine)))
            for (lo, hi), (a0, a1) in zip(sorted(span), mine):
                ck(abs((a0+a1)/2.0-(lo+hi)/2.0) < 0.01,
                   'board %d: a clip on a part slip is %.2f off its middle'
                   % (b['idx'], abs((a0+a1)/2.0-(lo+hi)/2.0)))
        else:
            ck(mine[0][0] <= END_MAX+1e-6 and L-mine[-1][1] <= END_MAX+1e-6,
               'board %d: a run is open %.1f / %.1f at its ends, the rule is %g'
               % (b['idx'], mine[0][0], L-mine[-1][1], END_MAX))
            ck(abs(mine[0][0]-(L-mine[-1][1])) < 1e-6,
               'board %d: a run is open %.1f at one end and %.1f at the other'
               % (b['idx'], mine[0][0], L-mine[-1][1]))
        for i in range(1, len(mine)):
            ck(mine[i][0]-mine[i-1][1] >= GAP-1e-6,
               'board %d: two rails are %.2f apart, the rule is %g'
               % (b['idx'], mine[i][0]-mine[i-1][1], GAP))
        for p in r['pieces']:
            sp = [alng(q) for q in p['p']]
            a, bb = min(sp), max(sp)
            held = max([min(hi, bb)-max(lo, a) for lo, hi in mine
                        if lo-1e-6 <= (a+bb)/2.0 <= hi+1e-6] or [0.0])
            ck(held >= GRIP-1e-6 or p['c'] not in RAILS or held == 0.0,
               'board %d: a rail holds a slip by %.1f over its middle, the rule is %g'
               % (b['idx'], held, GRIP))

# Every course of the same length on a board is set out identically - a fitter works off the
# course below, so ends that wander from one course to the next cannot be built to.
for b in D['boards']:
    if not b['rails']:
        continue
    seen = {}
    for r in runs9.runs(b):
        u, s0, L = r['u'], r['s0'], r['length']
        v = r['v']
        ends = sorted(round(min(q[0]*u[0]+q[1]*u[1]-s0 for q in rc['k']), 3)
                      for rc in b['rails']
                      if abs(sum(q[0]*v[0]+q[1]*v[1] for q in rc['k'])/4.0-r['t']) < 1e-6
                      and -1e-6 <= min(q[0]*u[0]+q[1]*u[1]-s0 for q in rc['k'])
                      and max(q[0]*u[0]+q[1]*u[1]-s0 for q in rc['k']) <= L+1e-6)
        if not ends:
            continue
        key = round(L, 3)
        seen.setdefault(key, []).append(tuple(ends))
    for L, got in seen.items():
        base = max(got, key=len)
        ck(all(set(g) <= set(base) for g in got),
           'board %d: courses %g long are not set out alike, %s'
           % (b['idx'], L, sorted(set(got))))


# ---------------------------------------------------------------- what is IN the models
# Nothing here ever opened a GLB, and that is how 703 clips came to be missing from all nine
# boards with every check green: the model is a deliverable like any other and has to be counted,
# not assumed.  Each clip is welded into one mesh per code, so what is counted is connected
# shells - a fixed number per clip, whatever the length, because the section is the same sweep.
# The number itself is never assumed: it has to divide the schedule exactly and agree across
# every board that uses that code.
def _glb(path):
    raw = open(path, 'rb').read()
    off, ch = 12, {}
    while off < len(raw):
        ln, ty = struct.unpack_from('<II', raw, off)
        ch[ty] = raw[off+8:off+8+ln]
        off += 8+ln
    return json.loads(ch[0x4E4F534A].decode('utf-8')), ch[0x004E4942]


def _shells(G, BIN, mesh):
    n = 0
    for pr in mesh['primitives']:
        a = G['accessors'][pr['attributes']['POSITION']]
        ia = G['accessors'][pr['indices']]
        bv = G['bufferViews'][ia['bufferView']]
        o = bv.get('byteOffset', 0)+ia.get('byteOffset', 0)
        fmt = {5121: 'B', 5123: 'H', 5125: 'I'}[ia['componentType']]
        ix = struct.unpack_from('<%d%s' % (ia['count'], fmt), BIN, o)
        par = list(range(a['count']))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x

        for k in range(0, len(ix), 3):
            r0 = find(ix[k])
            par[find(ix[k+1])] = r0
            par[find(ix[k+2])] = r0
        n += len({find(i) for i in range(a['count'])})
    return n


_per = {}
for b in D['boards']:
    q = os.path.join('site', 'models', 'board_%d.glb' % b['idx'])
    if not os.path.exists(q):
        ck(False, 'board %d has no model' % b['idx'])
        continue
    G, BIN = _glb(q)
    got = {m['name']: _shells(G, BIN, m) for m in G['meshes']
           if m['name'] not in ('backing', 'MORTAR') and not m['name'].startswith('T0')}
    want = {e['code']: e['qty'] for e in b['clips']}
    for c in sorted(set(got) | set(want)):
        g, w = got.get(c, 0), want.get(c, 0)
        ck(w > 0 and g > 0 and g % w == 0,
           'board %d: the model holds %d shells of %s against %d on the schedule'
           % (b['idx'], g, c, w))
        if w and g and g % w == 0:
            _per.setdefault(c, {})[b['idx']] = g//w
for c, per in _per.items():
    ck(len(set(per.values())) == 1,
       '%s is built %s shells per clip on different boards, so a board is short of some'
       % (c, sorted(set(per.values()))))

# ---------------------------------------------------------------- the schedules on paper
# The CSV carries a spec column per clip.  It read 50 mm and 2 holes against every rail on it,
# R700 included, because the catalogue had dropped length and holes and the writer fell back to
# the R50's figures.  Held to the family here, which is where the real numbers are.
sys.path.insert(0, HERE)
import rails9 as _R9                                                # noqa: E402
_rows = list(csv.reader(io.open('site/downloads/clip_schedule.csv', encoding='utf-8-sig')))
_h = _rows[0]
_ci, _cl, _ch = _h.index('件号 CODE'), _h.index('长度 LENGTH mm'), _h.index('孔数 HOLES')
for r in _rows[1:]:
    if r[_ci] not in _R9.FAMILY:
        continue
    ck(abs(float(r[_cl])-_R9.length(r[_ci])) < 1e-6,
       'clip_schedule.csv: %s reads %s mm, the drawing says %g'
       % (r[_ci], r[_cl], _R9.length(r[_ci])))
    ck(int(r[_ch]) == len(_R9.holes(r[_ci])),
       'clip_schedule.csv: %s reads %s holes, the drawing says %d'
       % (r[_ci], r[_ch], len(_R9.holes(r[_ci]))))

# ---------------------------------------------------------------- clashes
def _sep(A, B):
    for P in (A, B):
        for i in range(len(P)):
            ax, ay = P[i][1]-P[i-1][1], P[i-1][0]-P[i][0]
            n = math.hypot(ax, ay) or 1.0
            ax, ay = ax/n, ay/n
            a = [q[0]*ax+q[1]*ay for q in A]
            c = [q[0]*ax+q[1]*ay for q in B]
            if min(a) >= max(c)-1e-6 or min(c) >= max(a)-1e-6:
                return True
    return False


clash = 0
for b in D['boards']:
    cov = {i for lc in b['rails'] for i in lc['covers']}
    Q = [lc['k'] for lc in b['rails']]+[p['k'] for i, p in enumerate(b['pieces']) if i not in cov]
    cell, g = 200.0, {}
    for i, q in enumerate(Q):
        xs = [p[0] for p in q]; ys = [p[1] for p in q]
        for cx in range(int(min(xs)//cell), int(max(xs)//cell)+1):
            for cy in range(int(min(ys)//cell), int(max(ys)//cell)+1):
                g.setdefault((cx, cy), []).append(i)
    seen = set()
    for lst in g.values():
        for i, j in itertools.combinations(sorted(set(lst)), 2):
            if (i, j) in seen:
                continue
            seen.add((i, j))
            if not _sep(Q[i], Q[j]):
                clash += 1
ck(clash == 0, '%d pairs of clip trays overlap' % clash)

# ---------------------------------------------------------------- spare
for e in S['bricks']:
    ck(e['qty'] == sum(x['qty'] for x in e['products']), '%s product split' % e['code'])
    ck(e['spare'] == sum(math.ceil(x['qty']*1.15) for x in e['products']), '%s spare' % e['code'])
ck(S['brick_spare'] == sum(e['spare'] for e in S['bricks']), 'brick spare total')
PROD = {b['idx']: b['product'] for b in D['boards']}
clip_spare = 0
for e in S['clips']:
    per = {}
    for u in e['use']:
        per[PROD[u['board']]] = per.get(PROD[u['board']], 0)+u['qty']
    ck(sum(per.values()) == e['qty'], '%s use split' % e['code'])
    clip_spare += sum(math.ceil(v*1.15) for v in per.values())


# ---------------------------------------------------------------- the ordering copies
def dxf_text(p):
    d = ezdxf.readfile(p)
    return ' | '.join(e.dxf.text for e in d.modelspace() if e.dxftype() == 'TEXT')


def per_board_geom(p):
    """each board's geometry relative to its own datum, so where the panel sits does not count"""
    d = ezdxf.readfile(p)
    lay = {}
    for e in d.modelspace():
        if not e.dxf.layer.startswith('P'):
            continue
        if e.dxftype() == 'LWPOLYLINE':
            lay.setdefault(e.dxf.layer.split('_')[0], []).append(
                [(x, y) for x, y, *_ in e.get_points()])
        elif e.dxftype() == 'CIRCLE':
            lay.setdefault(e.dxf.layer.split('_')[0], []).append(
                [(e.dxf.center.x, e.dxf.center.y)])
    out = {}
    for k, polys in lay.items():
        mx = min(q[0] for pl in polys for q in pl)
        my = min(q[1] for pl in polys for q in pl)
        rel = sorted(tuple(sorted((round(q[0]-mx, 3), round(q[1]-my, 3)) for q in pl))
                     for pl in polys)
        out[k] = (len(polys), hashlib.sha256(repr(rel).encode()).hexdigest()[:12])
    return out


if os.path.exists('dxf/07_bricks_spare15_CN_EN.dxf'):
    t = dxf_text('dxf/07_bricks_spare15_CN_EN.dxf')
    ck('ORDER +15%' in t, 'dxf/07 ordering copy is not labelled as one')
    ck(str(S['brick_spare']) in t, 'dxf/07 ordering copy total %d' % S['brick_spare'])
    for e in S['bricks']:
        ck(str(e['spare']) in t, 'dxf/07 ordering copy qty for %s' % e['code'])
if os.path.exists('dxf/08_setout_spare15_CN_EN.dxf'):
    t = dxf_text('dxf/08_setout_spare15_CN_EN.dxf')
    ck('ORDER SUMMARY' in t, 'dxf/08 ordering copy has no order summary')
    for pz in S['products']:
        ck(pz['product'] in t and str(pz['spare']) in t,
           'dxf/08 ordering copy product %s' % pz['product'])
    ck(str(S['brick_spare']) in t and str(S['brick_total']) in t, 'dxf/08 ordering copy totals')
    a, b = (per_board_geom('dxf/08_setout_CN_EN.dxf'),
            per_board_geom('dxf/08_setout_spare15_CN_EN.dxf'))
    ck(a == b, 'dxf/08 ordering copy has moved the setting-out')

# ---------------------------------------------------------------- one colour per clip type
# A clip of a given length has to look the same wherever it is drawn, and different from every
# other length.  Every rail used to be the one blue on the drawings and the one steel in the
# model, so a course carrying an R700, an R100 and an R50 showed three identical boxes.  The
# palette lives in data/clip_colours.json; what is checked is that everything reads it.
CCOL = S.get('clip_colours') or {}
_used = {e['code'] for e in S['clips']}
for c in sorted(_used):
    ck(c in CCOL, 'clip %s has no colour in the palette' % c)
_lines = [CCOL[c]['line'] for c in sorted(_used) if c in CCOL]
_metal = [CCOL[c]['metal'] for c in sorted(_used) if c in CCOL]
ck(len(set(_lines)) == len(_lines), 'two clip types share a line colour: %s' % _lines)
ck(len(set(_metal)) == len(_metal), 'two clip types share a finish: %s' % _metal)

# dxf/08: a layer per clip type per board, in that type's own index colour
_d8 = ezdxf.readfile('dxf/08_setout_CN_EN.dxf')
_lay = {la.dxf.name: la.dxf.color for la in _d8.layers}
_pal = json.load(open(os.path.join(HERE, 'clip_colours.json'), encoding='utf-8'))
for b in D['boards']:
    on = {rc['code'] for rc in b['rails']}
    cov = {i for rc in b['rails'] for i in rc['covers']}
    on |= {p['c'] for i, p in enumerate(b['pieces']) if i not in cov}
    for c in sorted(on):
        nm = 'P%d_CLIP_%s' % (b['idx'], c.replace('-', '_'))
        ck(nm in _lay, 'dxf/08 has no layer %s' % nm)
        if nm in _lay:
            ck(_lay[nm] == _pal[c]['aci'],
               'dxf/08 layer %s is colour %d, the palette says %d'
               % (nm, _lay[nm], _pal[c]['aci']))

# the models: one material per clip mesh, its base colour the palette's finish
for b in D['boards']:
    q = os.path.join('site', 'models', 'board_%d.glb' % b['idx'])
    if not os.path.exists(q):
        continue
    G, _BIN = _glb(q)
    for m in G['meshes']:
        c = m['name']
        if c not in CCOL:
            continue
        for pr in m['primitives']:
            mat = G['materials'][pr['material']]
            f = mat.get('pbrMetallicRoughness', {}).get('baseColorFactor', [0, 0, 0, 1])
            got = tuple(max(0, min(255, int(round(x*255)))) for x in f[:3])
            wnt = tuple(int(CCOL[c]['metal'][1+2*j:3+2*j], 16) for j in range(3))
            # within a count, not equal to it: 0.30 x 255 is 76.5 and Blender and Python do not
            # round a half the same way
            ck(all(abs(g-w) <= 1 for g, w in zip(got, wnt)),
               'board %d: %s is #%02x%02x%02x in the model, the palette says %s'
               % ((b['idx'], c)+got+(CCOL[c]['metal'],)))

# ---------------------------------------------------------------- served copies and CSVs
# THE SAME DRAWING, not the same bytes.  A DXF is not reproducible byte for byte - ezdxf walks its
# object table in whatever order the handles hash to - so a byte compare here answered "did
# pack_downloads run last", which is not the question.  What is asked instead is whether the two
# files are the same drawing: every entity, its layer, where it is and what it says.  The SVGs are
# reproducible now (fixed hash salt, no date stamp), so those are still compared byte for byte and
# a single changed pixel fails.
def _drawing(p):
    d = ezdxf.readfile(p)
    out = []
    for e in d.modelspace():
        t = e.dxftype()
        g = ''
        if t == 'TEXT':
            g = '%s|%.4f,%.4f|%.4f' % (e.dxf.text, e.dxf.insert[0], e.dxf.insert[1], e.dxf.height)
        elif t == 'MTEXT':
            g = '%s|%.4f,%.4f' % (e.text, e.dxf.insert[0], e.dxf.insert[1])
        elif t == 'LINE':
            g = '%.4f,%.4f,%.4f,%.4f' % (e.dxf.start[0], e.dxf.start[1],
                                         e.dxf.end[0], e.dxf.end[1])
        elif t == 'LWPOLYLINE':
            g = ';'.join('%.4f,%.4f' % (q[0], q[1]) for q in e.get_points('xy'))
        elif t in ('CIRCLE', 'ARC'):
            g = '%.4f,%.4f,%.4f' % (e.dxf.center[0], e.dxf.center[1], e.dxf.radius)
        elif t == 'HATCH':
            g = '%d paths' % len(e.paths)
        out.append('%s|%s|%s' % (t, e.dxf.layer, g))
    return hashlib.sha256('\n'.join(sorted(out)).encode('utf-8')).hexdigest(), len(out)


h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
for a in sorted(os.listdir('dxf'))+['S7_nine_boards_schedule_CN_EN.svg', 'S8_clips_CN_EN.svg',
                                    'S9_bricks_CN_EN.svg']:
    src = os.path.join('dxf' if a.endswith('.dxf') else 'drawings', a)
    dst = os.path.join('site', 'downloads', a)
    if not (os.path.exists(src) and os.path.exists(dst)):
        continue
    if a.endswith('.dxf'):
        ha, na = _drawing(src)
        hb, nb = _drawing(dst)
        ck(ha == hb, 'site/downloads/%s is a different drawing from the master (%d vs %d entities)'
           % (a, na, nb))
    else:
        ck(h(src) == h(dst), 'site/downloads/%s is not the master' % a)
for path, col, want in (('site/downloads/brick_schedule.csv', 6, S['brick_total']),
                        ('site/downloads/clip_schedule.csv', 9, S['clip_total'])):
    rows = list(csv.reader(io.open(path, encoding='utf-8-sig')))[1:]
    tot = {}
    for r in rows:
        tot[r[0]] = tot.get(r[0], 0)+int(r[col])
    ck(set(tot.values()) == {want}, '%s: groupings give %s, want %d'
       % (os.path.basename(path), tot, want))

print('slips %d  ->  order %d        clips %d  ->  order %d'
      % (S['brick_total'], S['brick_spare'], S['clip_total'], clip_spare))
print('rails:  ' + ',  '.join('%s %g mm x %d, %d holes'
                              % (r['code'], r['length'], r['qty'], len(r['holes']))
                              for r in S['rails'])
      + '   |   filled to the ceiling, end clips flush, slack split round the middle one')
print('clips drawn:  ' + ',  '.join('%s %d' % kv for kv in sorted(cnt.items())))
print()
print('CHECKS FAILED: %d' % len(bad))
for x in bad[:30]:
    print('   ', x)
sys.exit(1 if bad else 0)
