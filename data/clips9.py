"""Assign a retaining clip to every piece on the nine boards.

The clip is the same M-section snap clamp used on the 1500 herringbone board: a 68 wide flat that
sits behind the slip, a 15 leg turned up at each side, and a 10 lip folded 16 degrees back in, so
the mouth closes to 62.5 and the slip has to be snapped past it.  It grips ACROSS the 65 mm
dimension, so what it needs is a length of slip that is still a full 65 wide.

Two rules decide which clip a piece gets:

  * find the longest run along the piece where it is still 65 wide.  A rail clip can only sit on
    that run, and it must not oversail the piece at either end.
  * a rail clip must cover at least 20% of the piece's back face.  Small pieces need a bigger
    share, not a smaller one, because they have less to hold them.

Anything with no 20 mm run of full width - a triangle, or a trapezoid tapering to a point - cannot
be held by a rail at all.  Clamping one edge of those just lets them swing out about that edge, so
they get a pocket clip instead, which turns a lip up on three sides and traps the piece.
"""
import json, math, os
from panels9_types import classify

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, 'panels9.json')))

SLIP_W = 65.0        # the dimension the clip grips across
PROF = dict(flat=68.0, leg=15.0, lip=10.0, lip_angle=16.0, mouth=62.5, sheet=0.25)
HOLE = 3.5           # fixing hole diameter, both rail and pocket clips
CLIP_MIN = 20.0      # no clip is made narrower than this
GRIP_MIN = 0.20      # clip footprint / piece back-face area
LIP_MIN = 30.0       # only turn a lip up on an edge at least this long
RAIL = (50.0, 20.0)  # the rail lengths held in stock, longest first


def to_local(piece, rect=None):
    """piece polygon in the frame of the slip it was cut from, plus that slip's w x h"""
    if rect is not None:
        x, y, w, h = rect
        return [(p[0]-x, p[1]-y) for p in piece], w, h
    ox, oy, w, h = piece['src']
    a = math.radians(piece['ang']); c, s = math.cos(a), math.sin(a)
    cx, cy = piece['org']
    out = []
    for (px, py) in piece['poly']:
        dx, dy = px-cx, py-cy
        out.append((dx*c+dy*s-ox, -dx*s+dy*c-oy))
    return out, w, h


def span_at(poly, t, axis):
    """the polygon's extent across `axis` on the line long==t; None if it does not reach"""
    lo, hi = None, None
    n = len(poly)
    for i in range(n):
        p, q = poly[i-1], poly[i]
        a, b = (p[axis], q[axis])
        if a == b:
            continue
        if min(a, b) <= t <= max(a, b):
            u = (t-a)/(b-a)
            v = p[1-axis] + u*(q[1-axis]-p[1-axis])
            lo = v if lo is None else min(lo, v)
            hi = v if hi is None else max(hi, v)
    return None if lo is None else (lo, hi)


def _run_on(poly, L, axis, need, cap, N=240):
    ok = []
    for i in range(N+1):
        sp = span_at(poly, L*i/N, axis)
        ok.append(sp is not None and need <= (sp[1]-sp[0]) <= cap)
    best, i = (0.0, 0.0, 0.0), 0
    while i <= N:
        if not ok[i]:
            i += 1; continue
        j = i
        while j+1 <= N and ok[j+1]:
            j += 1
        run = L*(j-i)/N
        if run > best[0]:
            best = (run, L*i/N, L*j/N)
        i = j+1
    return best


def full_width_run(poly, w, h, tol=1.0, N=240):
    """Longest interval along the slip where it is still SLIP_W across.

    Two things were wrong here.  The width it looked for was the piece's OWN bounding width, so a
    35 mm sliver counted as "full width" over its whole length and was handed a rail that has
    nothing to clamp - the rail grips across 65, and a piece that never reaches 65 cannot be held
    by one at all.  And the axis was taken from whichever bounding side was longer, which on a
    near-square cut is a coin toss; both are measured now and the better run wins.

    The width is bounded above as well as below.  Without the upper bound any section at least 65
    across counted, so on board 8 T09 - a piece cut off square at one end - the length direction
    measured 97 across and still qualified, and because that run was the longer one the rail was
    laid the wrong way round: the 68 flat along the length, the 50 rail across the 65 face it is
    supposed to grip.  The 65 face is 65, so a 97 section is not it.

    Returns (length, t0, t1, axis).  axis 0 means the run is measured along x.
    """
    need, cap = SLIP_W - tol, SLIP_W + tol
    cand = []
    for axis in (0, 1):
        L = w if axis == 0 else h
        if L <= 0:
            continue
        run, t0, t1 = _run_on(poly, L, axis, need, cap, N)
        cand.append((run, t0, t1, axis))
    cand.sort(key=lambda c: -c[0])
    return cand[0] if cand else (0.0, 0.0, 0.0, 0)


# ---------------------------------------------------------------- how much of an edge is lipped
# A lip does not have to run the whole edge.  Where two lipped edges meet, both fold inward and the
# two returns collide in the corner: on PK-8T02, three edges folding at once leave nowhere for the
# metal to go.  A tab at the middle of the edge folds without ever reaching a corner, so the tab is
# the general case and the full-length lip is the special one.
#
# EVERY fold on every clip hooks INWARD, back over the slip: the leg stands 1.5 outside the slip
# face, rises 15, and the lip returns 10 at 16 degrees so its tip lands 2.756 back inside, 5.386
# up.  That interference - a 62.5 mouth against a 65 slip - is the whole retention.  A tab is a
# short length of exactly that section, not a different part.
TAB_W = 20.0                         # the client's figure for a centre tab, along the edge


