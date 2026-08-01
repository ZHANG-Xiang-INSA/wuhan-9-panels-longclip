# -*- coding: utf-8 -*-
"""The register: every file this job delivers, and whether it still says what the geometry says.

    python data/check_files.py

check_all.py reconciles the NUMBERS - schedules against geometry, the models against the
schedules.  check_dxf.py and check_sheets.py check that a reader can see what is on a drawing.
Neither of them walks the register, and that is a real hole: a file can simply not be there, or be
there from three regenerations ago, and nothing says so.  Everything published was in the git tree
and the tree was clean, which is not the same as current.

So this one starts from what the job is supposed to hand over - nine boards, so nine models, nine
Blender files, nine textures, four renders each - counts it, opens it, and holds what is inside to
site/data/boards.json.  Nothing is taken on trust because it looks right.
"""
import io, sys, os, json, csv, zipfile, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import ezdxf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
os.chdir(ROOT)
D = json.load(open('site/data/boards.json', encoding='utf-8'))
S = D['summary']
N = len(D['boards'])
SLIPS = sum(len(b['pieces']) for b in D['boards'])
CLIPS = sum(len(b['rails']) for b in D['boards']) + sum(
    1 for b in D['boards'] for i, p in enumerate(b['pieces'])
    if i not in {j for rc in b['rails'] for j in rc['covers']})
bad, seen = [], 0


def ck(cond, msg):
    global seen
    seen += 1
    if not cond:
        bad.append(msg)


def has(path, least=1):
    ok = os.path.exists(path) and os.path.getsize(path) >= least
    ck(ok, 'missing or empty: %s (%d bytes)'
       % (path, os.path.getsize(path) if os.path.exists(path) else -1))
    return ok


# ------------------------------------------------------------------ the register, board by board
for b in D['boards']:
    i = b['idx']
    has('site/models/board_%d.glb' % i, 50000)
    has('site/blend/board_%d.blend' % i, 50000)
    has('site/textures/setout_board_%d.png' % i, 20000)
    for tag in ('front', 'hero', 'detail'):
        has('site/renders/b%d_%s.webp' % (i, tag), 5000)
        has('site/renders/b%d_%s.png' % (i, tag), 50000)
    has('site/renders/b%d_thumb.webp' % i, 1000)

# ------------------------------------------------------------------ the drawings
for q in ('dxf/05_nine_boards_CN_EN.dxf', 'dxf/06_clips_CN_EN.dxf', 'dxf/07_bricks_CN_EN.dxf',
          'dxf/07_bricks_spare15_CN_EN.dxf', 'dxf/08_setout_CN_EN.dxf',
          'dxf/08_setout_spare15_CN_EN.dxf', 'dxf/guiding_rail_clip_10_types_orthographic.dxf'):
    has(q, 1000)
for q in ('S7_nine_boards_schedule_CN_EN', 'S8_clips_CN_EN', 'S9_bricks_CN_EN'):
    has('drawings/%s.svg' % q, 10000)
    has('drawings/%s.png' % q, 10000)
has('docs/board_comparison.pdf', 10000)
has('docs/joint_report.html', 1000)
has('site/index.html', 1000)
has('site/app.js', 1000)
has('site/style.css', 1000)
has('data/clip_colours.json', 100)


def text(p):
    return [e.dxf.text for e in ezdxf.readfile(p).modelspace().query('TEXT')]


# dxf/05 carries the nine boards: every board's title and its size
t5 = ' '.join(text('dxf/05_nine_boards_CN_EN.dxf'))
for b in D['boards']:
    ck(b['en'] in t5 or b['zh'] in t5, 'dxf/05 does not name board %d' % b['idx'])

# dxf/06 carries one detail per clip type, at that type's own length
t6 = text('dxf/06_clips_CN_EN.dxf')
for e in S['clips']:
    ck(any(e['code'] == x or e['code'] in x for x in t6),
       'dxf/06 has no detail for %s' % e['code'])
for r in S['rails']:
    ck(any(x.strip() == ('%g' % r['length']) for x in t6),
       'dxf/06 does not dimension %s at %g' % (r['code'], r['length']))

# dxf/07 carries the brick schedule; every code and every quantity on it
t7 = text('dxf/07_bricks_CN_EN.dxf')
for e in S['bricks']:
    ck(e['code'] in t7, 'dxf/07 is missing brick %s' % e['code'])
    ck(str(e['qty']) in t7, 'dxf/07 is missing the quantity %d for %s' % (e['qty'], e['code']))
ck(str(S['brick_total']) in t7, 'dxf/07 does not carry the brick total %d' % S['brick_total'])

