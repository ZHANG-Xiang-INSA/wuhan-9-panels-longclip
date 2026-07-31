"""The nine Wuhan photography panels: identify, resolve and schedule.

Source: 'Wuhan Photography Proposal.pdf'.  The mock-up column is a set of raster texture
renders, so they fix the BOND and the border arrangement; the dimensions come from the table
(215 x 65 slip, per-panel mortar width) plus the brief's own licence -
"1.5m x 1.5m or similar convenient size for brick layout".

Two bonds constrain the joint rather than the other way round.  A 45 deg herringbone closes only
when the head of one slip meets the side of the next, i.e.

        L + J = n (W + J)

and for L=215, W=65 the only integer solution is n=3, J=10.  A triple basketweave needs a square
block, 3W + 2J = L, which gives the same J=10.  Panels 5, 6 and 8 are specified at 7, 7 and 5 mm,
so they cannot be built from a 215 slip.  Resolved here by keeping the client's mortar width -
that is the thing being photographed - and shortening the slip to suit.  The alternative, keeping
215 and moving the joint to 10 mm, is printed alongside.
"""
import math, json
from collections import OrderedDict

W = 65.0                      # slip height, common to every panel
TARGET = 1500.0


def herringbone_L(J, n=3):
    """slip length that makes an n:1 herringbone close at joint J"""
    return n*(W+J) - J


def basket_L(J, n=3):
    """slip length that makes an n-brick basketweave block square"""
    return n*W + (n-1)*J


# ---------------------------------------------------------------- helpers
def snap(target, pitch, minus=0.0):
    """largest k with k*pitch - minus <= target*1.06, nearest to target"""
    k = max(1, round((target+minus)/pitch))
    return k, k*pitch-minus


def rect(x, y, w, h, t):
    return dict(x=round(x, 2), y=round(y, 2), w=round(w, 2), h=round(h, 2), t=t)


# ---------------------------------------------------------------- bonds
def stretcher(Wd, Ht, L, J, y0=0.0):
    """half-lap stretcher; odd courses full, even courses start and end with a half"""
    out, ny = [], 0
    half = (L-J)/2.0
    y = y0
    while y < Ht - 5:
        h = min(W, Ht-y)                       # last course may be part height
        part = h < W-1e-6                      # a part-height course IS a cut
        if ny % 2 == 0:
            x = 0.0
        else:
            # the closing half at alternate course ends is a standard bond component,
            # not waste, so it is not scored as a cut
            out.append(rect(0, y, half, h, 'CUT' if part else 'HALF')); x = half+J
        while x + L <= Wd + 1e-6:
            out.append(rect(x, y, L, h, 'CUT' if part else 'FULL')); x += L+J
        r = Wd - x
        if r > 5:
            std = abs(r-half) < 0.51 and not part
            out.append(rect(x, y, r, h, 'HALF' if std else 'CUT'))
        y += W+J; ny += 1
    return out, ny


def on_end(Wd, y0, J, ht, whole='SOLDIER'):
    """a course of slips stood on end, W wide by `ht` tall, at the board's own joint.

    An earlier version nudged this course's perp joint to Je so that a whole number of slips
    filled the width, on the argument that a millimetre or two is invisible.  Measured, it was
    not: board 1 came out with 8.00 mm joints in a 10 mm board and board 4 carried 5.60 and
    8.50 mm in a 7 mm one, 112 joints of 477.  The joint is held exactly here and the panel size
    search is what closes the course.
    """
    out, x = [], 0.0
    while x < Wd-5:
        w = min(W, Wd-x)
        out.append(rect(x, y0, w, ht, whole if w >= W-1e-6 else 'CUT'))
        x += W+J
    return out


def soldiers(Wd, y0, L, J):
    return on_end(Wd, y0, J, L, 'SOLDIER')


def endcourse(Wd, y0, J, bl=102.0):
    return on_end(Wd, y0, J, bl, 'END')


def stack(Wd, Ht, L, J):
    out, y = [], 0.0
    while y < Ht-5:
        h = min(W, Ht-y); x = 0.0
        while x < Wd-5:
            w = min(L, Wd-x)
            out.append(rect(x, y, w, h, 'FULL' if (w >= L-1e-6 and h >= W-1e-6) else 'CUT'))
            x += L+J
        y += W+J
    return out


def basketweave(Wd, Ht, L, J, n=3):
    """square blocks of n slips, alternating orientation"""
    out = []
    B = L                                    # block side, = n*W+(n-1)*J by construction
    ny = 0; y = 0.0
    while y < Ht-5:
        nx = 0; x = 0.0
        while x < Wd-5:
            for i in range(n):
                if (nx+ny) % 2 == 0:
                    bx, by, bw, bh = x, y+i*(W+J), L, W
                else:
                    bx, by, bw, bh = x+i*(W+J), y, W, L
                if bx >= Wd-5 or by >= Ht-5: continue
                w2, h2 = min(bw, Wd-bx), min(bh, Ht-by)
                if w2 < 5 or h2 < 5: continue
                out.append(rect(bx, by, w2, h2,
                                'FULL' if (w2 >= bw-1e-6 and h2 >= bh-1e-6) else 'CUT'))
            x += B+J; nx += 1
        y += B+J; ny += 1
    return out


