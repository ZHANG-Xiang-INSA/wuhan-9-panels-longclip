"""One sheet: for each of the nine boards, the proposal's own mock-up, the layout coloured by
brick type, and the schedule of types, sizes and quantities, in Chinese and English.

The mock-ups are raster textures, so they carry the bond and nothing else.  No dimension is read
off them; they sit beside the drawing so the bond can be checked by eye.
"""
import json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, FancyArrowPatch
from matplotlib.gridspec import GridSpec
from PIL import Image
from panels9_types import classify
import labels9 as LB

matplotlib.rcParams['font.family'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

HERE = os.path.dirname(os.path.abspath(__file__))
PDFD = os.path.join(HERE, '..', 'proposal', 'extracted')
OUT = os.path.join(HERE, '..', 'drawings')
P = json.load(open(os.path.join(HERE, 'panels9.json')))

MOCK = {
    1: 'P1_stretcher_wall_vertstack.png', 2: 'P2_stretcher_floor.png',
    3: 'P3_herringbone_border102.png',    4: 'P4_stretcher_endborder.png',
    5: 'P5_herringbone_straight.png',     6: 'P6_basketweave.png',
    7: 'P7_runningbond.png',              8: 'P8_triple_herringbone.png',
    9: 'P9_horizontal_stack.png',
}
INK = '#2f2f2d'

fig = plt.figure(figsize=(21.0, 47.0))
fig.patch.set_facecolor('white')
gs = GridSpec(9, 3, figure=fig, width_ratios=[0.92, 1.10, 1.62],
              hspace=0.30, wspace=0.09, left=0.014, right=0.988, top=0.9555, bottom=0.008)


def dim_line(ax, p0, p1, text, off, horiz):
    a = (p0[0]+off[0], p0[1]+off[1]); b = (p1[0]+off[0], p1[1]+off[1])
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle='<->', mutation_scale=9,
                                 lw=0.9, color=INK, shrinkA=0, shrinkB=0, zorder=5))
    ax.text((a[0]+b[0])/2.0, (a[1]+b[1])/2.0, text, ha='center', va='center', fontsize=9,
            color=INK, zorder=6, rotation=0 if horiz else 90,
            bbox=dict(fc='white', ec='none', pad=1.4))


for row, p in enumerate(P):
    idx, Wd, Ht = p['idx'], p['Wd'], p['Ht']
    types, pieces = classify(p)
    zh, en = LB.bond(idx)

    ax = fig.add_subplot(gs[row, 0])
    ax.imshow(Image.open(os.path.join(PDFD, MOCK[idx])))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(INK); s.set_linewidth(1.0)
    ax.set_title('%d   %s' % (idx, LB.MOCKUP), fontsize=11, color=INK, pad=7, loc='left')

    ax = fig.add_subplot(gs[row, 1])
    ax.add_patch(Rectangle((0, 0), Wd, Ht, fc='#faf9f6', ec=INK, lw=1.5, zorder=0))
    for pc in pieces:
        ax.add_patch(Polygon(pc['poly'], closed=True, fc=types[pc['type']]['colour'],
                             ec=INK, lw=0.3, zorder=1))
    m = max(Wd, Ht)*0.10
    dim_line(ax, (0, Ht), (Wd, Ht), '%g' % Wd, (0, m*0.42), True)
    dim_line(ax, (Wd, 0), (Wd, Ht), '%g' % Ht, (m*0.42, 0), False)
    ax.set_xlim(-m*0.30, Wd+m*0.95); ax.set_ylim(-m*0.30, Ht+m*0.85)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('%s\n%s\n%g x %g mm    灰缝 joint %g mm    砖片 slip 215 x 65 x 20'
                 % (zh, en, Wd, Ht, p['J']), fontsize=10.5, color=INK, pad=7,
                 loc='left', linespacing=1.5)

    ax = fig.add_subplot(gs[row, 2])
    ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    nw, ns, nc, ncutt = LB.counts(types)
    for k, line in enumerate(LB.header(p, len(types), ncutt, nw, ns, nc, len(pieces))):
        ax.text(0.0, 0.985-k*0.043, line, va='top', ha='left', fontsize=9.6, color=INK)
    ax.plot([0.0, 0.63], [0.800, 0.800], color=INK, lw=0.8)
    for x, s in zip((0.075, 0.150, 0.225), LB.HDR):
        ax.text(x, 0.782, s, va='top', ha='left', fontsize=9.0, color=INK)

    y, dy = 0.735, min(0.049, 0.72/max(len(types), 1))
    for t in types:
        ax.add_patch(Rectangle((0.005, y-dy*0.60), 0.055, dy*0.60, fc=t['colour'],
                               ec=INK, lw=0.4, transform=ax.transAxes, clip_on=False))
        ax.text(0.075, y, t['code'], va='top', ha='left', fontsize=8.5, color=INK)
        ax.text(0.150, y, str(t['qty']), va='top', ha='left', fontsize=8.5, color=INK)
        ax.text(0.225, y, LB.describe(t), va='top', ha='left', fontsize=8.5, color=INK)
        y -= dy

fig.suptitle('%s\n%s' % LB.SHEET_TITLE, fontsize=16, color=INK, y=0.9885, linespacing=1.5)
q = os.path.join(OUT, 'S7_nine_boards_schedule_CN_EN.png')
fig.savefig(q, dpi=220, facecolor='white')

# The SVG is what the website's drawing viewer opens, so it is the one people zoom into.  Its line
# work, dimensions and text are vector and sharp at any magnification, but the nine proposal
# mock-ups are photographs, and matplotlib rasterises an imshow at the save DPI: at the default 100
# the 2048 px sources came out as 373 px and went soft the moment anyone zoomed in.  180 puts them
# near 670.
qs = q.replace('.png', '.svg')
fig.savefig(qs, format='svg', facecolor='white', dpi=180)

# That alone took the sheet from 4.0 to 10.5 MB, because matplotlib embeds every raster as PNG and
# PNG is the wrong format for a photograph.  Re-encoding the nine of them as JPEG costs nothing a
# reader can see and gives most of the file back.  Only the photographs are touched; every line,
# dimension and character in the sheet is vector and is not re-encoded.
import base64 as _b64, io as _io, re as _re
_svg = open(qs, encoding='utf-8').read()
_n, _before = 0, len(_svg)


def _jpg(m):
    global _n
    im = Image.open(_io.BytesIO(_b64.b64decode(m.group(1))))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    buf = _io.BytesIO()
    im.convert('RGB').save(buf, 'JPEG', quality=82, optimize=True, progressive=True)
    _n += 1
    return 'xlink:href="data:image/jpeg;base64,%s"' % _b64.b64encode(buf.getvalue()).decode()


_svg = _re.sub(r'xlink:href="data:image/png;base64,([^"]+)"', _jpg, _svg)
open(qs, 'w', encoding='utf-8').write(_svg)
print('   svg: %d rasters re-encoded to jpeg, %.1f -> %.1f MB'
      % (_n, _before/1048576, len(_svg)/1048576))
print('->', os.path.normpath(q.replace('.png', '.svg')))
print('->', os.path.normpath(q))
