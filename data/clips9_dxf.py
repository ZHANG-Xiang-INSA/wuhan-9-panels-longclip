# -*- coding: utf-8 -*-
"""Clip drawings for the nine boards, laid out and dimensioned in the same style as
New requirement/guiding rail designs/_gen_guiding_rail.py.

Every type gets FRONT (the face that beds against the slip), TOP (plan, showing where the hook
tips fall) and SIDE (the cross-section), on a fixed grid so the sheet reads in columns.

The section is an M: flat 68, a 15 leg up at each side, then a 10 return lip that hooks INWARD and
down, tip landing 2.75 in from the leg at 5.39 up, leaving a 62.5 clear opening.  The slip is
sprung past the two tips and the lips hold it against the flat.

Holes are dia 3.5.  On the 50 wide clip they sit 12.5 from each end on the centreline, taken
straight from the reference drawing.  On a pocket they are placed by eroding the tray: 8 mm clear
of a plain edge, 12 mm clear of a lipped one, the second figure being the 2.75 the hook reaches
inward plus room for a driver to come down on the screw without fouling it.
"""
import ezdxf, math, json, os
from ezdxf.enums import TextEntityAlignment as TA
from clips9 import lip_runs, edge_pts, TAB_W

W = 68.0; LEG = 15.0; RET = 10.0; THK = 0.25; DEVEL = RET+LEG+W+LEG+RET      # 118
LEGOUT = (W-65.0)/2.0                            # 1.5  the leg stands this far outside a slip
OPEN = 62.5; RIN = (W-OPEN)/2.0                  # 2.75 inward per side
SLIP_W = 65.0                                    # the slip is 2.5 wider than the mouth
ANGV = math.degrees(math.asin(RIN/RET))                                      # 15.96 from the leg
RUP = RET*math.cos(math.radians(ANGV))                                       # 9.614 rise of the lip
DIA = '%%c'                     # the DXF code for the diameter symbol.  It must never go
                               # through the %% operator: '%%%%c' %% x collapses to '%%c', and six
                               # hole call-outs went out reading '2 x %%c3.5' instead of 2 x O3.5.
HD = 3.5; TIPH = W/2-RIN                                                     # 31.25 half-opening
EDGE_MIN, LIP_CLR = 8.0, 12.0                                                # hole clearances

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'clips9.json')))
CLIPS = D['clips']

doc = ezdxf.new('R2010', setup=True); doc.header['$INSUNITS'] = 4
msp = doc.modelspace()
doc.styles.add('CN', font='msyh.ttc')
for n, c in {'OUTLINE': 7, 'HOLE': 1, 'DIM': 8, 'TXT': 7, 'TITLE': 7, 'CL': 4,
             'SECT': 7, 'NOTE': 7, 'BORDER': 7, 'LIP': 1}.items():
    if n not in doc.layers:
        doc.layers.add(n, color=c)
ASZ = 6.0
AMAP = {'LEFT': TA.LEFT, 'BL': TA.BOTTOM_LEFT, 'BC': TA.BOTTOM_CENTER, 'MC': TA.MIDDLE_CENTER,
        'ML': TA.MIDDLE_LEFT, 'MR': TA.MIDDLE_RIGHT, 'BR': TA.BOTTOM_RIGHT}


def Ln_(p0, p1, lay='OUTLINE', col=None):
    a = {'layer': lay}; a.update({'color': col} if col is not None else {})
    msp.add_line(p0, p1, dxfattribs=a)


def PL(pts, lay='OUTLINE', close=False, col=None):
    a = {'layer': lay}; a.update({'color': col} if col is not None else {})
    msp.add_lwpolyline(list(pts)+([pts[0]] if close else []), dxfattribs=a)


def TX(p, s, h=12, lay='TXT', al='LEFT', rot=0, col=None):
    a = {'layer': lay, 'height': h, 'rotation': rot, 'style': 'CN'}
    a.update({'color': col} if col is not None else {})
    t = msp.add_text(s, dxfattribs=a)
    t.set_placement(p, align=AMAP.get(al, TA.LEFT))
    return t


def arr(p, ang):
    for s in (1, -1):
        aa = ang+s*math.radians(20)
        Ln_(p, (p[0]+ASZ*math.cos(aa), p[1]+ASZ*math.sin(aa)), 'DIM')


def hole(x, y):
    msp.add_circle((x, y), HD/2, dxfattribs={'layer': 'HOLE'})
    m = HD/2+2.4
    Ln_((x-m, y), (x+m, y), 'CL'); Ln_((x, y-m), (x, y+m), 'CL')


def strw(s, h):
    return h*sum(1.05 if ord(c) > 0x2E80 else 0.62 for c in s.replace('%%c', 'O'))


