# -*- coding: utf-8 -*-
"""Measure what a slip face actually renders as, and write the per-board albedo gain that makes
it land on the sampled colour.

    blender -b -P build_blender9.py            # pass 1, gains default to 1.0
    python calibrate_albedo.py                 # measure -> albedo_gain.json
    blender -b -P build_blender9.py            # pass 2, gains applied
    python calibrate_albedo.py --check         # confirm

The light rig is already calibrated so a lone face-on surface renders at exactly its albedo (see
--probe in build_blender9.py: 0.995 of target).  On a real board it does not, because each slip
stands 20 proud of its neighbours and they cut off part of the sky - measured here at roughly 27 %
of the hemisphere even at the middle of a face, which is a 7-level drop on the pale sands.

That shading is physically right, but the numbers in pdf_colours.json were sampled off photographs
of laid brickwork, where the same occlusion is already in the pixel.  Matching albedo to sample
would therefore render every board a little darker than the reference it came from.  So the gain
is measured per board, not assumed: the occlusion depends on the bond, and a herringbone does not
shade itself like a stack bond.

Only the slip materials are lifted.  The backing sits 20 down in the joint and is far more
occluded than the faces this gain was measured on, so applying it there would be meaningless.
"""
import json, os, sys
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
RENDERS = os.path.join(ROOT, 'site', 'renders')
GAINS = os.path.join(HERE, 'albedo_gain.json')
COL = json.load(open(os.path.join(HERE, 'pdf_colours.json'), encoding='utf-8'))
D = json.load(open(os.path.join(ROOT, 'site', 'data', 'boards.json'), encoding='utf-8'))

lin = lambda c: c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
CHECK = '--check' in sys.argv


def face_mode(path):
    """the modal colour of slip-face interiors: joints, arris and the occlusion band eroded off

    The joints carry mortar now, and the mortar is lighter than every brick on the job, so "the
    brightest region" stopped meaning "a brick face".  Run as it stood it sampled mortar on the
    boards it could still read and lost boards 3, 4, 5, 6 and 8 outright - the erosion found no
    core and the gain silently fell back to whatever the file already held, which is how
    albedo_gain.json came to be nine gains measured on a board with no mortar in it.

    Masking by the nominal mortar colour is no good either: shading in a 20 mm deep joint moves
    the rendered mortar about 17 levels off its own albedo.  The two materials are split by Otsu
    on luminance instead, which needs no figure from either side, and the brick is the darker
    class on all nine boards.  audit.py splits the same way, so the two agree by construction.
    """
    a = np.asarray(Image.open(path).convert('RGBA')).astype(float)
    al, rgb = a[..., 3], a[..., :3]
    op = al > 250
    lum = rgb.mean(2)
    hist = np.bincount(lum[op].astype(int), minlength=256).astype(float)
    lev = np.arange(256)
    w0 = np.cumsum(hist)/hist.sum()
    m0 = np.cumsum(hist*lev)/hist.sum()
    var = np.where((w0 > 0) & (w0 < 1), (m0[-1]*w0-m0)**2/np.maximum(w0*(1-w0), 1e-9), 0)
    brick = op & (lum <= int(var.argmax()))
    core = binary_erosion(brick & (lum > 0.86*np.percentile(lum[brick], 92)), np.ones((9, 9)))
    if core.sum() < 5000:
        return None
    px = rgb[core]
    return np.array([np.bincount(px[:, c].astype(int), minlength=256).argmax()
                     for c in range(3)], dtype=float)


old = {}
if os.path.exists(GAINS):
    old = json.load(open(GAINS, encoding='utf-8'))

out, rows, worst = {}, [], 0.0
for b in D['boards']:
    i = str(b['idx'])
    p = os.path.join(RENDERS, 'b%s_front.png' % i)
    if not os.path.exists(p):
        print('missing %s' % p); continue
    got = face_mode(p)
    if got is None:
        print('board %s: no usable face core' % i); continue
    tgt = np.array([int(COL[i]['brick'][k:k+2], 16) for k in (1, 3, 5)], dtype=float)
    dE = float(np.abs(got-tgt).max())
    worst = max(worst, dE)
    # solve in linear light, where the shortfall is a clean multiplier
    r = float(np.mean([lin(tgt[c]/255.0)/max(1e-6, lin(got[c]/255.0)) for c in range(3)]))
    out[i] = round(float(old.get(i, 1.0))*r, 5)
    rows.append((i, tgt, got, dE, out[i]))

print('board  sampled          rendered face    dE   gain')
for i, t, g, dE, k in rows:
    print('  %-3s (%3d,%3d,%3d)    (%3d,%3d,%3d)  %4.1f   %.4f'
          % (i, t[0], t[1], t[2], g[0], g[1], g[2], dE, k))
print('\nworst channel error: %.0f / 255' % worst)

if CHECK:
    print('(check only, %s not written)' % os.path.basename(GAINS))
else:
    json.dump(out, open(GAINS, 'w'), indent=1, sort_keys=True)
    print('wrote %s' % GAINS)
