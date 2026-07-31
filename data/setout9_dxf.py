# -*- coding: utf-8 -*-
"""The setting-out drawing: what to scribe on each backing board before any slip is laid.

    python data/setout9_dxf.py    ->  dxf/08_setout_CN_EN.dxf

Nine panels, 1:1, one per board.  On each: the outline of every slip, the tray of the clip that
holds it, the two fixing holes under that clip, and a type code inside each outline - the brick
code in the brick, the clip code in the clip, both at the same height.  The board maker plots this
at 1:1 and marks the board; after that a fitter reads the board itself instead of a schedule.

Layers are per board and per thing - P1_SLIP, P1_CLIP, P1_HOLE, P1_TXT_B, P1_TXT_C - so one board
can be isolated and plotted on its own, and the holes can be sent to a driller on their own.
"""
import ezdxf, math, os
from ezdxf.enums import TextEntityAlignment as TA
from setout9 import board, TXT_H, SHORT, load

HERE = os.path.dirname(os.path.abspath(__file__))
HOLE_D = 3.5
# the long clip is described in the notes, and its length is read rather than repeated: it is a
# searched result and the drawing must not be able to disagree with the schedule about it
LSTD = load()['summary']['longclip']
LCODE = LSTD['code']
COLS, GAPX, GAPY = 3, 1000.0, 760.0

doc = ezdxf.new('R2010', setup=True); doc.header['$INSUNITS'] = 4
msp = doc.modelspace()
doc.styles.add('CN', font='msyh.ttc')
for n, c in {'BOARD': 7, 'DIM': 8, 'TITLE': 7, 'NOTE': 7, 'BORDER': 7, 'ORIGIN': 1}.items():
    if n not in doc.layers:
        doc.layers.add(n, color=c)
# one decimal, trailing zeros suppressed, and a full stop: four boards are sized on a half mm
DS = doc.dimstyles.add('MM')
DS.dxf.dimlfac, DS.dxf.dimtxsty = 1.0, 'CN'
DS.dxf.dimtxt, DS.dxf.dimasz = 34.0, 20.0
DS.dxf.dimexe, DS.dxf.dimexo, DS.dxf.dimgap = 12.0, 10.0, 8.0
DS.dxf.dimdec, DS.dxf.dimtad, DS.dxf.dimzin, DS.dxf.dimdsep = 1, 1, 8, ord('.')
AL = {'BL': TA.BOTTOM_LEFT, 'MC': TA.MIDDLE_CENTER, 'ML': TA.MIDDLE_LEFT}


def TX(p, s, h, lay, al='BL'):
    t = msp.add_text(s, dxfattribs={'layer': lay, 'height': h, 'style': 'CN'})
    t.set_placement(p, align=AL[al])
    return t


def PL(pts, lay, close=True, lw=None):
    a = {'layer': lay}
    if lw:
        a['lineweight'] = lw
    msp.add_lwpolyline(pts, close=close, dxfattribs=a)


def strw(s, h):
    return h*sum(1.05 if ord(c) > 0x2E80 else 0.62 for c in s)


def wrap(s, h, width, indent=''):
    out, line = [], ''
    for w in s.split(' '):
        t = (line+' '+w) if line else w
        if line and strw(t, h) > width:
            out.append(line); line = indent+w
        else:
            line = t
    if line:
        out.append(line)
    return out


