# -*- coding: utf-8 -*-
"""What gets drawn ON the backing board, so a fitter never has to work out where anything goes.

dxf/05 and S7 show the finished face; dxf/07 and S9 show the parts.  Neither tells the man holding
a slip where on the board it goes, and on a herringbone with five brick types and two clip types
that is the whole job.  This module turns site/data/boards.json into the setting-out for each
board: every slip's outline, every clip's tray, the two fixing holes under each clip, and a type
code inside each of them.  setout9_dxf.py plots it for the board maker to scribe on; setout9_tex.py
bakes the same thing to a texture so the 3D model and the website show it under the slips.

One clip per slip on all nine boards, so a slip outline and a clip outline are a pair everywhere.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
# One text height for every label, brick and clip alike.  The tightest cases are the RC-50 tray at
# 50 x 68 and board 3's T03 slip, and both hold this with room to spare; see setout9_dxf --check.
TXT_H = 9.0
# clearance a label needs round its anchor: half the widest code plus half the height, and a
# little over.  Below this the brick code cannot be fitted beside the tray and is stacked instead.
NEED = 16.0
# how far a label keeps off a fixing hole: the cross drawn through it reaches 6.5, and half a
# label's height is 4.5, so 12 leaves the drill mark readable.
HOLE_KEEP = 12.0
SHORT = {'RC-50': 'R50', 'PK-3T03': 'P3T03', 'PK-8T02': 'P8T02'}


def short(code):
    return SHORT.get(code, code.replace('LC-', 'L') if code.startswith('LC-') else code)


def load():
    return json.load(open(os.path.join(HERE, '..', 'site', 'data', 'boards.json'),
                          encoding='utf-8'))


def _fit(src, dst):
    """the rigid motion that carries polygon src onto polygon dst, rotation and translation only

    site_export.place_tray() already put each clip's real tray down on its piece, so boards.json
    carries the placed tray but not the placed holes.  Rather than repeat the vertex-order search
    that put it there, the motion is recovered from the two polygons - they are the same points in
    the same order - and then applied to whatever else needs carrying, which is the hole centres.
    """
    n = min(len(src), len(dst))
    cs = (sum(q[0] for q in src)/len(src), sum(q[1] for q in src)/len(src))
    cd = (sum(q[0] for q in dst)/len(dst), sum(q[1] for q in dst)/len(dst))
    num = sum((src[i][0]-cs[0])*(dst[i][1]-cd[1])-(src[i][1]-cs[1])*(dst[i][0]-cd[0])
              for i in range(n))
    den = sum((src[i][0]-cs[0])*(dst[i][0]-cd[0])+(src[i][1]-cs[1])*(dst[i][1]-cd[1])
              for i in range(n))
    th = math.atan2(num, den)
    c, s = math.cos(th), math.sin(th)
    return lambda p: (cd[0]+(p[0]-cs[0])*c-(p[1]-cs[1])*s,
                      cd[1]+(p[0]-cs[0])*s+(p[1]-cs[1])*c), math.degrees(th)


def pole(poly, step=2.0, avoid=None, keepout=()):
    """the point inside poly furthest from its boundary, for putting a label on

    The centroid is not good enough: board 3's T03 is a thin wedge and board 8's T02 a triangle,
    and on both the centroid sits close enough to an edge that a label crosses the outline.  This
    is a coarse grid search refined twice, which is ample for placing 9 mm text.

    avoid is a second polygon the point must stay out of.  The brick label needs it: the clip tray
    sits inside the slip, and on a 102.5 x 65 slip the tray is 50 x 68, so the best point in the
    slip alone is underneath the tray and the two labels printed on top of each other.

    keepout is a list of (x, y, r) the point must also stay clear of.  The fixing holes go in it:
    an RC-50's two holes straddle the centre of its own tray, so the clip label landed straight on
    both drill marks - 263 labels across the nine boards sat on a hole before this was added, and
    the hole is the one thing on the drawing that actually gets cut.
    """
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
    lo, hi = (min(xs), min(ys)), (max(xs), max(ys))
    best, bd = ((lo[0]+hi[0])/2, (lo[1]+hi[1])/2), -1e9
    for _ in range(3):
        x = lo[0]
        while x <= hi[0]:
            y = lo[1]
            while y <= hi[1]:
                d = _inside_dist(poly, (x, y))
                if avoid is not None:
                    a = _inside_dist(avoid, (x, y))
                    d = min(d, -a)               # outside the tray, and clear of its edge
                for hx, hy, r in keepout:
                    d = min(d, math.hypot(x-hx, y-hy)-r)
                if d > bd:
                    bd, best = d, (x, y)
                y += step
            x += step
        lo = (best[0]-step, best[1]-step); hi = (best[0]+step, best[1]+step)
        step /= 4.0
    return best, bd


def _inside_dist(poly, p):
    """signed distance to the outline, positive inside"""
    n = len(poly)
    inside = False
    d = 1e18
    for i in range(n):
        a, b = poly[i-1], poly[i]
        if (a[1] > p[1]) != (b[1] > p[1]):
            if p[0] < a[0]+(p[1]-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                inside = not inside
        vx, vy = b[0]-a[0], b[1]-a[1]
        L2 = vx*vx+vy*vy or 1.0
        t = max(0.0, min(1.0, ((p[0]-a[0])*vx+(p[1]-a[1])*vy)/L2))
        d = min(d, math.hypot(p[0]-(a[0]+t*vx), p[1]-(a[1]+t*vy)))
    return d if inside else -d


def strw(s, h):
    return h*sum(1.05 if ord(c) > 0x2E80 else 0.62 for c in s)


def _rad(code, h):
    """half-diagonal of a label's box, which is what has to fit inside the clearance"""
    return math.hypot(strw(code, h)/2+1.5, h/2+1.5)