def lip_runs(a, b, lipped, tab, tab_w=TAB_W):
    """the stretches of edge a->b that carry a fold, as (t0, t1) distances from a

    Empty for a plain edge, the whole edge for a full lip, and a tab_w length centred on the edge
    for a tab.  Everything that draws or builds a clip reads this, so the drawing, the DXF, the
    model and the page cannot disagree about where the metal is.
    """
    if not lipped:
        return []
    L = math.hypot(b[0]-a[0], b[1]-a[1])
    if not tab:
        return [(0.0, L)]
    if L <= tab_w:
        return [(0.0, L)]
    return [((L-tab_w)/2.0, (L+tab_w)/2.0)]


def edge_pts(a, b, t0, t1):
    """the two points at distances t0 and t1 along a->b"""
    L = math.hypot(b[0]-a[0], b[1]-a[1]) or 1.0
    ux, uy = (b[0]-a[0])/L, (b[1]-a[1])/L
    return (a[0]+ux*t0, a[1]+uy*t0), (a[0]+ux*t1, a[1]+uy*t1)


def poly_area(p):
    return abs(sum(p[i-1][0]*p[i][1]-p[i][0]*p[i-1][1] for i in range(len(p))))/2.0


def edges(poly):
    return [math.hypot(poly[i][0]-poly[i-1][0], poly[i][1]-poly[i-1][1]) for i in range(len(poly))]


def assign(poly, w, h, area):
    """-> (kind, length, grip, run, t0, t1, axis)"""
    run, t0, t1, axis = full_width_run(poly, w, h)
    for r in RAIL:
        if run >= r - 0.01 and (SLIP_W*r)/area >= GRIP_MIN:
            return 'RAIL', r, SLIP_W*r/area, run, t0, t1, axis
    # two short rails, if the run will take them and one alone is not enough grip
    if run >= 2*RAIL[1] and (SLIP_W*2*RAIL[1])/area >= GRIP_MIN:
        return 'RAIL2', RAIL[1], SLIP_W*2*RAIL[1]/area, run, t0, t1, axis
    if run >= RAIL[1]:
        return 'RAILSHORT', RAIL[1], SLIP_W*RAIL[1]/area, run, t0, t1, axis
    return 'POCKET', 0.0, 1.0, run, t0, t1, axis


_PK = {}


def pocket_code(idx, code, loc):
    """one part number per SHAPE, not per board

    A pocket clip is made to a piece's outline, so two boards carrying the same cut piece want the
    same clip.  Naming it after the board it first appears on used to be harmless because no shape
    was ever on two boards; once types within 2 mm are folded into one product, board 3's T03 and
    board 8's T05 are the same piece and must not carry two part numbers.  The first board to use
    the shape names it.
    """
    k = (len(loc), tuple(sorted(round(e, 1) for e in edges(loc))), round(poly_area(loc)))
    return _PK.setdefault(k, 'PK-%d%s' % (idx, code))


rows, need_pocket = [], {}
for p in P:
    types, pieces = classify(p)
    src = (p.get('rects', []), p.get('herr', []))
    seq = ([(r, (r['x'], r['y'], r['w'], r['h'])) for r in p.get('rects', [])] +
           [(f, None) for f in p.get('herr', [])])
    per = {}
    for (obj, rect), pc in zip(seq, pieces):
        t = types[pc['type']]
        if rect is not None:
            loc = [(0.0, 0.0), (rect[2], 0.0), (rect[2], rect[3]), (0.0, rect[3])]
            w, hh = rect[2], rect[3]
        else:
            loc, w, hh = to_local(obj)
        kind, ln, grip, run, t0, t1, axis = assign(loc, w, hh, poly_area(loc) or 1.0)
        key = t['code']
        d = per.setdefault(key, dict(t=t, kind=kind, ln=ln, grip=grip, run=run, qty=0))
        d['qty'] += 1
        if kind == 'POCKET':
            pk = pocket_code(p['idx'], t['code'], loc)
            e = need_pocket.setdefault(pk, dict(
                panel=p['idx'], code=t['code'], qty=0, sig=t['label'],
                area=t['area'], run=run, edges=sorted(round(v) for v in edges(loc) if v >= 2.0)))
            e['qty'] += 1
    rows.append((p['idx'], per))

print('%-3s %-6s %-5s %-9s %-8s %-7s %s' % ('#', 'type', 'qty', 'clip', 'grip', 'run', 'shape'))
print('-'*104)
nrail = npock = 0
for idx, per in rows:
    for code, d in sorted(per.items()):
        t = d['t']
        lab = {'RAIL': 'R%g', 'RAIL2': '2 x R%g', 'RAILSHORT': 'R%g',
               'POCKET': 'pocket'}[d['kind']]
        lab = lab % d['ln'] if '%' in lab else lab
        if d['kind'] == 'POCKET':
            npock += d['qty']
        else:
            nrail += d['qty']
        print('%-3d %-6s %-5d %-9s %-8s %-7.1f %s'
              % (idx, code, d['qty'], lab, '%.0f%%' % (d['grip']*100), d['run'],
                 ('%s %s' % (t['kind'].lower(), t['label']))[:44]))
print('-'*104)
print('%d pieces on rail clips, %d need a pocket clip' % (nrail, npock))
print()
print('pieces with no 20 mm run of full width, i.e. nothing for a rail to grip:')
for k in sorted(need_pocket):
    d = need_pocket[k]
    print('   panel %d  %s  x%-3d  run %5.1f mm   area %6.0f   edges %s'
          % (d['panel'], d['code'], d['qty'], d['run'], d['area'], d['edges']))
json.dump(need_pocket, open(os.path.join(HERE, 'clips9_pockets.json'), 'w'), indent=1)
