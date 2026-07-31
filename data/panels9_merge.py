# -*- coding: utf-8 -*-
"""Fold brick types that are within the client's tolerance into one product.

The client's rule: two similar bricks whose sizes are within 2 mm count as one type.  Folding them
means only one of the two gets made, and it has to be the SMALLER one, because a piece that is
oversize does not go into the slot at all.  The larger slot then takes the smaller piece and its
joints absorb the difference, which is why the tolerance is expressed on the joint and not on the
brick: on these boards the design joint is 10 mm, so a 2 mm merge leaves joints between 9 and 11.

Two rules keep it honest:

  * PAIRWISE ONLY, NEVER CHAINED.  If A and B are within 2 mm and B and C are within 2 mm, A and C
    can be 4 mm apart.  Once a type has been folded it is closed to further merges.  Without this
    the half slips would chain 102.5 - 104 - 105 and put 2.5 mm on one joint.
  * THE PIECE IS CENTRED IN THE SLOT, so the shortfall is split between the two ends instead of
    landing on one joint, except where the piece meets a board edge, where it stays flush and the
    inner joint takes all of it.

Everything it does is printed, because a merge is a change to what the yard cuts.
"""
import math
from panels9_types import classify

TOL = 2.0                       # the client's tolerance, on the joint
SAME = 0.05                     # below this the two are already one product
EDGE = 0.05                     # a piece within this of a board edge is flush to it


def _sig(poly):
    n = len(poly)
    return sorted(round(math.hypot(poly[i][0]-poly[i-1][0], poly[i][1]-poly[i-1][1]), 2)
                  for i in range(n))


def _area(poly):
    n = len(poly)
    return abs(sum(poly[i-1][0]*poly[i][1]-poly[i][0]*poly[i-1][1] for i in range(n)))/2.0


def _dev(a, b):
    """largest difference between corresponding edge lengths, or None if not comparable"""
    if len(a) != len(b):
        return None
    return max(abs(x-y) for x, y in zip(a, b))


def _centroid(poly):
    n = len(poly)
    return (sum(p[0] for p in poly)/n, sum(p[1] for p in poly)/n)


def _fit(src, dst):
    """place src on dst: same centroid, best rotation over the cyclic correspondences, no mirror

    No mirror, because mirroring a slip means laying it face down and the back face is not the
    face that was photographed.

    Returns the placed outline AND the transform, because the clip code needs it.  A herringbone
    piece carries the frame of the slip it was cut from (src, ang, org) and clips9.to_local reads
    that frame rather than the outline, so a replacement outline with the old frame attached is
    measured in the wrong place: board 3's T05 came out with a 0.9 mm run and was given a pocket
    clip, while the identical piece on board 8 measured 85 mm and got a rail.
    """
    if len(src) != len(dst):
        return None
    n = len(src)
    cs, cd = _centroid(src), _centroid(dst)
    S = [(p[0]-cs[0], p[1]-cs[1]) for p in src]
    Dd = [(p[0]-cd[0], p[1]-cd[1]) for p in dst]
    best = None
    for k in range(n):
        Rk = S[k:]+S[:k]
        num = sum(Dd[i][0]*Rk[i][1]-Dd[i][1]*Rk[i][0] for i in range(n))
        den = sum(Dd[i][0]*Rk[i][0]+Dd[i][1]*Rk[i][1] for i in range(n))
        th = math.atan2(-num, den)
        c, s = math.cos(th), math.sin(th)
        rot = [(p[0]*c-p[1]*s, p[0]*s+p[1]*c) for p in Rk]
        err = max(math.hypot(Dd[i][0]-rot[i][0], Dd[i][1]-rot[i][1]) for i in range(n))
        if best is None or err < best[0]:
            # as a map on the plane this is p -> R(th).p + t, with the source rolled by k
            t = (cd[0]-(cs[0]*c-cs[1]*s), cd[1]-(cs[0]*s+cs[1]*c))
            best = (err, [(cd[0]+p[0], cd[1]+p[1]) for p in rot], th, t)
    return best


