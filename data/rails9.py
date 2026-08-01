# -*- coding: utf-8 -*-
"""The rail clips the supplier actually stocks, and how a continuous run is made up out of them.

Replaces the searched single length.  LC-1366 was 1366 mm because that is what came out of a
search over the runs these nine boards offer, and the shop cannot make it: their line runs to a
fixed family, of which four lengths are on offer.  So the length is no longer a free variable.
What is left to decide is how to make up each run out of the four, and that is a packing problem
with a small answer.

    1000  700  300  100          available, from the supplier
    50                           the short clip that was already in the job, renamed R50
    2 mm                         the least there may be between two clips
    20 mm                        the most that may be left unclipped at each end of a run

The clips are SPACED ALONG the run, not laid end to end.  They are separate clips screwed to the
board and the 2 mm only buys that two of them do not meet; nothing makes them touch.  Two R700 with
52.5 mm of air between them reach both ends of board 2's 1452.5 course on their own, where a tight
chain of the same two stops 50 short and the course needs a third clip.  Both ends of a run are
left the same gap, and every course of the same length on a board is set out identically, because
a fitter sets a rail off the course below and cannot work to ends that wander.

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

# THE ~102 CUT SLIP.  Where an R50 lands on one of these it is centred on the slip and not slid
# to one end.  A whole slip has 165 mm of room and can take its clip wherever the run needs it;
# a 102 closer cannot, and a clip pushed to one end of one reads as a mistake.
CENTRE_LO, CENTRE_HI = 95.0, 115.0


def big_span(board):
    from runs9 import runs as _runs
    return long_ok(board) and any(r['n'] >= BIG_SPAN_SLIPS for r in _runs(board))


def _len_along(piece, u):
    s = [q[0]*u[0]+q[1]*u[1] for q in piece['p']]
    return max(s)-min(s)


def must_centre(piece, u):
    return CENTRE_LO <= _len_along(piece, u) <= CENTRE_HI


def solve_run(r, stock):
    """-> (combo, off, occ, [(piece, code, [t0, t1])], n50, gap) or None

    A LEFTOVER SLIP TAKES THE LONGEST RAIL THAT FITS ON IT, not an R50.  That is the whole point
    of the change: where the chain stops short, the slip beyond it used to get a 50 because a 50
    was all there was, and a 215 slip will take an R100 perfectly well.  R50 is the fallback, for
    a slip too short for anything else - board 8's 64.8 cuts - and where it does land on a ~102
    closer it is centred on that slip rather than slid to one end.

    Ranked as asked: fewest R50 first, then fewest pieces, then the smallest gap left at an end.
    """
    L, P, u = r['length'], r['pieces'], r['u']
    s0 = r['s0']

    def along(p):
        return sum(q[0]*u[0]+q[1]*u[1] for q in p['p'])/len(p['p'])-s0

    def span(p):
        v = [q[0]*u[0]+q[1]*u[1] for q in p['p']]
        return min(v)-s0, max(v)-s0

    order = sorted(set(stock)|{SHORT}, key=lambda c: -length(c))
    best = None
    for k in range(1, 17):
        for combo in itertools.combinations_with_replacement(
                sorted(stock, key=lambda c: -length(c)), k):
            occ = sum(length(c) for c in combo)+GAP*(k-1)
            if occ > L+1e-9:
                continue
            res = L-occ
            for off in sorted({0.0, min(res, END_MAX), res/2.0}):
                if off > END_MAX+1e-9 or off > res+1e-9:
                    continue
                lo, hi = off, off+occ
                spans, extra, n50, ok = [(lo, hi)], [], 0, True
                for p in P:
                    if lo <= along(p) <= hi:
                        continue
                    a, b = span(p)
                    after = along(p) > hi
                    aa = max(a, hi+CLEAR) if after else a
                    bb = b if after else min(b, lo-CLEAR)
                    put = None
                    for code in order:                 # longest that fits on this slip
                        Lc = length(code)
                        if bb-aa < Lc-1e-9:
                            continue
                        if code == SHORT and must_centre(p, u):
                            c = (a+b)/2.0
                            t = [c-Lc/2, c+Lc/2]
                            if t[0] < aa-1e-6 or t[1] > bb+1e-6:
                                continue
                        else:                          # out to the end, which is what reaches
                            t = [bb-Lc, bb] if after else [aa, aa+Lc]
                        put = (code, t); break
                    if put is None:
                        ok = False; break
                    code, t = put
                    n50 += (code == SHORT)
                    spans.append(tuple(t)); extra.append((p, code, t))
                if not ok:
                    continue
                near = min(x for x, _ in spans)
                far = L-max(y for _, y in spans)
                if near > END_MAX+1e-9 or far > END_MAX+1e-9:
                    continue
                cand = (n50, k+len(extra), round(max(near, far), 4))
                if best is None or cand < best[0]:
                    best = (cand, (list(combo), off, occ, extra, n50, max(near, far)))
    return best[1] if best else None


GRIP = 50.0     # the least of a slip a rail may hold it by


def _slips1d(r):
    """the run's slips as (start, end, piece) measured along the run from its datum end"""
    u, s0 = r['u'], r['s0']
    out = [(_span(p, u)[0]-s0, _span(p, u)[1]-s0, p) for p in r['pieces']]
    out.sort()
    return out


