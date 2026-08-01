# -*- coding: utf-8 -*-
"""The rail clips the supplier actually stocks, and how a continuous run is made up out of them.

Replaces the searched single length.  LC-1366 was 1366 mm because that is what came out of a
search over the runs these nine boards offer, and the shop cannot make it: their line runs to a
fixed family, of which four lengths are on offer.  So the length is no longer a free variable.
What is left to decide is how to make up each run out of the four, and that is a packing problem
with a small answer.

    1000  700  300  100          available, from the supplier
    50                           the short clip that was already in the job, renamed R50

FILL THE COURSE.  A run carries as much rail as the family can put in it: every length is a
multiple of 50, so the ceiling is floor(L/50)*50 and nothing beats it.  Clips may touch - there is
no minimum between them, only the ceiling on how much of the course may be left bare, which comes
out at nought because the two longest clips are set flush with the two ends.

Both ends flush, the rest butted on working inward, and the last clip - the one that reaches
neither neighbour - dead centre of the gap it is left with.  Every course of the same length on a
board is set out identically: a fitter sets a rail off the course below and cannot work to
dimensions that wander from one course to the next.

GEOMETRY AND HOLE POSITIONS COME FROM THE SUPPLIER'S OWN DRAWING, dxf/guiding_rail_clip_10_types
_orthographic.dxf, and are not derived here.  They do not follow one rule - R1000 is 7 holes at
125 with a 125 end margin, R300 is 3 at 75, R100 is 2 at 25 - so a formula would have been a
guess dressed up as arithmetic.  R50's two holes at 12.5 and 37.5 are the same positions the job
has always used for it; only its name has changed, from RC-50.

The section is identical on every length: 68 flat, 15 legs, 10 lips returned 16 deg inward, a
62.5 opening, 0.25 sheet, 118 developed.  That is the same section the job has used throughout.
"""
import itertools
import math

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
GAP = 0.0                  # two rails may touch: nothing is gained by holding them apart
END_MAX = 0.0              # and nothing is left bare at either end - the end clips are flush

FLAT = 68.0
SLIP_W = 65.0

def length(code):
    return FAMILY[code][0]


def holes(code):
    return list(FAMILY[code][1])


def long_ok(board):
    """can this board take rails longer than one slip at all?

    The flat is 68 across a 65 slip, so a clip stands 1.5 proud each side and wants 3 mm of joint
    to itself.  Below that the rails of neighbouring courses meet face to face, and the answer the
    R50 uses - slide each one to one side of its slip and alternate the side course by course - is
    not open to a clip that runs the length of a course.  Board 9 is laid on 3: 65 + 3 = 68 is
    exactly the flat, so it keeps its staggered R50s.  Board 7 is on 5 and is fine.
    """
    return board['joint'] > FLAT-SLIP_W+1e-9


# SCOPE.  The five boards with a big span - 1, 2, 4, 7 and 8 - get rails wherever a run carries
# more than one slip.  A run of a single slip keeps the one R50 it has always had: a whole 215
# needs nothing more, and putting a rail on it would be a different job.  A board qualifies by
# what it holds rather than by number: any board with a run of four slips or more.
MIN_SLIPS = 2                     # a run of one slip keeps its R50
BIG_SPAN_SLIPS = 4                # what makes a board a big-span board

def big_span(board):
    from runs9 import runs as _runs
    return long_ok(board) and any(r['n'] >= BIG_SPAN_SLIPS for r in _runs(board))


GRIP = 50.0     # the least of a slip a rail may hold it by: one R50 is 50, and one R50 has held a
                # whole 215 slip on its own everywhere in this job from the start


def _slips1d(r):
    """the run's slips as (start, end, piece) measured along the run from its datum end"""
    u, s0 = r['u'], r['s0']
    out = [(_span(p, u)[0]-s0, _span(p, u)[1]-s0, p) for p in r['pieces']]
    out.sort()
    return out


