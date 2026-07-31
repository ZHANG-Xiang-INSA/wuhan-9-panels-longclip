# -*- coding: utf-8 -*-
"""The long clip: one standard length for all nine boards, found by search, and where each one goes.

Same section as RC-50 - 68 flat, 15 legs, 10 lips returned 16 deg - so nothing about how a slip is
held changes.  Only the length differs, and with it the number of separate pieces a fitter handles.

THE LENGTH IS NOT WRITTEN DOWN ANYWHERE.  standard() searches every length from 150 to 1600 in
half-millimetre steps against the runs the nine boards actually offer, keeps the ones whose holes
divide equally at the 125 pitch with equal end margins, discards any that would leave a run with a
stub too short to take an RC-50, and returns the one that leaves the fewest pieces on the job.
Change a board and the length changes with it.

Long clips are laid from the run's datum end, and whatever is left over at the far end keeps the
RC-50s it always had.

Not every board can take one.  See long_ok(): board 9's 3 mm joint puts the courses at exactly the
clip's own flat, and a clip that runs the whole course cannot be staggered out of the way, so board
9 keeps the RC-50s it was designed with.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
from runs9 import load, runs

PITCH = 125.0                  # the hole pitch asked for
M_MIN, M_MAX = 12.5, 62.5      # end margin: never nearer the end than an RC-50's own hole, never
                               # so far out that another hole would fit at the pitch
R50_LEN = 50.0                 # an RC-50, and so the shortest leftover that can still be filled
END_GAP = 20.0                 # a long clip stops short of each end of its run by at least this,
END_GAP_MAX = 30.0             # and by no more than this where the arithmetic allows it.  Running
                               # a clip hard into the end of a course buys nothing and costs metal
FLAT = 68.0
SLIP_W = 65.0
_CACHE = {}


def long_ok(board):
    """can this board take long clips at all?

    The flat is 68 across a 65 slip, so a clip stands 1.5 proud on each side and wants 3 mm of
    joint to itself.  Where the joint is smaller than that, the rails of two neighbouring courses
    meet face to face.  The RC-50 answer is to slide each rail wholly to one side of its own slip
    and alternate the side course by course, so the two pass at a corner - see bias() in
    site_export - but that answer is not open to a clip which runs the whole length of a course:
    there is no course left to alternate against.

    Board 9 is laid on 3.  65 + 3 = 68 is exactly the flat, so long clips in successive courses
    would butt along their whole length and the board would finish with no joint down it at all.
    It keeps its staggered RC-50s, unchanged from the original design.  Board 7 is laid on 5, which
    leaves 2 mm between courses, and is fine.
    """
    return board['joint'] > FLAT-SLIP_W+1e-9


def holes_for(L):
    """(count, margin) at PITCH with equal end margins, or None if L admits none"""
    best = None
    for n in range(2, 40):
        m = (L-PITCH*(n-1))/2.0
        if M_MIN-1e-9 <= m <= M_MAX+1e-9:
            best = (n, m)
    return best


def _score(L, ALL):
    h = holes_for(L)
    if not h:
        return None
    n, m = h
    long_n = r50_n = 0
    for ok, R in ALL.values():
        for r in R:
            if not ok:
                r50_n += r['n']      # a board no long clip may go on still costs its RC-50s, and
                continue             # counting them keeps the reported totals the job's totals
            usable = r['length']-2*END_GAP
            k = int((usable+1e-9)//L) if usable >= L else 0
            left = r['length']-END_GAP-k*L
            if k and 1e-9 < left < R50_LEN-1e-9:
                return None                       # a stub no RC-50 can fill: reject the length
            if not k:
                r50_n += r['n']
            else:
                long_n += k
                end = r['s0']+END_GAP+k*L
                for p in r['pieces']:
                    if _along(p, r) > END_GAP+k*L:
                        if r50_tray(p, r, end) is None:
                            return None       # a leftover slip with nowhere to put its RC-50
                        r50_n += 1
    return dict(L=L, holes=n, margin=m, long=long_n, r50=r50_n, pieces=long_n+r50_n,
                drilled=long_n*n+r50_n*2)


CLEAR = 2.0                    # metal-to-metal gap between a long clip and the RC-50 after it


def _along(piece, r):
    """how far the piece's centre sits along the run from its datum end"""
    u = r['u']
    c = sum(q[0]*u[0]+q[1]*u[1] for q in piece['p'])/len(piece['p'])
    return c-r['s0']


def _span(piece, u):
    s = [q[0]*u[0]+q[1]*u[1] for q in piece['p']]
    return min(s), max(s)


def r50_tray(piece, r, end_s):
    """where this slip's RC-50 goes once a long clip has taken the first part of the run

    An RC-50 sits on the middle of its own slip.  Where the long clip stops part way along that
    slip - board 4 ends at 1375 on a slip running 1332 to 1436, board 9 at 1375 on one running
    1308 to 1523 - the centred tray backs into the long clip by 16 and 9.5 mm.  So the clip is
    centred on what is LEFT of the slip instead, clear of the long clip's end.  end_s is None on a
    run with no long clip, and then nothing moves.
    """
    if end_s is None:
        return list(piece['k'])
    u, v, t = r['u'], r['v'], r['t']
    a, b = _span(piece, u)
    lo = max(a, end_s+CLEAR)
    if b-lo < R50_LEN-1e-9:
        return None                                   # cannot be installed: caller must reject
    c = (lo+b)/2.0

    def pt(s, off):
        w = t+off
        return [round(u[0]*s+v[0]*w, 3), round(u[1]*s+v[1]*w, 3)]

    h = FLAT/2.0
    return [pt(c-R50_LEN/2, -h), pt(c+R50_LEN/2, -h), pt(c+R50_LEN/2, h), pt(c-R50_LEN/2, h)]