def wrap(s, h, width, indent=''):
    """break a note into lines no wider than `width` drawing units

    Notes are bilingual and run long.  Set as single lines they pushed the sheet border out to
    4.6 m to hold one sentence, which is not a drawing anybody can plot.
    """
    out, line = [], ''
    for w in s.split(' '):
        trial = (line+' '+w) if line else w
        if line and strw(trial, h) > width:
            out.append(line); line = indent+w
        else:
            line = trial
    if line:
        out.append(line)
    return out


def dimh(x0, x1, yd, txt=None, yfeat=None, th=11, out='right'):
    if yfeat is not None:
        Ln_((x0, yfeat), (x0, yd), 'DIM'); Ln_((x1, yfeat), (x1, yd), 'DIM')
    Ln_((x0, yd), (x1, yd), 'DIM'); arr((x0, yd), 0); arr((x1, yd), math.pi)
    s = txt if txt is not None else '%g' % round(x1-x0, 2)
    # if the number is wider than the gap it labels, it goes outside, the way it would be placed
    # by hand.  Left inside, it runs across its own extension line.
    if strw(s, th) > abs(x1-x0)*0.9:
        if out == 'left':
            TX((x0-th*0.6, yd+th*0.55), s, th, 'DIM', al='BR')
        else:
            TX((x1+th*0.6, yd+th*0.55), s, th, 'DIM', al='BL')
    else:
        TX(((x0+x1)/2, yd+th*0.55), s, th, 'DIM', al='BC')


def dimv(y0, y1, xd, txt=None, xfeat=None, th=11, left=False):
    if xfeat is not None:
        Ln_((xfeat, y0), (xd, y0), 'DIM'); Ln_((xfeat, y1), (xd, y1), 'DIM')
    Ln_((xd, y0), (xd, y1), 'DIM'); arr((xd, y0), math.pi/2); arr((xd, y1), -math.pi/2)
    s = txt if txt is not None else '%g' % round(y1-y0, 2)
    xt = xd+(-th*1.4 if left else th*1.4)
    if strw(s, th) > abs(y1-y0)*0.9:
        TX((xt, y1+th*0.6), s, th, 'DIM', al='BL', rot=90)
    else:
        TX((xt, (y0+y1)/2), s, th, 'DIM', al='MC', rot=90)


def dim_aln(p0, p1, off, txt, th=11):
    dx = p1[0]-p0[0]; dy = p1[1]-p0[1]; Lh = math.hypot(dx, dy) or 1
    nx, ny = -dy/Lh, dx/Lh
    q0 = (p0[0]+nx*off, p0[1]+ny*off); q1 = (p1[0]+nx*off, p1[1]+ny*off)
    Ln_(p0, q0, 'DIM'); Ln_(p1, q1, 'DIM'); Ln_(q0, q1, 'DIM')
    ang = math.atan2(dy, dx)
    # dimension text reads left to right or bottom to top, never upside down: a 135 deg edge like
    # the hypotenuse of PK-8T02 was labelled at 135 and read back to front on the sheet.
    r = math.degrees(ang) % 180
    rot = r-180 if r > 90 else r
    # the value belongs on the far side of the dimension line from the feature, so it has to follow
    # the SIGN of the offset.  Taking the left normal unconditionally put every outward dim's value
    # back on top of the outline it was measuring - four of the tab widths straddled their own flap.
    sgn = 1.0 if off >= 0 else -1.0
    tx, ty = nx*sgn*th*0.8, ny*sgn*th*0.8
    if strw(txt, th) > Lh*0.9:
        # no room between the arrows, so they turn outward and the value goes past the end, the way
        # it would be placed by hand.  An 8.5 gap with two 6 mm heads inside it is a bowtie.
        arr(q0, ang+math.pi); arr(q1, ang)
        rr = math.radians(rot); rvx, rvy = math.cos(rr), math.sin(rr)
        e = q1 if q1[0]*rvx+q1[1]*rvy >= q0[0]*rvx+q0[1]*rvy else q0
        TX((e[0]+rvx*th*0.7+tx, e[1]+rvy*th*0.7+ty), txt, th, 'DIM', al='ML', rot=rot)
    else:
        arr(q0, ang); arr(q1, ang+math.pi)
        TX(((q0[0]+q1[0])/2+tx, (q0[1]+q1[1])/2+ty), txt, th, 'DIM', al='MC', rot=rot)


def dim_ang(c, r, a0, a1, txt, th=11):
    msp.add_arc(c, r, a0, a1, dxfattribs={'layer': 'DIM'})
    am = math.radians((a0+a1)/2)
    TX((c[0]+(r+30)*math.cos(am), c[1]+(r+30)*math.sin(am)), txt, th, 'DIM', al='MC')


def leader(p0, p1, s, th=11, ha='LEFT'):
    Ln_(p0, p1, 'DIM'); arr(p0, math.atan2(p1[1]-p0[1], p1[0]-p0[0]))
    TX((p1[0]+(4 if ha == 'LEFT' else -4), p1[1]), s, th, 'DIM',
       al='ML' if ha == 'LEFT' else 'MR')


