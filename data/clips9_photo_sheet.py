# -*- coding: utf-8 -*-
"""Put the studio frames on a background and write the type and the quantity.  Nothing else.

    python data/clips9_photo_sheet.py    ->  _clip_renders/<code>.png

One picture per clip.  The full part large, and beside it a close-up of the end and the section,
because on the long clip the whole part at 1366 is a strip and the fold is only readable close to.
No captions on the views, no dimensions, no notes: the dimensions live on dxf/06 and S8, and a
picture carrying half of them is a drawing that disagrees with the drawing.

LOCAL ONLY.  _clip_renders/ sits outside site/, so none of this is published.
"""
import io, json, os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
FR = os.path.join(ROOT, '_clip_renders', 'frames')
OUT = os.path.join(ROOT, '_clip_renders')
CL = json.load(open(os.path.join(HERE, 'clips9.json'), encoding='utf-8'))['clips']
D = json.load(open(os.path.join(ROOT, 'site', 'data', 'boards.json'), encoding='utf-8'))

# What to write on each picture.  These are the ORDER quantities, +15 % on the net figures the
# schedules carry and rounded up per product - the number a shop is asked to make, which is the
# only number that belongs on a picture sent to one.  Checked against the data below.
QTY = {'RC-50': 989, 'LC-1366': 90, 'PK-3T03': 40, 'PK-8T02': 19}

W, H = 2400, 1500
BG_TOP, BG_BOT = (247, 246, 243), (228, 226, 221)
INK = (44, 44, 42)


def font(px, bold=False):
    for n in ('msyhbd.ttc' if bold else 'msyh.ttc', 'segoeuib.ttf' if bold else 'segoeui.ttf'):
        p = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', n)
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def backdrop(w, h):
    """a soft vertical wash, so the metal has something to sit on and the white edges read"""
    im = Image.new('RGB', (1, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        f = (y/(h-1))**1.25
        d.point((0, y), tuple(int(BG_TOP[i]+(BG_BOT[i]-BG_TOP[i])*f) for i in range(3)))
    return im.resize((w, h), Image.BILINEAR)


def place(canvas, path, box, margin=0.03):
    """the frame cropped to the part, scaled into box, centred"""
    im = Image.open(path).convert('RGBA')
    bb = im.getchannel('A').getbbox()
    if bb:
        m = int(max(im.size)*margin)
        im = im.crop((max(0, bb[0]-m), max(0, bb[1]-m),
                      min(im.width, bb[2]+m), min(im.height, bb[3]+m)))
    bx, by, bw, bh = box
    k = min(bw/im.width, bh/im.height)
    im = im.resize((max(1, int(im.width*k)), max(1, int(im.height*k))), Image.LANCZOS)
    canvas.paste(im, (bx+(bw-im.width)//2, by+(bh-im.height)//2), im)


def picture(c):
    code = c['code']
    canvas = backdrop(W, H).convert('RGBA')
    pad = 60
    if c['kind'] == 'RAIL' and c['length'] > 400:
        # the whole 1366 across the top, uncut, and the two close-ups under it
        place(canvas, os.path.join(FR, '%s_hero.png' % code), (pad, 40, W-2*pad, 470))
        place(canvas, os.path.join(FR, '%s_detail.png' % code), (pad, 530, 1110, 690))
        place(canvas, os.path.join(FR, '%s_end.png' % code), (1230, 530, 1110, 690))
    else:
        place(canvas, os.path.join(FR, '%s_hero.png' % code), (pad, 60, 1500, 1180))
        place(canvas, os.path.join(FR, '%s_detail.png' % code), (1600, 90, 740, 530))
        place(canvas, os.path.join(FR, '%s_end.png' % code), (1600, 660, 740, 530))

    d = ImageDraw.Draw(canvas)
    d.text((pad+6, H-150), code, font=font(74, True), fill=INK)
    d.text((pad+8, H-58), '× %d' % QTY[code], font=font(46), fill=(112, 109, 103))
    q = os.path.join(OUT, '%s.png' % code)
    canvas.convert('RGB').save(q, quality=96)
    return q


if __name__ == '__main__':
    # the numbers written on the pictures are the +15 % order quantities; say so if they are not
    net = {e['code']: e['qty'] for e in D['summary']['clips']}
    PROD = {b['idx']: b['product'] for b in D['boards']}
    import math
    for e in D['summary']['clips']:
        per = {}
        for u in e['use']:
            per[PROD[u['board']]] = per.get(PROD[u['board']], 0)+u['qty']
        want = sum(math.ceil(v*1.15) for v in per.values())
        if QTY[e['code']] != want:
            print('  NOTE  %s: picture says %d, +15%% on %d works out at %d'
                  % (e['code'], QTY[e['code']], net[e['code']], want))
    for c in CL:
        q = picture(c)
        print('  %-22s %-9s net %4d   picture %4d   %6.1f KB'
              % (os.path.basename(q), c['kind'], net[c['code']], QTY[c['code']],
                 os.path.getsize(q)/1024))