def _held(t, Lc, a, b):
    """does a rail from t to t+Lc hold the slip that runs from a to b

    It has to reach the MIDDLE of the slip and hold 50 mm of it.  The middle because that is the
    rule this job has always worked to - one R50 on the centre of a whole slip is the entire
    fixing - and 50 because that is how much of the slip an R50 holds.

    Overlap on its own is not the same thing.  50 mm taken off one end of a 215 leaves 165 hanging,
    and on that reading board 7 came out at two clips a course when it wants three.
    """
    return t-1e-9 <= (a+b)/2.0 <= t+Lc+1e-9 and min(t+Lc, b)-max(t, a) >= GRIP-1e-9


def _rails_for(r, placed):
    """the group's placement as it lands on THIS run -> [(code, t, [pieces])]

    A rail that holds nothing on this particular course comes off it.  Board 7's odd courses close
    on a 105 and its even ones open on a 104, so the middle clip that the odd ones need falls
    between two slips on the even ones and holds neither.  Dropping it costs nothing that matters:
    the two long rails keep the positions the whole board is set out to, so the ends still line up
    course to course, which is the thing that has to be true.  Unless dropping it opens up one of
    the run's own ends by more than the rule allows, in which case it stays.
    """
    codes, pos = placed
    sl = _slips1d(r)
    out = [(c, t, [p for a, b, p in sl if _held(t, length(c), a, b)]) for c, t in zip(codes, pos)]
    kept = [x for x in out if x[2]]
    if not kept:
        return out
    if kept[0][1] > END_MAX+1e-9 or r['length']-(kept[-1][1]+length(kept[-1][0])) > END_MAX+1e-9:
        return out
    return kept


