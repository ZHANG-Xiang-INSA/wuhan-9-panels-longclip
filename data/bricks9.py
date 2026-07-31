# -*- coding: utf-8 -*-
"""The twelve brick types as PARTS, not as pieces of a board.

dxf/05 and drawings/S7 show every slip where it is laid.  That is what the setter needs and it is
useless to the yard, which has to cut B01 x 1115, B04 x 34 and so on and never sees a board.  This
module turns site/data/boards.json - the same file the website and the model read - into one
canonical outline per brick type, squared up and ready to dimension.  bricks9_dxf.py draws it 1:1
and bricks9_draw.py draws the readable sheet.

boards.json is the source rather than panels9.json because the B01..B12 codes are assigned there,
in site_export.py, and a part drawing that used its own numbering would be a second schedule for
the yard to reconcile.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
SLIP = (215.0, 65.0, 20.0)


def load():
    return json.load(open(os.path.join(HERE, '..', 'site', 'data', 'boards.json'),
                          encoding='utf-8'))


def ccw(p):
    a = sum(p[i-1][0]*p[i][1]-p[i][0]*p[i-1][1] for i in range(len(p)))
    return list(p) if a > 0 else list(p)[::-1]


def clean(poly, tol=2.0):
    """CCW, and without the sub-2 mm slivers the polygon clipper leaves on a 45 degree cut

    The same 2 mm the type classifier ignores, for the same reason: nobody saws to it, and an
    11 mm edge with a 0.3 mm stub hanging off it would be dimensioned as two edges.
    """
    p = ccw([tuple(q) for q in poly])
    out = []
    for i, q in enumerate(p):
        if math.dist(q, p[i-1]) >= tol:
            out.append(q)
    return out


def sig(poly, nd=1):
    """rotation-invariant fingerprint: (edge, turn) round the outline, least cyclic rotation"""
    p = clean(poly)
    n = len(p)
    s = []
    for i in range(n):
        a, b, c = p[i-1], p[i], p[(i+1) % n]
        v1 = (b[0]-a[0], b[1]-a[1]); v2 = (c[0]-b[0], c[1]-b[1])
        s.append((round(math.dist(a, b), nd),
                  round(math.degrees(math.atan2(v1[0]*v2[1]-v1[1]*v2[0],
                                                v1[0]*v2[0]+v1[1]*v2[1])), 0)))
    return min(tuple(s[i:]+s[:i]) for i in range(n))


def square_up(poly):
    """the part as it would be set down to cut: longest edge along +x, material above it

    Field pieces are stored at whatever angle the bond laid them - board 8's are all at 45 - so
    drawn as stored, the same part appears at four different angles and nobody can see it is one
    part.  The longest edge is the one a saw fence is set against, so that is the datum.
    """
    p = clean(poly)
    n = len(p)
    i = max(range(n), key=lambda k: math.dist(p[k-1], p[k]))
    a, b = p[i-1], p[i]
    L = math.dist(a, b)
    c, s = (b[0]-a[0])/L, (b[1]-a[1])/L
    q = [((x-a[0])*c+(y-a[1])*s, -(x-a[0])*s+(y-a[1])*c) for x, y in p]
    ys = [v[1] for v in q]
    if sum(ys)/len(ys) < 0:                       # material below the datum: turn it over the edge
        q = [(x, -y) for x, y in q][::-1]
    xs = [v[0] for v in q]; ys = [v[1] for v in q]
    return [(round(x-min(xs), 4), round(y-min(ys), 4)) for x, y in q]


def types():
    """-> list of dicts, one per brick type, in the schedule's own order

    poly    the canonical outline, squared up, origin at its bottom-left
    edges   [(p0, p1, length)] round it
    angles  [(vertex, interior angle in degrees)]
    """
    D = load()
    where = {}
    for b in D['summary']['bricks']:
        for u in b['use']:
            where[(u['board'], u['code'])] = b['code']
    grp, col = {}, {}
    for bd in D['boards']:
        for pc in bd['pieces']:
            ty = bd['types'][pc['t']]
            c = where.get((bd['idx'], ty['code']))
            if c:
                grp.setdefault(c, []).append(pc['p'])
                col.setdefault(c, ty['colour'])

    out = []
    for e in D['summary']['bricks']:
        polys = grp[e['code']]
        # The nominal outline is the one most of them are.  B04's 34 pieces are two families
        # 0.81 mm apart, which the classifier rounds together at 1 mm; the drawing carries the
        # majority figure rather than inventing an average nobody cut.
        cnt = {}
        for p in polys:
            k = sig(p, 0)
            cnt.setdefault(k, []).append(p)
        best = max(cnt.values(), key=len)
        q = square_up(best[0])
        n = len(q)
        edges = [(q[i-1], q[i], math.dist(q[i-1], q[i])) for i in range(n)]
        angles = []
        for i in range(n):
            a, b, c = q[i-1], q[i], q[(i+1) % n]
            # INTERIOR angle, so it is measured from the outgoing edge round to the incoming one.
            # Taken the other way round on a CCW outline it returns the explement - every right
            # angle read 270 and the drawing dimensioned all of them.
            v1 = (a[0]-b[0], a[1]-b[1]); v2 = (c[0]-b[0], c[1]-b[1])
            ang = math.degrees(math.atan2(v2[0]*v1[1]-v2[1]*v1[0], v2[0]*v1[0]+v2[1]*v1[1]))
            angles.append((b, ang % 360.0))
        xs = [v[0] for v in q]; ys = [v[1] for v in q]
        out.append(dict(e, poly=q, edges=edges, angles=angles, colour=col[e['code']],
                        bw=max(xs)-min(xs), bh=max(ys)-min(ys)))
    return out


if __name__ == '__main__':
    for t in types():
        print('%-4s %-6s %-20s x%-5d %2d sides  bbox %6.1f x %5.1f  area %6.0f'
              % (t['code'], t['kind'], t['label'], t['qty'], len(t['poly']),
                 t['bw'], t['bh'], t['area']))
