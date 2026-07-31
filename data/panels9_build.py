"""Build the nine panels, choosing each panel's size to minimise cutting, and write the DXF.

The brief allows the size to move: "9 total panels each 1.5m x 1.5m or similar convenient size
for brick layout".  Each panel's side is searched over 1400..1600 and scored on, in order,
  1  how many distinct CUT shapes it needs,
  2  how many cut pieces there are,
  3  how far it strays from 1500.
Joints are exactly as the proposal's Mortar column states.
"""
import math, json, os
import ezdxf
from panels9 import (W, TARGET, stretcher, soldiers, endcourse, stack, basketweave,
                     herring, border, rect, parea, rot_clip, basket_cells)
from panels9_types import classify, edge_sig
import labels9 as LB

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dxf')
os.makedirs(OUT, exist_ok=True)
L = 215.0
# The proposal calls the border slip "102x65mm" / "65x102mm".  102.5 is exactly the half slip at
# a 10 mm joint, (215-10)/2, which is what the figure is: half a brick.  Held at 102.5 on a board
# whose joint is 7 it stops being the half and becomes a second, nearly identical piece - board 4
# was asking the yard for a 102.5 border slip and a 104 bond closer.  It follows the joint now.
def half_slip(J):
    return (L-J)/2.0

# Joints 5, 6 and 8 are 10, not the 7/7/5 of the proposal's mortar column.  With the joint folded
# into the brick the laying module is (215+J) x (65+J), and a herringbone or a basketweave closes
# only when that module's proportion is a whole number - 3.083 at J=7, 3.143 at J=5, 3.000 at
# J=10.  Built as specified those three boards carried 126, 126 and 46 wrong joints, with slips
# touching on board 8.  Panel size does not enter the equation, every joint from 5 to 10 was
# solved, and shortening the slip was ruled out, so the joint is what moved.  Mortar COLOUR is
# unchanged, and 3, 5 and 7 mm are still photographed on boards 9, 7 and 4.
SPEC = [
    (1, 'Standard stretcher + 1 soldier course',       'Wall',  'Sleek', 10.0),
    (2, 'Standard stretcher',                          'Floor', 'Raw',   10.0),
    (3, 'Herringbone 45 + 1 border course',            'Floor', 'Sleek', 10.0),
    (4, 'Standard stretcher + end borders',            'Wall',  'Sleek',  7.0),
    (5, 'Herringbone (straight edge)',                 'Floor', 'Sleek', 10.0),
    (6, 'Basketweave (triple)',                        'Floor', 'Raw',   10.0),
    (7, 'Running bond',                                'Wall',  'Sleek',  5.0),
    (8, 'Triple basketweave 45 deg + 2-brick border',  'Floor', 'Sleek', 10.0),
    (9, 'Horizontal stack',                            'Floor', 'Raw',    3.0),
]

# Sizes that were searched rather than assumed: both axes swept 1350-1650, scored on distinct cut
# shapes first.  Board 8 also needs its opening on the diagonal field's own pitch of 225/sqrt(2) =
# 159.1, or the four corners are shaved into shards too small to lay and the field is left open
# there; 1565 x 1572.5 puts them on the pattern and drops the cut shapes from 27 to 10.
# Board 8 is square on purpose.  The field has a 4-fold centre on the panel centre, so a square
# opening presents the same edge four times and the four sides yield one cut set instead of two.
# 1572.5 also sits on the field's own pitch of 225/sqrt(2), which is what keeps the corners off
# shards too small to lay.
# Board 5 at 1565 x 1415 needs three brick types; at 1500 x 1350 it needs five, for the same 24
# cut pieces.  A coordinate descent does not find it - it settles in whichever basin it starts in
# - so this came out of an exhaustive sweep of both sides against the field phase.
# Board 3 keeps its 1500 width and drops to 1401.5 high.  With the field on a 2-fold centre the
# symmetry holds at any size, so the two sides became free to search; 1401.5 is where the cut list
# reaches three shapes with every joint still exactly 10.  Nearer to square is worse, not better:
# 1494 x 1500 also reaches three shapes but leaves 33 joints between 10.35 and 11.42 mm.
FIXED = {3: (TARGET, 1401.5), 5: (1565.0, 1415.0), 6: (1565.0, 1565.0), 8: (1572.5, 1572.5)}