def _seg_box(a, b, x0, y0, x1, y1):
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
        return True
    if x0 <= b[0] <= x1 and y0 <= b[1] <= y1:
        return True
    for p, q in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                 ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        d1 = (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        d2 = (b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0])
        d3 = (q[0]-p[0])*(a[1]-p[1])-(q[1]-p[1])*(a[0]-p[0])
        d4 = (q[0]-p[0])*(b[1]-p[1])-(q[1]-p[1])*(b[0]-p[0])
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
    return False


def _bbox(poly):
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
    return min(xs), min(ys), max(xs), max(ys)


def box_in(poly, c, w, h, pad=1.5):
    """is the label box at c wholly inside poly?

    The real rectangle, not a circle round it.  A circle is far too pessimistic on the shapes this
    job cuts: board 8's T02 is a wide flat triangle, and a 27.9 x 9 label lies down in it happily
    while the circle that contains that label does not.
    """
    x0, y0 = c[0]-w/2-pad, c[1]-h/2-pad
    x1, y1 = c[0]+w/2+pad, c[1]+h/2+pad
    if _inside_dist(poly, c) <= 0:
        return False
    for k in range(len(poly)):
        if _seg_box(poly[k-1], poly[k], x0, y0, x1, y1):
            return False
    return True


def _clear_ko(c, w, h, ko):
    for hx, hy, r in ko:
        if abs(hx-c[0]) < w/2+r*0.55 and abs(hy-c[1]) < h/2+r*0.55:
            return False
    return True


def _spots(poly, w, h, ko, step=4.0):
    """every grid point where the box fits inside poly and clears the holes, best clearance first"""
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
    out = []
    x = min(xs)
    while x <= max(xs):
        y = min(ys)
        while y <= max(ys):
            c = (x, y)
            if _clear_ko(c, w, h, ko) and box_in(poly, c, w, h):
                out.append((_inside_dist(poly, c), c))
            y += step
        x += step
    out.sort(reverse=True)
    return out


def place(slip, tray, ko, tcode, ccode, extra=()):
    """where the two codes go, and how big they are

    extra is any OTHER tray lying across this slip - a long clip whose end falls inside it.  The
    brick code keeps off those the same way it keeps off the piece's own tray.

    The brick code goes in the brick and the clip code in the clip, so the brick code keeps off
    the tray.  On a pocket clip that is impossible - the tray IS the slip's outline pushed 1.5 out,
    so it covers the piece - and the two are stacked instead, brick above clip.

    Height comes down only where a piece genuinely cannot hold the pair.  Board 8's T02 is a
    65/65/92 triangle of 2099 mm2 whose largest inscribed circle has a radius of 19: a 9 mm P8T02
    needs 14.7 of that and a 9 mm T02 another 9.5, and their centres would have to be 24 apart, so
    both inside at 9 is not a matter of placing them better, it is impossible.  The brick label and
    the clip label always come down together, so the pair still reads at one size.
    """
    for h in (TXT_H, 8.0, 7.0, 6.0, 5.0, 4.0):
        tw_, ch_ = strw(tcode, h), h
        cw_ = strw(ccode, h)
        cs = _spots(tray, cw_, ch_, ko)
        if not cs:
            continue
        cl = cs[0][1]
        # first choice: the brick code beside the tray, each code in its own outline.  The whole
        # box has to be clear of the tray, not just its centre - testing the centre alone left 172
        # brick codes straddling a tray edge.
        clean = lambda t: all(_outside(x, t, tw_, ch_) or box_in(x, t, tw_, ch_) for x in extra)
        for _, t in _spots(slip, tw_, ch_, ko):
            if _outside(tray, t, tw_, ch_) and clean(t) \
                    and not _overlap(t, tw_, ch_, cl, cw_, ch_):
                return t, cl, h, False
        # the tray covers the slip, so they stack.  Wholly inside the tray for preference, so
        # the code does not straddle the tray outline; inside the slip at worst.
        cands = [t for _, t in _spots(slip, tw_, ch_, ko)
                 if not _overlap(t, tw_, ch_, cl, cw_, ch_)]
        for t in cands:
            if box_in(tray, t, tw_, ch_) and clean(t):
                return t, cl, h, True
        for t in cands:
            if clean(t):
                return t, cl, h, True
        if cands:
            return cands[0], cl, h, True
    return pole(slip)[0], pole(tray)[0], 4.0, True