def _place(groups, codes, e, L):
    """where the rails go, both ends e clear of the run's ends -> [t] or None

    RAILS DO NOT HAVE TO TOUCH.  A run was being made up as a chain laid end to end with 2 mm
    between, and that is not what a run is: they are separate clips screwed to the board, and the
    2 mm only buys that two of them do not meet.  Let the space between open up and two R700 reach
    both ends of board 2's 1452.5 on their own.  Held to a tight chain the same two lengths stop
    50 short of one end, so the run took an R1000 and two R100 instead - three clips, and the
    little ones at that.

    Both ends are the same e by construction.  A fitter sets a course's rails off the course
    below; ends that wander 10 or 20 mm from one course to the next cannot be worked to.
    """
    k = len(codes)
    Ls = [length(c) for c in codes]
    if k > 3:
        return None                      # more than one free rail: left to the tight chain
    t = [e]*k
    if k > 1:
        t[k-1] = L-e-Ls[k-1]
        if t[k-1] < t[0]+Ls[0]+GAP-1e-9:
            return None
    elif abs(L-2*e-Ls[0]) > 1e-6:
        return None
    if k == 3:
        # the two ends are pinned, so the only freedom is the middle rail, and every slip neither
        # end rail holds has to be held by it - which is an interval, not a search
        lo, hi = t[0]+Ls[0]+GAP, t[2]-Ls[1]-GAP
        for sl in groups:
            orph = [(a, b) for a, b, _p in sl
                    if not _held(t[0], Ls[0], a, b) and not _held(t[2], Ls[2], a, b)]
            if orph:
                lo = max(lo, max(a for a, _b in orph)+GRIP-Ls[1])
                hi = min(hi, min(b for _a, b in orph)-GRIP)
        if lo > hi+1e-9:
            return None
        t[1] = (lo+hi)/2.0
    for sl in groups:
        for a, b, _p in sl:
            if not any(_held(t[m], Ls[m], a, b) for m in range(k)):
                return None
    return [round(x, 3) for x in t]


def solve_group(runs, stock):
    """one placement for every run of this length on this board -> (codes, [t]) or None

    Solved for the group and not one run at a time, because the ends have to line up.  Two courses
    of the same length carry different slips - board 7's odd courses close on a 105, its even ones
    open on a 104 - and solved separately they come out with one course's rails 10 mm along from
    the next one's.

    Ranked: fewest clips, which with a fixed run length IS "use the long ones"; then fewest types;
    then the smallest end gap; then the longest metal, which is what picks 2 x R700 over
    R1000 + R300 when both cover board 2 in two clips.
    """
    L = runs[0]['length']
    groups = [_slips1d(r) for r in runs]
    best = None
    for k in range(1, 4):
        for combo in itertools.combinations_with_replacement(
                sorted(stock, key=lambda c: -length(c)), k):
            tot = sum(length(c) for c in combo)
            if tot+GAP*(k-1) > L+1e-9:
                continue
            for codes in sorted(set(itertools.permutations(combo))):
                for e2 in range(0, int(END_MAX*2)+1):
                    pos = _place(groups, codes, e2/2.0, L)
                    if pos is None:
                        continue
                    cand = (k, len(set(codes)), e2, -round(tot, 4))
                    if best is None or cand < best[0]:
                        best = (cand, (list(codes), pos))
                    break                     # the smallest e this sequence will take
    return best[1] if best else None


def in_scope(board):
    from runs9 import runs as _runs
    if not big_span(board):
        return []
    return [r for r in _runs(board) if r['n'] >= MIN_SLIPS]


def _solve_board(board, stock):
    """-> (runs, scope, {run length: (codes, [t])})  the placement each length on this board gets"""
    from runs9 import runs as _runs
    R = _runs(board)
    big = big_span(board)
    scope = [r for r in R if big and r['n'] >= MIN_SLIPS]
    bylen = {}
    for r in scope:
        bylen.setdefault(round(r['length'], 3), []).append(r)
    return R, scope, {L: solve_group(rs, stock) for L, rs in bylen.items()}