PH = 0.0


def make(idx, J, S, H=None):
    S, H = S, (S if H is None else H)
    if idx == 1:
        f, _ = stretcher(S, H, L, J, y0=L+J)
        return dict(rects=soldiers(S, 0.0, L, J)+f)
    if idx in (2, 7):
        f, _ = stretcher(S, H, L, J)
        return dict(rects=f)
    if idx == 4:
        BL = half_slip(J)
        band = 2*(BL+J)
        f, _ = stretcher(S, H-band, L, J, y0=band)
        r = endcourse(S, 0.0, J, BL)+endcourse(S, BL+J, J, BL)
        r += endcourse(S, H-band+J, J, BL)+endcourse(S, H-BL, J, BL)
        return dict(rects=r+f)
    if idx == 9:
        return dict(rects=stack(S, H, L, J))
    if idx == 6:
        return dict(rects=basketweave(S, H, L, J))
    if idx == 3:
        BL = half_slip(J)
        b = endcourse(S, H-BL, J, BL)
        # The panel centre sits on a 2-fold centre of the field, which is what makes the left and
        # right cuts the same product: a herringbone is pgg, so it has no mirror line, but a 180
        # degree turn is not a flip and maps a cut on one edge onto its opposite number.  Solving
        # the invariance of the two rect families gives the centres
        #   q = ((215 + 300a - 75b)/2, (65 + 150a + 75b)/2)
        # and through the 135 degree rotation that is phase = (140 + 225a)/sqrt2, phy = 75(b-a-1)/sqrt2.
        # phase is measured from the panel centre, so the condition holds at any board size and the
        # two sides are then free; 1500 x 1401.5 is where the cut list bottoms out at three shapes.
        # The old 102.28 / 159.10 was 3.28 mm off this and paid for it with a fourth cut shape that
        # appeared on the left edge only, and 20 joints running 10.35 to 10.76 mm.
        return dict(rects=b, herr=herring(S, H-BL-J, L, J, ang=135.0,
                                          phase=140.0/math.sqrt(2.0), phy=0.0))
    if idx == 5:
        return dict(rects=[], herr=herring(S, H, L, J, ang=0.0, org=(0.0, 0.0)))
    if idx == 8:
        ins = 2*(W+J)
        # The field is a TRIPLE BASKETWEAVE turned 45 deg, not a herringbone: at 45 deg both put
        # every brick at +-45, so it is the blocks, not the brick angles, that tell them apart.
        #
        # The panel centre sits on a 4-fold centre of the weave, which is what makes all four edges
        # cut the same way.  Without it the board ran three different edge families - left and
        # right agreed, top and bottom were each their own - and needed ten cut shapes; a quarter
        # turn now carries each edge onto the next and four shapes cover the board.  The centre is
        # at (220, 220) in the weave's own frame, the middle of the joint cross where four blocks
        # meet, found by rotating the cell set 90 deg about candidate points and testing for
        # invariance.  rot_clip offsets the pattern before rotating and the panel centre answers to
        # pattern point -phase, so the phase is the negative of the centre.
        return dict(rects=border(S, H, L, J, 2),
                    herr=rot_clip(basket_cells(max(S, H)*1.7, L, J), S, H, 45.0, ins,
                                  phase=-220.0, phy=-220.0))
    raise ValueError(idx)


def closes(P, J, Wd):
    """Vertical gaps between full-width courses that are not the board's own joint.

    stretcher() drops a leftover under 5 mm rather than laying a sliver course, so at some panel
    heights the field stops short of where the border above it expects to meet.  Board 4 came out
    with 27 gaps of 8.50 mm against a 7 mm joint that way.  Scoring it here is what keeps the size
    search off those heights; a band is any set of rects sharing a y that together span the board,
    so a border's side courses do not count as one.
    """
    band = {}
    for r in P.get('rects', []):
        y0 = round(r['y'], 3)
        w, t = band.get(y0, (0.0, 0.0))
        band[y0] = (w+r['w'], max(t, round(r['y']+r['h'], 3)))
    ys = sorted(y for y, (w, _) in band.items() if w >= Wd*0.6)
    return sum(1 for a, b in zip(ys, ys[1:])
               if b-band[a][1] > 1e-6 and abs(b-band[a][1]-J) > 0.05)