def panel(B, ox, oy):
    i = B['idx']
    # slips black, clips blue, holes red - the same three colours the baked texture and the website
    # legend use, so a fitter reading the plot and a fitter reading the model see the same thing.
    # Clips were cyan (4), which plots the same weight as the black slip line on a mono printer.
    for nm, col in (('SLIP', 7), ('CLIP', 5), ('HOLE', 1), ('TXT_B', 7), ('TXT_C', 5)):
        lay = 'P%d_%s' % (i, nm)
        if lay not in doc.layers:
            doc.layers.add(lay, color=col)
    S, C, H = 'P%d_SLIP' % i, 'P%d_CLIP' % i, 'P%d_HOLE' % i
    TB, TC = 'P%d_TXT_B' % i, 'P%d_TXT_C' % i

    PL([(ox, oy), (ox+B['w'], oy), (ox+B['w'], oy+B['h']), (ox, oy+B['h'])], 'BOARD', lw=50)
    for lc in B['longs']:
        PL([(ox+q[0], oy+q[1]) for q in lc['tray']], C)
        for hx, hy in lc['holes']:
            msp.add_circle((ox+hx, oy+hy), HOLE_D/2, dxfattribs={'layer': H})
            for dx, dy in ((6.5, 0), (0, 6.5)):
                msp.add_line((ox+hx-dx, oy+hy-dy), (ox+hx+dx, oy+hy+dy), dxfattribs={'layer': H})
        TX((ox+lc['clab'][0], oy+lc['clab'][1]), lc['ccode'], lc['th'], TC, 'MC')
    for p in B['pieces']:
        PL([(ox+q[0], oy+q[1]) for q in p['slip']], S)
        if p['tray']:
            PL([(ox+q[0], oy+q[1]) for q in p['tray']], C)
        for hx, hy in p['holes']:
            msp.add_circle((ox+hx, oy+hy), HOLE_D/2, dxfattribs={'layer': H})
            for dx, dy in ((6.5, 0), (0, 6.5)):
                msp.add_line((ox+hx-dx, oy+hy-dy), (ox+hx+dx, oy+hy+dy),
                             dxfattribs={'layer': H})
        TX((ox+p['tlab'][0], oy+p['tlab'][1]), p['tcode'], p['th'], TB, 'MC')
        if p['ccode']:
            TX((ox+p['clab'][0], oy+p['clab'][1]), p['ccode'], p['th'], TC, 'MC')

    # the datum corner the whole layout is measured from
    msp.add_line((ox-70, oy), (ox+90, oy), dxfattribs={'layer': 'ORIGIN'})
    msp.add_line((ox, oy-70), (ox, oy+90), dxfattribs={'layer': 'ORIGIN'})
    TX((ox-64, oy-58), '0,0', 26, 'ORIGIN')

    # control dimensions only.  The layout itself is the setting out - it is scribed on the board
    # at 1:1 - so what a plotter needs is enough to prove the sheet came out at scale.
    d = msp.add_linear_dim(base=(ox+B['w']/2, oy-190), p1=(ox, oy), p2=(ox+B['w'], oy),
                           dimstyle='MM', dxfattribs={'layer': 'DIM'}); d.render()
    d = msp.add_linear_dim(base=(ox+B['w']+190, oy+B['h']/2), p1=(ox+B['w'], oy),
                           p2=(ox+B['w'], oy+B['h']), angle=90.0, dimstyle='MM',
                           dxfattribs={'layer': 'DIM'}); d.render()
    # a whole slip drawn beside the board, dimensioned, so a plotter can put a rule on the print
    # and know it came out at 1:1.  Drawn OUTSIDE: dimensioning a slip in the field put the value
    # and its arrows straight across the layout.
    sx, sy = ox+B['w']+300, oy
    PL([(sx, sy), (sx+215, sy), (sx+215, sy+65), (sx, sy+65)], 'DIM')
    d = msp.add_linear_dim(base=(sx+107.5, sy-130), p1=(sx, sy), p2=(sx+215, sy),
                           dimstyle='MM', dxfattribs={'layer': 'DIM'}); d.render()
    d = msp.add_linear_dim(base=(sx+215+130, sy+32.5), p1=(sx+215, sy), p2=(sx+215, sy+65),
                           angle=90.0, dimstyle='MM', dxfattribs={'layer': 'DIM'}); d.render()
    TX((sx, sy+110), '比例校核 SCALE CHECK   整砖片 whole slip', 26, 'DIM')

    ty = oy+B['h']+300
    TX((ox, ty), '%d   %s   %s' % (i, B['zh'], B['en']), 54, 'TITLE'); ty -= 68
    TX((ox, ty), '板面 board %g x %g     灰缝 joint %g     砖片 slip 215 x 65 x 20     '
                 '共 %d 片砖、%d 个卡扣'
       % (B['w'], B['h'], B['joint'], len(B['pieces']),
          sum(c[2] for c in B['clips'])), 30, 'TITLE'); ty -= 46
    TX((ox, ty), '砖型 bricks: ' + '，'.join('%s %s x%d' % t for t in B['types']), 26, 'TITLE')
    ty -= 40
    TX((ox, ty), '卡扣 clips: ' + '，'.join('%s = %s x%d' % c for c in B['clips']), 26, 'TITLE')


