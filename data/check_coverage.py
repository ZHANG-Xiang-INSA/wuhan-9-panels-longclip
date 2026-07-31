# -*- coding: utf-8 -*-
"""Do any two slips occupy the same place, and is the board actually covered?

Two blind spots that every other check in this project shares.  A joint test measures the gap
between two pieces, so it reports nothing when they intersect - there is no gap left to be wrong.
A type count counts the pieces that exist, so it reports nothing when one is missing.  Between them
a board can overlap itself and stand open and still pass everything else, which is exactly what
happened when a merge placed 8 pieces by a mirror that does not exist.

Both are measured off a raster of the board: covered twice is an overlap, never covered and further
from a brick than a joint crossing is a hole.  The threshold is J/sqrt2 and not J/2 because where
two joints cross the middle is J/sqrt2 from any brick, and that is not a fault.

    python data/check_coverage.py
"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, label

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, '..', 'site', 'data', 'boards.json'), encoding='utf-8'))

bad = 0
for b in D['boards']:
    W, H, J = b['w'], b['h'], b['joint']
    w, h = int(W)+2, int(H)+2
    acc = np.zeros((h, w), np.int16)
    for p in b['pieces']:
        im = Image.new('1', (w, h), 0)
        ImageDraw.Draw(im).polygon([(q[0], q[1]) for q in p['p']], fill=1)
        acc += np.array(im, np.int16)
    ov = int((acc > 1).sum())
    cov = acc > 0
    d = distance_transform_edt(~cov)
    m = np.zeros_like(cov)
    m[2:-2, 2:-2] = True
    op = (~cov) & m & (d > J/math.sqrt(2.0)+2.0)
    lab, n = label(op)
    holes = sorted([a for a in (int((lab == k).sum()) for k in range(1, n+1)) if a >= 200],
                   reverse=True)
    if ov or holes:
        bad += 1
    print('  board %d  %-16s overlap %6d mm2   open field %6d mm2 in %d patch%s'
          % (b['idx'], '%g x %g' % (W, H), ov, sum(holes), len(holes),
             '' if len(holes) == 1 else 'es'))

# The strip left where the last course does not reach the board edge.  Up to one joint reads as the
# edge joint; more than that is backing board on show.
print()
print('  unfilled margin at each edge, mm:')
for b in D['boards']:
    xs = [q[0] for p in b['pieces'] for q in p['p']]
    ys = [q[1] for p in b['pieces'] for q in p['p']]
    u = b['h']-max(ys)
    print('    board %d  left %.1f  right %.1f  bottom %.1f  top %.1f%s'
          % (b['idx'], min(xs), b['w']-max(xs), min(ys), u,
             '   WIDER THAN ONE JOINT' if u > b['joint']+0.5 else ''))
print()
print('  boards with an overlap or an open patch: %d' % bad)