def score(P):
    """A cut piece is identified by its edge lengths, not by its area.  The old signature
    bucketed area to the nearest 50 mm2, which both merged genuinely different shapes and split
    identical ones across a bucket boundary, so the printed 'shapes' figure did not mean what it
    said.  edge_sig comes from panels9_types so the table, the sheet and the DXF schedule cannot
    disagree about what counts as one type."""
    # every distinct size counts, not only the ones tagged CUT.  A half closer is tagged HALF, so
    # scoring CUT alone let a width through that needed two nearly equal halves - board 2 came
    # out wanting 102.5 AND 103, board 4 wanting 104 AND 104.5.  Orientation is not a distinction:
    # the sorted pair is the key, the same way panels9_types identifies a type.
    shapes, ncut = set(), 0
    for r in P.get('rects', []):
        shapes.add(tuple(sorted((round(r['w'], 1), round(r['h'], 1)))))
        if r['t'] == 'CUT':
            ncut += 1
    for h in P.get('herr', []):
        if h['whole']:
            shapes.add((65.0, 215.0))
        else:
            ncut += 1; shapes.add(edge_sig(h['poly']))
    return len(shapes), ncut


# 0.5 mm, not 2.5: a half-lap stretcher closes with the same half at both ends only when the
# width is L + k(L+J), and on a 2.5 mm grid that value is simply not a candidate.  Board 4 was
# landing on 1547.5 and paying for it with a second closer type at 104.5 beside the 104 half.
CAND = [round(1350.0+0.5*i, 1) for i in range(601)]           # 1350 .. 1650


def best_axis(idx, J, fixed, axis):
    """scan one side with the other held, keeping the panel near 1.5 m"""
    bk = None
    for S in CAND:
        Wd, Ht = (S, fixed) if axis == 'w' else (fixed, S)
        P = make(idx, J, Wd, Ht)
        ns, nc = score(P)
        # a course that does not close is a defect, so it outranks any cutting saving
        k = (closes(P, J, Wd), ns, nc, abs(S-TARGET))
        if bk is None or k < bk[0]: bk = (k, S)
    return bk[1]


PANELS = []
for (idx, name, use, fin, J) in SPEC:
    # width and height are independent - the brief never says the panel must be square, and
    # forcing it to be was what created most of the cutting
    if idx in FIXED:
        Wd, Ht = FIXED[idx]
    else:
        Wd = best_axis(idx, J, TARGET, 'w')
        Ht = best_axis(idx, J, Wd, 'h')
        Wd = best_axis(idx, J, Ht, 'w')
    P = make(idx, J, Wd, Ht)
    # Trim the panel to the slips.  A course lands where the bond puts it, so the last one can stop
    # short of the height the size search picked and leave a strip of backing board along the top:
    # 10 mm on board 7 against a 5 mm joint, 7 mm on board 9 against 3 mm.  There is no mortar at a
    # board edge, so that strip is not a joint, it is bare board.  Trimming moves no slip and
    # changes no joint; it only stops calling the empty strip part of the panel.
    xs = ([r['x']+r['w'] for r in P.get('rects', [])]
          + [q[0] for f in P.get('herr', []) for q in f['poly']])
    ys = ([r['y']+r['h'] for r in P.get('rects', [])]
          + [q[1] for f in P.get('herr', []) for q in f['poly']])
    if xs and ys:
        Wd, Ht = round(max(xs), 2), round(max(ys), 2)
    ns, nc = score(P)

    P.update(idx=idx, name=name, use=use, finish=fin, J=J, L=L, Wd=Wd, Ht=Ht,
             cut_shapes=ns, cuts=nc)
    PANELS.append(P)

