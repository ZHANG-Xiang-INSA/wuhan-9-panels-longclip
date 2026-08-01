"""Export everything the site needs as one JSON: board outlines, every slip with its type, the
brick and clip schedules, and where each clip sits on its piece.

Clip placement is worked out here rather than in the browser, because it needs the same
full-width-run test that chose the clip in the first place.  A rail sits centred on that run; a
pocket sits on the piece's own tray outline.
"""
import json, math, os
from panels9_types import classify
from clips9 import (to_local, full_width_run, poly_area, assign, span_at,
                    PROF, SLIP_W, RAIL, pocket_code, TAB_W)
import labels9 as LB

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'site', 'data')
os.makedirs(OUT, exist_ok=True)
P = json.load(open(os.path.join(HERE, 'panels9.json')))
CL = json.load(open(os.path.join(HERE, 'clips9.json')))
COL = json.load(open(os.path.join(HERE, 'pdf_colours.json')))
FLAT = PROF['flat']
CLIP_BY_CODE = {c['code']: c for c in CL['clips']}


def rot(p, c, s, ox, oy, cx, cy):
    """brick-local -> board coordinates"""
    x, y = p[0]+ox, p[1]+oy
    return [cx+x*c-y*s, cy+x*s+y*c]


def ccw(p):
    a = sum(p[i-1][0]*p[i][1]-p[i][0]*p[i-1][1] for i in range(len(p)))
    return list(p) if a > 0 else list(p)[::-1]


def _elen(p):
    return [math.hypot(p[i][0]-p[i-1][0], p[i][1]-p[i-1][1]) for i in range(len(p))]


def place_tray(loc, clip):
    """the clip's own tray outline, put down on this instance of the piece

    A pocket's fold flags are per TYPE and are read by index, but classify() hands out each
    instance's outline starting at whichever vertex the generator happened to emit first: on board
    3 the same cut piece arrives with its 10.7 mm stub at index 0 on twelve pieces, at index 3 on
    seventeen more and at index 1 on the last five.  Exporting that raw polygon and indexing it
    with the type's flags folded 22 of the 34 clips on the wrong two edges in the 3D model, and
    every check agreed with it, because they all rebuilt the runs from the same misaligned polygon.

    So the piece is turned CCW, rotated onto the clip's own vertex order, and then the clip's real
    tray - the thing the drawings dimension, 68 across where the drawings say 68 - is fitted onto
    it.  What is exported is the metal, in the clip's own edge order, on every instance.
    """
    p = ccw(loc)
    ref, base = [tuple(q) for q in clip['piece']], [tuple(q) for q in clip['base']]
    n = len(p)
    if len(ref) != n:
        return [list(q) for q in p]
    a, b = _elen(p), _elen(ref)
    # edge i of p[k:]+p[:k] is edge (i+k) of p, so score the cyclic shifts against the clip's
    k = min(range(n), key=lambda k: sum(abs(a[(i+k) % n]-b[i]) for i in range(n)))
    p = p[k:]+p[:k]
    # rigid fit, rotation only: the merged types differ by up to 0.8 mm, so take the least-squares
    # angle over every vertex rather than trusting one edge
    cx, cy = sum(q[0] for q in ref)/n, sum(q[1] for q in ref)/n
    dx, dy = sum(q[0] for q in p)/n, sum(q[1] for q in p)/n
    num = sum((ref[i][0]-cx)*(p[i][1]-dy)-(ref[i][1]-cy)*(p[i][0]-dx) for i in range(n))
    den = sum((ref[i][0]-cx)*(p[i][0]-dx)+(ref[i][1]-cy)*(p[i][1]-dy) for i in range(n))
    th = math.atan2(num, den)
    c, s = math.cos(th), math.sin(th)
    return [[dx+(q[0]-cx)*c-(q[1]-cy)*s, dy+(q[0]-cx)*s+(q[1]-cy)*c] for q in base]


STAGGER_BELOW = 7.0     # joints under this stagger the rails; 7 and 10 sit aligned