# dxf/08 is the setting-out: one closed outline per slip and one per clip, and the drill marks
d8 = ezdxf.readfile('dxf/08_setout_CN_EN.dxf')
pl = [e for e in d8.modelspace().query('LWPOLYLINE')]
slip = [e for e in pl if e.dxf.layer.endswith('_SLIP')]
clip = [e for e in pl if '_CLIP' in e.dxf.layer]
hole = [e for e in d8.modelspace().query('CIRCLE') if e.dxf.layer.endswith('_HOLE')]
ck(len(slip) == SLIPS, 'dxf/08 draws %d slips, the geometry has %d' % (len(slip), SLIPS))
ck(len(clip) == CLIPS, 'dxf/08 draws %d clips, the geometry has %d' % (len(clip), CLIPS))
# a piece carries no hole list of its own - the holes belong to the clip type it wears
CG = D['clipgeo']
nh = sum(len(rc['holes']) for b in D['boards'] for rc in b['rails']) + sum(
    len(CG[p['c']]['holes']) for b in D['boards'] for i, p in enumerate(b['pieces'])
    if i not in {j for rc in b['rails'] for j in rc['covers']})
ck(len(hole) == nh, 'dxf/08 draws %d drill marks, the geometry has %d' % (len(hole), nh))

# the ordering copies carry the +15 % figures and the same setting-out
t7s = text('dxf/07_bricks_spare15_CN_EN.dxf')
ck(str(S['brick_spare']) in t7s, 'dxf/07 spare does not carry the order total %d' % S['brick_spare'])

# ------------------------------------------------------------------ the sheets
for q, want in (('drawings/S7_nine_boards_schedule_CN_EN.svg', [str(S['brick_total'])]),
                ('drawings/S8_clips_CN_EN.svg', [e['code'] for e in S['clips']]),
                ('drawings/S9_bricks_CN_EN.svg', [e['code'] for e in S['bricks']])):
    body = io.open(q, encoding='utf-8').read()
    for w in want:
        ck(w in body, '%s does not carry %s' % (os.path.basename(q), w))

# ------------------------------------------------------------------ the schedules
for q, tot, col in (('site/downloads/brick_schedule.csv', S['brick_total'], 6),
                    ('site/downloads/clip_schedule.csv', S['clip_total'], 9)):
    rows = list(csv.reader(io.open(q, encoding='utf-8-sig')))[1:]
    by = {}
    for r in rows:
        by[r[0]] = by.get(r[0], 0)+int(r[col])
    ck(len(by) == 3, '%s has %d groupings, want 3' % (os.path.basename(q), len(by)))
    ck(set(by.values()) == {tot}, '%s groupings %s, want %d' % (os.path.basename(q), by, tot))

# ------------------------------------------------------------------ the zip
z = zipfile.ZipFile('site/downloads/wuhan-9-panels.zip')
names = z.namelist()
for b in D['boards']:
    # the zip pads the number - board_01.glb - so ask for the board's folder, not its filename
    fold = '02_boards/board_%02d/' % b['idx']
    for ext in ('.glb', '.blend'):
        ck(any(n.startswith(fold) and n.endswith(ext) for n in names),
           'zip has no %s for board %d' % (ext, b['idx']))
    ck(sum(1 for n in names if n.startswith(fold)) >= 5,
       'zip carries only %d files for board %d'
       % (sum(1 for n in names if n.startswith(fold)), b['idx']))
for w in ('05_nine_boards', '06_clips', '07_bricks', '08_setout', 'S7_', 'S8_', 'S9_',
          'brick_schedule.csv', 'clip_schedule.csv', 'boards.json'):
    ck(any(w in n for n in names), 'zip is missing %s' % w)
for n in names:
    ck(z.getinfo(n).file_size > 0, 'zip entry %s is empty' % n)

# ------------------------------------------------------------------ the page
app = io.open('site/app.js', encoding='utf-8').read()
idx = io.open('site/index.html', encoding='utf-8').read()
for b in D['boards']:
    ck('renders/b%d_hero.webp' % b['idx'] in app or 'b${b.idx}_hero' in app,
       'the page never asks for board %d\'s hero' % b['idx'])
    break
ck('clip_colours' in app, 'the page does not read the clip palette')
ck('data/boards.json' in app, 'the page does not read boards.json')
for q in ('S7_preview.webp', 'S8_preview.webp', 'S9_preview.webp'):
    ck(q in idx, 'index.html does not show %s' % q)
    has('site/renders/%s' % q, 2000)

print('%d checks over %d boards, %d slips, %d clips' % (seen, N, SLIPS, CLIPS))
print('CHECKS FAILED: %d' % len(bad))
for x in bad[:40]:
    print('   ', x)
sys.exit(1 if bad else 0)
