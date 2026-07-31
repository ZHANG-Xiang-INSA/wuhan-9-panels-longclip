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
S, L = D['summary'], D['summary']['longclip']
FLAT, SLIP_W = 68.0, 65.0
bad = []


def ck(cond, msg):
    if not cond:
        bad.append(msg)


# ---------------------------------------------------------------- holding and schedule
cnt = {}
for b in D['boards']:
    for _ in b['longs']:
        cnt[L['code']] = cnt.get(L['code'], 0)+1
    for p in b['pieces']:
        if p['c'] != L['code']:
            cnt[p['c']] = cnt.get(p['c'], 0)+1
ck(cnt == {e['code']: e['qty'] for e in S['clips']},
   'clip schedule %s != clips drawn %s' % ({e['code']: e['qty'] for e in S['clips']}, cnt))
ck(sum(len(b['pieces']) for b in D['boards']) == S['brick_total'], 'brick total')
ck(sum(e['qty'] for e in S['bricks']) == S['brick_total'], 'brick catalogue total')
ck(sum(e['qty'] for e in S['clips']) == S['clip_total'], 'clip catalogue total')
for b in D['boards']:
    cov = set()
    for lc in b['longs']:
        for i in lc['covers']:
            ck(i not in cov, 'board %d: piece %d held twice' % (b['idx'], i))
            cov.add(i)
    own = {i for i, p in enumerate(b['pieces']) if p['c'] != L['code']}
    ck(own | cov == set(range(len(b['pieces']))) and not (own & cov),
       'board %d: %d own + %d covered != %d pieces' % (b['idx'], len(own), len(cov),
                                                       len(b['pieces'])))

# ---------------------------------------------------------------- the long clip
ck(abs(2*L['margin']+(L['holes']-1)*L['pitch']-L['length']) < 1e-6,
   '2 x %g + %d x %g != %g' % (L['margin'], L['holes']-1, L['pitch'], L['length']))
for b in D['boards']:
    ck(not (b['joint'] <= FLAT-SLIP_W+1e-9 and b['longs']),
       'board %d has a %g joint and %d long clips' % (b['idx'], b['joint'], len(b['longs'])))
    for lc in b['longs']:
        k = lc['k']
        e = sorted(math.dist(k[i-1], k[i]) for i in range(4))
        ck(abs(e[3]-L['length']) < 0.05 and abs(e[0]-FLAT) < 0.05,
           'board %d long clip is %.1f x %.1f' % (b['idx'], e[3], e[0]))
        ck(len(lc['holes']) == L['holes'], 'board %d long clip has %d holes' % (b['idx'],
                                                                                len(lc['holes'])))
        hs = sorted(lc['holes'])
        d = [math.dist(hs[i], hs[i+1]) for i in range(len(hs)-1)]
        ck(all(abs(x-L['pitch']) < 0.05 for x in d), 'board %d hole pitch' % b['idx'])


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
    cov = {i for lc in b['longs'] for i in lc['covers']}
    Q = [lc['k'] for lc in b['longs']]+[p['k'] for i, p in enumerate(b['pieces']) if i not in cov]
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
print('%s  %g mm x %d,  %d holes at %g,  %g from each end'
      % (L['code'], L['length'], L['qty'], L['holes'], L['pitch'], L['margin']))
print('clips drawn:  ' + ',  '.join('%s %d' % kv for kv in sorted(cnt.items())))
print()
print('CHECKS FAILED: %d' % len(bad))
for x in bad[:30]:
    print('   ', x)
sys.exit(1 if bad else 0)
