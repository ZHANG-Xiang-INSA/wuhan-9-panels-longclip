# -*- coding: utf-8 -*-
"""The rail clips the supplier actually stocks, and how a continuous run is made up out of them.

Replaces the searched single length.  LC-1366 was 1366 mm because that is what came out of a
search over the runs these nine boards offer, and the shop cannot make it: their line runs to a
fixed family, of which four lengths are on offer.  So the length is no longer a free variable.
What is left to decide is how to make up each run out of the four, and that is a packing problem
with a small answer.

    1000  700  300  100          available, from the supplier
    50                           the short clip that was already in the job, renamed R50
    2 mm                         between two clips end to end
    20 mm                        the most that may be left unclipped at each end of a run

GEOMETRY AND HOLE POSITIONS COME FROM THE SUPPLIER'S OWN DRAWING, dxf/guiding_rail_clip_10_types
_orthographic.dxf, and are not derived here.  They do not follow one rule - R1000 is 7 holes at
125 with a 125 end margin, R300 is 3 at 75, R100 is 2 at 25 - so a formula would have been a
guess dressed up as arithmetic.  R50's two holes at 12.5 and 37.5 are the same positions the job
has always used for it; only its name has changed, from RC-50.

The section is identical on every length: 68 flat, 15 legs, 10 lips returned 16 deg inward, a
62.5 opening, 0.25 sheet, 118 developed.  That is the same section the job has used throughout.
"""
import itertools

# code -> (length, [hole x from the left end])   from the supplier's drawing, sheet 1
FAMILY = {
    'R1000': (1000.0, [125.0, 250.0, 375.0, 500.0, 625.0, 750.0, 875.0]),
    'R700':  (700.0,  [100.0, 225.0, 350.0, 475.0, 600.0]),
    'R300':  (300.0,  [75.0, 150.0, 225.0]),
    'R100':  (100.0,  [25.0, 75.0]),
    'R50':   (50.0,   [12.5, 37.5]),
}
# The four the supplier has quoted.  R50 is not in that quotation - it is the clip the job was
# already using, one per slip, and it stays.  R20, R250 and R500 are on the same sheet and are
# NOT offered, so nothing here may reach for them however well they would fit.
STOCK = ('R1000', 'R700', 'R300', 'R100')
SHORT = 'R50'
GAP = 2.0                  # between two rails end to end in the same course
END_MAX = 20.0             # the most that may be left unclipped at either end of a run

# SCOPE.  This change replaces the long clip and nothing else.  R100 and R300 are short enough to
# sit on runs that have always taken one R50 per slip - board 6's 147 single slips would each
# take an R100, and the packer will happily do it - but that is a different job, affecting eight
# hundred positions and every board's drawings, and it is not what was asked for.  A run is in
# scope only if the searched clip could have gone in it: 1366 plus the 20 it stood off each end.
# The same 77 runs, on the same five boards, as before.
SCOPE_MIN = 1366.0+2*20.0
FLAT = 68.0
SLIP_W = 65.0
CLEAR = 2.0                # metal to metal between a rail and the R50 after it


def length(code):
    return FAMILY[code][0]


def holes(code):
    return list(FAMILY[code][1])


def long_ok(board):
    """can this board take rails longer than one slip at all?

    The flat is 68 across a 65 slip, so a clip stands 1.5 proud each side and wants 3 mm of joint
    to itself.  Below that the rails of neighbouring courses meet face to face, and the answer the
    R50 uses - slide each one to one side of its slip and alternate the side course by course -
    is not open to a clip that runs the length of a course.  Board 9 is laid on 3: 65 + 3 = 68 is
    exactly the flat, so it keeps its staggered R50s.  Board 7 is on 5 and is fine.
    """
    return board['joint'] > FLAT-SLIP_W+1e-9


def _tray_1d(piece, r, lo, hi, bias):
    """where this slip's R50 goes, in run coordinates: [t0, t1], or None if it cannot go on

    bias  -1 push it toward the datum end of the run, +1 toward the far end, 0 centre it.
    An R50 on the LAST slip of a run is pushed out to the end, because how far the clip system
    reaches is measured from there: centred on its own slip it can stop 30 mm short and fail the
    20 mm rule for no reason other than where the clip happened to be put.
    """
    L50 = length(SHORT)
    a, b = _span(piece, r['u'])
    a, b = a-r['s0'], b-r['s0']
    a, b = max(a, lo), min(b, hi)
    if b-a < L50-1e-9:
        return None
    if bias < 0:
        return [a, a+L50]
    if bias > 0:
        return [b-L50, b]
    c = (a+b)/2.0
    return [c-L50/2, c+L50/2]


def _simulate(r, combo, off, occ):
    """-> (r50 placements, near standoff, far standoff) or None if the 20 mm rule is broken"""
    L, pieces = r['length'], r['pieces']
    lo, hi = off, off+occ
    rest = [q for q in pieces if not (lo <= _along(q, r) <= hi)]
    spans, r50 = [(lo, hi)], []
    for q in rest:
        before = _along(q, r) < lo
        a, b = (0.0, lo-CLEAR) if before else (hi+CLEAR, L)
        bias = -1 if (before and q is pieces[0]) else (1 if (not before and q is pieces[-1]) else 0)
        t = _tray_1d(q, r, a, b, bias)
        if t is None:
            return None                       # a slip with nowhere to put its clip
        r50.append((q, t))
        spans.append(tuple(t))
    near = min(a for a, _ in spans)
    far = L-max(b for _, b in spans)
    if near > END_MAX+1e-9 or far > END_MAX+1e-9:
        return None
    return r50, near, far


