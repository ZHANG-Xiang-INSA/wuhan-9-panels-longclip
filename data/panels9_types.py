"""Classify every piece in a panel into brick types, so the drawing and the DXF agree.

A "type" is one thing the yard has to produce.  Two pieces are the same type when they are the
same shape, which for a rectangle means the same w x h and for a clipped field piece means the
same set of edge lengths.  Edges under 2 mm are ignored: they are numerical slivers off the
polygon clipper, not a face anyone saws.

Types come back ordered - whole slips first, then standard bond components, then cut pieces by
descending quantity - so the colour a type gets is stable between the sheet and the DXF.
"""
import math

KIND_ORDER = {'WHOLE': 0, 'STD': 1, 'CUT': 2}

# 20 distinct hues; index 0 is reserved for the plain 215 x 65 slip
PALETTE = [
    '#b9b7b0', '#4f7fb5', '#e08a3c', '#5fa864', '#c0504d', '#8064a2',
    '#4bacc6', '#d99694', '#9bbb59', '#e5b84b', '#7f6084', '#3f8f8a',
    '#c46f9a', '#6f8fbf', '#b07a45', '#7aa0a8', '#a3546e', '#5d7a3f',
    '#8c6d3f', '#546e91',
]


def edge_sig(poly):
    """Edges to the nearest millimetre.  Finer than that is not a distinction anyone can saw to,
    and rounding to 0.1 mm split families that are in fact one type."""
    e = [math.hypot(poly[i][0]-poly[i-1][0], poly[i][1]-poly[i-1][1]) for i in range(len(poly))]
    return tuple(sorted(round(x) for x in e if x >= 2.0))


def poly_area(p):
    return abs(sum(p[i-1][0]*p[i][1]-p[i][0]*p[i-1][1] for i in range(len(p))))/2.0


def classify(P):
    """-> (types, pieces)

    types  : list of dicts  {code, kind, label, dims, area, qty, colour, nsides}
    pieces : list of dicts  {poly, type}  in draw order, type = index into types
    """
    raw, pieces = {}, []

    def add(key, kind, label, dims, area, nsides, poly):
        if key not in raw:
            raw[key] = dict(kind=kind, label=label, dims=dims, area=area, nsides=nsides, qty=0)
        raw[key]['qty'] += 1
        pieces.append(dict(poly=poly, key=key))

    for r in P.get('rects', []):
        x, y, w, h = r['x'], r['y'], r['w'], r['h']
        # An uncut 215 x 65 is a whole slip wherever it is laid.  Reading the kind off the bond
        # role instead made it depend on which piece the generator happened to emit first: board 1
        # starts with its soldier course and board 8 with its border, so both called the plain
        # slip 标准件 standard while the other seven boards called the same product 整砖片 whole.
        kind = ('CUT' if r['t'] == 'CUT' else
                'WHOLE' if sorted((round(w, 1), round(h, 1))) == [65.0, 215.0] else 'STD')
        # A 215 x 65 slip is one thing the yard cuts, whether it is then laid flat, stood on end
        # or used in a border.  Keying on (w, h, kind) counted 215x65, 65x215 and the same slip
        # tagged STD as three separate types: board 6 was reported as needing two kinds of brick
        # when every piece on it is the same slip, and board 8 as three.  The key is the sorted
        # pair, and the bond label no longer splits it.
        a, b = sorted((round(w, 1), round(h, 1)))
        add(('r', a, b, kind == 'CUT'), kind, '%g x %g' % (max(w, h), min(w, h)),
            (max(w, h), min(w, h)), w*h, 4, [(x, y), (x+w, y), (x+w, y+h), (x, y+h)])

    for f in P.get('herr', []):
        poly = [tuple(p) for p in f['poly']]
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        bb = (max(xs)-min(xs), max(ys)-min(ys))
        if f['whole']:
            add(('r', 65.0, 215.0, False), 'WHOLE', '215 x 65', (215.0, 65.0), 215*65, 4, poly)
        else:
            sig = edge_sig(poly)
            add(('f',)+sig, 'CUT', '/'.join('%g' % s for s in sig),
                bb, poly_area(poly), len(sig), poly)

    order = sorted(raw, key=lambda k: (KIND_ORDER[raw[k]['kind']], -raw[k]['qty'], raw[k]['label']))
    types, idx = [], {}
    for i, k in enumerate(order):
        idx[k] = i
        t = dict(raw[k]); t['code'] = 'T%02d' % (i+1); t['colour'] = PALETTE[i % len(PALETTE)]
        types.append(t)
    for p in pieces:
        p['type'] = idx[p['key']]
    return types, pieces


def describe(t):
    """one schedule line: what this type is, in words"""
    if t['kind'] == 'WHOLE':
        return 'whole slip  %s' % t['label']
    if t['kind'] == 'STD':
        return 'standard  %s' % t['label']
    return 'cut  %d sides  %s mm  (bbox %.0f x %.0f, %.0f mm2)' % (
        t['nsides'], t['label'], t['dims'][0], t['dims'][1], t['area'])
