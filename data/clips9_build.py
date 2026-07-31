"""Build the retaining clips for the nine boards: geometry, flat blanks, DXF and drawing sheet.

Two families.

RAIL  a straight length of the M-section: a 68 flat behind the slip, a 15 leg turned up at each
      side, a 10 lip folded 16 deg back in so the mouth closes to 62.5 and the slip snaps past it.
      It grips across the 65 dimension, so it needs a length of slip that is still a full 65 wide.
      One length, R50, covers every whole slip, every standard component and every cut piece with
      a run of full width long enough to take it.

POCKET  for pieces a rail cannot hold: a triangle, or a trapezoid that tapers to a few millimetres.
      Clamping one edge of those lets them swing out about that edge, so the pocket turns a lip up
      on three sides instead and traps the piece.  Each pocket is cut to its own piece.  They were
      tested for merging: the four trapezoids differ only in where the 45 deg saw cut falls, 3 to 9
      mm apart, and a shared pocket either loses the lip on that cut, leaving a two-sided grip, or
      oversails the piece by more than half the joint.  Neither is acceptable, so they stay
      separate.
"""
import json, math, os
import ezdxf
from panels9_types import classify
from clips9 import (PROF, HOLE, CLIP_MIN, GRIP_MIN, LIP_MIN, SLIP_W, RAIL,
                    to_local, full_width_run, poly_area, assign, edges, pocket_code, TAB_W, lip_runs, edge_pts)
import labels9 as LB

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'dxf')
DRW = os.path.join(HERE, '..', 'drawings')
P = json.load(open(os.path.join(HERE, 'panels9.json')))

FLAT, LEG, LIP, ANG = PROF['flat'], PROF['leg'], PROF['lip'], math.radians(PROF['lip_angle'])
TIP_IN = LIP*math.sin(ANG)          # 2.76  how far the lip tip reaches back over the slip
TIP_UP = LEG - LIP*math.cos(ANG)    # 5.39  the height it reaches it at
LEGOUT = (FLAT-SLIP_W)/2.0          # 1.5   the leg stands this far outside the slip face
GRIP = TIP_IN - LEGOUT              # 1.26  so how far the tip ends up over the slip face itself.
                                    # A pocket's outline is the slip's own, so the rail's 62.5
                                    # mouth is not a figure that transfers to it - PK-8T02 is a
                                    # triangle and has no mouth.  What does transfer is this, the
                                    # interference: twice 1.26 is the same 2.5 the rail closes by.
INSET = 3.0                         # an unlipped edge is held back inside the piece by this


def ccw(poly):
    a = sum(poly[i-1][0]*poly[i][1]-poly[i][0]*poly[i-1][1] for i in range(len(poly)))
    return poly if a > 0 else poly[::-1]


