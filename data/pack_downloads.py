# -*- coding: utf-8 -*-
"""Bundle every deliverable into one zip, so the page can offer a single download.

Nine boards times four files each plus the sheets is thirty-odd links; asking somebody to click
each one is not a download, it is a chore.  The zip is built here rather than in the browser so the
page needs no library and the file is the same one every time.

    python data/pack_downloads.py
"""
import os, shutil, zipfile, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
SITE = os.path.join(ROOT, 'site')
OUT = os.path.join(SITE, 'downloads', 'wuhan-9-panels.zip')
D = json.load(open(os.path.join(SITE, 'data', 'boards.json'), encoding='utf-8'))

# site/downloads holds a copy of each drawing, because the page serves it from there.  Refreshing
# that copy by hand is a step nobody remembers: regenerate the clip DXF, forget the copy, and the
# page and the zip both hand out yesterday's drawing while every check upstream passes.  The copy
# is made here, from the file the generator actually wrote.
MIRROR = [('dxf/05_nine_boards_CN_EN.dxf', '05_nine_boards_CN_EN.dxf'),
          ('dxf/06_clips_CN_EN.dxf', '06_clips_CN_EN.dxf'),
          ('drawings/S7_nine_boards_schedule_CN_EN.svg', 'S7_nine_boards_schedule_CN_EN.svg'),
          ('drawings/S7_nine_boards_schedule_CN_EN.png', 'S7_nine_boards_schedule_CN_EN.png'),
          ('drawings/S8_clips_CN_EN.svg', 'S8_clips_CN_EN.svg'),
          ('drawings/S8_clips_CN_EN.png', 'S8_clips_CN_EN.png'),
          ('dxf/07_bricks_CN_EN.dxf', '07_bricks_CN_EN.dxf'),
          ('drawings/S9_bricks_CN_EN.svg', 'S9_bricks_CN_EN.svg'),
          ('drawings/S9_bricks_CN_EN.png', 'S9_bricks_CN_EN.png'),
          ('dxf/08_setout_CN_EN.dxf', '08_setout_CN_EN.dxf'),
          ('docs/board_comparison.pdf', 'board_comparison.pdf')]
for src, dst in MIRROR:
    s = os.path.join(ROOT, src)
    d = os.path.join(SITE, 'downloads', dst)
    if not os.path.exists(s):
        print('  missing source', src)
        continue
    if not os.path.exists(d) or os.path.getmtime(s) > os.path.getmtime(d) \
            or os.path.getsize(s) != os.path.getsize(d):
        shutil.copy2(s, d)
        print('  refreshed downloads/%s' % dst)

items = [('downloads/05_nine_boards_CN_EN.dxf', '01_drawings/05_nine_boards_CN_EN.dxf'),
         ('downloads/06_clips_CN_EN.dxf', '01_drawings/06_clips_CN_EN.dxf'),
         ('downloads/S7_nine_boards_schedule_CN_EN.svg', '01_drawings/S7_schedule.svg'),
         ('downloads/S7_nine_boards_schedule_CN_EN.png', '01_drawings/S7_schedule.png'),
         ('downloads/S8_clips_CN_EN.svg', '01_drawings/S8_clips.svg'),
         ('downloads/S8_clips_CN_EN.png', '01_drawings/S8_clips.png'),
         ('downloads/07_bricks_CN_EN.dxf', '01_drawings/07_bricks_CN_EN.dxf'),
         ('downloads/S9_bricks_CN_EN.svg', '01_drawings/S9_bricks.svg'),
         ('downloads/S9_bricks_CN_EN.png', '01_drawings/S9_bricks.png'),
         ('downloads/08_setout_CN_EN.dxf', '01_drawings/08_setout_CN_EN.dxf'),
         ('downloads/board_comparison.pdf', '01_drawings/board_comparison.pdf'),
         ('data/boards.json', '03_data/boards.json')]
for b in D['boards']:
    i = b['idx']
    items.append(('models/board_%d.glb' % i, '02_boards/board_%02d/board_%02d.glb' % (i, i)))
    items.append(('blend/board_%d.blend' % i,
                  '02_boards/board_%02d/board_%02d.blend' % (i, i)))
    # the WEB renders, not the print masters.  Twenty-seven 1500 px PNGs are 75 MB of a
    # 100 MB zip, and GitHub refuses any file over 100 MiB - adding dxf/08 took the archive to
    # 100.39 and the push would have been rejected.  The masters are one click each in the Files
    # section of the site and in site/renders; what belongs in a one-click bundle is the drawings,
    # the models and the data.
    for tag in ('front', 'hero', 'detail'):
        items.append(('renders/b%d_%s.webp' % (i, tag),
                      '02_boards/board_%02d/b%02d_%s.webp' % (i, i, tag)))

n = 0
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for src, arc in items:
        p = os.path.join(SITE, src)
        if not os.path.exists(p):
            print('  missing', src)
            continue
        z.write(p, arc)
        n += 1
    readme = ['武汉摄影展板 九块板  Wuhan photography boards, nine panels', '',
              '01_drawings  DXF and the two schedule sheets',
              '02_boards    one folder per board: the Blender file, the glTF model and three',
              '             renders as .webp.  Open the .blend and the MORTAR collection can be',
              '             switched with the eye in the Outliner; it is on, the finished board.',
              '             Full-resolution PNG renders are downloaded individually from the site,',
              '             under Files, or taken from site/renders in the repository.',
              '03_data      boards.json, the geometry every other file is generated from', '']
    for b in D['boards']:
        readme.append('board %02d  %-34s %g x %g mm   joint %g   %d slips   %d brick types'
                      % (b['idx'], b['en'], b['w'], b['h'], b['joint'],
                         len(b['pieces']), len(b['types'])))
    z.writestr('README.txt', '\n'.join(readme).encode('utf-8'))
print('%d files -> %s  (%.1f MB)' % (n, os.path.normpath(OUT), os.path.getsize(OUT)/1048576))
