# -*- coding: utf-8 -*-
"""The same setting-out, baked to a texture for the backing board in the 3D model and the website.

    python data/setout9_tex.py    ->  site/textures/setout_board_1..9.png

dxf/08 is for the board maker.  This is for everyone looking at the model: switch the slips off, or
pull them off with the exploded view, and the board underneath carries the identical lines and
codes.  A texture rather than real line geometry because the alternative is tens of thousands of
extra edges per board in a file the website has to download.

Drawn on the board's own backing colour, so the model does not suddenly show a white board, and at
a resolution fixed in millimetres so every board gets the same sharpness whatever its size.
"""
import json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
from setout9 import board, load

matplotlib.rcParams['font.family'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'site', 'textures')
os.makedirs(OUT, exist_ok=True)
PXMM = 2.6              # pixels per millimetre: a 1565 board comes out about 4070 px
# Three colours a fitter can name across a room.  The first version drew the slips in #39332c and
# the clips in #1d5f86, which are a different hue but the same darkness: at hairline width on a
# pale board both simply read as "a dark line" and nobody could tell which was which.  The clip is
# now a light-valued blue against a near-black slip, so the two differ in brightness as well as
# hue, which is what the eye actually separates at this size.
INK = '#141414'         # the slip outline, and its brick code
HOLE = '#d92b2b'        # the fixing holes
# ONE COLOUR PER CLIP TYPE, from data/clip_colours.json, and the same one wherever that clip is
# drawn - here, on dxf/08, in the model and on the page.  Every clip used to be the one blue, so a
# board carrying an R700, an R100 and an R50 in the same course showed three clips and no way to
# tell which was which; the code beside each was doing all the work.
CLIPC = json.load(open(os.path.join(HERE, 'clip_colours.json'), encoding='utf-8'))
CLIP = CLIPC['R50']['line']
COL = json.load(open(os.path.join(HERE, 'pdf_colours.json'), encoding='utf-8'))


def bake(i):
    B = board(i)
    w, h = B['w'], B['h']
    px, py = int(round(w*PXMM)), int(round(h*PXMM))
    fig = plt.figure(figsize=(px/100.0, py/100.0), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w); ax.set_ylim(0, h)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_facecolor(COL[str(i)]['mortar'])
    fig.patch.set_facecolor(COL[str(i)]['mortar'])

    # 1.2 mm of ink at any board size, so a line looks the same weight on board 3 as on board 8
    lw = 1.2*PXMM*72/100.0/PXMM*1.0
    for lc in B['rails']:
        cc = CLIPC.get(lc['ccode'], CLIPC['R50'])['line']
        ax.add_patch(Polygon(lc['tray'], closed=True, fill=False, ec=cc, lw=lw*0.85, zorder=3))
        for hx, hy in lc['holes']:
            ax.add_patch(Circle((hx, hy), 1.75, fill=False, ec=HOLE, lw=lw*0.8, zorder=4))
            ax.plot([hx-6.5, hx+6.5], [hy, hy], color=HOLE, lw=lw*0.7, zorder=4)
            ax.plot([hx, hx], [hy-6.5, hy+6.5], color=HOLE, lw=lw*0.7, zorder=4)
        ax.text(lc['clab'][0], lc['clab'][1], lc['ccode'], ha='center', va='center',
                fontsize=lc['th']*PXMM*72.0/100.0, color=cc, zorder=6)
    for p in B['pieces']:
        ax.add_patch(Polygon(p['slip'], closed=True, fill=False, ec=INK, lw=lw, zorder=2))
        pc = CLIPC.get(p['ccode'], CLIPC['R50'])['line']
        if p['tray']:
            ax.add_patch(Polygon(p['tray'], closed=True, fill=False, ec=pc, lw=lw*0.85,
                                 zorder=3))
        for hx, hy in p['holes']:
            ax.add_patch(Circle((hx, hy), 1.75, fill=False, ec=HOLE, lw=lw*0.8, zorder=4))
            ax.plot([hx-6.5, hx+6.5], [hy, hy], color=HOLE, lw=lw*0.7, zorder=4)
            ax.plot([hx, hx], [hy-6.5, hy+6.5], color=HOLE, lw=lw*0.7, zorder=4)
        fs = p['th']*PXMM*72.0/100.0        # matplotlib points for a cap height in millimetres
        ax.text(p['tlab'][0], p['tlab'][1], p['tcode'], ha='center', va='center',
                fontsize=fs, color=INK, zorder=6)
        if p['ccode']:
            ax.text(p['clab'][0], p['clab'][1], p['ccode'], ha='center', va='center',
                    fontsize=fs, color=pc, zorder=6)
    q = os.path.join(OUT, 'setout_board_%d.png' % i)
    fig.savefig(q, dpi=100, facecolor=COL[str(i)]['mortar'], pad_inches=0)
    plt.close(fig)
    return q, px, py


if __name__ == '__main__':
    tot = 0
    for i in range(1, 10):
        q, px, py = bake(i)
        n = os.path.getsize(q); tot += n
        print('  %-24s %5d x %-5d px   %6.0f KB   %.2f mm/px'
              % (os.path.basename(q), px, py, n/1024, 1.0/PXMM))
    print('  nine textures, %.1f MB' % (tot/1048576.0))
