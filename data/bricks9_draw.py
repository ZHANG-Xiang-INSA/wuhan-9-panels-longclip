# -*- coding: utf-8 -*-
"""S9: the brick cutting sheet, the readable companion to dxf/07.

    python data/bricks9_draw.py    ->  drawings/S9_bricks_CN_EN.png and .svg

Same twelve parts and the same schedule as the DXF, laid out to be read on a screen or printed on
one sheet rather than opened in CAD.  All twelve panels are drawn at ONE scale, so the parts can
be compared by eye; the DXF is the one to measure off.
"""
import json, math, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyArrowPatch, Arc
from matplotlib.gridspec import GridSpec
from bricks9 import types, SLIP

matplotlib.rcParams['font.family'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'drawings')
INK = '#2f2f2d'
DIMC = '#8a8781'
T = types()
KIND = {'WHOLE': '整砖片 whole slip', 'STD': '标准件 standard', 'CUT': '切割件 cut piece'}

fig = plt.figure(figsize=(19.0, 25.0))
fig.patch.set_facecolor('white')
gs = GridSpec(5, 3, figure=fig, height_ratios=[1.35, 1, 1, 1, 1],
              hspace=0.30, wspace=0.10, left=0.020, right=0.985, top=0.955, bottom=0.012)


def dim(ax, p0, p1, off, txt, fs=8.0):
    """aligned dimension, value on the far side of the line from the part"""
    dx, dy = p1[0]-p0[0], p1[1]-p0[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy/L, dx/L
    q0 = (p0[0]+nx*off, p0[1]+ny*off); q1 = (p1[0]+nx*off, p1[1]+ny*off)
    ax.plot([p0[0], q0[0]], [p0[1], q0[1]], color=DIMC, lw=0.5, zorder=4)
    ax.plot([p1[0], q1[0]], [p1[1], q1[1]], color=DIMC, lw=0.5, zorder=4)
    ax.add_patch(FancyArrowPatch(q0, q1, arrowstyle='<->', mutation_scale=6, lw=0.7,
                                 color=DIMC, shrinkA=0, shrinkB=0, zorder=4))
    r = math.degrees(math.atan2(dy, dx)) % 180
    rot = r-180 if r > 90 else r
    s = 1.0 if off >= 0 else -1.0
    ax.text((q0[0]+q1[0])/2+nx*s*7, (q0[1]+q1[1])/2+ny*s*7, txt, ha='center', va='center',
            fontsize=fs, color=INK, rotation=rot, rotation_mode='anchor', zorder=6,
            bbox=dict(fc='white', ec='none', pad=0.7))


# The whole slip is the biggest part at 215 long, so one scale for all twelve is set by it.
SPAN = max(max(t['bw'], t['bh']) for t in T)+150.0

for k, t in enumerate(T):
    ax = fig.add_subplot(gs[1+k//3, k % 3])
    p = t['poly']
    ax.add_patch(Polygon(p, closed=True, fc=t['colour'], ec=INK, lw=1.1, alpha=0.55, zorder=2))
    n = len(p)
    cx = sum(q[0] for q in p)/n; cy = sum(q[1] for q in p)/n
    for i in range(n):
        a, b = p[i-1], p[i]
        L = math.dist(a, b)
        mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
        nx, ny = -(b[1]-a[1])/L, (b[0]-a[0])/L
        dim(ax, a, b, 26.0 if (mx-cx)*nx+(my-cy)*ny > 0 else -26.0, '%g' % round(L, 1))
    for q, ang in t['angles']:
        if abs(ang-90.0) < 0.5:
            continue
        i = [j for j in range(n) if math.dist(p[j], q) < 1e-6][0]
        a, c = p[i-1], p[(i+1) % n]
        a0 = math.degrees(math.atan2(a[1]-q[1], a[0]-q[0]))
        a1 = math.degrees(math.atan2(c[1]-q[1], c[0]-q[0]))
        if (a1-a0) % 360 > 180:
            a0, a1 = a1, a0
        ax.add_patch(Arc(q, 26, 26, angle=0, theta1=a0, theta2=a1, color=DIMC, lw=0.7, zorder=4))
        am = math.radians((a0+a1)/2.0)
        ax.text(q[0]+24*math.cos(am), q[1]+24*math.sin(am), '%g°' % round(ang, 1),
                ha='center', va='center', fontsize=7.4, color=INK, zorder=6,
                bbox=dict(fc='white', ec='none', pad=0.6))
    ax.set_xlim(t['bw']/2-SPAN/2, t['bw']/2+SPAN/2)
    ax.set_ylim(t['bh']/2-SPAN/2*0.62, t['bh']/2+SPAN/2*0.62)
    ax.set_aspect('equal'); ax.axis('off')
    use = '，'.join('板 %d x%d' % (u['board'], u['qty']) for u in t['use'])
    ax.set_title('%s   %s\n%s   %d 边 sides   面积 area %.0f mm²   数量 qty %d\n%s'
                 % (t['code'], t['label'], KIND[t['kind']], n, t['area'], t['qty'], use),
                 fontsize=9.4, color=INK, pad=8, loc='left', linespacing=1.55)

# the schedule, across the top three cells
ax = fig.add_subplot(gs[0, :])
ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
ax.text(0.0, 0.985, '明细表  SCHEDULE', va='top', ha='left', fontsize=13, color=INK)
COL = (0.0, 0.055, 0.185, 0.300, 0.375, 0.470)
HDR = ('件号 CODE', '规格 SIZE mm', '类别 KIND', '数量 QTY', '面积 AREA mm²', '用在 USED ON')
for x, s in zip(COL, HDR):
    ax.text(x, 0.905, s, va='top', ha='left', fontsize=9.2, color=INK)
ax.plot([0.0, 1.0], [0.875, 0.875], color=INK, lw=0.8)
y = 0.845
for t in T:
    use = '，'.join('板 %d x%d' % (u['board'], u['qty']) for u in t['use'])
    for x, s in zip(COL, (t['code'], t['label'], KIND[t['kind']], str(t['qty']),
                          '%.0f' % t['area'], use)):
        ax.text(x, y, s, va='top', ha='left', fontsize=8.6, color=INK)
    y -= 0.062
ax.plot([0.0, 1.0], [y+0.030, y+0.030], color=INK, lw=0.8)
ax.text(0.0, y-0.004, '合计 TOTAL', va='top', ha='left', fontsize=9.2, color=INK)
ax.text(COL[3], y-0.004, '%d' % sum(t['qty'] for t in T), va='top', ha='left',
        fontsize=9.2, color=INK)
ax.text(0.0, y-0.075,
        '砖片 slip %g x %g x %g mm。各零件以其最长边摆正绘制，非按铺贴角度；'
        '仅标注非 90° 的角。数量为九块板合计，未计损耗。测量请用 dxf/07。\n'
        'Slip %g x %g x %g. Each part is drawn squared up on its longest edge, not at the angle it '
        'is laid; angles are dimensioned only where they are not 90°. Quantities are the nine '
        'boards total and carry no allowance. Measure off dxf/07.'
        % (SLIP[0], SLIP[1], SLIP[2], SLIP[0], SLIP[1], SLIP[2]),
        va='top', ha='left', fontsize=8.6, color='#6d6a63', linespacing=1.6)

fig.suptitle('武汉摄影展板　砖片下料图\nWuhan photography boards - brick slips, cutting drawing',
             fontsize=15, color=INK, y=0.988, linespacing=1.5)
q = os.path.join(OUT, 'S9_bricks_CN_EN.png')
fig.savefig(q, dpi=220, facecolor='white', bbox_inches='tight')
fig.savefig(q.replace('.png', '.svg'), format='svg', facecolor='white', bbox_inches='tight')
print('->', os.path.normpath(q.replace('.png', '.svg')))
print('->', os.path.normpath(q))
