# -*- coding: utf-8 -*-
"""Rebuild the six generated figures in docs/joint_report.html from the geometry as it stands.

The report compares three boards three ways: the proposal mock-up, the same bond built to the
mortar width the proposal gave it, and the board as delivered at 10 mm.  The mock-ups are
photographs and never change.  The other two columns are drawn here, so the report cannot drift
away from the boards once a size or a phase moves - which is exactly what had happened: board 5
was captioned 1500 x 1350 with 132 slips when it is 1565 x 1415 with 145, and the footer still
counted 1427 slips against an actual 1425.

The right column is read from panels9.json rather than rebuilt, so it is the delivered geometry
itself.  The left column of each pair is built here at the proposal's joint, which is the whole
point of the comparison, and its joints are then measured the same way the delivered boards are.

    python data/joint_report_figs.py
"""
import json, math, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from panels9 import W, herring, basketweave, border, rot_clip, basket_cells
from panels9_types import classify

L = 215.0                                        # the slip, fixed; panels9_build declares the same

DOC = os.path.join(HERE, '..', 'docs', 'joint_report.html')
PAN = json.load(open(os.path.join(HERE, 'panels9.json')))
BY = {p['idx']: p for p in PAN}
# boards.json is the same geometry after classification, and it is what carries the brick types,
# so the delivered figure and its caption both come from there
BD = {b['idx']: b for b in json.load(
    open(os.path.join(HERE, '..', 'site', 'data', 'boards.json'), encoding='utf-8'))['boards']}

# proposal joint per board, and the tint each figure is drawn in (kept from the existing sheet so
# the three columns of a row still read as one row)
CASE = {5: dict(J0=7.0, bg='#efe8e8', ink=('#916050', '#7f5142')),
        6: dict(J0=7.0, bg='#edebeb', ink=('#916050', '#7f5142')),
        8: dict(J0=5.0, bg='#e4e3de', ink=('#9a9a93', '#86867f'))}
SIDE = 290.0


def counterfactual(idx, J):
    """the same bond at the proposal's joint, on the delivered board size"""
    S, H = BY[idx]['Wd'], BY[idx]['Ht']
    if idx == 5:
        return dict(rects=[], herr=herring(S, H, L, J, ang=0.0, org=(0.0, 0.0)), Wd=S, Ht=H)
    if idx == 6:
        return dict(rects=basketweave(S, H, L, J), herr=[], Wd=S, Ht=H)
    ins = 2*(W+J)
    return dict(rects=border(S, H, L, J, 2),
                herr=rot_clip(basket_cells(max(S, H)*1.7, L, J), S, H, 45.0, ins), Wd=S, Ht=H)


def polys(P):
    if 'ready' in P:
        return P['ready']
    out = []
    for r in P.get('rects', []):
        x, y, w, h = r['x'], r['y'], r['w'], r['h']
        out.append([(x, y), (x+w, y), (x+w, y+h), (x, y+h)])
    for f in P.get('herr', []):
        out.append([tuple(q) for q in f['poly']])
    return out


def facing(e, f, minlap=8.0, cap=40.0):
    """distance between two facing parallel faces, or None if they do not face each other

    Measuring the plain closest approach between two outlines will not do.  A joint that is too
    WIDE is still a joint, and a nearest-point filter tuned around the nominal width throws exactly
    those away: at 7 mm the three-slip block of a basketweave is 209 against a 215 slip, so the
    joints that prove the point are the 13 mm ones.  A joint is two faces looking at each other, so
    that is the test - parallel, overlapping along their own direction, and the gap measured across.
    """
    (a0, a1), (b0, b1) = e, f
    ux, uy = a1[0]-a0[0], a1[1]-a0[1]
    vx, vy = b1[0]-b0[0], b1[1]-b0[1]
    lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
    if lu < 1e-9 or lv < 1e-9:
        return None
    ux, uy, vx, vy = ux/lu, uy/lu, vx/lv, vy/lv
    if abs(ux*vy-uy*vx) > 0.02:                       # not parallel
        return None
    d = abs((b0[0]-a0[0])*(-uy) + (b0[1]-a0[1])*ux)   # across the faces
    if d > cap:
        return None                                   # d may be 0: two slips touching IS the fault
    ta = (0.0, lu)                                    # along the faces, in e's frame
    s0 = (b0[0]-a0[0])*ux + (b0[1]-a0[1])*uy
    s1 = (b1[0]-a0[0])*ux + (b1[1]-a0[1])*uy
    lap = min(ta[1], max(s0, s1)) - max(ta[0], min(s0, s1))
    return d if lap >= minlap else None