def pack_run(r, stock=STOCK):
    """-> (chain, off, occ, r50) or None: how this run is made up

    Judged on the SLIPS, not on lengths alone.  A chain can end part way along the last slip,
    which leaves that slip held but the system reaching 50 mm short of the run's own end - and how
    far it reaches is exactly what the 20 mm rule is about.  So every candidate is simulated:
    which slips the chain covers, where the R50s then go, and what is really left open at each
    end.  Fewest pieces wins, then the most metal on the run.
    """
    L = r['length']
    best = None
    for k in range(1, 9):
        for combo in itertools.combinations_with_replacement(
                sorted(stock, key=lambda c: -length(c)), k):
            occ = sum(length(c) for c in combo)+GAP*(k-1)
            if occ > L+1e-9:
                continue
            res = L-occ
            for off in sorted({0.0, min(res, END_MAX), res/2.0}):
                if off > END_MAX+1e-9 or off > res+1e-9:
                    continue
                got = _simulate(r, combo, off, occ)
                if got is None:
                    continue
                cost = (k+len(got[0]), -occ)
                if best is None or cost < best[0]:
                    best = (cost, (list(combo), off, occ, got[0]))
    return best[1] if best else None


def tray(r, s0, L, half=FLAT/2.0):
    """a rail's footprint on the run: 68 across, L along, starting s0 from the datum end

    The across coordinate is t + off, not off.  t is which course the run is on; dropping it put
    every rail on the board's own datum line, stacked on each other and half of them off the board.
    """
    u, v, t = r['u'], r['v'], r['t']

    def pt(s, off):
        w = t+off
        return [round(u[0]*s+v[0]*w, 3), round(u[1]*s+v[1]*w, 3)]

    return [pt(s0, -half), pt(s0+L, -half), pt(s0+L, half), pt(s0, half)]


def hole_pts(r, s0, code):
    u, v, t = r['u'], r['v'], r['t']
    return [[round(u[0]*(s0+h)+v[0]*t, 3), round(u[1]*(s0+h)+v[1]*t, 3)] for h in holes(code)]


def _along(piece, r):
    u = r['u']
    c = sum(q[0]*u[0]+q[1]*u[1] for q in piece['p'])/len(piece['p'])
    return c-r['s0']


def _span(piece, u):
    s = [q[0]*u[0]+q[1]*u[1] for q in piece['p']]
    return min(s), max(s)


def _tray_from_1d(r, t):
    """a 1-D span along the run turned into the tray quad on the board"""
    u, v, tt = r['u'], r['v'], r['t']
    a, b = r['s0']+t[0], r['s0']+t[1]
    h = FLAT/2.0

    def pt(sv, off):
        w = tt+off
        return [round(u[0]*sv+v[0]*w, 3), round(u[1]*sv+v[1]*w, 3)]

    return [pt(a, -h), pt(b, -h), pt(b, h), pt(a, h)]


def plan(board):
    """-> dict(rails=[...], r50=[...], runs=[...])  what this board gets

    rails  one per rail longer than an R50: dict(code, tray, holes, s0, covers)
    r50    the pieces that keep an R50, in the board's own piece order, with the tray the
           simulation put there rather than the one boards.json carries
    """
    from runs9 import runs as _runs
    R = _runs(board)
    ok = long_ok(board)
    rails, keep = [], []
    for r in R:
        p = pack_run(r) if (ok and r['length'] >= SCOPE_MIN-1e-9) else None
        if not p:
            keep.extend(dict(piece=q, tray=list(q['k']), moved=False) for q in r['pieces'])
            continue
        combo, off, occ, r50 = p
        s = r['s0']+off
        lo, hi = off, off+occ
        for code in combo:
            L = length(code)
            covers = [q for q in r['pieces'] if lo <= _along(q, r) <= hi
                      and s-r['s0'] <= _along(q, r) <= s-r['s0']+L]
            rails.append(dict(code=code, tray=tray(r, s, L), holes=hole_pts(r, s, code),
                              s0=s, run=r, covers=covers))
            s += L+GAP
        for q, t in r50:
            tr = _tray_from_1d(r, t)
            keep.append(dict(piece=q, tray=tr, moved=tr != list(q['k'])))
    order = {id(q): i for i, q in enumerate(board['pieces'])}
    keep.sort(key=lambda e: order[id(e['piece'])])
    return dict(rails=rails, r50=keep, runs=R)


if __name__ == '__main__':
    import io, sys, json, os
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from runs9 import load
    D = load()
    print('available: ' + ', '.join('%s %g mm, %d holes' % (c, length(c), len(holes(c)))
                                    for c in STOCK)
          + '   |   %s %g mm, %d holes' % (SHORT, length(SHORT), len(holes(SHORT))))
    print('rule: %g mm between rails, at most %g mm left open at each end of a run\n'
          % (GAP, END_MAX))
    tot, n50 = {}, 0
    print('board  joint  runs  rails on this board                      R50')
    for b in D['boards']:
        p = plan(b)
        c = {}
        for x in p['rails']:
            c[x['code']] = c.get(x['code'], 0)+1
            tot[x['code']] = tot.get(x['code'], 0)+1
        n50 += len(p['r50'])
        print('  %d    %4g   %4d  %-38s %4d'
              % (b['idx'], b['joint'], len(p['runs']),
                 ', '.join('%s x%d' % kv for kv in sorted(c.items())) or '-', len(p['r50'])))
    print('\n  ' + ', '.join('%s x%d' % kv for kv in sorted(tot.items()))
          + ', %s x%d' % (SHORT, n50))
    print('  %d pieces in all, against 1414 one to a slip' % (sum(tot.values())+n50))