def offset_poly(poly, dists):
    """CCW polygon; push edge i (poly[i-1] -> poly[i]) outward by dists[i], then re-intersect"""
    n = len(poly)
    lines = []
    for i in range(n):
        a, b = poly[i-1], poly[i]
        dx, dy = b[0]-a[0], b[1]-a[1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = dy/L, -dx/L                      # outward normal of a CCW polygon
        lines.append((a[0]+nx*dists[i], a[1]+ny*dists[i], dx, dy))
    out = []
    for i in range(n):
        x1, y1, u1, v1 = lines[i]
        x2, y2, u2, v2 = lines[(i+1) % n]
        den = u1*v2-v1*u2
        if abs(den) < 1e-9:
            out.append((x2, y2)); continue
        t = ((x2-x1)*v2-(y2-y1)*u2)/den
        out.append((x1+u1*t, y1+v1*t))
    return out


# Per-type fold plan.  Which edges can be folded is a property of one shape in one position on one
# board, and none of it can be read off the edge lengths, so it is written down.  Each entry maps an
# edge index (edge i runs piece[i-1] -> piece[i]) to how that edge folds - 'lip' for the whole edge,
# 'tab' for a TAB_W stretch at its middle - and an edge not named carries no fold at all.
# 'setback' overrides how far a particular PLAIN edge is held back inside the piece.
#
# PK-3T03  the 91.9 rake is the board's own outline on 29 of the 34 pieces, so a lip there stood
#          1.5 mm of steel proud of the board edge.  The folds move to the two edges that face each
#          other across the 65 face - the 10.7 stub and the 75.7 vertical, exactly antiparallel and
#          64.997 apart - which is the same grip a rail takes, and puts the tray 68.0 across.
#
#          How far the two plain edges are held back decides how much of the short edge is left to
#          fold, and the short edge is the whole grip at that end of the piece, so it is set by
#          measurement rather than by habit.  The top sits in a 10 mm joint and is left flush.  The
#          rake is the board outline and the leg beside it stands 1.5 proud, so at 45 degrees the
#          leg's outer corner crosses the board line 1.06 before the fold would end: every 1 mm of
#          rake setback costs 1.41 mm of fold.  Measured on the real piece:
#
#              rake setback   3.0    2.0    1.0    0.5    0.25   0.0
#              short fold     4.92   6.33   7.75   8.46   8.81   9.16 (on the board line)
#
#          0.5 is the setting: the fold is 8.46 - four fifths of the 10.66 the piece itself has -
#          and the nearest steel is still 0.5 clear of the board outline, twice the 0.25 sheet.
#          3.0 was the blanket figure and left 4.92, too little to hold a slip.
# PK-8T02  a 45-45-90 triangle: three full lips have nowhere for any corner to go, so each edge
#          keeps a tab at its middle, 23 mm clear of the nearest corner at TAB_W = 20.
FOLD = {
    'PK-3T03': dict(
        fold={0: 'lip', 2: 'tab'}, setback={1: 0.5, 3: 0.0},
        why_zh='斜边落在板边上，顶边落在 10 mm 灰缝里，两条都不折；托盘退到斜边内侧 0.5 mm，'
               '板边看不到金属，短边仍能折足 8.5 mm。',
        why_en='The rake is the board outline itself and the top sits in a 10 mm joint, so neither '
               'is folded; the tray stops 0.5 inside the rake, which keeps steel off the board '
               'edge and still leaves the short edge 8.5 of fold.'),
    'PK-8T02': dict(
        fold={0: 'tab', 1: 'tab', 2: 'tab'},
        why_zh='相邻边整条内折会在转角处打架，故每边只在中部留一个小卡扣，离转角 23 mm 以上。',
        why_en='Whole edges folding inward jam in the corners, so each edge keeps only a centre '
               'tab, over 23 mm clear of the nearest corner.'),
}


def pocket(loc, code=None):
    """tray outline, which edges fold and how, and the edge lengths, for one cut piece"""
    p = ccw(loc)
    n = len(p)
    ln = [math.hypot(p[i][0]-p[i-1][0], p[i][1]-p[i-1][1]) for i in range(n)]
    spec = FOLD.get(code)
    if spec is None:
        lipped = [ln[i] >= LIP_MIN for i in range(n)]
        if sum(lipped) < 3:                        # never fewer than three restrained faces
            for i in sorted(range(n), key=lambda k: -ln[k]):
                if not lipped[i]:
                    lipped[i] = True
                if sum(lipped) >= 3:
                    break
        tabs = [False]*n
        back = [INSET]*n
    else:
        f = spec['fold']
        lipped = [i in f for i in range(n)]
        tabs = [f.get(i) == 'tab' for i in range(n)]
        back = [spec.get('setback', {}).get(i, INSET) for i in range(n)]
    # A tab folds in the middle of the edge, so the leg no longer runs the whole side; the tray
    # still stands its 1.5 out there, because that is where the metal has to be for the tab to
    # reach over the slip at all.
    base = offset_poly(p, [LEGOUT if lipped[i] else -back[i] for i in range(n)])
    return base, lipped, ln, tabs


# ---------------------------------------------------------------- assign every piece
CLIPS, ASSIGN = [], []
CLIPS.append(dict(code='RC-50', kind='RAIL', zh='通用导轨卡扣', en='Universal rail clip',
                  length=RAIL[0], qty=0,
                  note_zh='M 型卡扣，直段 50 mm。平板 68 宽贴砖背面，两侧立边 15 高，'
                          '边缘 10 mm 唇边内折 16 度，开口收至 62.5，砖片需压入卡紧。'
                          '2 个 3.5 直径固定孔。',
                  note_en='M-section snap clamp, 50 mm long. 68 flat behind the slip, 15 legs, '
                          '10 lips folded 16 deg in, mouth 62.5 so the slip snaps past. '
                          '2 off dia 3.5 fixing holes.'))

for p in P:
    types, pieces = classify(p)
    seq = ([(r, (r['x'], r['y'], r['w'], r['h'])) for r in p.get('rects', [])] +
           [(f, None) for f in p.get('herr', [])])
    for (obj, rect), pc in zip(seq, pieces):
        t = types[pc['type']]
        if rect is not None:
            loc = [(0.0, 0.0), (rect[2], 0.0), (rect[2], rect[3]), (0.0, rect[3])]
            w, h = rect[2], rect[3]
        else:
            loc, w, h = to_local(obj)
        area = poly_area(loc) or 1.0
        kind, ln, grip, run, t0, t1, axis = assign(loc, w, h, area)
        if kind != 'POCKET':
            CLIPS[0]['qty'] += 1
            ASSIGN.append(dict(panel=p['idx'], type=t['code'], clip='RC-50', grip=round(grip, 3)))
            continue
        code = pocket_code(p['idx'], t['code'], loc)
        ex = next((c for c in CLIPS if c['code'] == code), None)
        if ex is None:
            base, lipped, elen, tabs = pocket(loc, code)
            ex = dict(code=code, kind='POCKET', zh='专用包边卡扣', en='Dedicated pocket clip',
                      panel=p['idx'], type=t['code'], qty=0,
                      piece=[list(q) for q in ccw(loc)], base=[list(q) for q in base],
                      lipped=lipped, tabs=tabs, tab_w=TAB_W,
                      elen=[round(e, 1) for e in elen], area=round(area, 0),
                      nlip=sum(lipped), run=round(run, 1))
            # The note has to say what the part actually is now that two of them fold differently
            # from the rest: a dropped edge and a centre tab are both things a fabricator has to
            # read off the schedule, not only off the drawing.
            # The note has to describe the part that is actually made, so it is built from the
            # flags rather than written out: how many edges fold, which of those are full-length
            # lips and which are centre tabs, that every one of them hooks INWARD - which is the
            # only thing that retains the slip - and why the remaining edges are left flat.
            nfull = sum(1 for i in range(len(lipped)) if lipped[i] and not tabs[i])
            ntab, plain = sum(tabs), len(lipped)-sum(lipped)
            # Quote the folded edges at their own length.  The note used to give only the BRICK's
            # shortest edge, rounded to 11, while the drawing dimensions the CLIP's short edge at
            # 8.5 - two different measurements of two different parts, and it read as one number
            # disagreeing with itself.
            tl = [round(math.hypot(base[i][0]-base[i-1][0], base[i][1]-base[i-1][1]), 1)
                  for i in range(len(base))]
            full = [tl[i] for i in range(len(lipped)) if lipped[i] and not tabs[i]]
            zh, en = [], []
            if nfull:
                zh.append('%d 条边整条折起唇边（边长 %s）'
                          % (nfull, '、'.join('%g' % v for v in full)))
                en.append('%d full-length lip%s, on the %s edge%s'
                          % (nfull, 's' if nfull > 1 else '',
                             ' and '.join('%g' % v for v in full), 's' if nfull > 1 else ''))
            if ntab:
                zh.append('%d 条边%s在中部折一个 %g 宽小卡扣'
                          % (ntab, '各' if ntab > 1 else '', TAB_W))
                en.append('%d centre tab%s %g wide' % (ntab, 's' if ntab > 1 else '', TAB_W))
            spec = FOLD.get(code, {})
            ex['note_zh'] = ('按第 %d 号板 %s 号砖型定制。该砖片最短边 %.1f mm（是砖的边长，'
                             '不是卡扣的边长），整幅无 20 mm 以上'
                             '等宽段，导轨卡扣无处可夹。折边：%s；唇边一律向内折回扣住砖片，'
                             '唇尖压进砖面 %.2f mm，与导轨卡扣的过盈量相同。'
                             '%s2 个 3.5 直径固定孔。'
                             % (p['idx'], t['code'], min(elen), '，'.join(zh), GRIP,
                                spec.get('why_zh', '')))
            ex['note_en'] = ('Made for board %d type %s. The shortest edge of the SLIP is %.1f mm '
                             '(that is the brick, not the clip) and it has no 20 mm run of full '
                             'width, so a rail has nothing to grip. The piece is held by %s; '
                             'every one of them folds INWARD back over the slip, gripping the '
                             'slip face by %.2f mm, the same interference as the rail. '
                             '%s2 off dia 3.5 fixing holes.'
                             % (p['idx'], t['code'], min(elen), ' and '.join(en), GRIP,
                                (spec.get('why_en', '')+' ').lstrip()))
            CLIPS.append(ex)
        ex['qty'] += 1
        ASSIGN.append(dict(panel=p['idx'], type=t['code'], clip=code, grip=1.0))

json.dump(dict(clips=CLIPS, assign=ASSIGN), open(os.path.join(HERE, 'clips9.json'), 'w'), indent=1)

print('%-9s %-8s %-6s %s' % ('clip', 'kind', 'qty', 'covers'))
print('-'*78)
for c in CLIPS:
    if c['kind'] == 'RAIL':
        print('%-9s %-8s %-6d %s' % (c['code'], c['kind'], c['qty'],
                                     'every whole slip, every standard component, every cut piece '
                                     'with a 20 mm run'))
    else:
        print('%-9s %-8s %-6d board %d %s   edges %s   %d lips'
              % (c['code'], c['kind'], c['qty'], c['panel'], c['type'],
                 '/'.join('%g' % e for e in c['elen']), c['nlip']))
print('-'*78)
print('%d clip types for %d pieces' % (len(CLIPS), sum(c['qty'] for c in CLIPS)))