def xsec(cx, cy, sc=1.0, col=None):
    """M-section. The lips hook INWARD: from the leg top at +-b the tip moves toward the centre
    and down, so the two tips face each other across a 62.5 opening."""
    b = W/2*sc; lg = LEG*sc; ri = RIN*sc; ru = RUP*sc
    pts = [(cx-b+ri, cy+lg-ru), (cx-b, cy+lg), (cx-b, cy), (cx+b, cy),
           (cx+b, cy+lg), (cx+b-ri, cy+lg-ru)]
    PL(pts, 'SECT', col=col)
    return pts


# ---------------------------------------------------------------- hole placement
def poly_holes(base, lipped):
    """two hole centres inside the tray, clear of every edge and of the inward hooks"""
    xs = [q[0] for q in base]; ys = [q[1] for q in base]
    cand = []
    x = min(xs)
    while x <= max(xs):
        y = min(ys)
        while y <= max(ys):
            if _in(base, (x, y)) and _clear(base, lipped, (x, y)):
                cand.append((x, y))
            y += 1.0
        x += 1.0
    if not cand:
        return []
    best, bd = None, -1.0
    for i, a in enumerate(cand):
        for b in cand[i+1:]:
            d = math.hypot(a[0]-b[0], a[1]-b[1])
            if d > bd:
                bd, best = d, (a, b)
    if bd < 2*HD:
        return [cand[len(cand)//2]]
    return list(best)


def _in(poly, pt):
    x, y = pt; c = False
    for i in range(len(poly)):
        a, b = poly[i-1], poly[i]
        if (a[1] > y) != (b[1] > y):
            if x < a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                c = not c
    return c


def _clear(poly, lipped, pt):
    for i in range(len(poly)):
        a, b = poly[i-1], poly[i]
        dx, dy = b[0]-a[0], b[1]-a[1]
        L2 = dx*dx+dy*dy or 1.0
        t = max(0.0, min(1.0, ((pt[0]-a[0])*dx+(pt[1]-a[1])*dy)/L2))
        d = math.hypot(pt[0]-(a[0]+t*dx), pt[1]-(a[1]+t*dy))
        if d < (LIP_CLR if lipped[i] else EDGE_MIN):
            return False
    return True


def blank_flaps(base, lipped, tabs=None, tab_w=TAB_W):
    """one unfolded flap per lipped RUN: a whole edge for a full lip, a short tab for a tab"""
    out = []
    tabs = tabs or [False]*len(base)
    for i in range(len(base)):
        a, b = base[i-1], base[i]
        for (t0, t1) in lip_runs(a, b, lipped[i], tabs[i], tab_w):
            p0, p1 = edge_pts(a, b, t0, t1)
            dx, dy = b[0]-a[0], b[1]-a[1]
            L = math.hypot(dx, dy) or 1.0
            nx, ny = dy/L, -dx/L
            out.append(([p0, p1, (p1[0]+nx*(LEG+RET), p1[1]+ny*(LEG+RET)),
                         (p0[0]+nx*(LEG+RET), p0[1]+ny*(LEG+RET))],
                        [(p0[0]+nx*LEG, p0[1]+ny*LEG), (p1[0]+nx*LEG, p1[1]+ny*LEG)],
                        math.hypot(p1[0]-p0[0], p1[1]-p0[1])))
    return out


def geom(c):
    if c['kind'] == 'RAIL':
        Lg = c['length']
        base = [(0.0, 0.0), (Lg, 0.0), (Lg, W), (0.0, W)]
        # Edge i runs base[i-1] -> base[i] everywhere in this project: clips9_build.offset_poly
        # defines it that way and writes the pocket flags to match, and _clear and blank_flaps
        # above read it that way.  On base = [(0,0), (Lg,0), (Lg,FLAT), (0,FLAT)] the two Lg-long
        # sides are therefore edges 1 and 3, not 0 and 2.  The old [True, False, True, False] put
        # the legs on the two 68-long sides, so every drawing and the 3D model carried a rail
        # lipped across its width instead of along its length.
        lipped = [False, True, False, True]
        hs = [(12.5, W/2), (Lg-12.5, W/2)]         # exactly as the reference R50
    else:
        base = [tuple(q) for q in c['base']]
        lipped = list(c['lipped'])
        hs = poly_holes(base, lipped)
    return base, lipped, hs


def tabs_of(c):
    return list(c.get('tabs') or [False]*len(c.get('lipped') or [])) or [False]*4


def tabw_of(c):
    """the tab width this clip was built with

    clips9.json carries tab_w per clip.  Reading the module constant instead meant the drawing
    could be regenerated at a new TAB_W while boards.json, the page and the model still held the
    old one, and every cross-check would still pass because they were comparing like with like.
    """
    return float(c.get('tab_w') or TAB_W)


def runs_of(c, base, lipped, tabs, i):
    a, b = base[i-1], base[i]
    return lip_runs(a, b, lipped[i], tabs[i], tabw_of(c))


# ---------------------------------------------------------------- title and notes
def title_block(x, y):
    TX((x, y), 'WUHAN PHOTOGRAPHY BOARDS  -  RETAINING CLIPS  -  ORTHOGRAPHIC DRAWING',
       40, 'TITLE', al='BL')
    TX((x, y-54), '武汉摄影展板　卡扣详图　　3 Monahan Avenue (HA23007)   |   formed sheet-metal '
                  'clip profile   |   FRONT + TOP + SIDE per type', 16, 'TITLE', al='BL')
    notes = [
        'NOTES  说明:',
        '1. ALL DIMENSIONS IN MILLIMETRES.  Drawing 1:1, typical cross-section 3:1.   '
        '全部尺寸单位为毫米，图纸 1:1，典型断面 3:1。',
        '2. MATERIAL: formed steel sheet, thickness 0.25.   材料：冷弯钢板，料厚 0.25。',
        '3. RAIL PROFILE (RC-50 only): flat 68 + leg 15 each side + return lip 10 each side, '
        'developed blank 10+15+68+15+10 = 118.  A POCKET clip has no 68 flat, no second leg and no '
        '62.5 mouth: its tray follows its own piece and only the edges shown folded are folded.   '
        '导轨卡扣（仅 RC-50）断面：平板 68，两侧立边 15，两侧回折唇边 10，展开料 118。包边卡扣无 68 '
        '平板、无对侧立边、无 62.5 开口，托盘随砖形，仅图示折边处折弯。',
        '4. EVERY FOLD ON EVERY TYPE HOOKS INWARD, BACK OVER THE SLIP: leg 15 up, then a 10 lip '
        'returned 16 deg so its tip lands 2.76 inside the leg at 5.39 up.  That is the whole '
        'retention - nothing folds outward anywhere on this drawing.   各型所有折边一律向内折回、'
        '扣住砖片：立边 15，再按 16 度回折唇边 10，唇尖内收 2.76、高 5.39。全靠这道内折夹持，'
        '本图无任何向外折弯。',
        '5. ALL HOLES dia 3.5 (%%c3.5), position dimensioned per type.   全部孔径 3.5，孔位逐型标注。',
        '6. Hole centres are kept 8 clear of a plain edge and 12 clear of a lipped edge, so a '
        'screwdriver reaches the screw without fouling the inward hook.   '
        '孔心距普通边不小于 8，距折唇边不小于 12，确保螺丝刀不被内折唇边挡住。',
        '7. RC-50 hole positions taken from guiding_rail_clip.dwg: 12.5 from each end, on the 68 '
        'centreline.   RC-50 孔位取自导轨卡扣原图：距两端各 12.5，位于 68 中线。',
        '8. A DEVELOPED BLANK is drawn 1:1 for every type.  It shows the flaps UNFOLDED, lying '
        'flat outside the tray; the arrow on each flap is the direction it is folded, always back '
        'toward the inside of the tray.  Red = the bend on the tray edge, blue = the bend at the '
        'top of the leg; the metal beyond the blue line is the return lip.   每型均按 1:1 画出展开图，'
        '图中折边为展平状态、平铺在托盘之外；每个折边上的箭头即折弯方向，一律折向托盘内侧。'
        '红线为料边折弯线，蓝线为立边顶折弯线，蓝线以外为回折唇边。',
        '9. Where two lipped edges meet, both returns fold inward and collide in the corner, so a '
        'fold does not have to run the whole edge.  PK-8T02 keeps a %g wide tab at the middle of '
        'each of its three edges; PK-3T03 folds its short edge in full and takes a %g tab at the '
        'middle of the long edge opposite, gripping across the 65 face the way a rail does.   '
        '两条相邻边同时内折会在转角处打架，故折边不必占满整条边：PK-8T02 三条边各在中部做 %g 宽小卡扣；'
        'PK-3T03 短边整条折起，对面长边中部做 %g 宽小卡扣，与导轨卡扣一样夹住 65 面。'
        % (TAB_W, TAB_W, TAB_W, TAB_W),
        '10. PK-3T03 IS NOT FOLDED ON ITS RAKE OR ITS TOP EDGE.  The rake is the board outline on '
        '29 of the 34 pieces, so a lip there stood 1.5 proud of the finished board.  The tray is '
        'held back 0.5 behind the rake - enough to keep steel off the board edge, and no more, '
        'because every 1 of setback there costs 1.41 of the short edge opposite.  The top edge '
        'sits in a 10 mm joint, never within 7.5 of a board edge, so the tray runs flush with it.   '
        'PK-3T03 的斜边与顶边不折：34 片中有 29 片的斜边就落在板边上，折唇会高出成品板面 1.5。'
        '托盘在斜边处后退 0.5，够挡住金属不外露，且不多退——斜边每退 1 就吃掉对面短边 1.41。'
        '顶边落在 10 mm 灰缝里，离板边最近也有 7.5，故托盘与顶边取齐。',
    ]
    yy = y-96
    for s in notes:
        for k, ln in enumerate(wrap(s, 14, 1700, '    ')):
            TX((x, yy), ln, 14, 'NOTE', al='BL'); yy -= 25
        yy -= 6
    return yy


def typical(x, y):
    SC = 3.0
    TX((x, y), 'RAIL CROSS-SECTION  RC-50  (SCALE 3:1)  -  a pocket has one leg of this, on the '
               'edges shown folded   导轨卡扣断面（RC-50），包边卡扣仅在图示折边处做同样的单侧立边'
               '与唇边', 24, 'TITLE', al='BL')
    cx = x+240; cy = y-190
    b = W/2*SC; lg = LEG*SC; ru = RUP*SC; ri = RIN*SC
    xsec(cx, cy, SC)
    # the reference slip is 65 wide, not OPEN.  Drawn at 62.5 it slid through the hooks with room
    # to spare, which is the opposite of what the section is there to show: the slip is 2.5 wider
    # than the mouth and has to be sprung past the two tips.
    msp.add_lwpolyline([(cx-SLIP_W/2*SC, cy), (cx+SLIP_W/2*SC, cy),
                        (cx+SLIP_W/2*SC, cy+20*SC), (cx-SLIP_W/2*SC, cy+20*SC)],
                       close=True, dxfattribs={'layer': 'DIM', 'color': 8})
    leader((cx+SLIP_W/2*SC, cy+20*SC), (cx+SLIP_W/2*SC+150, cy+20*SC+40),
           'slip 65 x 20 shown for reference  砖片', 14, ha='LEFT')
    dimh(cx-b, cx+b, cy-60, '68', yfeat=cy, th=16)
    dimv(cy, cy+lg, cx+b+56, '15', xfeat=cx+b, th=16)
    dimv(cy, cy+lg, cx-b-56, '15', xfeat=cx-b, th=16, left=True)
    dim_aln((cx+b, cy+lg), (cx+b-ri, cy+lg-ru), 30, '10', th=14)
    msp.add_arc((cx+b, cy+lg), 44, 254.04, 270, dxfattribs={'layer': 'DIM'})
    leader((cx+b-14, cy+lg-40), (cx+b+210, cy-150),
           'return lip hooks 16 deg inward  唇边内折 16 度', 13, ha='LEFT')
    Ln_((cx-TIPH*SC, cy+lg-ru), (cx-TIPH*SC, cy+lg+56), 'DIM', col=8)
    Ln_((cx+TIPH*SC, cy+lg-ru), (cx+TIPH*SC, cy+lg+56), 'DIM', col=8)
    dimh(cx-TIPH*SC, cx+TIPH*SC, cy+lg+56,
         'opening 62.5 between inward hook tips  内折唇尖净开口', th=15)
    leader((cx-b, cy), (cx-b-110, cy-40), 't = 0.25 formed sheet  料厚', 14, ha='RIGHT')

    sx = cx+b+300; sy = cy-20; hh = 40; xb = sx
    PL([(sx, sy), (sx+DEVEL*SC, sy), (sx+DEVEL*SC, sy+hh), (sx, sy+hh)], 'OUTLINE', close=True)
    TX((sx, sy+hh+22), 'DEVELOPED / FLAT BLANK  (SCALE 3:1)   展开料', 16, 'TITLE', al='BL')
    for seg, lab in [(RET, '10'), (LEG, '15'), (W, '68'), (LEG, '15'), (RET, '10')]:
        if xb > sx+0.1:
            Ln_((xb, sy), (xb, sy+hh), 'OUTLINE', col=8)
        dimh(xb, xb+seg*SC, sy-26, lab, yfeat=sy, th=13); xb += seg*SC
    dimh(sx, sx+DEVEL*SC, sy-66, 'developed width 118  展开宽', yfeat=sy-26, th=14)
    return cy-260


def blank_view(c, base, lipped, tabs, hs, ox, oy):
    """DEVELOPED BLANK: the piece as it is cut flat, every fold opened out.

    This is the sheet the laser cuts and the press brake folds, so it is the one view the
    fabricator actually works from.  Each lipped RUN opens out into a flap LEG+RET long standing
    off its edge, with the first bend on the tray edge and the second at LEG.  A tab is the same
    flap taken over TAB_W at the middle of the edge instead of the whole of it.

    (ox, oy) is the top-left corner of the blank's envelope.
    """
    tw = tabw_of(c)
    fl = blank_flaps(base, lipped, tabs, tw)
    pts = list(base)+[p for (quad, fold, L) in fl for p in quad]
    x0 = min(p[0] for p in pts); x1 = max(p[0] for p in pts)
    y0 = min(p[1] for p in pts); y1 = max(p[1] for p in pts)
    dx, dy = ox-x0, oy-(y1-y0)-y0
    T = lambda p: (p[0]+dx, p[1]+dy)
    bx0, bx1, by0, by1 = ox, ox+(x1-x0), oy-(y1-y0), oy

    # the top tray edge's dim lands at reach+42, i.e. 42 above the envelope top whatever the
    # shape, so the title clears that rather than sitting at a fixed 34 and being crossed by it
    TX((ox, oy+74), 'DEVELOPED BLANK  展开图  (1:1)', 13, 'TITLE', al='BL')
    PL([T(q) for q in base], 'OUTLINE', close=True)
    for (quad, fold, L) in fl:
        p0, p1, p2, p3 = [T(p) for p in quad]
        Ln_(p0, p3); Ln_(p1, p2); Ln_(p3, p2)      # the flap, minus the tray edge it grows from
        Ln_(T(fold[0]), T(fold[1]), 'CL')          # second bend, at the top of the leg
        Ln_(p0, p1, 'LIP')                         # first bend, on the tray edge
        fold_arrow(p0, p1, p3)
    for hx, hy in hs:
        hole(hx+dx, hy+dy)

    # every tray edge, so the cut profile is fully dimensioned.  A fixed offset put the dim for
    # the short edge of PK-3T03 straight through the flap that folds off the diagonal next to it,
    # so each dim is pushed out past however far the whole blank reaches in that direction.
    for i in range(len(base)):
        a, b = base[i-1], base[i]
        L = math.hypot(b[0]-a[0], b[1]-a[1])
        if L < 0.8:
            continue
        nx, ny = (b[1]-a[1])/L, -(b[0]-a[0])/L            # outward normal of a CCW tray
        reach = max((p[0]-a[0])*nx+(p[1]-a[1])*ny for p in pts)
        dim_aln(T(a), T(b), -(max(reach, 0.0)+42.0), '%g' % round(L, 1), th=11)

    # Every TAB gets its width dimensioned here.  It was called up only in a note before, so the
    # flaps the laser cuts carried no dimension anywhere on the drawing.  The 15 + 10 through the
    # fold is NOT repeated on each flap: at 1:1 an 11 mm figure on a 95 mm part is large, and three
    # tabs each carrying 15, 10, 25 and its own width buried the blank.  It is dimensioned once, in
    # the edge section alongside, and stated in the note.
    for i in range(len(base)):
        if not (lipped[i] and tabs[i]):
            continue
        for (t0, t1) in runs_of(c, base, lipped, tabs, i):
            q0, q1 = edge_pts(base[i-1], base[i], t0, t1)
            dim_aln(T(q0), T(q1), -(LEG+RET+8.0), '%g' % round(t1-t0, 1), th=11)
    dimh(bx0, bx1, by0-108, '%g' % round(bx1-bx0, 1), yfeat=by0-(LEG+RET+46), th=12)
    dimv(by0, by1, bx0-(LEG+RET+108), '%g' % round(by1-by0, 1), xfeat=bx0-(LEG+RET+46),
         th=12, left=True)
    # A leader off each tab crossed the envelope dimensions and the title, so the tabs are called
    # up once in a note instead.  Centred on an edge whose length is dimensioned above, a tab is
    # fully located by its width.
    ntab = sum(1 for i in range(len(base)) if lipped[i] and tabs[i])
    nlip = sum(1 for i in range(len(base)) if lipped[i] and not tabs[i])
    lines = ['ARROWS SHOW THE FOLD DIRECTION: EVERY FLAP FOLDS TOWARD THE INSIDE OF THE TRAY, '
             'BACK OVER THE SLIP.   箭头为折弯方向：所有折边一律向托盘内侧折回，扣住砖片。',
             'red = bend on the tray edge   blue = bend at the top of the leg   '
             '红线为料边折弯，蓝线为立边顶折弯',
             'every flap folds 15 up then 10 back in at 16 deg, as the EDGE SECTION alongside   '
             '各折边均先立 15，再按 16 度回折 10，见旁边的边缘断面']
    if nlip:
        lines.append('%d x full-length lip, the whole of that edge folded   '
                     '%d 条边整条折起唇边' % (nlip, nlip))
    if ntab:
        lines.append('%d x tab %g wide, centred on its edge - the rest of that edge stays flat   '
                     '%d 条边各在中部做 1 个 %g 宽小卡扣，其余部分不折'
                     % (ntab, tw, ntab, tw))
    if not all(lipped):
        lines.append('%d edge(s) drawn without a flap carry no fold at all   '
                     '%d 条边不做折弯' % (len(base)-sum(lipped), len(base)-sum(lipped)))
    yy = by0-142
    for s in lines:
        for ln in wrap(s, 11, 620, '   '):
            TX((ox, yy), ln, 11, 'NOTE', al='BL'); yy -= 17
        yy -= 4
    return yy-20


def fold_arrow(p0, p1, out):
    """an arrow across a flap pointing back at the tray, i.e. the way the metal folds

    The blank is the one view a fabricator folds from, and it showed its flaps lying flat outside
    the tray with nothing to say which way they go.  Drawn outward and unlabelled, an unfolded flap
    reads as a flap that folds outward, which is exactly how the client read it.
    """
    mx, my = (p0[0]+p1[0])/2.0, (p0[1]+p1[1])/2.0
    ux, uy = out[0]-p0[0], out[1]-p0[1]
    n = math.hypot(ux, uy) or 1.0
    ux, uy = ux/n, uy/n
    a = (mx+ux*(LEG+RET)*0.86, my+uy*(LEG+RET)*0.86)
    b = (mx+ux*(LEG+RET)*0.12, my+uy*(LEG+RET)*0.12)
    Ln_(a, b, 'LIP')
    # arr() draws its two barbs FROM the point, at +-20 deg about the angle given, so the angle has
    # to be the one pointing back up the shaft.  Given the forward angle the barbs opened out past
    # the tip and the arrow read as pointing the other way - the opposite of what it is here for.
    arr(b, math.atan2(a[1]-b[1], a[0]-b[0]))


def side_view(c, ox, oy):
    """the cross section of THIS clip, not of the rail

    A pocket has no 68 flat, no second leg and no 62.5 mouth: it follows its piece, so its width is
    whatever the plan says and differs edge to edge.  Stamping the rail M-section on all three
    panels dimensioned two parts that do not exist - the same fault the S8 sheet and the web page
    were fixed for, which this file never got.  A pocket gets the section through one folded edge
    instead: the tray, one leg, its return lip, and the slip the lip closes on.
    """
    if c['kind'] == 'RAIL':
        xsec(ox, oy, 1.0); b = W/2
        dimh(ox-b, ox+b, oy-26, '68', yfeat=oy, th=11)
        dimv(oy, oy+LEG, ox+b+30, '15', xfeat=ox+b, th=11)
        Ln_((ox-TIPH, oy+LEG-RUP), (ox-TIPH, oy+LEG+22), 'DIM', col=8)
        Ln_((ox+TIPH, oy+LEG-RUP), (ox+TIPH, oy+LEG+22), 'DIM', col=8)
        dimh(ox-TIPH, ox+TIPH, oy+LEG+22, '62.5', th=11)
        TX((ox-b, oy-46), 't = 0.25  |  both lips hook 16 deg inward  |  opening 62.5',
           11, 'NOTE', al='BL')
        return
    b = 46.0
    PL([(ox+RIN, oy+LEG-RUP), (ox, oy+LEG), (ox, oy), (ox+b, oy)], 'SECT')
    msp.add_lwpolyline([(ox+LEGOUT, oy), (ox+b, oy), (ox+b, oy+20.0), (ox+LEGOUT, oy+20.0)],
                       close=True, dxfattribs={'layer': 'DIM', 'color': 8})
    dimv(oy, oy+LEG, ox-30, '15', xfeat=ox, th=11, left=True)
    leader((ox+RIN*0.5, oy+LEG-RUP*0.5), (ox+b*0.72, oy+LEG+42),
           'lip %g hooks 16 deg INWARD, tip lands %g over the slip face   '
           '唇边 %g 向内折 16 度，唇尖压住砖片 %g'
           % (RET, round(RIN-LEGOUT, 2), RET, round(RIN-LEGOUT, 2)), 11, ha='LEFT')
    TX((ox-30, oy-46), 't = 0.25  |  leg stands %g outside the slip  |  no 68 flat and no mouth: '
       'the tray follows the piece   料厚 0.25，立边在砖外 %g，托盘随砖形，无 68 平板与 62.5 开口'
       % (LEGOUT, LEGOUT), 11, 'NOTE', al='BL')
    TX((ox+b, oy+22), 'slip 20 thick  砖片', 11, 'NOTE', al='BL')


HDR = 190


def panel(c, ox, oy):
    base, lipped, hs = geom(c)
    xs = [q[0] for q in base]; ys = [q[1] for q in base]
    bw, bh = max(xs)-min(xs), max(ys)-min(ys)
    TX((ox, oy), c['code'], 26, 'TITLE', al='BL')
    TX((ox, oy-30), '%s %s   QTY = %d pcs' % (c['zh'], c['en'], c['qty']), 14, 'TITLE', al='BL')

    # FRONT VIEW
    TX((ox, oy-62), 'FRONT VIEW  正视图', 13, 'TITLE', al='BL')
    yF = oy-HDR-bh
    dx, dy = ox-min(xs), yF-min(ys)
    P0 = [(q[0]+dx, q[1]+dy) for q in base]
    PL(P0, 'OUTLINE', close=True)
    tb0 = tabs_of(c)
    for i in range(len(P0)):
        a, b = P0[i-1], P0[i]
        for (t0, t1) in lip_runs(a, b, lipped[i], tb0[i], tabw_of(c)):
            q0, q1 = edge_pts(a, b, t0, t1)
            Ln_(q0, q1, 'LIP')
    for hx, hy in hs:
        hole(hx+dx, hy+dy)
    dimh(ox, ox+bw, yF-40, '%g' % round(bw, 1), yfeat=yF, th=13)
    dimv(yF, yF+bh, ox-172, '%g' % round(bh, 1), xfeat=ox, th=12, left=True)
    if hs:
        hx_s = sorted(hs)
        chain = [min(xs)]+[h[0] for h in hx_s]+[max(xs)]
        for k in range(len(chain)-1):
            if chain[k+1]-chain[k] < 1.0:           # a hole sitting on the outline edge
                continue
            dimh(chain[k]+dx, chain[k+1]+dx, yF+bh+50, '%g' % round(chain[k+1]-chain[k], 1),
                 yfeat=yF+bh, th=11, out='left' if k == 0 else 'right')
        # the hole height goes on the left, opposite the dia 3.5 leader, so the two never meet
        dimv(yF, sorted(hs)[0][1]+dy, ox-112, '%g' % round(sorted(hs)[0][1]-min(ys), 1),
             xfeat=ox, th=11, left=True)
        leader((sorted(hs)[-1][0]+dx, sorted(hs)[-1][1]+dy),
               (ox+bw+110, sorted(hs)[-1][1]+dy+30), '%d x ' % len(hs)+DIA+'3.5', 12, ha='LEFT')
    TX((ox, yF-66), '%d x ' % len(hs)+DIA+'3.5   red edge = folded, and every fold hooks INWARD'
       '   红线为折边，一律向内折回', 12, 'NOTE', al='BL')

    # TOP VIEW
    yTl = yF-150
    TX((ox, yTl), 'TOP VIEW  俯视图', 13, 'TITLE', al='BL')
    yT = yTl-24-bh
    P1 = [(q[0]+dx, q[1]+(yT-min(ys))) for q in base]
    PL(P1, 'OUTLINE', close=True)
    tb = tabs_of(c)
    for i in range(len(P1)):
        a, b = P1[i-1], P1[i]
        ex, ey = b[0]-a[0], b[1]-a[1]
        L = math.hypot(ex, ey) or 1.0
        nx, ny = -ey/L, ex/L                           # inward normal of a CCW tray
        for (t0, t1) in lip_runs(a, b, lipped[i], tb[i], tabw_of(c)):
            q0, q1 = edge_pts(a, b, t0, t1)
            Ln_((q0[0]+nx*RIN, q0[1]+ny*RIN), (q1[0]+nx*RIN, q1[1]+ny*RIN), 'LIP')
    TX((ox, yT-30), 'inner line = inward hook tip, %g in from the leg   内线为唇尖，'
       '自立边内收 %g' % (RIN, RIN), 11, 'NOTE', al='BL')

    # SIDE VIEW
    sx = ox+max(bw, 150.0)+330
    TX((sx-W/2, oy-62), 'SIDE VIEW  侧视图', 13, 'TITLE', al='BL')
    side_view(c, sx, oy-230)

    # DEVELOPED BLANK, in its own column clear of the top view's note line and the side view's
    yb = blank_view(c, base, lipped, tabs_of(c), hs, ox+max(bw, 150.0)+620, oy-400)
    return min(yT-70, yb)


# ---------------------------------------------------------------- build
yend = title_block(0, 0)
gtop = typical(0, yend-40)
# One type per row.  Two columns fitted the three views but not the developed blank: the blank
# needs a column of its own and its call-up notes are a full text line wide, which ran straight
# into the neighbouring type.  A single column costs sheet height, which is free.
ROWPITCH = 830.0
GTOP = gtop-120
for i, c in enumerate(CLIPS):
    panel(c, 0.0, GTOP-i*ROWPITCH)

import ezdxf.bbox as bb
ext = bb.extents(msp); mn, mx = ext.extmin, ext.extmax; pad = 60
PL([(mn[0]-pad, mn[1]-pad), (mx[0]+pad, mn[1]-pad), (mx[0]+pad, mx[1]+pad),
    (mn[0]-pad, mx[1]+pad)], 'BORDER', close=True)
q = os.path.join(HERE, '..', 'dxf', '06_clips_CN_EN.dxf')
doc.saveas(q)
print('SAVED', os.path.normpath(q), '| entities', len(list(msp)),
      '| x[%.0f..%.0f] y[%.0f..%.0f]' % (mn[0], mx[0], mn[1], mx[1]))