def joints(P, J, tol=0.35):
    """every joint on the board: each pair of faces that look at each other across a gap"""
    Q = polys(P)
    C = [(sum(v[0] for v in p)/len(p), sum(v[1] for v in p)/len(p)) for p in Q]
    R = [max(math.hypot(v[0]-c[0], v[1]-c[1]) for v in p) for p, c in zip(Q, C)]
    gaps = []
    for a in range(len(Q)):
        for b in range(a+1, len(Q)):
            if math.hypot(C[a][0]-C[b][0], C[a][1]-C[b][1]) > R[a]+R[b]+40.0:
                continue
            best = None
            for u in range(len(Q[a])):
                ea = (Q[a][u], Q[a][(u+1) % len(Q[a])])
                for v in range(len(Q[b])):
                    d = facing(ea, (Q[b][v], Q[b][(v+1) % len(Q[b])]))
                    if d is not None and (best is None or d < best):
                        best = d
            if best is not None:
                gaps.append(best)
    bad = [g for g in gaps if abs(g-J) > tol]
    return len(gaps), bad


def svg(P, bg, ink):
    Wd, Ht = P['Wd'], P['Ht']
    s = SIDE/max(Wd, Ht)
    w, h = Wd*s, Ht*s
    out = ['<svg viewBox="0 0 %.1f %.1f" width="%.1f" height="%.1f">' % (w, h, w, h),
           '<rect width="%.1f" height="%.1f" fill="%s"/>' % (w, h, bg)]
    for i, q in enumerate(polys(P)):
        pts = ' '.join('%.2f,%.2f' % (v[0]*s, h-v[1]*s) for v in q)
        out.append('<polygon points="%s" fill="%s"/>' % (pts, ink[i % 2]))
    out.append('</svg>')
    return ''.join(out)


def cuts_of(idx):
    t = [x for x in BD[idx]['types'] if x['kind'] == 'CUT']
    n = sum(x['qty'] for x in t)
    return ('cut none' if not n else
            'cut %d in %d shape%s' % (n, len(t), '' if len(t) == 1 else 's'))


def cut_cost(P, idx):
    """how much cutting the counterfactual needs, against the delivered board"""
    types, pieces = classify(dict(rects=P.get('rects', []), herr=P.get('herr', []),
                                  idx=idx, Wd=P['Wd'], Ht=P['Ht']))
    c = [t for t in types if t['kind'] == 'CUT']
    d = [t for t in BD[idx]['types'] if t['kind'] == 'CUT']
    return (sum(t['qty'] for t in c), len(c),
            sum(t['qty'] for t in d), len(d),
            min([t['area'] for t in types]))


def num(x):
    return ('%g' % x)


html = open(DOC, encoding='utf-8').read()
blocks = list(re.finditer(
    r'<figure class="(bad|ok)"><div class="d">(<svg.*?</svg>)</div>'
    r'<figcaption><b>(.*?)</b>(.*?)</figcaption></figure>', html, re.S))
assert len(blocks) == 6, len(blocks)

