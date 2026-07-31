# -*- coding: utf-8 -*-
"""The brick cutting drawing: every type drawn 1:1 as a part, dimensioned edge by edge.

    python data/bricks9_dxf.py    ->  dxf/07_bricks_CN_EN.dxf

dxf/05 shows the nine boards with every slip in place, which is the setting drawing.  This is the
other half: what the yard has to cut, one panel per type, squared up on its longest edge, with
every edge and every angle that is not a right angle dimensioned, and the quantity and the boards
it goes to beside it.  The type codes B01..B12 are the ones site_export.py assigns and the ones
the website's summary table shows, so the two schedules are one schedule.

Layer per type, carrying that type's colour, so a single type can be isolated, counted or
exported on its own in CAD - the same convention dxf/05 uses for the board layouts.
"""
import ezdxf, math, os
from ezdxf.enums import TextEntityAlignment as TA
from bricks9 import types, SLIP

HERE = os.path.dirname(os.path.abspath(__file__))
ASZ = 6.0
# The edge dimensions stand this far off the part, and an angle value sits between the corner and
# them, on the OUTWARD bisector: the inward one points into the material and a 135 degree value
# placed along it landed across the far edge of the part.
DOFF, RARC, RTX = 44.0, 12.0, 26.0
AMAP = {'LEFT': TA.LEFT, 'BL': TA.BOTTOM_LEFT, 'BC': TA.BOTTOM_CENTER, 'MC': TA.MIDDLE_CENTER,
        'ML': TA.MIDDLE_LEFT, 'MR': TA.MIDDLE_RIGHT, 'BR': TA.BOTTOM_RIGHT}

doc = ezdxf.new('R2010', setup=True); doc.header['$INSUNITS'] = 4
msp = doc.modelspace()
doc.styles.add('CN', font='msyh.ttc')
for n, c in {'OUTLINE': 7, 'DIM': 8, 'TXT': 7, 'TITLE': 7, 'NOTE': 7, 'BORDER': 7}.items():
    if n not in doc.layers:
        doc.layers.add(n, color=c)


_SEG, _TXT = [], []          # everything drawn in the current panel, for the angle-value placer


def Ln_(p0, p1, lay='OUTLINE'):
    msp.add_line(p0, p1, dxfattribs={'layer': lay})
    _SEG.append((p0[:2], p1[:2]))


def PL(pts, lay='OUTLINE', close=False):
    msp.add_lwpolyline(pts, close=close, dxfattribs={'layer': lay})
    q = list(pts)+([pts[0]] if close else [])
    _SEG.extend((q[i][:2], q[i+1][:2]) for i in range(len(q)-1))


def _clear(pt, txt, th):
    """is a text box centred at pt clear of everything drawn in this panel so far?

    These parts are 45 to 65 mm across and an angle value is 20 mm wide, so there is no fixed
    offset that works on all twelve: inside a 135 degree corner the value crossed the far edge,
    outside it crossed the two extension lines the edge dimensions run out of that same corner.
    It is placed by trying candidates and taking the first that touches nothing.
    """
    hw, hh = strw(txt, th)/2+3.0, th/2+3.0
    x0, y0, x1, y1 = pt[0]-hw, pt[1]-hh, pt[0]+hw, pt[1]+hh
    for a0, b0, a1, b1 in _TXT:
        if x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1:
            return False
    for a, b in _SEG:
        if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
            return False
        if x0 <= b[0] <= x1 and y0 <= b[1] <= y1:
            return False
        for p, q in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                     ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            d1 = (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
            d2 = (b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0])
            d3 = (q[0]-p[0])*(a[1]-p[1])-(q[1]-p[1])*(a[0]-p[0])
            d4 = (q[0]-p[0])*(b[1]-p[1])-(q[1]-p[1])*(b[0]-p[0])
            if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
                return False
    return True