def standard(D=None):
    """-> dict(L, holes, margin, pieces, ...)  the one length, and what it costs"""
    if 'std' in _CACHE:
        return _CACHE['std']
    D = D or load()
    ALL = {bd['idx']: (long_ok(bd), runs(bd)) for bd in D['boards']}
    best, x = None, 150.0
    while x <= 1600.0:
        e = _score(x, ALL)
        # fewest pieces on the job; then fewest holes to drill; then the longest, which is the
        # one whose margin comes out at half the pitch, so butted clips keep the 125 going
        if e and (best is None or (e['pieces'], e['drilled'], -e['L'])
                  < (best['pieces'], best['drilled'], -best['L'])):
            best = e
        x += 0.5
    _CACHE['std'] = best
    return best


def code(std=None):
    std = std or standard()
    return 'LC-%g' % std['L']


def tray(r, s0, L, half=FLAT/2.0):
    """the long clip's own tray, laid on the run: 68 across, L along, from s0

    The across coordinate is t + off, not off.  t is which course the run is on; dropping it put
    every long clip on the board's own datum line, stacked on top of each other and half of them
    off the board.
    """
    u, v, t = r['u'], r['v'], r['t']

    def pt(s, off):
        w = t+off
        return [round(u[0]*s+v[0]*w, 3), round(u[1]*s+v[1]*w, 3)]

    return [pt(s0, -half), pt(s0+L, -half), pt(s0+L, half), pt(s0, half)]


def hole_pts(r, s0, std):
    u, v, t = r['u'], r['v'], r['t']
    out = []
    for k in range(std['holes']):
        s = s0+std['margin']+k*PITCH
        out.append([round(u[0]*s+v[0]*t, 3), round(u[1]*s+v[1]*t, 3)])
    return out


def plan(board, std=None):
    """-> dict(longs=[...], r50=[piece, ...], runs=[...])  what this board gets

    longs  one entry per long clip: dict(tray, holes, run, s0, covers=[pieces it lies on])
    r50    the pieces that keep an RC-50, in the board's own piece order
    """
    std = std or standard()
    L = std['L']
    R = runs(board)
    longs, keep = [], []
    ok = long_ok(board)
    for r in R:
        usable = r['length']-2*END_GAP if ok else -1.0
        k = int((usable+1e-9)//L) if usable >= L else 0
        if not k:
            keep.extend(dict(piece=p, tray=list(p['k']), moved=False) for p in r['pieces'])
            continue
        # centre the run of long clips in the course where the slack allows, but never closer
        # than END_GAP and never further out than END_GAP_MAX
        gap = min(END_GAP_MAX, max(END_GAP, (r['length']-k*L)/2.0))
        for j in range(k):
            s0 = r['s0']+gap+j*L
            covers = [p for p in r['pieces']
                      if gap+j*L <= _along(p, r) <= gap+(j+1)*L]
            longs.append(dict(tray=tray(r, s0, L), holes=hole_pts(r, s0, std),
                              s0=s0, run=r, covers=covers))
        end = r['s0']+gap+k*L
        for p in r['pieces']:
            if not (gap <= _along(p, r) <= gap+k*L):
                t2 = r50_tray(p, r, end)
                keep.append(dict(piece=p, tray=t2, moved=t2 != list(p['k'])))
    order = {id(p): i for i, p in enumerate(board['pieces'])}
    keep.sort(key=lambda e: order[id(e['piece'])])
    return dict(longs=longs, r50=keep, runs=R, std=std)


if __name__ == '__main__':
    D = load()
    std = standard(D)
    print('standard long clip, found by search over 150..1600 mm in 0.5 mm steps')
    print('  length %.1f mm   %d holes at %g pitch   end margin %.2f (= pitch/%.1f)'
          % (std['L'], std['holes'], PITCH, std['margin'], PITCH/std['margin']))
    print('  %d long + %d RC-50 = %d pieces, %d holes drilled'
          % (std['long'], std['r50'], std['pieces'], std['drilled']))
    base = sum(len(b['pieces']) for b in D['boards'])
    print('  as built: %d clips, %d holes   ->  %+d pieces, %+d holes'
          % (base, base*2, std['pieces']-base, std['drilled']-base*2))
    print()
    print('board  long  RC-50  total  was   verdict')
    tl = tr = 0
    for bd in D['boards']:
        p = plan(bd, std)
        nl, nr = len(p['longs']), len(p['r50'])
        tl += nl; tr += nr
        v = ('unchanged' if nl == 0 else
             'all runs' if all(int((r['length']+1e-9)//std['L']) for r in p['runs'])
             else 'partial')
        print('  %d    %4d   %4d   %4d  %4d   %s'
              % (bd['idx'], nl, nr, nl+nr, len(bd['pieces']), v))
    print('       %4d   %4d   %4d  %4d' % (tl, tr, tl+tr, base))
