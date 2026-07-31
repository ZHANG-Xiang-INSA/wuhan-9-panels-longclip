# -*- coding: utf-8 -*-
"""Continuous runs: the stretches of board where one long clip could replace several RC-50s.

A clip's tray is 68 ACROSS the slip - 65 plus the 1.5 it stands proud each side - and 50 ALONG it.
So the clip lies along the course, its two lips gripping the slip's two long edges, and a longer
clip of the same section simply carries on into the next slip of the same course.  A RUN is a
maximal chain of slips that a single clip could lie on: same direction, same band across the
course, and consecutive, with nothing between them but the perpend joint.

Nothing here decides a length.  It reports what the nine boards actually offer, and setout9_long
searches that for the one standard length.
"""
import json, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    return json.load(open(os.path.join(HERE, '..', 'site', 'data', 'boards.json'),
                          encoding='utf-8'))


def tray_axis(k):
    """-> (u, v) unit vectors: u along the clip's 50, v across its 68"""
    n = len(k)
    best = None
    for i in range(n):
        a, b = k[i-1], k[i]
        L = math.dist(a, b)
        if best is None or abs(L-50.0) < abs(best[0]-50.0):
            best = (L, a, b)
    L, a, b = best
    u = ((b[0]-a[0])/L, (b[1]-a[1])/L)
    if u[0] < -1e-9 or (abs(u[0]) < 1e-9 and u[1] < 0):
        u = (-u[0], -u[1])
    return u, (-u[1], u[0])


def extent(poly, u):
    s = [q[0]*u[0]+q[1]*u[1] for q in poly]
    return min(s), max(s)


def runs(board, tol=2.0):
    """-> list of runs, each a dict(u, v, t, pieces, s0, s1, length, n)

    Two slips join a run when they lie on the same line across the course (same v offset of the
    tray centre, to a tenth) and the gap between their extents along the run is a joint.  Anything
    else - a different course, a bond that steps, a cut piece turned 45 - starts a new run.  A
    single slip with nothing beside it is a run of one, which is where an RC-50 stays.

    A JOINT, not THE joint.  Board 7 closes its staggered courses on 6.0 mm rather than its
    nominal 5.0 - 20 joints, the two either side of each closer, the 2 mm the course needs to
    reach 1535 - and requiring the nominal width split every one of those courses into
    104 + 1315 + 104 and left the board looking as though it could not be done.  A clip is
    continuous metal and does not care about a millimetre, so the test is the tolerance the rest
    of the job already works to: any gap up to the joint plus 2 mm is a joint.
    """
    J = board['joint']
    g = defaultdict(list)
    for pc in board['pieces']:
        u, v = tray_axis(pc['k'])
        cx = sum(q[0] for q in pc['k'])/len(pc['k'])
        cy = sum(q[1] for q in pc['k'])/len(pc['k'])
        t = cx*v[0]+cy*v[1]
        a, b = extent(pc['p'], u)
        g[(round(u[0], 4), round(u[1], 4), round(t, 1))].append((a, b, pc))
    out = []
    for (ux, uy, t), lst in g.items():
        u, v = (ux, uy), (-uy, ux)
        lst.sort(key=lambda z: z[0])
        cur = [lst[0]]
        for prev, nxt in zip(lst, lst[1:]):
            if -0.05 < nxt[0]-prev[1] <= J+tol:
                cur.append(nxt)
            else:
                out.append((u, v, t, cur)); cur = [nxt]
        out.append((u, v, t, cur))
    res = []
    for u, v, t, lst in out:
        s0 = min(x[0] for x in lst); s1 = max(x[1] for x in lst)
        res.append(dict(u=u, v=v, t=t, pieces=[x[2] for x in lst], s0=s0, s1=s1,
                        length=s1-s0, n=len(lst)))
    res.sort(key=lambda r: -r['length'])
    return res


if __name__ == '__main__':
    D = load()
    print('board  slips  runs   accounted   longest  gap   run lengths and how many slips')
    for bd in D['boards']:
        R = runs(bd)
        acc = sum(r['n'] for r in R)
        # every run's length must be its slips plus the gaps actually between them, and every one
        # of those gaps must be a joint - not the nominal joint, the real one.  Board 7 closes its
        # staggered courses on 6.0 against a nominal 5.0.
        ok, worst = True, 0.0
        for r in R:
            ext = sorted(extent(p['p'], r['u']) for p in r['pieces'])
            gaps = [b[0]-a[1] for a, b in zip(ext, ext[1:])]
            ok &= all(-0.05 < g <= bd['joint']+2.0 for g in gaps)
            ok &= abs(sum(b-a for a, b in ext)+sum(gaps)-r['length']) < 0.05
            worst = max([worst]+gaps)
        tally = defaultdict(int)
        for r in R:
            tally[(round(r['length'], 1), r['n'])] += 1
        top = sorted(tally.items(), key=lambda z: (-z[0][0], -z[1]))[:3]
        print('  %d    %4d   %4d   %s   %7.1f  %4.1f   %s'
              % (bd['idx'], len(bd['pieces']), len(R),
                 'OK ' if (acc == len(bd['pieces']) and ok) else 'BAD',
                 R[0]['length'], worst,
                 ', '.join('%.1f x%d slips, %d off' % (a, b, c) for (a, b), c in top)))
