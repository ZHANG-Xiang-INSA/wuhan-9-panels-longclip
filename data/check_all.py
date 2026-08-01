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
  SERVED      site/downloads byte for byte the masters, since the page serves from there
  CSV         the three groupings in each schedule sum to the same total

Run data/check_dxf.py and data/check_sheets.py alongside it for the drawing-quality half:
this file checks the numbers, those two check that a reader can see them.
"""
import io, sys, os, json, math, csv, itertools, hashlib
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
        for i in lc['covers']:
            ck(i not in cov, 'board %d: piece %d held twice' % (b['idx'], i))
            cov.add(i)
    own = {i for i in range(len(b['pieces'])) if i not in cov}
    ck(own | cov == set(range(len(b['pieces']))) and not (own & cov),
       'board %d: %d own + %d covered != %d pieces' % (b['idx'], len(own), len(cov),
                                                       len(b['pieces'])))
    for i in cov:
        ck(b['pieces'][i]['c'] in RAILS, 'board %d: piece %d is covered but reads %s'
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
        ck(abs(e[3]-spec['length']) < 0.05 and abs(e[0]-FLAT) < 0.05,
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

# ---------------------------------------------------------------- served copies and CSVs
h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
for a in sorted(os.listdir('dxf'))+['S7_nine_boards_schedule_CN_EN.svg', 'S8_clips_CN_EN.svg',
                                    'S9_bricks_CN_EN.svg']:
    src = os.path.join('dxf' if a.endswith('.dxf') else 'drawings', a)
    dst = os.path.join('site', 'downloads', a)
    if os.path.exists(src) and os.path.exists(dst):
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
      + '   |   %g apart, at most %g open at each end' % (GAP, END_MAX))
print('clips drawn:  ' + ',  '.join('%s %d' % kv for kv in sorted(cnt.items())))
print()
print('CHECKS FAILED: %d' % len(bad))
for x in bad[:30]:
    print('   ', x)
sys.exit(1 if bad else 0)