def _held(t, Lc, a, b):
    """does a rail from t to t+Lc hold the slip that runs from a to b"""
    return min(t+Lc, b)-max(t, a) >= GRIP-1e-9


def pick(L):
    """which lengths a run of L takes  ->  (code, ...) longest first

    FILL THE COURSE.  Every length in the family is a multiple of 50, so the most metal a run of L
    can carry is floor(L/50)*50 and no combination beats it.  That settles the first question and
    leaves only two: how few clips reach it, and how long those clips are.  So the rule is - most
    metal, then fewest clips, then the longest pieces.

    Three lines, and they give back by themselves every layout this job was told to use: 700+700
    +100 on board 7's 1535, 700+700 on board 4's 1436, 1000+100+100+50 on board 8's 1272.5.  That
    is the test that the rule is the right one and not a fit to the answer.
    """
    target = math.floor((L+1e-9)/50.0)*50.0
    order = sorted(FAMILY, key=lambda c: -length(c))
    for k in range(1, 13):
        best = None
        for c in itertools.combinations_with_replacement(order, k):
            if abs(sum(length(x) for x in c)-target) > 1e-9:
                continue
            c = tuple(sorted(c, key=lambda x: -length(x)))
            key = [-length(x) for x in c]
            if best is None or key < best[0]:
                best = (key, c)
        if best:
            return best[1]
    return ()


def place(L, codes):
    """where they go  ->  [(code, start along the run)] in order

    The two longest go flush at the two ends of the course.  What is left goes inside, each butted
    against the clip already there, working in from both ends - and the last one, the one that
    cannot reach either neighbour, sits in the MIDDLE of the gap it is left with.

    So a run is never open at its ends, and the air that the family cannot fill ends up split in
    two either side of one short clip rather than left as one hole.
    """
    codes = list(codes)
    if not codes:
        return []
    put = [(codes[0], 0.0)]
    if len(codes) > 1:
        put.append((codes[1], L-length(codes[1])))
    lo = length(codes[0])                       # the free span still to be filled
    hi = L-(length(codes[1]) if len(codes) > 1 else 0.0)
    rest = codes[2:]
    for i, c in enumerate(rest):
        Lc = length(c)
        if i == len(rest)-1:
            s = (lo+hi)/2.0-Lc/2.0              # the last one, dead centre of what is left
        elif i % 2 == 0:
            s = lo                              # otherwise butted on, from one end then the other
        else:
            s = hi-Lc
        put.append((c, round(s, 4)))
        if i % 2 == 0:
            lo = s+Lc
        else:
            hi = s
    put.sort(key=lambda x: x[1])
    return put


_LAYOUT = {}


def layout(L):
    """the setting-out for every course of this length, worked out once

    Per run LENGTH, not per course: two courses of the same length carry different slips - board
    7's odd courses close on a 105, its even ones open on a 104 - and a fitter sets a rail off the
    course below, so the clips have to land on the same dimensions whichever course it is.
    """
    k = round(L, 3)
    if k not in _LAYOUT:
        _LAYOUT[k] = place(L, pick(L))
    return _LAYOUT[k]


# A PART SLIP - a 102.5 or a 104 closer - is not a whole slip with room to spare.  Where one is
# the only thing a clip has to hold, the clip goes on the MIDDLE of it and nothing else: pushed to
# one end of a 104 it reads as a mistake and holds the piece off-centre.  Board 4's four border
# courses are nothing but these, stacked in pairs, and filling those pairs the way a course is
# filled put an R100 on each and both of them hard against an end.
HALF_MAX = 120.0


def all_part(r):
    """is every slip in this run a part slip, so that none of them can take a long clip?"""
    return all(b-a <= HALF_MAX+1e-9 for a, b, _p in _slips1d(r))


def centred(r):
    """-> [(code, start)]  one R50 on the middle of each slip"""
    L = length(SHORT)
    return [(SHORT, round((a+b)/2.0-L/2.0, 4)) for a, b, _p in _slips1d(r)]