def herring(Wd, Ht, L, J, ang=45.0, inset=0.0, org=None, phase=0.0, phy=0.0):
    """45 deg herringbone clipped to the panel; returns whole and cut pieces"""
    M = W+J
    A = (4*M, 2*M); Bv = (-M, M)
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    # a 45 deg field is centred; an orthogonal one is aligned to the corner so a
    # panel on the 6(W+J) module closes on whole bricks
    cx, cy = (Wd/2.0, Ht/2.0) if org is None else org
    cx += phase; cy += phy
    R = int(max(Wd, Ht)/M)+6
    cells = []
    for m in range(-R, R+1):
        for n in range(-R, R+1):
            ox, oy = A[0]*m+Bv[0]*n, A[1]*m+Bv[1]*n
            cells.append((ox, oy, L, W))
            cells.append((ox+L+J, oy, W, L))
    out = []
    x0, y0, x1, y1 = inset, inset, Wd-inset, Ht-inset
    for (ox, oy, w, h) in cells:
        pts = [(ox, oy), (ox+w, oy), (ox+w, oy+h), (ox, oy+h)]
        q = []
        for (px, py) in pts:
            dx, dy = px-0, py-0
            q.append((cx+dx*c-dy*s, cy+dx*s+dy*c))
        cl = clip_rect(q, x0, y0, x1, y1)
        if len(cl) < 3: continue
        a = parea(cl)
        if a < 400: continue
        out.append(dict(poly=[[round(v, 2) for v in p] for p in cl],
                        area=round(a, 1), whole=abs(a-w*h) < 1.0,
                        src=[ox, oy, w, h], ang=ang, org=[cx, cy]))
    return out


def clip_rect(poly, x0, y0, x1, y1):
    for (nx, ny, d) in ((1, 0, x0), (-1, 0, -x1), (0, 1, y0), (0, -1, -y1)):
        src, poly = poly, []
        if not src: break
        for i in range(len(src)):
            p, qq = src[i-1], src[i]
            dp = nx*p[0]+ny*p[1]-d
            dq = nx*qq[0]+ny*qq[1]-d
            if dq >= 0:
                if dp < 0:
                    t = dp/(dp-dq); poly.append((p[0]+t*(qq[0]-p[0]), p[1]+t*(qq[1]-p[1])))
                poly.append(qq)
            elif dp >= 0:
                t = dp/(dp-dq); poly.append((p[0]+t*(qq[0]-p[0]), p[1]+t*(qq[1]-p[1])))
    return poly


def parea(p):
    return abs(sum(p[i-1][0]*p[i][1]-p[i][0]*p[i-1][1] for i in range(len(p))))/2.0


def border(Wd, Ht, L, J, rows=1):
    """A lapped picture-frame border, `rows` deep.

    Top and bottom courses run the FULL width; the left and right courses then fill the height
    between them.  Every brick is whole, and each course meets the next head to tail - the old
    version started each ring at its own inset, which is why the two rings broke apart at the
    corners instead of closing.
    """
    out = []
    band = rows*(W+J) - J                       # depth of the frame, e.g. 2 rows -> 2W+J
    for r in range(rows):
        o = r*(W+J)
        x = 0.0                                 # top and bottom: full width, one grid
        while x + L <= Wd + 1e-6:
            out.append(rect(x, o, L, W, 'BORDER'))
            out.append(rect(x, Ht-o-W, L, W, 'BORDER'))
            x += L+J
        if Wd - x > 5:
            out.append(rect(x, o, Wd-x, W, 'CUT'))
            out.append(rect(x, Ht-o-W, Wd-x, W, 'CUT'))
        y = band + J                            # sides: fill between the two bands
        while y + L <= Ht-band-J + 1e-6:
            out.append(rect(o, y, W, L, 'BORDER'))
            out.append(rect(Wd-o-W, y, W, L, 'BORDER'))
            y += L+J
        if (Ht-band-J) - y > 5:
            out.append(rect(o, y, W, (Ht-band-J)-y, 'CUT'))
            out.append(rect(Wd-o-W, y, W, (Ht-band-J)-y, 'CUT'))
    return out


def rot_clip(cells, Wd, Ht, ang, inset=0.0, phase=0.0, phy=0.0):
    """rotate a field of axis-aligned rects about the panel centre and clip to it

    phase and phy slide the pattern under the panel, in the pattern's own frame before the
    rotation.  Without them the pattern origin is pinned to the panel centre, which fixes where the
    opening slices the field and so fixes the cut list; a basketweave has 4-fold centres, and
    landing the panel centre on one is what makes all four edges cut the same way.
    """
    c, sn = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    cells = [(ox+phase, oy+phy, w, h) for (ox, oy, w, h) in cells]
    cx, cy = Wd/2.0, Ht/2.0
    x0, y0, x1, y1 = inset, inset, Wd-inset, Ht-inset
    out = []
    for (ox, oy, w, h) in cells:
        pts = [(ox, oy), (ox+w, oy), (ox+w, oy+h), (ox, oy+h)]
        q = [(cx+px*c-py*sn, cy+px*sn+py*c) for (px, py) in pts]
        cl = clip_rect(q, x0, y0, x1, y1)
        if len(cl) < 3: continue
        a = parea(cl)
        if a < 400: continue
        out.append(dict(poly=[[round(v, 2) for v in p] for p in cl], area=round(a, 1),
                        whole=abs(a-w*h) < 1.0,
                        src=[ox, oy, w, h], ang=ang, org=[cx, cy]))
    return out


def basket_cells(R, L, J, n=3):
    """infinite triple-basketweave field, centred on the origin, as axis-aligned rects"""
    B = n*W + (n-1)*J
    P = B + J
    k = int(R/P)+2
    cells = []
    for iy in range(-k, k+1):
        for ix in range(-k, k+1):
            x, y = ix*P, iy*P
            for i in range(n):
                if (ix+iy) % 2 == 0: cells.append((x, y+i*(W+J), L, W))
                else:                cells.append((x+i*(W+J), y, W, L))
    return cells