def bias(p, obj, rect):
    """which side of the piece's own centre the rail sits on, -1, 0 or +1

    The rail's flat is 68 across a 65 slip, so it stands 1.5 proud on each side and needs 3 mm of
    joint to itself.  Below a 7 mm joint the course pitch leaves too little between neighbouring
    rails to work with, so the rail is slid wholly to one side of the slip's own midpoint and the
    side alternates course by course: the two then touch at a corner instead of running into each
    other.  At 7 mm and above - boards 4 at 7 and the rest at 10 - there is room to spare and the
    rails sit square on their slips, aligned course to course, which is easier to set out and
    easier to check.
    """
    if rect is None or p['J'] >= STAGGER_BELOW - 0.01:
        return 0
    row = int(round(rect[1] / (SLIP_W + p['J'])))
    return -1 if row % 2 == 0 else 1


def rail_quad(loc, w, h, run, t0, t1, axis, length, bias=0):
    """The rail's footprint in brick-local coordinates, centred on the full-width run.

    The first edge is always the rail's own length, so whatever reads this quad knows which pair
    of sides carries the legs.  The old version returned the axis-1 case the other way round,
    which put the legs across the two ENDS of the rail instead of along its sides - every soldier
    and every end-border slip on boards 1, 3 and 4 was clipped the wrong way.

    Across the slip the quad is the rail's real flat, not the piece's own width, so it reads as
    a clamp gripping the 65 face with its legs just outside rather than as a plate lying on it.
    """
    mid = (t0+t1)/2.0
    if bias:
        # sit the rail wholly on one side of the midpoint, still inside the run
        a = mid if bias > 0 else mid-length
    else:
        a = mid-length/2.0
    a = max(t0, min(a, t1-length)) if run >= length else t0
    b = a+length
    sp = span_at(loc, (a+b)/2.0, axis) or (0.0, h if axis == 0 else w)
    c = (sp[0]+sp[1])/2.0
    lo, hi = c-FLAT/2.0, c+FLAT/2.0
    if axis == 0:
        return [[a, lo], [b, lo], [b, hi], [a, hi]]
    return [[lo, a], [lo, b], [hi, b], [hi, a]]


boards = []
for p in P:
    types, pieces = classify(p)
    seq = ([(r, (r['x'], r['y'], r['w'], r['h'])) for r in p.get('rects', [])] +
           [(f, None) for f in p.get('herr', [])])
    out_pieces, used = [], {}
    for (obj, rect), pc in zip(seq, pieces):
        t = types[pc['type']]
        if rect is not None:
            loc = [(0.0, 0.0), (rect[2], 0.0), (rect[2], rect[3]), (0.0, rect[3])]
            w, h = rect[2], rect[3]
            to_board = (lambda q, r=rect: [q[0]+r[0], q[1]+r[1]])
        else:
            loc, w, h = to_local(obj)
            a = math.radians(obj['ang']); c, s = math.cos(a), math.sin(a)
            ox, oy = obj['src'][0], obj['src'][1]
            cx, cy = obj['org']
            to_board = (lambda q, c=c, s=s, ox=ox, oy=oy, cx=cx, cy=cy:
                        rot(q, c, s, ox, oy, cx, cy))
        area = poly_area(loc) or 1.0
        kind, ln, grip, run, t0, t1, axis = assign(loc, w, h, area)
        if kind == 'POCKET':
            code = pocket_code(p['idx'], t['code'], loc)
            cq = place_tray(loc, CLIP_BY_CODE[code])
        else:
            code = 'R50'
            cq = rail_quad(loc, w, h, run, t0, t1, axis, RAIL[0], bias=bias(p, obj, rect))
        used[code] = used.get(code, 0)+1
        out_pieces.append(dict(
            t=pc['type'], c=code,
            # classify() already gives the outline in board coordinates; only the clip quad is
            # built in the slip's own frame and has to be brought across
            # 2 dp, not 1: a 45 deg field rounded to 0.1 shifts each edge by up to 0.07 across
            # the joint, which showed up as 9.81-10.27 on board 3 where the geometry itself is
            # 9.989-10.022.  The extra digit costs a few percent of file size.
            p=[[round(v, 2) for v in q] for q in pc['poly']],
            k=[[round(v, 2) for v in to_board(q)] for q in cq],
            g=round(grip, 3)))

    boards.append(dict(
        idx=p['idx'], w=p['Wd'], h=p['Ht'], joint=p['J'],
        zh=LB.bond(p['idx'])[0], en=LB.bond(p['idx'])[1],
        use=p['use'], finish=p['finish'], colour=COL[str(p['idx'])],
        # nsides travels with the type: a rectangular cut is labelled "147.5 x 65" and a polygonal
        # one "65/92/140", so the page cannot count sides off the label without calling the first
        # one a one-sided brick.
        types=[dict(code=t['code'], kind=t['kind'], qty=t['qty'], colour=t['colour'],
                    label=t['label'], desc=LB.describe(t), area=round(t['area']),
                    nsides=t['nsides'],
                    dims=[round(t['dims'][0], 1), round(t['dims'][1], 1)]) for t in types],
        # provisional; the rails block below rebuilds it once the packing is known, and on a
        # first run from an empty tree clips9.json may not name the rails at all yet
        clips=[dict(code=k, qty=v, **{f: CLIP_BY_CODE.get(k, {}).get(f, '')
                                      for f in ('kind', 'zh', 'en', 'note_zh', 'note_en')})
               for k, v in sorted(used.items())],
        pieces=out_pieces))