def in_scope(board):
    from runs9 import runs as _runs
    if not big_span(board):
        return []
    return [r for r in _runs(board) if r['n'] >= MIN_SLIPS]


def _solve_board(board):
    """-> (runs, scope, {run length: [(code, start)]})  the setting-out this board gets"""
    from runs9 import runs as _runs
    R = _runs(board)
    big = big_span(board)
    scope = [r for r in R if big and r['n'] >= MIN_SLIPS]
    # keyed on run length, so every course of a length is set out alike; a run of nothing but part
    # slips is keyed on its slips as well, because what it gets is one clip centred on each
    sol = {}
    for r in scope:
        k = round(r['length'], 3)
        sol[k] = centred(r) if all_part(r) else layout(r['length'])
    return R, scope, sol


def choose_stock(boards):
    """-> the lengths this job orders, longest first

    Reported, not chosen.  Which lengths get bought used to be a search with its own ranking; now
    the fill decides it run by run and this only says which of the family the answer calls for, so
    that the drawings and the schedule carry those and no others.
    """
    used = set()
    for b in boards:
        for r in in_scope(b):
            used.update(c for c, _t in layout(r['length']))
    used.discard(SHORT)
    return tuple(sorted(used, key=lambda c: -length(c)))


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


def _span(piece, u):
    s = [q[0]*u[0]+q[1]*u[1] for q in piece['p']]
    return min(s), max(s)


_STOCK_USED = None


def stock_used(boards):
    global _STOCK_USED
    if _STOCK_USED is None:
        _STOCK_USED = choose_stock(boards)
    return _STOCK_USED


def plan(board, stock=None):
    """-> dict(rails=[...], r50=[...], runs=[...])  what this board gets"""
    R, scope, sol = _solve_board(board)
    rails, keep = [], []
    for r in R:
        put = sol.get(round(r['length'], 3)) if any(r is x for x in scope) else None
        if put is None:                 # out of scope, or a run of one slip: it keeps its R50
            keep.extend(dict(piece=q, tray=list(q['k']), moved=False) for q in r['pieces'])
            continue
        sl = _slips1d(r)
        for code, t in put:
            Lc = length(code)
            rails.append(dict(code=code, tray=tray(r, r['s0']+t, Lc),
                              holes=hole_pts(r, r['s0']+t, code), s0=r['s0']+t, run=r,
                              covers=[p for a, b, p in sl if _held(t, Lc, a, b)]))
    order = {id(q): i for i, q in enumerate(board['pieces'])}
    keep.sort(key=lambda e: order[id(e['piece'])])
    return dict(rails=rails, r50=keep, runs=R)



if __name__ == '__main__':
    import io as _io, sys as _sys, os as _os
    _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8')
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from runs9 import load
    D = load()
    st = stock_used(D['boards'])
    print('lengths to order: ' + ', '.join('%s %g mm, %d holes' % (c, length(c), len(holes(c)))
                                           for c in st)
          + '   |   %s %g mm' % (SHORT, length(SHORT)))
    print('rule: fill the course - both end clips flush, the rest butted on inward, the last one '
          'centred in what is left; every rail holds %g of each slip it is on' % GRIP)
    print()
    tot, n50 = {}, 0
    print('board  big span  runs  in scope  rails                              R50')
    for b in D['boards']:
        p = plan(b, st)
        c = {}
        for x in p['rails']:
            c[x['code']] = c.get(x['code'], 0)+1
            tot[x['code']] = tot.get(x['code'], 0)+1
        n50 += len(p['r50'])
        print('  %d    %-8s %5d %9d  %-34s %4d'
              % (b['idx'], 'yes' if big_span(b) else '-', len(p['runs']), len(in_scope(b)),
                 ', '.join('%s x%d' % kv for kv in sorted(c.items())) or '-', len(p['r50'])))
    print()
    print('  ' + ', '.join('%s x%d' % kv for kv in sorted(tot.items()))
          + ', %s x%d' % (SHORT, n50))
    print('  %d pieces in all' % (sum(tot.values())+n50))