def legend(x, y):
    TX((x, y), 'WUHAN PHOTOGRAPHY BOARDS  -  SETTING OUT ON THE BACKING BOARD', 66, 'TITLE')
    TX((x, y-84), '武汉摄影展板　背板放线图　　3 Monahan Avenue (HA23007)   |   nine boards, 1:1   |   '
                  'scribe this on the board before any slip is laid', 30, 'TITLE')
    notes = [
        'NOTES  说明:',
        '1. ALL DIMENSIONS IN MILLIMETRES.  Every board is drawn 1:1 - plot at 1:1 and the lines '
        'are where the slips go.   全部尺寸单位为毫米，各板均按 1:1 绘制；按 1:1 出图，图上的线'
        '就是砖片的位置。',
        '2. WHAT IS DRAWN, AND IN WHAT COLOUR.  The slip outlines are BLACK (layer P#_SLIP), the '
        'clip trays BLUE (P#_CLIP) and the dia %g fixing holes RED (P#_HOLE).  Where a course runs '
        'unbroken one %s spans several slips, so its tray crosses the slip lines under it; '
        'everywhere else one RC-50 or one pocket clip sits on its own slip.   '
        '画的内容与颜色：砖片轮廓为黑色（图层 P#_SLIP），卡扣托盘为蓝色（P#_CLIP），'
        '%g 固定孔为红色（P#_HOLE）。整排连续处由一根 %s 横跨数片砖，其托盘会压过下面的砖线；'
        '其余位置仍为一砖一扣（RC-50 或包边卡扣）。' % (HOLE_D, LCODE, HOLE_D, LCODE),
        '3. THE CODES ARE WRITTEN INSIDE.  The brick code sits in the brick, the clip code in the '
        'clip, both %g high.  A fitter reads the board, not a schedule.   '
        '编号写在框里：砖型写在砖片轮廓内，卡扣型写在卡扣托盘内，字高均为 %g。'
        '师傅只看板上的字，不必对表。' % (TXT_H, TXT_H),
        '4. CLIP CODES: ' + '，'.join('%s = %s' % (v, k) for k, v in SHORT.items()) +
        '.  Shortened only so the code fits inside a 50 x 68 tray; the full designation is on '
        'dxf/06 and S8.   卡扣编号为缩写，只因要写进 50 x 68 的托盘内；全称见 dxf/06 与 S8。',
        '5. THE HOLES ARE THE ONLY THING DRILLED.  Slip and tray outlines are surface marks.  '
        'RC-50: 12.5 from each end on the 68 centreline.  %s: %d holes at %g pitch on the same '
        'centreline, %g from each end.  Pocket clips are eroded off the tray - 8 clear of a plain '
        'edge, 12 of a folded one.   '
        '只有孔需要钻；砖片与托盘轮廓仅为表面画线。RC-50 孔位为距两端各 12.5、在 68 中线上；'
        '%s 为同一中线上 %d 个孔，孔距 %g，距两端各 %g；包边卡扣按托盘内缩定位，距普通边 8，'
        '距折边 12。' % (LCODE, LSTD['holes'], LSTD['pitch'], LSTD['margin'],
                         LCODE, LSTD['holes'], LSTD['pitch'], LSTD['margin']),
        '6. LAYERS ARE PER BOARD.  Freeze all but P3_* to plot board 3 alone, or plot P#_HOLE by '
        'itself for the driller.   图层按板分组：只留 P3_* 即可单独出板 3；单独打开 P#_HOLE '
        '可只出钻孔图。',
        '7. THE DATUM is the bottom-left corner of each board, marked 0,0.  Every outline on that '
        'board is positioned from it.   每块板的基准为其左下角，图中标 0,0，该板所有轮廓均自此定位。',
        '8. Joints are already in the outlines and differ from board to board (3, 5, 7, 10 mm).  '
        'Do not add a joint - lay each slip to its own line.   '
        '灰缝已含在轮廓之间，各板不同（3、5、7、10 mm）。不要另留缝，照线贴即可。',
    ]
    yy = y-140
    for s in notes:
        for ln in wrap(s, 26, 3400, '    '):
            TX((x, yy), ln, 26, 'NOTE'); yy -= 44
        yy -= 10
    return yy


# ---------------------------------------------------------------- build
BD = [board(i) for i in range(1, 10)]
CW = max(b['w'] for b in BD)+GAPX
CH = max(b['h'] for b in BD)+GAPY
yend = legend(0, 0)
top = yend-420
for k, B in enumerate(BD):
    panel(B, (k % COLS)*CW, top-(k//COLS)*CH-B['h'])

import ezdxf.bbox as bb
ext = bb.extents(msp); mn, mx = ext.extmin, ext.extmax; pad = 120
PL([(mn[0]-pad, mn[1]-pad), (mx[0]+pad, mn[1]-pad), (mx[0]+pad, mx[1]+pad),
    (mn[0]-pad, mx[1]+pad)], 'BORDER')
q = os.path.join(HERE, '..', 'dxf', '08_setout_CN_EN.dxf')
doc.saveas(q)
print('SAVED', os.path.normpath(q), '| entities', len(list(msp)),
      '| %d slips, %d clips, %d holes'
      % (sum(len(b['pieces']) for b in BD),
         sum(c[2] for b in BD for c in b['clips']),
         sum(len(p['holes']) for b in BD for p in b['pieces'])
         + sum(len(lc['holes']) for b in BD for lc in b['longs'])))
print('  x[%.0f..%.0f] y[%.0f..%.0f] mm' % (mn[0], mx[0], mn[1], mx[1]))