# clip geometry for the three orthographic views drawn in the browser
import clips9_dxf as CD
clipgeo = {}
for c in CL['clips']:
    base, lipped, hs = CD.geom(c)
    xs = [q[0] for q in base]; ys = [q[1] for q in base]
    clipgeo[c['code']] = dict(
        base=[[round(q[0]-min(xs), 2), round(q[1]-min(ys), 2)] for q in base],
        lipped=lipped,
        tabs=list(c.get('tabs') or [False]*len(lipped)),
        tab_w=c.get('tab_w', TAB_W),   # the tab was 2 mm before the fold rule changed; R50 has
                                       # no tab and was still shipping that 2.0 as its width
        holes=[[round(q[0]-min(xs), 2), round(q[1]-min(ys), 2)] for q in hs],
        bw=round(max(xs)-min(xs), 1), bh=round(max(ys)-min(ys), 1),
        kind=c['kind'], zh=c['zh'], en=c['en'], qty=c['qty'],
        note_zh=c['note_zh'], note_en=c['note_en'])

prof = dict(flat=FLAT, leg=PROF['leg'], lip=PROF['lip'], angle=PROF['lip_angle'],
            mouth=PROF['mouth'], sheet=PROF['sheet'], hole=3.5, tab_w=TAB_W,
            tip_in=round(PROF['lip']*math.sin(math.radians(PROF['lip_angle'])), 3),
            tip_up=round(PROF['leg']-PROF['lip']*math.cos(math.radians(PROF['lip_angle'])), 3))

# ---------------------------------------------------------------- the rails
# Where a course runs unbroken, a chain of the supplier's stock lengths replaces the row of R50s
# along it.  rails9 does the packing against the runs these nine boards actually offer; no length
# is invented here - the four on offer are 1000, 700, 300 and 100, and their hole positions come
# from the supplier's own drawing.  Each board gains a `rails` list, one entry per rail with its
# code, tray, holes and the pieces it lies on, and a covered piece changes its `c` to that code.
# A piece left over keeps its R50 with the tray the packer put there: clear of the chain's end,
# and on the last slip of a run pushed out to the end, because how far the system reaches is
# measured from there.
import rails9 as RAILS

RAIL_ZH = {'R1000': '通用导轨卡扣 1000', 'R700': '通用导轨卡扣 700', 'R300': '通用导轨卡扣 300',
           'R100': '通用导轨卡扣 100', 'R50': '通用导轨卡扣 50'}
RAIL_EN = {c: 'Universal rail clip %g' % RAILS.length(c) for c in RAILS.FAMILY}
RORD = {c: i for i, c in enumerate(('R1000', 'R700', 'R300', 'R100', 'R50'))}