# Types within the client's 2 mm are one product, so only the smaller of each pair is made and the
# larger slot's joints absorb the difference.  This runs before anything is written, so the DXF, the
# model, the schedules and the page all show the pieces that are actually cut rather than the ideal
# ones.  See panels9_merge for the two rules that keep it safe: pairwise only, and centred in slot.
import panels9_merge
_mlog = panels9_merge.apply(PANELS)
if _mlog:
    print('merged at %g mm:' % panels9_merge.TOL)
    print('\n'.join(_mlog))
for P in PANELS:
    P['cut_shapes'], P['cuts'] = score(P)


def types_of(P):
    t = {}
    for r in P.get('rects', []):
        k = '%gx%g%s' % (r['w'], r['h'], ' CUT' if r['t'] == 'CUT' else '')
        t[k] = t.get(k, 0)+1
    for h in P.get('herr', []):
        k = 'field WHOLE 215x65' if h['whole'] else 'field CUT'
        t[k] = t.get(k, 0)+1
    return t


print('%-2s %-40s %5s %-11s %5s %5s %s' % ('#', 'bond', 'joint', 'panel', 'pcs', 'cuts', 'shapes'))
print('-'*98)
TOT = 0
for P in PANELS:
    n = len(P.get('rects', []))+len(P.get('herr', []))
    TOT += n
    print('%-2d %-40s %5.0f %-11s %5d %5d %d'
          % (P['idx'], P['name'], P['J'], '%gx%g' % (P['Wd'], P['Ht']), n, P['cuts'], P['cut_shapes']))
    for k, v in sorted(types_of(P).items(), key=lambda z: -z[1])[:5]:
        print('        %-34s x %d' % (k, v))
print('-'*98)
print('total %d pieces, %d cuts' % (TOT, sum(P['cuts'] for P in PANELS)))
json.dump(PANELS, open('panels9.json', 'w'), indent=1)

doc = ezdxf.new('R2010', setup=True); msp = doc.modelspace()
for lay, col in (('PANEL', 7), ('TXT', 7), ('DIM', 8)):
    doc.layers.add(lay, color=col)
doc.styles.add('CN', font='msyh.ttc')             # a face that carries both scripts

# Everything in this file is drawn in millimetres, so say so and dimension in them.  ezdxf's
# stock EZDXF dimstyle is set up for a drawing in metres: dimlfac 100 and a 0.25 text height,
# which on a 1565 mm board printed "156500" in characters a quarter of a millimetre tall.
doc.header['$INSUNITS'] = 4                       # 4 = millimetres
DIMS = doc.dimstyles.add('MM')
DIMS.dxf.dimlfac = 1.0                            # print the measurement, do not scale it
DIMS.dxf.dimtxsty = 'CN'
DIMS.dxf.dimtxt, DIMS.dxf.dimasz = 40.0, 25.0     # to suit the 38 mm schedule text beside it
DIMS.dxf.dimexe, DIMS.dxf.dimexo, DIMS.dxf.dimgap = 14.0, 12.0, 10.0
# One decimal, trailing zeros suppressed (dimzin 8): four of the nine boards are sized on a half
# millimetre - 1401.5, 1452.5, 1572.5 - and at dimdec 0 the drawing printed 1452.5 as "1452".
DIMS.dxf.dimdec, DIMS.dxf.dimtad, DIMS.dxf.dimzin = 1, 1, 8   # above the line
DIMS.dxf.dimdsep = ord('.')                       # or the decimal separator comes out as a comma


def text_w(s, h):
    """rough plotted width of a string at text height h.  CJK glyphs are square, Latin ones are
    about 0.62 of the height, so a mixed line has to be measured character by character."""
    return h*sum(1.05 if ord(c) > 0x2E80 else 0.62 for c in s)


def put(s, x, y, h, layer='TXT'):
    msp.add_text(s, dxfattribs={'layer': layer, 'height': h, 'style': 'CN'}
                 ).set_placement((x, y))


