"""Draw the clips: plan, section and flat blank for each type, with notes in Chinese and English.
Writes both the DXF and the sheet, from the same geometry, so the two cannot disagree.
"""
import json, math, os
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Rectangle
from clips9 import PROF, HOLE, SLIP_W, lip_runs, edge_pts, TAB_W
import sheetwrap as SW

matplotlib.rcParams['font.family'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
# A drawing has to come out the same twice.  matplotlib stamps the wall-clock time into every
# SVG it writes and salts the clip-path ids per run, so two runs of the same script produced two
# different files - which made "site/downloads is byte for byte the master" a check that could
# only pass if pack_downloads happened to run last, and quietly went false the next time anything
# regenerated.  A fixed salt and no date makes the output a function of the data alone.
matplotlib.rcParams['svg.hashsalt'] = 'wuhan-9-panels'
SVG_META = {'Date': None}

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'dxf')
D = json.load(open(os.path.join(HERE, 'clips9.json')))
CLIPS = D['clips']
FLAT, LEG, LIP = PROF['flat'], PROF['leg'], PROF['lip']
ANG = math.radians(PROF['lip_angle'])
TIP_IN, TIP_UP = LIP*math.sin(ANG), LEG-LIP*math.cos(ANG)
INK, LIPC, PIECE = '#2f2f2d', '#c0504d', '#9aa7b5'


def section():
    """the M profile across the 68 flat.  The return lips hook INWARD: from each leg top the tip
    moves toward the centre and down, so the two tips face each other across a 62.5 opening and
    the slip has to be sprung past them."""
    return [(TIP_IN, TIP_UP), (0.0, LEG), (0.0, 0.0), (FLAT, 0.0), (FLAT, LEG),
            (FLAT-TIP_IN, TIP_UP)]


EDGE_MIN, LIP_CLR = 8.0, 12.0


