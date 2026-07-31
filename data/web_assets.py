# -*- coding: utf-8 -*-
"""Derive the web-sized stills from the EEVEE renders.

    python web_assets.py

The renders are 1.5-3.5 MB PNGs, 27 of them: fine as the archive copy, hopeless as page weight.
These are WebP with the alpha kept, so the boards still sit on the page background rather than on
a baked-in card.  The PNGs stay where they are for print and for the lightbox originals.
"""
import os, json
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
R = os.path.join(ROOT, 'site', 'renders')
D = json.load(open(os.path.join(ROOT, 'site', 'data', 'boards.json'), encoding='utf-8'))

# tag -> (long edge, quality); thumb is derived from the front elevation
SIZES = (('front', 1100, 86), ('hero', 1500, 84), ('detail', 1500, 84))
THUMB = 300

tot_in = tot_out = 0
for b in D['boards']:
    i = b['idx']
    for tag, edge, q in SIZES:
        src = os.path.join(R, 'b%d_%s.png' % (i, tag))
        if not os.path.exists(src):
            print('missing', src); continue
        im = Image.open(src).convert('RGBA')
        s = edge/max(im.size)
        im2 = im.resize((round(im.width*s), round(im.height*s)), Image.LANCZOS) if s < 1 else im
        dst = os.path.join(R, 'b%d_%s.webp' % (i, tag))
        im2.save(dst, 'WEBP', quality=q, method=6)
        tot_in += os.path.getsize(src); tot_out += os.path.getsize(dst)
        if tag == 'front':
            t = im.resize((round(im.width*THUMB/max(im.size)),
                           round(im.height*THUMB/max(im.size))), Image.LANCZOS)
            tdst = os.path.join(R, 'b%d_thumb.webp' % i)
            t.save(tdst, 'WEBP', quality=82, method=6)
            tot_out += os.path.getsize(tdst)
    print('board %d ok' % i)

# the three drawing sheets, all far too big to put on a page as they stand
Image.MAX_IMAGE_PIXELS = None
# the masters, not site/downloads: the copy there is made by pack_downloads, which runs
# after this, so a newly added sheet had no preview until the build was run twice
DL = os.path.join(ROOT, 'drawings')
for src, dst, edge in (('S7_nine_boards_schedule_CN_EN.png', 'S7_preview.webp', 1800),
                       ('S8_clips_CN_EN.png', 'S8_preview.webp', 1800),
                       ('S9_bricks_CN_EN.png', 'S9_preview.webp', 1800)):
    p = os.path.join(DL, src)
    if not os.path.exists(p):
        print('missing', p); continue
    im = Image.open(p).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    im = Image.alpha_composite(bg, im).convert('RGB')      # sheets are line work on nothing
    s = edge/max(im.size)
    im = im.resize((round(im.width*s), round(im.height*s)), Image.LANCZOS)
    q = os.path.join(R, dst)
    im.save(q, 'WEBP', quality=88, method=6)
    tot_in += os.path.getsize(p); tot_out += os.path.getsize(q)
    print('%s -> %s  %dx%d' % (src, dst, im.width, im.height))

print('\nPNG originals %.1f MB  ->  web assets %.1f MB' % (tot_in/1048576, tot_out/1048576))
