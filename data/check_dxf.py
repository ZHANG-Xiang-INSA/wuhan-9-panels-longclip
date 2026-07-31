import io, sys as _s
_s.stdout = io.TextIOWrapper(_s.stdout.buffer, encoding='utf-8')
"""Check a DXF for text sitting on top of geometry, or on other text.

Bounding boxes are no good here: the sheet border's box contains every entity, and a diagonal
line's box is far larger than the line.  So this tests the text rectangle against each segment
directly, and skips the border.
"""
import ezdxf, math, sys


def tw(s, h):
    return h*sum(1.05 if ord(c) > 0x2E80 else 0.62 for c in s)


def text_box(e):
    """the text's rectangle IN ITS OWN FRAME, plus that frame's origin and angle

    Text on this sheet is set at 0, 90 and at the rake angles, so an axis-aligned box is not good
    enough: the box round a 45 degree "96.2" is a 27 x 11 rectangle standing on the page, and the
    45 degree dimension line it labels runs corner to corner through it while never touching a
    glyph.  That reported two collisions that do not exist.  The box is built once, unrotated, and
    segments are brought into this frame to be tested against it.
    """
    h = e.dxf.height
    s = e.dxf.text.replace('%%c', 'O')
    w = tw(s, h)
    p = e.dxf.insert
    if e.dxf.hasattr('align_point') and e.dxf.get('halign', 0) != 0:
        p = e.dxf.align_point
    ha = e.dxf.get('halign', 0); va = e.dxf.get('valign', 0)
    x0 = -w/2 if ha == 1 else (-w if ha == 2 else 0.0)
    y0 = -h/2 if va == 2 else (-h if va == 3 else 0.0)
    return (x0, y0, x0+w, y0+h), (p.x, p.y), math.radians(e.dxf.rotation or 0.0)


def segs(e):
    t = e.dxftype()
    if t == 'LINE':
        return [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
    if t == 'LWPOLYLINE':
        p = [(x, y) for x, y, *_ in e.get_points()]
        return [(p[i], p[i+1]) for i in range(len(p)-1)]
    if t in ('CIRCLE', 'ARC'):
        c, r = e.dxf.center, e.dxf.radius
        a0 = math.radians(e.dxf.start_angle) if t == 'ARC' else 0.0
        a1 = math.radians(e.dxf.end_angle) if t == 'ARC' else 2*math.pi
        if a1 <= a0:
            a1 += 2*math.pi
        n = 16
        pts = [(c.x+r*math.cos(a0+(a1-a0)*k/n), c.y+r*math.sin(a0+(a1-a0)*k/n))
               for k in range(n+1)]
        return [(pts[i], pts[i+1]) for i in range(n)]
    return []


def to_frame(p, org, ang):
    c, s = math.cos(-ang), math.sin(-ang)
    x, y = p[0]-org[0], p[1]-org[1]
    return (x*c-y*s, x*s+y*c)


def seg_rect(a, b, box):
    r, org, ang = box
    if ang:
        a, b = to_frame(a, org, ang), to_frame(b, org, ang)
    else:
        a = (a[0]-org[0], a[1]-org[1]); b = (b[0]-org[0], b[1]-org[1])
    x0, y0, x1, y1 = r
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


def check(path, skip_layers=('BORDER',)):
    d = ezdxf.readfile(path); m = d.modelspace()
    # A DIMENSION draws itself into an anonymous block, so its value, its arrows and its extension
    # lines are invisible to a modelspace query and were going unchecked.  The block is placed at
    # the origin on this sheet, so its contents are already in sheet coordinates.
    ents = list(m)
    for e in m.query('DIMENSION'):
        ents += list(d.blocks.get(e.dxf.geometry))
    q = lambda kinds: [x for x in ents if x.dxftype() in kinds]
    T = [(text_box(e), e.dxf.text, e.dxf.layer) for e in q(('TEXT',))]
    # ezdxf sets the dimension value as MTEXT, middle-centre on the dimension line
    for e in q(('MTEXT',)):
        h, s = e.dxf.char_height, e.text
        w, a = tw(s, h), math.radians(e.dxf.get('rotation', 0.0))
        T.append((((-w/2, -h/2, w/2, h/2), tuple(e.dxf.insert)[:2], a), s, e.dxf.layer))
    S = [s for e in q(('LINE', 'LWPOLYLINE', 'CIRCLE', 'ARC'))
         if e.dxf.layer not in skip_layers for s in segs(e)]
    # A grid over the segments, because the setting-out drawing carries 59,546 of them against
    # 2,933 pieces of text and the straight product is 175 million tests - it ran for ten minutes.
    # Each text only ever meets the segments near it.
    CELL = 150.0
    G = {}
    for k, (a, b) in enumerate(S):
        for gx in range(int(min(a[0], b[0])//CELL), int(max(a[0], b[0])//CELL)+1):
            for gy in range(int(min(a[1], b[1])//CELL), int(max(a[1], b[1])//CELL)+1):
                G.setdefault((gx, gy), []).append(k)

    def near(box):
        r, org, ang = box
        rad = math.hypot(max(abs(r[0]), abs(r[2])), max(abs(r[1]), abs(r[3])))+2.0
        out = set()
        for gx in range(int((org[0]-rad)//CELL), int((org[0]+rad)//CELL)+1):
            for gy in range(int((org[1]-rad)//CELL), int((org[1]+rad)//CELL)+1):
                out.update(G.get((gx, gy), ()))
        return out

    on_geom = [t for t in T if any(seg_rect(S[k][0], S[k][1], t[0]) for k in near(t[0]))]
    on_text = []
    for i, a in enumerate(T):
        for b in T[i+1:]:
            # each is tested as four segments in the other's frame, so a rotated pair is judged on
            # the rectangles the glyphs really occupy rather than on the boxes standing on the page
            (rb, ob, ab) = b[0]
            crn = [(rb[0], rb[1]), (rb[2], rb[1]), (rb[2], rb[3]), (rb[0], rb[3])]
            c, s = math.cos(ab), math.sin(ab)
            crn = [(ob[0]+p[0]*c-p[1]*s, ob[1]+p[0]*s+p[1]*c) for p in crn]
            if any(seg_rect(crn[k-1], crn[k], a[0]) for k in range(4)):
                on_text.append((a[1], b[1]))
    print('%-34s TEXT %3d  segments %4d   text-on-geometry %3d   text-on-text %3d'
          % (path.split('\\')[-1], len(T), len(S), len(on_geom), len(on_text)))
    return on_geom, on_text


if __name__ == '__main__':
    for p in sys.argv[1:]:
        g, t = check(p)
        for b in g[:6]:
            print('   on geometry:', b[1][:64])
        for a, b in t[:6]:
            print('   on text:', a[:34], '||', b[:34])