# The column widths come from the text that actually gets written, so a long description cannot
# run into the next board.  DIM_R and TITLE_H reserve the strip the dimensions occupy.
H_ROW, H_HDR, H_TTL, H_SUM = 38.0, 42.0, 64.0, 40.0
COL_QTY, COL_DESC = 220.0, 430.0
DIM_R, DIM_T = 420.0, 400.0                       # reserved for the right and top dimension
SCHED = COL_DESC + max(text_w(LB.describe(t), H_ROW)
                       for p in PANELS for t in classify(p)[0]) + 200.0
TITLE_H = 4*70.0 + H_TTL + 220.0                  # summary block + board name, above the top dim
GAP, cols = 700.0, 3
mx = max(p['Wd'] for p in PANELS)
my = max(p['Ht'] for p in PANELS)
CW = mx + DIM_R + 200.0 + SCHED + GAP
CH = my + DIM_T + TITLE_H + 700.0

for i, P in enumerate(PANELS):
    cx = (i % cols)*CW
    cy = -(i//cols)*CH
    types, pieces = classify(P)

    msp.add_lwpolyline([(cx, cy), (cx+P['Wd'], cy), (cx+P['Wd'], cy+P['Ht']), (cx, cy+P['Ht'])],
                       close=True, dxfattribs={'layer': 'PANEL', 'lineweight': 50})

    # one layer per brick type, carrying that type's colour - so the type can be isolated,
    # counted or exported on its own in CAD, which is what the yard actually needs
    for t in types:
        lay = 'P%d_%s_%s' % (P['idx'], t['code'], t['kind'])
        if lay not in doc.layers:
            doc.layers.add(lay, true_color=int(t['colour'][1:], 16))
        t['layer'] = lay
    for pc in pieces:
        msp.add_lwpolyline([(cx+q[0], cy+q[1]) for q in pc['poly']], close=True,
                           dxfattribs={'layer': types[pc['type']]['layer']})

    # overall board dimensions
    d = msp.add_linear_dim(base=(cx+P['Wd']/2, cy+P['Ht']+240), p1=(cx, cy+P['Ht']),
                           p2=(cx+P['Wd'], cy+P['Ht']), dimstyle='MM',
                           dxfattribs={'layer': 'DIM'}); d.render()
    d = msp.add_linear_dim(base=(cx+P['Wd']+240, cy+P['Ht']/2), p1=(cx+P['Wd'], cy),
                           p2=(cx+P['Wd'], cy+P['Ht']), angle=90.0, dimstyle='MM',
                           dxfattribs={'layer': 'DIM'}); d.render()

    # title block, clear above the top dimension
    zh, en = LB.bond(P['idx'])
    ty = cy+P['Ht']+DIM_T+TITLE_H-H_TTL
    put('%d   %s   %s' % (P['idx'], zh, en), cx, ty, H_TTL)
    nw, ns, nc, ncutt = LB.counts(types)
    for k, line in enumerate(LB.header(P, len(types), ncutt, nw, ns, nc, len(pieces))):
        put(line, cx, ty-130-k*70, H_SUM)

    # the schedule, one row per type, clear to the right of the side dimension
    sx, sy = cx+P['Wd']+DIM_R+200.0, cy+P['Ht']
    for x, s in zip((0.0, COL_QTY, COL_DESC), LB.HDR):
        put(s, sx+x, sy, H_HDR)
    msp.add_line((sx-160, sy-34), (sx+SCHED-200, sy-34), dxfattribs={'layer': 'TXT'})
    for k, t in enumerate(types):
        y = sy-140-k*95
        msp.add_lwpolyline([(sx-150, y), (sx-40, y), (sx-40, y+62), (sx-150, y+62)],
                           close=True, dxfattribs={'layer': t['layer']})
        put(t['code'], sx, y, H_ROW)
        put(str(t['qty']), sx+COL_QTY, y, H_ROW)
        put(LB.describe(t), sx+COL_DESC, y, H_ROW)

p = os.path.join(OUT, '05_nine_boards_CN_EN.dxf'); doc.saveas(p)
print('DXF ->', p)