new, last, log = [], 0, []
for k, (idx, kind) in enumerate([(b, k) for b in (5, 6, 8) for k in ('bad', 'ok')]):
    m = blocks[k]
    assert m.group(1) == kind, (k, m.group(1), kind)
    c = CASE[idx]
    if kind == 'bad':
        J0 = c['J0']
        P = counterfactual(idx, J0)
        tot, bad = joints(P, J0)
        nc, ns_, dc, ds, small = cut_cost(P, idx)
        body = svg(P, c['bg'], c['ink'])
        head = 'Built to the %g mm mortar width' % J0
        # the same board, same bond, only the joint changed, so the cutting is comparable
        was = ('no cutting at all' if dc == 0 else
               '%d in %d shape%s' % (dc, ds, '' if ds == 1 else 's'))
        if bad:
            cap = ('%d of %d joints come out at %s mm instead of %g. %d cut pieces in %d shapes, '
                   'against %s at 10 mm; smallest piece %.0f mm&sup2;.'
                   % (len(bad), tot,
                      '%.2f' % min(bad) if max(bad)-min(bad) < 0.005
                      else '%.2f to %.2f' % (min(bad), max(bad)),
                      J0, nc, ns_, was, small))
        else:
            cap = ('Joints hold at %g mm, but the weave no longer meets the border on the pattern: '
                   '%d cut pieces in %d shapes, against %s at 10 mm.'
                   % (J0, nc, ns_, was))
    else:
        b = BD[idx]
        P = dict(ready=[[tuple(v) for v in p['p']] for p in b['pieces']], Wd=b['w'], Ht=b['h'])
        body = svg(P, c['bg'], c['ink'])
        head = 'Built at %g mm' % b['joint']
        cap = ('%s &times; %s, %d slips, %s. Every joint %g mm.'
               % (num(b['w']), num(b['h']), len(b['pieces']), cuts_of(idx), b['joint']))
    log.append('  board %d %-3s  %s' % (idx, kind, cap))
    new.append(html[last:m.start()])
    new.append('<figure class="%s"><div class="d">%s</div><figcaption><b>%s</b>%s</figcaption>'
               '</figure>' % (kind, body, head, cap))
    last = m.end()
new.append(html[last:])
html = ''.join(new)

total = sum(len(p.get('rects', []))+len(p.get('herr', [])) for p in PAN)
html = re.sub(r'carry [0-9]+ slips', 'carry %d slips' % total, html)

# Section 05 quotes two measured figures for board 8.  They were written by hand against an
# earlier phase of the board and stayed behind when it moved: the page claimed a 1501 mm2 smallest
# piece and 10 cut shapes six lines under a generated caption reading "cut 52 in 4 shapes".  Both
# are measured here now, the second against the same board with the weave left off the panel's
# 4-fold centre, which is the correction the sentence is about.
b8 = BY[8]
off = dict(rects=border(b8['Wd'], b8['Ht'], L, b8['J'], 2), idx=8, Wd=b8['Wd'], Ht=b8['Ht'],
           herr=rot_clip(basket_cells(max(b8['Wd'], b8['Ht'])*1.7, L, b8['J']),
                         b8['Wd'], b8['Ht'], 45.0, 2*(W+b8['J']), phase=0.0, phy=0.0))
small = min(t['area'] for t in classify(b8)[0])
was, now = len([t for t in classify(off)[0] if t['kind'] == 'CUT']), len(
    [t for t in BD[8]['types'] if t['kind'] == 'CUT'])
html = re.sub(r'smallest piece on the board is [0-9]+ mm&sup2;',
              'smallest piece on the board is %.0f mm&sup2;' % small, html)
html = re.sub(r'distinct cut shapes from [0-9]+ down to [0-9]+',
              'distinct cut shapes from %d down to %d' % (was, now), html)
log.append('  board 8 05  smallest %.0f mm2, cut shapes %d -> %d' % (small, was, now))
open(DOC, 'w', encoding='utf-8').write(html)
print('\n'.join(log))
print('footer: nine boards carry %d slips' % total)
print('->', os.path.normpath(DOC))