def _leader_clear(p0, p1):
    """does a leader run from p0 to p1 without crossing a value already placed?"""
    for k in range(21):
        f = k/20.0
        x, y = p0[0]+(p1[0]-p0[0])*f, p0[1]+(p1[1]-p0[1])*f
        for a0, b0, a1, b1 in _TXT:
            if a0 <= x <= a1 and b0 <= y <= b1:
                return False
    return True


def TX(p, s, h=12, lay='TXT', al='LEFT', rot=0):
    t = msp.add_text(s, dxfattribs={'layer': lay, 'height': h, 'rotation': rot, 'style': 'CN'})
    t.set_placement(p, align=AMAP.get(al, TA.LEFT))
    # a conservative axis-aligned box round the glyphs, whatever the rotation, so the angle-value
    # placer can keep off text as well as off lines
    w = strw(s, h)
    ox = {'MC': -w/2, 'BC': -w/2, 'MR': -w, 'BR': -w}.get(al, 0.0)
    oy = {'MC': -h/2, 'ML': -h/2, 'MR': -h/2}.get(al, 0.0)
    r = max(abs(ox), abs(ox+w))+abs(oy)+h
    _TXT.append((p[0]-r, p[1]-r, p[0]+r, p[1]+r) if rot else
                (p[0]+ox, p[1]+oy, p[0]+ox+w, p[1]+oy+h))
    return t


def arr(p, ang):
    """barbs splaying back FROM the apex along ang, so pass the angle back along the shaft"""
    for s in (1, -1):
        aa = ang+s*math.radians(20)
        Ln_(p, (p[0]+ASZ*math.cos(aa), p[1]+ASZ*math.sin(aa)), 'DIM')


def strw(s, h):
    return h*sum(1.05 if ord(c) > 0x2E80 else 0.62 for c in s)


def wrap(s, h, width, indent=''):
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


def dim_aln(p0, p1, off, txt, th=11):
    """aligned dimension, value on the far side of the line from the feature

    Copied from clips9_dxf rather than shared: that file builds its whole drawing at import time,
    so importing it here would write dxf/06 as a side effect of writing dxf/07.
    """
    dx = p1[0]-p0[0]; dy = p1[1]-p0[1]; L = math.hypot(dx, dy) or 1
    nx, ny = -dy/L, dx/L
    q0 = (p0[0]+nx*off, p0[1]+ny*off); q1 = (p1[0]+nx*off, p1[1]+ny*off)
    Ln_(p0, q0, 'DIM'); Ln_(p1, q1, 'DIM'); Ln_(q0, q1, 'DIM')
    ang = math.atan2(dy, dx)
    r = math.degrees(ang) % 180                       # never upside down
    rot = r-180 if r > 90 else r
    sgn = 1.0 if off >= 0 else -1.0
    tx, ty = nx*sgn*th*0.8, ny*sgn*th*0.8
    if strw(txt, th) > L*0.9:
        arr(q0, ang+math.pi); arr(q1, ang)            # too tight: heads out, value past the end
        rr = math.radians(rot); rvx, rvy = math.cos(rr), math.sin(rr)
        far = q1 if q1[0]*rvx+q1[1]*rvy >= q0[0]*rvx+q0[1]*rvy else q0
        near = q0 if far is q1 else q1
        # B04's 10.7 edge has an adjacent dimension line running right where the value wants to
        # be, so both ends and a few further steps out are tried and the first clear one taken.
        w = strw(txt, th)
        for e, sgn in ((far, 1.0), (near, -1.0)):
            for k in (0.7, 1.6, 2.6, 3.8):
                pt = (e[0]+sgn*rvx*(th*0.7+w*(k-0.7))+tx, e[1]+sgn*rvy*(th*0.7+w*(k-0.7))+ty)
                cen = (pt[0]+sgn*rvx*w/2, pt[1]+sgn*rvy*w/2)
                if _clear(cen, txt, th):
                    TX(pt, txt, th, 'DIM', al='ML' if sgn > 0 else 'MR', rot=rot)
                    return
        TX((far[0]+rvx*th*0.7+tx, far[1]+rvy*th*0.7+ty), txt, th, 'DIM', al='ML', rot=rot)
    else:
        arr(q0, ang); arr(q1, ang+math.pi)
        TX(((q0[0]+q1[0])/2+tx, (q0[1]+q1[1])/2+ty), txt, th, 'DIM', al='MC', rot=rot)


