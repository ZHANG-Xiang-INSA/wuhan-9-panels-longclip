# -*- coding: utf-8 -*-
"""One sheet per clip type: six rendered views, the section, and what a shop has to be told.

    blender -b -P data/clips9_render.py     # first, the views
    python  data/clips9_sheet.py            # ->  drawings/R1..R4_<code>_CN_EN.png and .svg

S8 and dxf/06 give the flat blank and the fold lines, which is what a shop cuts and bends to.
This is the part in the hand, so nobody has to picture it from a section: which way the lip hooks,
what the fold looks like from underneath, and that the two lips face EACH OTHER across a 62.5
mouth rather than standing apart.  That last point has been misread more than once, and it is the
whole retention.

Every figure on the sheet is read from clips9.json and boards.json.  Nothing is typed twice.
"""
import io, json, math, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheetwrap as SW

matplotlib.rcParams['font.family'] = ['Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
REN = os.path.join(ROOT, 'site', 'renders')
OUT = os.path.join(ROOT, 'drawings')
INK, DIM, ACC = '#2f2f2d', '#6d6a63', '#b4553a'
CL = json.load(open(os.path.join(HERE, 'clips9.json'), encoding='utf-8'))['clips']
D = json.load(open(os.path.join(ROOT, 'site', 'data', 'boards.json'), encoding='utf-8'))
P, LC = D['profile'], D['summary']['longclip']
LONG_CUT = 320.0                     # must match clips9_render.LONG_CUT
FIGS = []

VIEWS = [('iso_a', '立体图 A　上方前侧', 'ISOMETRIC A - above, front'),
         ('iso_b', '立体图 B　上方右侧', 'ISOMETRIC B - above, to the right'),
         ('under', '立体图 C　仰视：背面与孔', 'ISOMETRIC C - underside, back face and holes'),
         ('plan', '俯视', 'PLAN, looking down'),
         ('end', '端视：折弯就是这个样子', 'END VIEW - this is the fold'),
         ('side', '侧视', 'SIDE VIEW')]


def onto_white(path, margin=0.04):
    """the render, cropped to the part and set on white

    Each view is framed on the part in its own axis, so a 50 x 68 clip seen end-on fills a tenth
    of a square frame and the tile is mostly paper.  Cropping to what was actually drawn - the
    alpha channel knows exactly - puts the part at a size a fabricator can look at.
    """
    im = Image.open(path).convert('RGBA')
    bb = im.getchannel('A').getbbox()
    if bb:
        m = int(max(im.size)*margin)
        im = im.crop((max(0, bb[0]-m), max(0, bb[1]-m),
                      min(im.width, bb[2]+m), min(im.height, bb[3]+m)))
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert('RGB')


def sheet(n, c):
    fig = plt.figure(figsize=(16.5, 13.6))
    fig.patch.set_facecolor('white')
    gs = GridSpec(3, 3, figure=fig, height_ratios=[0.80, 1, 1], hspace=0.20, wspace=0.05,
                  left=0.028, right=0.972, top=0.955, bottom=0.018)

    long = c['kind'] == 'RAIL' and c['length'] > LONG_CUT
    zh = c['zh']
    en = c['en']

    ax = fig.add_subplot(gs[0, :])
    ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0.0, 1.0, '%s   %s' % (c['code'], zh), va='top', ha='left', fontsize=24, color=INK)
    ax.text(0.0, 0.80, en, va='top', ha='left', fontsize=14, color=DIM)

    # the numbers a shop is held to, from the data
    if c['kind'] == 'RAIL':
        spec = [('料厚 SHEET', '%g mm' % P['sheet']),
                ('平板 FLAT', '%g mm' % P['flat']),
                ('立边 LEG', '%g mm' % P['leg']),
                ('唇边 LIP', '%g mm @ %g° 内折 inward' % (P['lip'], P['angle'])),
                ('开口 MOUTH', '%g mm  (砖 slip %g)' % (P['mouth'], D['slip'][1])),
                ('直段 LENGTH', '%g mm' % c['length']),
                ('固定孔 HOLES', '%d × φ%g' % (len(D['clipgeo'][c['code']]['holes']), P['hole'])),
                ('数量 QTY', '%d' % c['qty'])]
        if long:
            spec.insert(6, ('孔距 PITCH', '%g mm，两端各 %g  from each end'
                            % (LC['pitch'], LC['margin'])))
    else:
        elen = c.get('elen') or []
        spec = [('料厚 SHEET', '%g mm' % P['sheet']),
                ('立边 LEG', '%g mm' % P['leg']),
                ('唇边 LIP', '%g mm @ %g° 内折 inward' % (P['lip'], P['angle'])),
                ('压住砖片 GRIP', '%.2f mm  同导轨 as the rail' % 1.26),
                ('外形 OUTLINE', '随砖片 follows the slip, %d 边 sides' % len(c['base'])),
                ('边长 EDGES', '/'.join('%g' % round(e, 1) for e in elen) + ' mm'),
                ('固定孔 HOLES', '%d × φ%g' % (len(D['clipgeo'][c['code']]['holes']), P['hole'])),
                ('数量 QTY', '%d' % c['qty'])]
    # two columns of at most five rows each, so the block never grows past the header
    per = (len(spec)+1)//2
    for i, (k, v) in enumerate(spec):
        cx = (i // per)*0.325
        y = 0.56 - (i % per)*0.112
        ax.text(cx, y, k, va='top', ha='left', fontsize=10.5, color=DIM)
        ax.text(cx+0.125, y, v, va='top', ha='left', fontsize=11, color=INK)

    note = ('折边一律向内折回压住砖片，两条唇边彼此相对，砖片需压入卡紧；这是唯一的固定方式。'
            if c['kind'] == 'RAIL' else
            '折边一律向内折回压住砖片；本件随砖形定制，仅用于所标注的那一种砖。')
    if long:
        note += ('本图为端部 %g mm，全长 %g mm，%d 个孔按 %g 等分。'
                 % (LONG_CUT, c['length'], LC['holes'], LC['pitch']))
    note += ('展开料与折弯线见 dxf/06 与 S8；本图为成形后的实物，供核对折向与孔位。\n'
             'Every fold hooks INWARD, back over the slip. The flat blank and the fold lines are on '
             'dxf/06 and sheet S8; this sheet is the formed part, for checking which way the metal '
             'goes and where the holes land.')
    if long:
        note = note.replace('\n', '\n', 1)
    ax.text(0.655, 0.56, SW.wrap(fig, note, 10, ax.get_window_extent().width*0.335),
            va='top', ha='left', fontsize=10, color=DIM, linespacing=1.55)
    ax.plot([0, 1], [0.665, 0.665], color=INK, lw=0.9)

    for i, (tag, cz, ce) in enumerate(VIEWS):
        a = fig.add_subplot(gs[1+i//3, i % 3])
        p = os.path.join(REN, 'clip_%s_%s.png' % (c['code'], tag))
        a.imshow(onto_white(p))
        a.set_xticks([]); a.set_yticks([])
        for s in a.spines.values():
            s.set_color('#d8d5cd'); s.set_linewidth(1.0)
        a.set_title('%s\n%s' % (cz, ce), fontsize=11, color=INK, pad=7, loc='left',
                    linespacing=1.45)

    fig.suptitle('武汉摄影展板　卡扣实物视图 %d / %d\n'
                 'Wuhan photography boards - clip %d of %d, formed part'
                 % (n, len(CL), n, len(CL)),
                 fontsize=15, color=INK, y=0.992, linespacing=1.45)
    q = os.path.join(OUT, 'R%d_%s_CN_EN.png' % (n, c['code']))
    fig.savefig(q, dpi=200, facecolor='white')
    fig.savefig(q.replace('.png', '.svg'), format='svg', facecolor='white', dpi=150)
    # four sheets from one module, so the figures are handed to check_sheets rather than closed;
    # it inspects one figure per module otherwise and would see only the last clip
    if os.environ.get('SHEET_CHECK'):
        FIGS.append(fig)
    else:
        plt.close(fig)
    return q


def build_all():
    missing = [c['code'] for c in CL for t, _, _ in VIEWS
               if not os.path.exists(os.path.join(REN, 'clip_%s_%s.png' % (c['code'], t)))]
    if missing:
        raise SystemExit('no renders for %s - run: blender -b -P data/clips9_render.py'
                         % sorted(set(missing)))
    for n, c in enumerate(CL, 1):
        q = sheet(n, c)
        print('  %-34s %6.1f KB' % (os.path.basename(q), os.path.getsize(q)/1024))


if __name__ == '__main__':
    build_all()