def holes_rule(poly, lipped, rail_len=None):
    """R50 takes the reference drawing's positions, 12.5 from each end on the centreline.
    A pocket is eroded instead: 8 clear of a plain edge, 12 of a lipped one, so a driver reaches
    the screw without fouling the inward hook."""
    if rail_len is not None:
        return [(12.5, FLAT/2), (rail_len-12.5, FLAT/2)]
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
    cand = []
    x = min(xs)
    while x <= max(xs):
        y = min(ys)
        while y <= max(ys):
            if _pin(poly, (x, y)) and _pclear(poly, lipped, (x, y)):
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
    return list(best) if bd >= 2*HOLE else [cand[len(cand)//2]]


def _pin(poly, pt):
    x, y = pt; c = False
    for i in range(len(poly)):
        a, b = poly[i-1], poly[i]
        if (a[1] > y) != (b[1] > y):
            if x < a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                c = not c
    return c


def _pclear(poly, lipped, pt):
    for i in range(len(poly)):
        a, b = poly[i-1], poly[i]
        dx, dy = b[0]-a[0], b[1]-a[1]
        L2 = dx*dx+dy*dy or 1.0
        t = max(0.0, min(1.0, ((pt[0]-a[0])*dx+(pt[1]-a[1])*dy)/L2))
        if math.hypot(pt[0]-(a[0]+t*dx), pt[1]-(a[1]+t*dy)) < (LIP_CLR if lipped[i] else EDGE_MIN):
            return False
    return True


def holes(poly):
    """two fixing holes on the polygon's long axis, kept inside it"""
    cx = sum(q[0] for q in poly)/len(poly); cy = sum(q[1] for q in poly)/len(poly)
    sxx = sum((q[0]-cx)**2 for q in poly); syy = sum((q[1]-cy)**2 for q in poly)
    sxy = sum((q[0]-cx)*(q[1]-cy) for q in poly)
    a = 0.5*math.atan2(2*sxy, sxx-syy)
    ux, uy = math.cos(a), math.sin(a)
    for d in (0.30, 0.22, 0.15, 0.08, 0.0):
        R = d*math.sqrt(max(sxx, syy)/len(poly))*3.0
        p = [(cx+ux*R, cy+uy*R), (cx-ux*R, cy-uy*R)]
        if all(inside(q, poly, HOLE) for q in p):
            return p
    return [(cx, cy)]


def inside(pt, poly, clear):
    n, c = len(poly), False
    x, y = pt
    for i in range(n):
        a, b = poly[i-1], poly[i]
        if (a[1] > y) != (b[1] > y):
            xx = a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x < xx:
                c = not c
    if not c:
        return False
    for i in range(n):
        a, b = poly[i-1], poly[i]
        dx, dy = b[0]-a[0], b[1]-a[1]
        L2 = dx*dx+dy*dy or 1.0
        t = max(0.0, min(1.0, ((x-a[0])*dx+(y-a[1])*dy)/L2))
        if math.hypot(x-(a[0]+t*dx), y-(a[1]+t*dy)) < clear:
            return False
    return True


def blank(base, lipped, tabs=None, tab_w=TAB_W):
    """the developed blank: the tray, plus a flap on every lipped RUN

    A run is the whole edge for a full-length lip and a TAB_W stretch at the middle of the edge
    for a tab, which is what PK-8T02 carries: three edges folding inward over their full length
    collide in both corners, so each is reduced to a tab that never reaches one.
    """
    flaps, n = [], len(base)
    tabs = tabs or [False]*n
    for i in range(n):
        a, b = base[i-1], base[i]
        for (t0, t1) in lip_runs(a, b, lipped[i], tabs[i], tab_w):
            p0, p1 = edge_pts(a, b, t0, t1)
            dx, dy = b[0]-a[0], b[1]-a[1]
            L = math.hypot(dx, dy) or 1.0
            nx, ny = dy/L, -dx/L
            w = LEG+LIP
            flaps.append(([p0, p1, (p1[0]+nx*w, p1[1]+ny*w), (p0[0]+nx*w, p0[1]+ny*w)],
                          [(p0[0]+nx*LEG, p0[1]+ny*LEG), (p1[0]+nx*LEG, p1[1]+ny*LEG)]))
    return flaps


BRK_KEEP, BRK_GAP = 210.0, 60.0


def broken(base):
    """is this part too long and thin to draw whole?

    R1000 is 1000 along and 68 across.  Drawn to fit a column beside two other views it is a
    hairline: the sheet shows a part 15 times as long as it is wide and nothing can be read off
    it.  Over 6:1 the part is drawn broken, which is what any drawing of a long section does.
    """
    xs = [q[0] for q in base]; ys = [q[1] for q in base]
    return (max(xs)-min(xs)) > 6.0*(max(ys)-min(ys))


def break_parts(base):
    """-> ([(base, lipped), ...], [x of each break])  BRK_KEEP off each end, the middle omitted

    The two cut faces are not ends of the part and carry no lip, which is why the flags are built
    here rather than copied: lipped[i] is the edge base[i-1] -> base[i], so on each half the two
    long edges are lipped and the two vertical ones are not.
    """
    xs = [q[0] for q in base]; ys = [q[1] for q in base]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    shift = (x1-x0)-(2*BRK_KEEP+BRK_GAP)
    rect = lambda a, b: [(a, y0), (b, y0), (b, y1), (a, y1)]
    lip = [False, True, False, True]
    return ([(rect(x0, x0+BRK_KEEP), lip),
             (rect(x0+BRK_KEEP+BRK_GAP, x1-shift), lip)],
            [x0+BRK_KEEP, x0+BRK_KEEP+BRK_GAP], shift)


def zig(ax, x, y0, y1, w=2.6, n=6):
    """the break line: a shallow zigzag down the cut face"""
    k = (y1-y0)/n
    px = [x]+[x+(w if j % 2 else -w) for j in range(1, n+1)]+[x]
    py = [y0]+[y0+k*(j-0.5) for j in range(1, n+1)]+[y1]
    ax.plot(px, py, color=INK, lw=1.1, solid_joinstyle='miter')


def title(ax, s, fontsize=10):
    """set_title, wrapped to the axes it belongs to

    These titles run to two and three clauses in two languages and were each set as one line.
    Nothing clips a title, so the long ones simply ran out of their column and over the next one.
    """
    ax.set_title(SW.wrap(ax.figure, s, fontsize, SW.cellpx(ax)),
                 fontsize=fontsize, color=INK, loc='left', pad=6, linespacing=1.5)


def tabs_of(c):
    return list(c.get('tabs') or [False]*len(c.get('lipped') or [])) or [False]*4


def tabw_of(c):
    return float(c.get('tab_w') or TAB_W)


def geom(c):
    """-> (tray outline, lipped flags, fold lines, holes, blank flaps)"""
    if c['kind'] == 'RAIL':
        Lg = c['length']
        base = [(0.0, 0.0), (Lg, 0.0), (Lg, FLAT), (0.0, FLAT)]
        # the legs run along the clip's length, so lip the edges that are Lg long.  Edge i runs
        # base[i-1] -> base[i], which is why this is derived rather than written out.
        lipped = [abs(math.hypot(base[i][0]-base[i-1][0], base[i][1]-base[i-1][1])-Lg) < 1e-6
                  for i in range(len(base))]
        hs = [tuple(q) for q in c['holes']] if c.get('holes') else             holes_rule(base, lipped, rail_len=Lg)
        return base, lipped, hs, blank(base, lipped)
    else:
        # the tray follows the piece exactly.  Where the piece tapers to a few millimetres the
        # tray tapers with it; that end carries no lip (the edge is under the 30 mm minimum), so
        # the point is spare material, not a grip.  CLIP_MIN is read as the clip's smallest
        # overall dimension, which every pocket meets at 65 across.
        base = [tuple(q) for q in c['base']]
        lipped = c['lipped']
    return base, lipped, holes_rule(base, lipped), blank(base, lipped, tabs_of(c), tabw_of(c))


# ---------------------------------------------------------------- sheet
n = len(CLIPS)
fig = plt.figure(figsize=(19.0, 4.4*n+1.0))
fig.patch.set_facecolor('white')
# Four columns, not three.  The note used to be written at 1.005 of the blank's axes, which is off
# the right of the paper: matplotlib's own wrap measures against the figure, found no room, and
# left the block running 200 to 560 px past the sheet edge on every row.  It now has a column of
# its own and is wrapped to it.
gs = fig.add_gridspec(n, 4, width_ratios=[1.0, 0.95, 1.35, 1.30], hspace=0.42, wspace=0.10,
                      left=0.02, right=0.985, top=0.955, bottom=0.012)

for row, c in enumerate(CLIPS):
    base, lipped, hs, flaps = geom(c)
    brk = broken(base)
    if brk:
        parts, cuts, shift = break_parts(base)
        # a hole in the omitted middle is omitted with it; one past the break moves with its half
        x1 = max(q[0] for q in base)
        hs = [q for q in hs if q[0] <= BRK_KEEP+1e-6] + \
             [(q[0]-shift, q[1]) for q in hs if q[0] >= x1-BRK_KEEP-1e-6]
        flaps = [f for p, lp in parts for f in blank(p, lp)]
    else:
        parts, cuts = [(base, lipped)], []

    ax = fig.add_subplot(gs[row, 0])
    for p, lp in parts:
        ax.add_patch(Polygon(p, closed=True, fc='#eeeeea', ec=INK, lw=1.4))
        for i in range(len(p)):
            a, b = p[i-1], p[i]
            tb_i = tabs_of(c)[i] if not brk else False
            for (t0, t1) in lip_runs(a, b, lp[i], tb_i, tabw_of(c)):
                q0, q1 = edge_pts(a, b, t0, t1)
                ax.plot([q0[0], q1[0]], [q0[1], q1[1]], color=LIPC, lw=2.6, solid_capstyle='butt')
    ys = [q[1] for q in base]
    for x in cuts:
        zig(ax, x, min(ys), max(ys))
    for q in hs:
        ax.add_patch(Circle(q, HOLE/2.0, fc='white', ec=INK, lw=1.0))
    if brk:
        # a broken view without the real length on it is a drawing of the wrong part
        xa = min(q[0] for p, _ in parts for q in p)
        xb = max(q[0] for p, _ in parts for q in p)
        ax.annotate('', xy=(xa, -22), xytext=(xb, -22),
                    arrowprops=dict(arrowstyle='<->', lw=0.8))
        ax.text((xa+xb)/2.0, -26, '%g' % c['length'], ha='center', va='top', fontsize=8.5)
        ax.annotate('', xy=(xa, -46), xytext=(hs[0][0], -46),
                    arrowprops=dict(arrowstyle='<->', lw=0.8))
        ax.text((xa+hs[0][0])/2.0, -50, '%g' % hs[0][0], ha='center', va='top', fontsize=8.5)
        ax.annotate('', xy=(hs[0][0], -46), xytext=(hs[1][0], -46),
                    arrowprops=dict(arrowstyle='<->', lw=0.8))
        ax.text((hs[0][0]+hs[1][0])/2.0, -50, '%g' % (hs[1][0]-hs[0][0]),
                ha='center', va='top', fontsize=8.5)
        ax.set_ylim(-62, max(ys)+14)
    ax.set_aspect('equal'); ax.axis('off')
    tb = tabs_of(c)
    nfull = sum(1 for i in range(len(base)) if lipped[i] and not tb[i])
    ntab = sum(1 for i in range(len(base)) if lipped[i] and tb[i])
    how = []
    if nfull:
        how.append('%d 条整边折起 / %d full' % (nfull, nfull))
    if ntab:
        how.append('%d 条中部 %g 宽小卡扣 / %d tab' % (ntab, tabw_of(c), ntab))
    title(ax, '%s\n平面 PLAN   红线为折边\nred = fold, always INWARD%s%s'
          % (c['code'], ('\n'+'，'.join(how)) if how else '',
             '\n断开画法，中间等断面省略 / broken, identical middle omitted' if brk else ''))

    ax = fig.add_subplot(gs[row, 1])
    if c['kind'] == 'RAIL':
        s = section()
        ax.add_patch(Rectangle(((FLAT-SLIP_W)/2.0, 0), SLIP_W, 20.0, fc=PIECE, ec=INK,
                               lw=0.8, alpha=0.55))
        ax.plot([q[0] for q in s], [q[1] for q in s], color=INK, lw=2.2)
        ax.annotate('', xy=(0, -6), xytext=(FLAT, -6), arrowprops=dict(arrowstyle='<->', lw=0.8))
        ax.text(FLAT/2, -9, '%g' % FLAT, ha='center', va='top', fontsize=8.5)
        # the mouth is the gap BETWEEN the two hook tips, so it runs from TIP_IN to FLAT-TIP_IN.
        # Signed the other way it came out at FLAT + 2*TIP_IN = 73.5 and the drawing showed a 62.5
        # opening dimensioned wider than the 68 flat it sits inside.
        ax.annotate('', xy=(TIP_IN, -14), xytext=(FLAT-TIP_IN, -14),
                    arrowprops=dict(arrowstyle='<->', lw=0.8, color=LIPC))
        ax.text(FLAT/2, -17, '开口 mouth %g' % PROF['mouth'], ha='center', va='top',
                fontsize=8.5, color=LIPC)
        ax.set_xlim(-12, FLAT+12); ax.set_ylim(-24, 26)
        ttl = '断面 SECTION   68 平板，开口 mouth %g' % PROF['mouth']
    else:
        # A pocket has no 68 flat and no mouth: it follows the piece, so its width is whatever the
        # plan says and differs edge to edge.  Dimensioning 68 and 62.5 here, as the rail section
        # did on every row, described a part that does not exist.  What a pocket shares with the
        # rail is the edge itself, so that is what is drawn - one leg and its return lip, with the
        # slip sitting against it.
        W2 = 34.0
        s = [(TIP_IN, TIP_UP), (0.0, LEG), (0.0, 0.0), (W2, 0.0)]
        ax.add_patch(Rectangle((1.5, 0), W2-1.5, 20.0, fc=PIECE, ec=INK, lw=0.8, alpha=0.55))
        ax.plot([q[0] for q in s], [q[1] for q in s], color=INK, lw=2.2)
        ax.annotate('', xy=(-6, 0), xytext=(-6, LEG), arrowprops=dict(arrowstyle='<->', lw=0.8))
        ax.text(-8, LEG/2, '%g' % LEG, ha='right', va='center', fontsize=8.5)
        ax.annotate('', xy=(0.0, LEG+5), xytext=(TIP_IN, TIP_UP+5),
                    arrowprops=dict(arrowstyle='<->', lw=0.8, color=LIPC))
        ax.text(TIP_IN+1.5, LEG+6, '唇边 lip %g @ %g°' % (LIP, PROF['lip_angle']),
                ha='left', va='bottom', fontsize=8.5, color=LIPC)
        ax.plot([1.5, 1.5], [0, 20.0], color=INK, lw=0.6, ls=':')
        ax.text(W2, 21.5, '砖片 slip t20', ha='right', va='bottom', fontsize=8.5, color=INK)
        ax.set_xlim(-16, W2+8); ax.set_ylim(-10, 32)
        ttl = ('边缘断面 EDGE SECTION   沿任一折边剖开\n唇尖向内压住砖片 %g   lip tip %g over the slip'
               % (round(SLIP_W/2.0-(FLAT/2.0-TIP_IN), 2), round(SLIP_W/2.0-(FLAT/2.0-TIP_IN), 2)))
    ax.set_aspect('equal'); ax.axis('off')
    title(ax, '%s\n立边 leg %g，唇边 lip %g @ %g°，料厚 t %g'
          % (ttl, LEG, LIP, PROF['lip_angle'], PROF['sheet']))

    ax = fig.add_subplot(gs[row, 2])
    for p, _ in parts:
        ax.add_patch(Polygon(p, closed=True, fc='#eeeeea', ec=INK, lw=1.3))
    for x in cuts:
        zig(ax, x, min(ys), max(ys))
    for fp, fold in flaps:
        ax.add_patch(Polygon(fp, closed=True, fc='#f7ece9', ec=INK, lw=1.0))
        ax.plot([fold[0][0], fold[1][0]], [fold[0][1], fold[1][1]], color=LIPC, lw=1.0, ls='--')
        # An unfolded flap drawn outside the tray, with nothing to say which way it goes, reads as
        # a flap that folds outward.  The arrow points back at the tray, which is where it folds.
        mx, my = (fp[0][0]+fp[1][0])/2.0, (fp[0][1]+fp[1][1])/2.0
        vx, vy = fp[3][0]-fp[0][0], fp[3][1]-fp[0][1]
        ax.annotate('', xy=(mx+vx*0.10, my+vy*0.10), xytext=(mx+vx*0.92, my+vy*0.92),
                    arrowprops=dict(arrowstyle='-|>', lw=1.1, color=LIPC, shrinkA=0, shrinkB=0))
    for q in hs:
        ax.add_patch(Circle(q, HOLE/2.0, fc='white', ec=INK, lw=1.0))
    ax.set_aspect('equal'); ax.axis('off')
    xs = [q[0] for f in flaps for q in f[0]]+[q[0] for p, _ in parts for q in p]
    ys2 = [q[1] for f in flaps for q in f[0]]+[q[1] for p, _ in parts for q in p]
    ax.set_xlim(min(xs)-14, max(xs)+14); ax.set_ylim(min(ys2)-14, max(ys2)+14)
    title(ax, '展开料 FLAT BLANK   虚线为折线 dashed = fold line\n'
          '箭头为折弯方向，均折向托盘内侧   arrow = fold direction, always in toward the tray%s' %
          ('\n断开画法，中间等断面省略 / broken, identical middle omitted' if brk else ''))

    # the note, in a column of its own and wrapped to it
    ax = fig.add_subplot(gs[row, 3])
    ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    body = '%s  %s\n数量 qty %d\n\n%s\n\n%s' % (c['zh'], c['en'], c['qty'],
                                               c['note_zh'], c['note_en'])
    ax.text(0.0, 1.0, SW.wrap(fig, body, 8.6, SW.cellpx(ax, 10)),
            transform=ax.transAxes, va='top', ha='left', fontsize=8.6, color=INK,
            linespacing=1.6)

fig.suptitle('武汉摄影展板　卡扣详图\nWuhan photography boards - clip details',
             fontsize=15, color=INK, y=0.988, linespacing=1.5)
q = os.path.join(HERE, '..', 'drawings', 'S8_clips_CN_EN.png')
fig.savefig(q, dpi=220, facecolor='white', bbox_inches='tight')
fig.savefig(q.replace('.png', '.svg'), format='svg', facecolor='white',
            bbox_inches='tight', metadata=SVG_META)
print('->', os.path.normpath(q.replace('.png', '.svg')))
print('->', os.path.normpath(q))

# The DXF is written by clips9_dxf.py, which lays the types out on a grid and dimensions
# them in the style of the reference guiding-rail drawing.  This file only makes the sheet.