def dim_ang(c, r, a0, a1, txt, th=9):
    """arc in the corner, value on the bisector at the first radius that is clear

    Inside first, which is where an angular dimension belongs; then further out past the edge
    dimensions if the part is too small to hold it.  A leader is drawn whenever the value has had
    to leave the arc, so it is never ambiguous which corner it belongs to.
    """
    msp.add_arc(c, r, a0, a1, dxfattribs={'layer': 'DIM'})
    am = math.radians((a0+a1)/2.0)
    # Inside the corner first, which is where an angular dimension belongs.  Then, if the part is
    # too small to hold the value there, a sweep outward, widening and turning away from the
    # bisector: these parts are 45 to 65 mm across with a 20 mm value to place, so no fixed offset
    # works on all twelve and a shortlist of candidates ran out on B10.
    cand = [(rr, am, False) for rr in (r+13, r+21, r+30)]
    for rr in range(int(DOFF)+20, int(DOFF)+230, 16):
        for k in range(24):
            cand.append((rr, am+math.pi+(k//2+1)*math.radians(15)*(1 if k % 2 else -1), True))
    for rr, a, out in cand:
        pt = (c[0]+rr*math.cos(a), c[1]+rr*math.sin(a))
        if not _clear(pt, txt, th):
            continue
        if out:
            l0 = (c[0]+(r+2)*math.cos(a), c[1]+(r+2)*math.sin(a))
            l1 = (c[0]+(rr-strw(txt, th)/2-4)*math.cos(a),
                  c[1]+(rr-strw(txt, th)/2-4)*math.sin(a))
            # the value itself was clear, but the leader that reaches it still has to get there
            # without running through an edge dimension on the way
            if not _leader_clear(l0, l1):
                continue
            Ln_(l0, l1, 'DIM')
        TX(pt, txt, th, 'DIM', al='MC')
        return
    raise SystemExit('no clear spot for the %s angle value at (%.1f, %.1f)' % (txt, c[0], c[1]))


def title_block(x, y):
    TX((x, y), 'WUHAN PHOTOGRAPHY BOARDS  -  BRICK SLIPS  -  CUTTING DRAWING', 40, 'TITLE',
       al='BL')
    TX((x, y-54), '武汉摄影展板　砖片下料图　　3 Monahan Avenue (HA23007)   |   %d types, '
                  '%d slips   |   one panel per type, 1:1'
       % (len(T), sum(t['qty'] for t in T)), 16, 'TITLE', al='BL')
    notes = [
        'NOTES  说明:',
        '1. ALL DIMENSIONS IN MILLIMETRES.  Every part is drawn 1:1.   '
        '全部尺寸单位为毫米，各零件均按 1:1 绘制。',
        '2. SLIP: %g x %g x %g mm, face and back as supplied.  Thickness is not dimensioned on any '
        'panel - it is the same %g on every type.   砖片 %g x %g x %g，正反面按来料。各型厚度一律 %g，'
        '图中不再重复标注。' % (SLIP[0], SLIP[1], SLIP[2], SLIP[2],
                               SLIP[0], SLIP[1], SLIP[2], SLIP[2]),
        '3. B01 is the whole slip as supplied and needs no cutting.  B02, B03 and B12 are straight '
        'cuts across it.  Everything from B04 on is a field piece: it is cut to close a herringbone '
        'or a weave against a border, so it carries angles other than 90 degrees.   '
        'B01 为整砖片，来料即用，无需切割；B02、B03、B12 为直切件；B04 及以后均为场内收边件，'
        '用于人字纹或编织纹收到边框，故带非直角。',
        '4. EACH PART IS DRAWN SQUARED UP ON ITS LONGEST EDGE, which is the edge a saw fence is '
        'set against.  It is NOT drawn at the angle it is laid: on board 8 every field piece lies '
        'at 45 degrees, and drawn as laid the same part appears at four different angles.  For '
        'where a piece actually goes, see dxf/05 and drawing S7.   '
        '各零件均以其最长边摆正绘制，该边即锯切靠尺边，并非按铺贴角度绘制：板 8 的场内件全部铺成 '
        '45 度，按铺贴角度画则同一零件会出现四个方向。零件的实际位置见 dxf/05 与 S7 图。',
        '5. ANGLES ARE DIMENSIONED ONLY WHERE THEY ARE NOT 90 DEGREES.  An unmarked corner is a '
        'right angle.   仅标注非 90 度的角，未标注的转角均为直角。',
        '6. QUANTITIES ARE THE NINE BOARDS TOTAL and are listed per board beside each part.  They '
        'carry no cutting allowance and no breakage allowance.   '
        '数量为九块板合计，并在每个零件旁按板列出。未计切割损耗与破损备料。',
        '7. ONE LAYER PER TYPE, named B01_WHOLE, B04_CUT and so on and carrying that type\'s '
        'colour, so a single type can be isolated or counted in CAD.  dxf/05 uses the same '
        'convention for the board layouts.   '
        '每型一个图层，命名为 B01_WHOLE、B04_CUT 等并带该型颜色，便于在 CAD 中单独提取或计数；'
        'dxf/05 的排布图使用同一约定。',
        '8. Joint widths differ from board to board (3, 5, 7 and 10 mm) and are already taken into '
        'the sizes above; they are dimensioned on dxf/05, not here.   '
        '各板灰缝宽度不同（3、5、7、10 mm），已计入以上尺寸；灰缝标注见 dxf/05，本图不重复。',
    ]
    yy = y-96
    for s in notes:
        for ln in wrap(s, 14, 1700, '    '):
            TX((x, yy), ln, 14, 'NOTE', al='BL'); yy -= 25
        yy -= 6
    return yy


def schedule(x, y):
    """the cut list, before the panels, so the sheet opens on the numbers"""
    TX((x, y), 'SCHEDULE  明细表', 24, 'TITLE', al='BL')
    cols = (0, 130, 430, 600, 710, 870)
    hdr = ('件号 CODE', '规格 SIZE mm', '类别 KIND', '数量 QTY', '面积 AREA mm2', '用在 USED ON')
    yy = y-40
    for cx, s in zip(cols, hdr):
        TX((x+cx, yy), s, 15, 'TITLE', al='BL')
    yy -= 10
    Ln_((x, yy), (x+1540, yy), 'DIM')
    yy -= 30
    KIND = {'WHOLE': '整砖片 whole', 'STD': '标准件 standard', 'CUT': '切割件 cut'}
    for t in T:
        use = ', '.join('%d x%d' % (u['board'], u['qty']) for u in t['use'])
        for cx, s in zip(cols, (t['code'], t['label'], KIND[t['kind']], str(t['qty']),
                                '%.0f' % t['area'], use)):
            TX((x+cx, yy), s, 15, 'TXT', al='BL')
        yy -= 30
    yy -= 6
    Ln_((x, yy), (x+1540, yy), 'DIM')
    TX((x+cols[3], yy-30), '%d' % sum(t['qty'] for t in T), 15, 'TITLE', al='BL')
    TX((x, yy-30), '合计 TOTAL', 15, 'TITLE', al='BL')
    return yy-70


def panel(t, ox, oy):
    del _SEG[:]; del _TXT[:]
    """one type: the part 1:1, dimensioned, with its own schedule line beside it"""
    lay = '%s_%s' % (t['code'], t['kind'])
    if lay not in doc.layers:
        doc.layers.add(lay, true_color=int(t['colour'][1:], 16))
    p = [(ox+q[0], oy+q[1]) for q in t['poly']]
    PL(p, lay, close=True)

    # every edge, dimensioned outward.  The offset alternates with the edge's own direction so a
    # dimension never lands inside the part.
    n = len(p)
    cx = sum(q[0] for q in p)/n; cy = sum(q[1] for q in p)/n
    for i in range(n):
        a, b = p[i-1], p[i]
        L = math.dist(a, b)
        mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
        dx, dy = b[0]-a[0], b[1]-a[1]
        nx, ny = -dy/L, dx/L
        off = DOFF if (mx-cx)*nx+(my-cy)*ny > 0 else -DOFF
        dim_aln(a, b, off, '%g' % round(L, 1))

    # angles, only where they are not right angles
    for q, ang in t['angles']:
        if abs(ang-90.0) < 0.5:
            continue
        v = (ox+q[0], oy+q[1])
        i = [k for k in range(n) if math.dist(p[k], v) < 1e-6]
        if not i:
            continue
        k = i[0]
        a, c = p[k-1], p[(k+1) % n]
        a0 = math.degrees(math.atan2(a[1]-v[1], a[0]-v[0]))
        a1 = math.degrees(math.atan2(c[1]-v[1], c[0]-v[0]))
        if (a1-a0) % 360 > 180:
            a0, a1 = a1, a0
        dim_ang(v, RARC, a0, a1, '%g°' % round(ang, 1))

    # Overall width and height, but only where they are not already on the drawing: a rectangle
    # has its 215 on the edge itself, and printing it again underneath is six dimensions on a part
    # that needs two.
    xs = [q[0] for q in p]; ys = [q[1] for q in p]
    flat = [(abs(b[1]-a[1]) < 0.05, abs(b[0]-a[0]) < 0.05, round(math.dist(a, b), 1))
            for a, b in zip(p, p[1:]+p[:1])]
    if not any(h and abs(L-round(t['bw'], 1)) < 0.05 for h, v, L in flat):
        dim_aln((min(xs), min(ys)-96), (max(xs), min(ys)-96), 0.0, '%g' % round(t['bw'], 1), 12)
    if not any(v and abs(L-round(t['bh'], 1)) < 0.05 for h, v, L in flat):
        dim_aln((min(xs)-96, min(ys)), (min(xs)-96, max(ys)), 0.0, '%g' % round(t['bh'], 1), 12)

    tx = ox+300.0
    ty = oy+t['bh']+40.0
    KIND = {'WHOLE': '整砖片 WHOLE SLIP', 'STD': '标准件 STANDARD', 'CUT': '切割件 CUT PIECE'}
    TX((tx, ty), '%s   %s' % (t['code'], t['label']), 26, 'TITLE', al='BL'); ty -= 40
    TX((tx, ty), '%s   %d 边 sides   面积 area %.0f mm2   数量 qty %d'
       % (KIND[t['kind']], len(t['poly']), t['area'], t['qty']), 15, 'TXT', al='BL'); ty -= 30
    for u in t['use']:
        TX((tx, ty), '板 board %d   %s   x %d' % (u['board'], u['code'], u['qty']),
           14, 'TXT', al='BL')
        ty -= 24
    return ty


# ---------------------------------------------------------------- build
T = types()
yend = title_block(0, 0)
gtop = schedule(0, yend-40)

ROW = 430.0
for i, t in enumerate(T):
    panel(t, 120.0, gtop-140.0-i*ROW)

import ezdxf.bbox as bb
ext = bb.extents(msp); mn, mx = ext.extmin, ext.extmax; pad = 60
PL([(mn[0]-pad, mn[1]-pad), (mx[0]+pad, mn[1]-pad), (mx[0]+pad, mx[1]+pad),
    (mn[0]-pad, mx[1]+pad)], 'BORDER', close=True)
q = os.path.join(HERE, '..', 'dxf', '07_bricks_CN_EN.dxf')
doc.saveas(q)
print('SAVED', os.path.normpath(q), '| entities', len(list(msp)),
      '| x[%.0f..%.0f] y[%.0f..%.0f]' % (mn[0], mx[0], mn[1], mx[1]))