def _outside(poly, c, w, h, pad=1.5):
    """is the label box wholly outside poly?  centre out, and no edge cutting the box"""
    if _inside_dist(poly, c) > 0:
        return False
    x0, y0 = c[0]-w/2-pad, c[1]-h/2-pad
    x1, y1 = c[0]+w/2+pad, c[1]+h/2+pad
    for k in range(len(poly)):
        if _seg_box(poly[k-1], poly[k], x0, y0, x1, y1):
            return False
    return True


def _overlap(a, aw, ah, b, bw, bh, gap=2.5):
    return (abs(a[0]-b[0]) < (aw+bw)/2+gap) and (abs(a[1]-b[1]) < (ah+bh)/2+gap)


def _seg_dist(p, a, b):
    vx, vy = b[0]-a[0], b[1]-a[1]
    L2 = vx*vx+vy*vy or 1.0
    t = max(0.0, min(1.0, ((p[0]-a[0])*vx+(p[1]-a[1])*vy)/L2))
    return math.hypot(p[0]-(a[0]+t*vx), p[1]-(a[1]+t*vy))


def _long_label(tray, holes, edges, code):
    """where the long clip's own code goes

    The tray is 1375 x 68 with eleven holes down its centreline and the perpends of every slip it
    covers crossing it, so the middle of it is the one place the label cannot go.  Candidates are
    the midpoints between consecutive holes, offset either side of the centreline; the one
    furthest from any slip line wins.
    """
    if len(holes) < 2:
        return (sum(q[0] for q in tray)/4.0, sum(q[1] for q in tray)/4.0)
    ux = holes[1][0]-holes[0][0]; uy = holes[1][1]-holes[0][1]
    L = math.hypot(ux, uy) or 1.0
    ux, uy = ux/L, uy/L
    nx, ny = -uy, ux
    near = [e for e in edges
            if _seg_dist(holes[len(holes)//2], e[0], e[1]) < 900]
    best, bd = None, -1e9
    for i in range(len(holes)-1):
        mx = (holes[i][0]+holes[i+1][0])/2.0
        my = (holes[i][1]+holes[i+1][1])/2.0
        for off in (20.0, -20.0):
            c = (mx+nx*off, my+ny*off)
            d = min([_seg_dist(c, a, bb) for a, bb in near] or [999])
            d = min(d, min(math.dist(c, h) for h in holes))
            if d > bd:
                bd, best = d, c
    return best


def board(idx):
    """-> dict(w, h, joint, pieces=[...])  everything one board needs drawn on it

    Each piece:  slip     the outline as laid
                 tcode    the brick type code, T01..T05
                 tlab     where to put it, and the clearance there
                 tray     the clip's own tray outline as laid
                 ccode    the clip type, shortened for the board
                 clab     where to put it
                 holes    the two fixing centres, carried onto this instance
                 angle    how far the clip is turned, degrees, for reference
    """
    D = load()
    b = [x for x in D['boards'] if x['idx'] == idx][0]
    CG = D['clipgeo']
    # which long clip lies on each covered piece, so its brick code can keep off that tray
    covered = {}
    LONGS = []
    for lc in b.get('longs', []):
        tray = [tuple(q) for q in lc['k']]
        ko = [(hx, hy, HOLE_KEEP) for hx, hy in lc['holes']]
        LONGS.append((tray, ko, _bbox(tray)))
        for i in lc['covers']:
            covered[i] = (tray, ko)
    out = []
    for pi, pc in enumerate(b['pieces']):
        slip = [tuple(q) for q in pc['p']]
        if pi in covered:
            # held by a long clip: the slip still gets its brick code, but the clip box and its
            # code belong to the long clip, which is drawn once for the whole run.  The code has
            # to keep off that tray and its holes, exactly as it keeps off an RC-50's.
            ltray, lko = covered[pi]
            tcode = b['types'][pc['t']]['code']
            tl, th = None, TXT_H
            for h in (TXT_H, 8.0, 7.0, 6.0, 5.0):
                w = strw(tcode, h)
                sp = [c for _, c in _spots(slip, w, h, lko) if _outside(ltray, c, w, h)]
                if sp:
                    tl, th = sp[0], h
                    break
            if tl is None:
                # Nothing fits beside the long clip on a piece this small - a 104 x 65 closer is
                # narrower than the 68 tray, so every point of it is under the rail - and the code
                # sits ON the tray instead: still inside its own slip, still clear of the holes.
                # WHOLLY inside the tray for preference.  Taking the best clear spot outright put
                # board 2's ten T02 codes across the end line of the long clip they sit on, the
                # one place on the piece where a tray outline crosses it.
                for h in (TXT_H, 8.0, 7.0, 6.0, 5.0, 4.0):
                    w = strw(tcode, h)
                    sp = _spots(slip, w, h, lko)
                    inner = [c for _, c in sp if box_in(ltray, c, w, h)]
                    if inner:
                        tl, th = inner[0], h
                        break
                    if sp:
                        tl, th = sp[0][1], h
                        break
            if tl is None:
                tl = pole(slip, keepout=lko)[0]
            out.append(dict(slip=slip, tray=None, holes=[], angle=0.0, stacked=False,
                            tcode=tcode, tlab=tl, ccode=None, clab=None, th=th))
            continue
        tray = [tuple(q) for q in pc['k']]
        g = CG[pc['c']]
        base = [tuple(q) for q in g['base']]
        holes = []
        ang = 0.0
        if len(base) == len(tray):
            mv, ang = _fit(base, tray)
            holes = [mv(tuple(q)) for q in g['holes']]
        ko = [(hx, hy, HOLE_KEEP) for hx, hy in holes]
        # A piece that keeps its own clip can still have a LONG clip lying across part of it: the
        # last slip of a run is only partly past the long clip's end, and that end line runs
        # through it.  place() only ever knew about the piece's own tray, so board 2's ten T02
        # closers printed their code straight across it.  Every long clip whose box reaches this
        # slip is handed over as well, tray and holes both.
        sb = _bbox(slip)
        near = [(t, k) for t, k, tb in LONGS
                if tb[0] <= sb[2] and sb[0] <= tb[2] and tb[1] <= sb[3] and sb[1] <= tb[3]]
        for _, k in near:
            ko = ko+k
        tcode = b['types'][pc['t']]['code']
        ccode = SHORT.get(pc['c'], pc['c'])
        tl, cl, th, stacked = place(slip, tray, ko, tcode, ccode,
                                    extra=[t for t, _ in near])
        out.append(dict(slip=slip, tray=tray, holes=holes, angle=ang, stacked=stacked,
                        tcode=tcode, tlab=tl, ccode=ccode, clab=cl, th=th))
    longs = []
    lcode = short(D['summary']['longclip']['code'])
    edges = [(q, r['slip'][j-1]) for r in out for j, q in enumerate(r['slip'])]
    for lc in b.get('longs', []):
        tr = [tuple(q) for q in lc['k']]
        hs = [tuple(q) for q in lc['holes']]
        longs.append(dict(tray=tr, holes=hs, ccode=lcode, th=TXT_H,
                          clab=_long_label(tr, hs, edges, lcode)))
    return dict(w=b['w'], h=b['h'], joint=b['joint'], idx=idx, longs=longs,
                zh=b['zh'], en=b['en'], pieces=out,
                types=[(t['code'], t['label'], t['qty']) for t in b['types']],
                clips=[(SHORT.get(c['code'], c['code']), c['code'], c['qty'])
                       for c in b['clips']])


if __name__ == '__main__':
    print('board  pieces  holes  tightest brick label  tightest clip label  (clearance mm at h=%g)'
          % TXT_H)
    worst = 1e9
    for i in range(1, 10):
        B = board(i)
        tb = min(p['tclr'] for p in B['pieces'])
        tc = min(p['cclr'] for p in B['pieces'])
        worst = min(worst, tb, tc)
        print('  %d    %4d   %4d      %6.1f              %6.1f'
              % (i, len(B['pieces']), sum(len(p['holes']) for p in B['pieces']), tb, tc))
    print('\ntightest clearance anywhere: %.1f mm; a %g mm capital needs about %.1f'
          % (worst, TXT_H, TXT_H/2))
