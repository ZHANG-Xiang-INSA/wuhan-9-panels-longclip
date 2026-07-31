# -*- coding: utf-8 -*-
"""Check the matplotlib sheets for text that overlaps something it should not.

    python data/check_sheets.py            # all three
    python data/check_sheets.py S9         # one

check_dxf.py does this for the DXFs.  The sheets had no equivalent, so a column that grew by one
entry, or a note that gained a clause, ran into its neighbour and nothing said so: the file still
wrote, the build still passed, and the fault only showed on the printed sheet.

Four things are tested, in display pixels off a real render:

  TEXT vs TEXT       two labels sharing pixels
  TEXT vs BORDER     a label crossing the edge of its own axes.  bbox_inches='tight' hides this
                     by growing the canvas instead of clipping, so an overrunning note simply
                     widens the sheet and leaves the rules stopping short of it
  TEXT vs LINE       a label sitting on a rule, a dimension line or an outline
  TEXT vs FIGURE     a label off the paper

The sheet modules build their figure at import time, so importing one is what draws it - and also
what SAVES it.  Running this REWRITES drawings/S7, S8 and S9, and matplotlib stamps a date into an
SVG, so the bytes change even when nothing else did.  Run it BEFORE pack_downloads.py, or run
pack_downloads.py again afterwards, or site/downloads is left holding the previous save.
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SHEETS = {'S7': 'panels9_sheet', 'S8': 'clips9_draw', 'S9': 'bricks9_draw',
          'R': 'clips9_sheet'}
PAD = 1.0          # pixels of slack: two boxes touching at the edge are not an overlap


def boxes(fig):
    r = fig.canvas.get_renderer()
    out = []
    for ax in fig.axes:
        # an axes turned off still carries its tick labels, and they still report visible
        if not ax.axison:
            for t in ax.get_xticklabels()+ax.get_yticklabels():
                t.set_visible(False)
    for t in fig.findobj(Text):
        s = t.get_text()
        if not s.strip() or not t.get_visible():
            continue
        try:
            bb = t.get_window_extent(renderer=r)
        except Exception:
            continue
        if bb.width <= 0 or bb.height <= 0:
            continue
        out.append((bb, t, s))
    return out


def hit(a, b):
    return (a.x0 < b.x1-PAD and b.x0 < a.x1-PAD and a.y0 < b.y1-PAD and b.y0 < a.y1-PAD)


def seg_box(p0, p1, bb):
    """does the segment p0-p1 cross the rectangle bb?"""
    x0, y0, x1, y1 = bb.x0+PAD, bb.y0+PAD, bb.x1-PAD, bb.y1-PAD
    if x1 <= x0 or y1 <= y0:
        return False
    if x0 <= p0[0] <= x1 and y0 <= p0[1] <= y1:
        return True
    if x0 <= p1[0] <= x1 and y0 <= p1[1] <= y1:
        return True
    for q0, q1 in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                   ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        d1 = (p1[0]-p0[0])*(q0[1]-p0[1])-(p1[1]-p0[1])*(q0[0]-p0[0])
        d2 = (p1[0]-p0[0])*(q1[1]-p0[1])-(p1[1]-p0[1])*(q1[0]-p0[0])
        d3 = (q1[0]-q0[0])*(p0[1]-q0[1])-(q1[1]-q0[1])*(p0[0]-q0[0])
        d4 = (q1[0]-q0[0])*(p1[1]-q0[1])-(q1[1]-q0[1])*(p1[0]-q0[0])
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
    return False


def segments(fig):
    """every drawn line as display-space segments, with the axes it belongs to"""
    out = []
    for ax in fig.axes:
        for ln in ax.get_lines():
            if not ln.get_visible():
                continue
            d = ln.get_transform().transform(ln.get_xydata())
            for i in range(len(d)-1):
                out.append((ax, tuple(d[i]), tuple(d[i+1])))
    return out


def check(tag, mod):
    # a module that makes several sheets hands them over in FIGS; the rest leave one current
    os.environ['SHEET_CHECK'] = '1'
    m = __import__(mod)
    if hasattr(m, 'build_all'):
        m.FIGS.clear()
        m.build_all()
    figs = list(getattr(m, 'FIGS', None) or [plt.gcf()])
    n = 0
    for k, f in enumerate(figs):
        n += check_fig('%s%s' % (tag, k+1 if len(figs) > 1 else ''), mod, f)
    plt.close('all')
    return n


def check_fig(tag, mod, fig):
    fig.canvas.draw()
    B = boxes(fig)
    W, H = fig.canvas.get_width_height()
    faults = []

    # Text on text, across axes as well as within one.  Restricted to a single axes it missed the
    # case that matters most on a gridded sheet: S9's note sits at the foot of the schedule axes
    # and ran into the title of the panel in the row below, which belongs to a different axes.
    for i in range(len(B)):
        for j in range(i+1, len(B)):
            a, ta, sa = B[i]
            b, tb, sb = B[j]
            if hit(a, b):
                faults.append(('TEXT/TEXT', '%.40r  x  %.40r' % (sa, sb)))

    # Text over the edge of the COLUMN it belongs to.  Sideways only, and against the grid cell
    # rather than the axes box: a title sits above its axes by design and an aspect='equal' axes
    # shrinks its box inside the cell, so a title may legitimately use space the axes does not.
    # What is never intended is a label running into the next column.
    for bb, t, s in B:
        ax = t.axes
        if ax is not None:
            ss = ax.get_subplotspec()
            ab = ss.get_position(fig).transformed(fig.transFigure) if ss is not None \
                else ax.get_window_extent()
            over = max(bb.x1-ab.x1, ab.x0-bb.x0)
            if over > 2.0:
                faults.append(('TEXT/BORDER', '%.50r  sideways by %.0f px' % (s, over)))
        if bb.x0 < -2 or bb.y0 < -2 or bb.x1 > W+2 or bb.y1 > H+2:
            faults.append(('TEXT/FIGURE', '%.50r' % s))

    # text on a drawn line
    SEG = segments(fig)
    for bb, t, s in B:
        for ax, p0, p1 in SEG:
            if ax is not t.axes:
                continue
            if seg_box(p0, p1, bb):
                faults.append(('TEXT/LINE', '%.50r' % s))
                break

    print('%-5s %-22s %5d texts  %5d segments  %d faults'
          % (tag, os.path.basename(mod)+'.py', len(B), len(SEG), len(faults)))
    seen = set()
    for kind, msg in faults:
        k = (kind, msg)
        if k in seen:
            continue
        seen.add(k)
        print('     %-12s %s' % (kind, msg))
    return len(faults)


if __name__ == '__main__':
    want = [a for a in sys.argv[1:] if a in SHEETS] or list(SHEETS)
    n = 0
    for tag in want:
        n += check(tag, SHEETS[tag])
    print('total faults:', n)