def _rail_note(code):
    L, hs = RAILS.length(code), RAILS.holes(code)
    at = '，'.join('%g' % h for h in hs)
    return ('M 型卡扣，直段 %g mm。平板 %g 宽贴砖背面，两侧立边 %g 高，边缘 %g mm 唇边内折 %g 度，'
            '开口收至 %g，砖片需压入卡紧。%d 个 %g 直径固定孔，距端部 %s。规格与孔位见'
            ' dxf/guiding_rail_clip_10_types_orthographic.dxf。'
            % (L, FLAT, PROF['leg'], PROF['lip'], PROF['lip_angle'], PROF['mouth'],
               len(hs), 3.5, at),
            'M-section snap clamp, %g mm long. %g flat behind the slip, %g legs, %g lips folded '
            '%g deg in, mouth %g so the slip snaps past. %d off dia %g fixing holes at %s from '
            'the end. Sizes and hole positions per the supplier drawing '
            'guiding_rail_clip_10_types_orthographic.dxf.'
            % (L, FLAT, PROF['leg'], PROF['lip'], PROF['lip_angle'], PROF['mouth'],
               len(hs), 3.5, ', '.join('%g' % h for h in hs)))


for b in boards:
    pl = RAILS.plan(b)
    ix = {id(p): i for i, p in enumerate(b['pieces'])}
    b['rails'] = [dict(code=rc['code'],
                       k=[[round(q[0], 2), round(q[1], 2)] for q in rc['tray']],
                       holes=[[round(q[0], 2), round(q[1], 2)] for q in rc['holes']],
                       covers=sorted(ix[id(q)] for q in rc['covers']))
                  for rc in pl['rails']]
    for rc in pl['rails']:
        for q in rc['covers']:
            q['c'] = rc['code']
    for e in pl['r50']:
        e['piece']['k'] = [[round(v[0], 2), round(v[1], 2)] for v in e['tray']]
    # a rail counts once, however many slips it lies on; everything else counts per piece
    cnt = {}
    for rc in pl['rails']:
        cnt[rc['code']] = cnt.get(rc['code'], 0)+1
    covered = {i for rc in b['rails'] for i in rc['covers']}
    for i, p in enumerate(b['pieces']):
        if i not in covered:
            cnt[p['c']] = cnt.get(p['c'], 0)+1
    b['clips'] = []
    for k in sorted(cnt, key=lambda c: (RORD.get(c, 99), c)):
        base = CLIP_BY_CODE.get(k, {})
        e = dict(code=k, qty=cnt[k], kind=base.get('kind', 'RAIL'),
                 zh=base.get('zh', ''), en=base.get('en', ''),
                 note_zh=base.get('note_zh', ''), note_en=base.get('note_en', ''))
        if k in RAILS.FAMILY:
            e['length'] = RAILS.length(k)
            e['holes'] = len(RAILS.holes(k))
            e['zh'], e['en'] = RAIL_ZH[k], RAIL_EN[k]
            e['note_zh'], e['note_en'] = _rail_note(k)
        b['clips'].append(e)

# ---------------------------------------------------------------- brick product
# The slips are the same size and the same count as before; what is new is which product they are
# cut from, which differs by board and has to travel with every brick record.
PRODUCT = {1: 'L10 Yellow', 2: 'L10 Yellow', 3: 'L10 Yellow',
           4: 'L10 B2', 5: 'L10 B2', 6: 'L10 B2',
           7: 'L10 Grey', 8: 'L10 Grey', 9: 'L10 Grey'}
for b in boards:
    b['product'] = PRODUCT[b['idx']]
    for t in b['types']:
        t['product'] = PRODUCT[b['idx']]

# ---------------------------------------------------------------- ordering summary
# One catalogue across all nine boards, which is what somebody ordering material actually needs.
# T-codes are per board - board 1's T01 and board 8's T01 are both the plain slip, but board 3's T04
# and board 8's T04 are different cut shapes - so summing by code would be wrong and would look
# right, which is worse.  Types are keyed the way panels9_types keys them, on size alone, so the
# same product is one row however it is laid.
def gkey(t):
    # A rectangle can arrive by either path and gets a different label each way: the border
    # generator labels it "147.5 x 65" and the herringbone labels the same kind of piece with its
    # edge signature, "65/65/140/140".  Keying on the label would file one product under two rows.
    # A polygon whose area fills its bounding box is a rectangle, whatever the label says.
    rect = abs(t['area'] - t['dims'][0]*t['dims'][1]) < 1.5
    if rect:
        return ('r', tuple(sorted(t['dims'])), t['kind'] == 'CUT')
    return ('f', t['label'])