def choose_stock(boards):
    """-> the tuple of lengths to buy

    Fewest PIECES first, then fewest types, then the smallest worst gap - the order asked for.
    Taken over the whole job at once, because which lengths to order is one decision and not one
    per run: a set that saves two pieces on board 2 and costs a whole extra SKU is a bad trade.
    """
    nslips = sum(r['n'] for b in boards for r in in_scope(b))
    best = None
    for n in range(1, len(STOCK)+1):
        for sub in itertools.combinations(STOCK, n):
            tot, n50, worst, ok = 0, 0, 0.0, True
            for b in boards:
                R, scope, sol = _solve_board(b, sub)
                for r in scope:
                    got = sol.get(round(r['length'], 3))
                    if got is not None:
                        tot += len(_rails_for(r, got))
                        worst = max(worst, got[1][0])
                        continue
                    got = solve_run(r, sub)      # no placement covers the whole run: tight chain
                    if got is None:
                        ok = False; break
                    tot += len(got[0])+len(got[3])
                    n50 += got[4]
                    worst = max(worst, got[5])
                if not ok:
                    break
            if not ok or tot*2 > nslips:
                continue
            # USE THE LONG ONES is the gate above, not a tie-break: a set of lengths only counts as
            # long if it covers the in-scope runs at no more than one clip per two slips.  R100 on
            # its own is one SKU and would win every ranking that puts types first, but it is 661
            # clips - one on every slip - and the exact opposite of what was asked for.  Past the
            # gate the order is the one asked for: fewest TYPES, then fewest pieces, then the
            # smallest end gap.  Four lengths shave 8 clips off the two-length answer and cost two
            # more purchase lines, one of them for 4 pieces; two lengths is the better buy.
            cand = (n, n50, tot, round(worst, 4))
            if best is None or cand < best[0]:
                best = (cand, sub)
    return best[1] if best else STOCK


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
    """a span along the run turned into the tray quad on the board"""
    u, v, tt = r['u'], r['v'], r['t']
    a, b = r['s0']+t[0], r['s0']+t[1]
    h = FLAT/2.0

    def pt(sv, off):
        w = tt+off
        return [round(u[0]*sv+v[0]*w, 3), round(u[1]*sv+v[1]*w, 3)]

    return [pt(a, -h), pt(b, -h), pt(b, h), pt(a, h)]


_STOCK_USED = None


def stock_used(boards):
    global _STOCK_USED
    if _STOCK_USED is None:
        _STOCK_USED = choose_stock(boards)
    return _STOCK_USED


def plan(board, stock=None):
    """-> dict(rails=[...], r50=[...], runs=[...])  what this board gets"""
    from runs9 import load as _load
    # Resolve the order here rather than defaulting to all of STOCK.  A caller that plans one board
    # at a time still gets the set chosen over the whole job, which is the only set that gets
    # bought; stock_used memoises, so the nine boards are read once.
    stock = stock or stock_used(_load()['boards'])
    R, scope, sol = _solve_board(board, stock)
    rails, keep = [], []
    for r in R:
        placed = sol.get(round(r['length'], 3)) if any(r is x for x in scope) else None
        if placed is not None:
            for code, t, cov in _rails_for(r, placed):
                rails.append(dict(code=code, tray=tray(r, r['s0']+t, length(code)),
                                  holes=hole_pts(r, r['s0']+t, code), s0=r['s0']+t, run=r,
                                  covers=cov))
            continue
        got = solve_run(r, stock) if any(r is x for x in scope) else None
        if got is None:
            keep.extend(dict(piece=q, tray=list(q['k']), moved=False) for q in r['pieces'])
            continue
        combo, off, occ, extra, _n50, _gap = got
        s = r['s0']+off
        lo, hi = off, off+occ
        for code in combo:
            L = length(code)
            covers = [q for q in r['pieces'] if lo <= _along(q, r) <= hi
                      and s-r['s0'] <= _along(q, r) <= s-r['s0']+L]
            rails.append(dict(code=code, tray=tray(r, s, L), holes=hole_pts(r, s, code),
                              s0=s, run=r, covers=covers))
            s += L+GAP
        for q, code, t in extra:
            tr = _tray_from_1d(r, t)
            if code == SHORT:
                keep.append(dict(piece=q, tray=tr, moved=tr != list(q['k'])))
            else:                       # a rail on its own slip, not a chain member
                rails.append(dict(code=code, tray=tr,
                                  holes=hole_pts(r, r['s0']+t[0], code), s0=r['s0']+t[0],
                                  run=r, covers=[q]))
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
    print('rule: at least %g between rails, both ends of a run the same and at most %g, every rail '
          'over the middle of what it holds and %g of it' % (GAP, END_MAX, GRIP))
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