def apply(PANELS):
    """fold what is within tolerance; returns a list of lines describing what was done"""
    cat, log = [], []
    for P in PANELS:
        types, pieces = classify(P)
        # the herr entry a piece came from, so the merged copy can inherit its slip frame
        src = {}
        for f in P.get('herr', []):
            src[_key(f['poly'])] = f
        for ti, t in enumerate(types):
            polys = [pc['poly'] for pc in pieces if pc['type'] == ti]
            cat.append(dict(idx=P['idx'], code=t['code'], kind=t['kind'], qty=t['qty'],
                            sig=_sig(polys[0]), area=_area(polys[0]), rep=polys[0], P=P, ti=ti,
                            frame=src.get(_key(polys[0]))))

    # only cut and closer pieces are candidates: the plain 215 x 65 slip is the product itself
    cand = [c for c in cat if c['kind'] != 'WHOLE']
    pairs = []
    for i in range(len(cand)):
        for j in range(i+1, len(cand)):
            a, b = cand[i], cand[j]
            d = _dev(a['sig'], b['sig'])
            # Types that are already the same shape need no merge: the schedules group by size, so
            # the 102.5 half slip on boards 1, 2 and 3 is one product already.  Pairing them here
            # would change no geometry and would use up the one merge each type is allowed.
            if d is None or not (SAME < d <= TOL):
                continue
            # Equal edge lengths are not enough.  A sorted edge list is the same for a shape and
            # for its mirror image, so the signature test happily pairs two pieces that no amount
            # of turning will bring together - board 3's T05 and board 8's T10 are mirror twins and
            # were being merged with a 31 mm misfit that drove the replacement through the border
            # course.  The pair is real only if a rotation actually lands it, and only rotation is
            # allowed: mirroring a slip means laying it face down.
            f = _fit(b['rep'], a['rep']) if a['area'] >= b['area'] else _fit(a['rep'], b['rep'])
            if f is None or f[0] > TOL:
                continue
            pairs.append((d, -(a['qty']+b['qty']), i, j))
    pairs.sort()

    used, plan = set(), []
    for d, negq, i, j in pairs:
        if i in used or j in used:
            continue                           # pairwise only, never chained
        a, b = cand[i], cand[j]
        keep, drop = (a, b) if a['area'] <= b['area'] else (b, a)
        used.add(i); used.add(j)
        plan.append((d, keep, drop))

    for d, keep, drop in plan:
        P = drop['P']
        types, pieces = classify(P)
        # Find the type by its shape, not by the index recorded when the catalogue was built.  A
        # board can be on the losing side of two merges - board 3 gives up both T03 and T05 - and
        # the first merge renumbers its types, so the stored index then points at the wrong one and
        # the wrong 34 pieces get overwritten.
        ti = None
        for k, t in enumerate(types):
            first = next((pc['poly'] for pc in pieces if pc['type'] == k), None)
            if first is not None and _sig(first) == drop['sig']:
                ti = k
                break
        if ti is None:
            log.append('  %d.%s no longer present, skipped' % (drop['idx'], drop['code']))
            continue
        n = 0
        for pc in pieces:
            if pc['type'] != ti:
                continue
            r = _fit(keep['rep'], pc['poly'])
            if r is None:
                continue
            _, placed, th, t = r
            placed2 = _snap_edges(placed, pc['poly'], P['Wd'], P['Ht'])
            t = (t[0]+placed2[0][0]-placed[0][0], t[1]+placed2[0][1]-placed[0][1])
            _rewrite(P, pc['poly'], placed2, keep.get('frame'), th, t)
            n += 1
        log.append('  %d.%s (x%d, %s) <- made as %d.%s (x%d, %s), %d pieces replaced, joint +%.2f mm'
                   % (drop['idx'], drop['code'], drop['qty'], '/'.join('%g' % v for v in drop['sig']),
                      keep['idx'], keep['code'], keep['qty'], '/'.join('%g' % v for v in keep['sig']),
                      n, d))
    return log


def _snap_edges(placed, orig, Wd, Ht):
    """a piece that met a board edge keeps meeting it; the inner joint takes the whole difference"""
    out = list(placed)
    for axis, lim in ((0, Wd), (1, Ht)):
        lo0 = min(p[axis] for p in orig)
        hi0 = max(p[axis] for p in orig)
        lo1 = min(p[axis] for p in out)
        hi1 = max(p[axis] for p in out)
        sh = 0.0
        if lo0 < EDGE:
            sh = -lo1
        elif hi0 > lim-EDGE:
            sh = lim-hi1
        if sh:
            out = [(p[0]+sh, p[1]) if axis == 0 else (p[0], p[1]+sh) for p in out]
    return out


def _key(poly):
    return tuple(sorted((round(p[0], 2), round(p[1], 2)) for p in poly))


def _rewrite(P, old, new, frame, th, t):
    """put the new outline back where the old one came from, in rects or in herr

    A herr piece also carries the frame of the slip it was cut from, and the clip code measures the
    piece in that frame rather than off the outline.  The replacement therefore inherits the KEEP
    piece's frame carried through the same rigid map: a piece placed by p -> R(th).p + t has
    ang' = ang + th and org' = t + R(th).org, with src unchanged because the slip is the same slip.
    """
    ox0, oy0 = min(p[0] for p in old), min(p[1] for p in old)
    ox1, oy1 = max(p[0] for p in old), max(p[1] for p in old)
    for r in P.get('rects', []):
        if (abs(r['x']-ox0) < .02 and abs(r['y']-oy0) < .02
                and abs(r['x']+r['w']-ox1) < .02 and abs(r['y']+r['h']-oy1) < .02):
            r['x'] = round(min(p[0] for p in new), 2)
            r['y'] = round(min(p[1] for p in new), 2)
            r['w'] = round(max(p[0] for p in new)-r['x'], 2)
            r['h'] = round(max(p[1] for p in new)-r['y'], 2)
            return
    for f in P.get('herr', []):
        if len(f['poly']) == len(old) and all(
                abs(a[0]-b[0]) < .02 and abs(a[1]-b[1]) < .02 for a, b in zip(f['poly'], old)):
            f['poly'] = [[round(v, 2) for v in p] for p in new]
            f['area'] = round(_area(new), 1)
            f['whole'] = False
            if frame is not None:
                c, s = math.cos(th), math.sin(th)
                gx, gy = frame['org']
                f['src'] = list(frame['src'])
                f['ang'] = frame['ang']+math.degrees(th)
                f['org'] = [t[0]+gx*c-gy*s, t[1]+gx*s+gy*c]
            return