KORD = {'WHOLE': 0, 'STD': 1, 'CUT': 2}
cat = {}
for b in boards:
    for t in b['types']:
        e = cat.setdefault(gkey(t), dict(kind=t['kind'], label=t['label'], dims=t['dims'],
                                         nsides=t['nsides'], area=t['area'], qty=0, use=[]))
        e['qty'] += t['qty']
        e['use'].append(dict(board=b['idx'], code=t['code'], qty=t['qty']))
bricks = sorted(cat.values(), key=lambda e: (KORD[e['kind']], -e['qty'], e['label']))
for i, e in enumerate(bricks):
    e['code'] = 'B%02d' % (i+1)
# One shape can be cut from more than one product - the plain 215 x 65 is on all nine boards and so
# is all three - so the row carries the split as well as the total.  Spare is 15 % on top, rounded
# up, and rounded up PER PRODUCT: rounding the shape total and then dividing it would order a
# fraction of a brick from somebody.
for e in bricks:
    per = {}
    for u in e['use']:
        per[PRODUCT[u['board']]] = per.get(PRODUCT[u['board']], 0)+u['qty']
    e['products'] = [dict(product=k, qty=v, spare=int(math.ceil(v*1.15)))
                     for k, v in sorted(per.items())]
    e['spare'] = sum(x['spare'] for x in e['products'])

clipcat = {}
for b in boards:
    for c in b['clips']:
        e = clipcat.setdefault(c['code'], dict(code=c['code'], kind=c['kind'], zh=c['zh'],
                                               en=c['en'], qty=0, use=[]))
        e['qty'] += c['qty']
        e['use'].append(dict(board=b['idx'], qty=c['qty']))
clips_sum = sorted(clipcat.values(), key=lambda e: (e['kind'] != 'RAIL', -e['qty'], e['code']))

# Which brick products each clip serves.  Every slip takes exactly one clip, so a spare slip needs a
# spare clip: ordering the two independently and rounding each up on its own gave 1633 slips against
# 1628 clips, which is arithmetically fine and obviously wrong to anybody reading it.  The page
# derives the clip quantity from the brick quantity through this map, so the two always agree.
bcode = {}
for i, e in enumerate(bricks):
    for u in e['use']:
        bcode[(u['board'], u['code'])] = e['code']
for e in clips_sum:
    e['serves'] = {}
for b in boards:
    for p in b['pieces']:
        t = b['types'][p['t']]
        e = clipcat[p['c']]
        k = bcode[(b['idx'], t['code'])]
        e['serves'][k] = e['serves'].get(k, 0)+1
for e in clips_sum:
    e['serves'] = [dict(brick=k, qty=v) for k, v in sorted(e['serves'].items())]

prodtot = {}
for e in bricks:
    for x in e['products']:
        d = prodtot.setdefault(x['product'], dict(product=x['product'], qty=0, spare=0))
        d['qty'] += x['qty']; d['spare'] += x['spare']
summary = dict(bricks=bricks, clips=clips_sum,
               brick_total=sum(e['qty'] for e in bricks),
               brick_spare=sum(e['spare'] for e in bricks),
               products=[prodtot[k] for k in sorted(prodtot)],
               rails=[dict(code=c, length=RAILS.length(c),
                           holes=RAILS.holes(c),
                           qty=sum(1 for b in boards for r in b['rails'] if r['code'] == c))
                      for c in ('R1000', 'R700', 'R300', 'R100')
                      if any(r['code'] == c for b in boards for r in b['rails'])],
               rail_gap=RAILS.GAP, rail_end_max=RAILS.END_MAX,
               clip_total=sum(e['qty'] for e in clips_sum),
               boards=len(boards))

json.dump(dict(boards=boards, clipgeo=clipgeo, profile=prof, slip=[215, 65, 20], summary=summary),
          open(os.path.join(OUT, 'boards.json'), 'w'), separators=(',', ':'))
print('summary: %d brick types, %d clip types across %d boards'
      % (len(bricks), len(clips_sum), len(boards)))
n = sum(len(b['pieces']) for b in boards)
print('site data: %d boards, %d pieces, %d clip types -> %s'
      % (len(boards), n, len(clipgeo), os.path.normpath(os.path.join(OUT, 'boards.json'))))
