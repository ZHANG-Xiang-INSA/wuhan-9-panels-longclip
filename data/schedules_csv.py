# -*- coding: utf-8 -*-
"""The two schedules as CSV, so an order can be placed without reading a drawing.

    python data/schedules_csv.py   ->  site/downloads/brick_schedule.csv
                                       site/downloads/clip_schedule.csv

Each file holds the SAME numbers three times over, in the three groupings the website offers:
by what is made, by what is ordered, and by what is delivered to a board.  A GROUP column carries
the grouping so one file can be filtered in a spreadsheet rather than opened three times.

THE ORDERING CELL IS (type, product).  Spare is 15 % rounded up, and it has to be rounded
somewhere definite: per shape and the split by product orders a fraction of a brick, per board and
the same brick is rounded up nine times.  A purchase order line is a product, so that is the cell,
which is also why the by-board rows carry no spare figure - a board is a slice of a cell.

Written UTF-8 with a BOM, because Excel on a Chinese Windows opens a plain UTF-8 CSV as mojibake.
"""
import csv, io, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'site', 'downloads')
os.makedirs(OUT, exist_ok=True)
D = json.load(open(os.path.join(HERE, '..', 'site', 'data', 'boards.json'), encoding='utf-8'))
S = D['summary']
PROD = {b['idx']: b['product'] for b in D['boards']}
PRODS = [x['product'] for x in S['products']]
SPARE = 1.15


def up(n):
    return int(math.ceil(n*SPARE))


def write(path, head, rows):
    with io.open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(head)
        for r in rows:
            w.writerow(r)
    return path


def bricks():
    head = ['分组 GROUP', '分组值 GROUP VALUE', '件号 CODE', '类别 KIND', '规格 SIZE mm',
            '砖类型 PRODUCT', '数量 QTY', '备料+15% ORDER', '用在 USED ON']
    kind = {'WHOLE': '整砖片 whole slip', 'STD': '标准件 standard', 'CUT': '切割件 cut piece'}
    rows = []
    for e in S['bricks']:
        rows.append(['按形状 by shape', e['code'], e['code'], kind[e['kind']],
                     '%g x %g' % (e['dims'][0], e['dims'][1]),
                     '; '.join('%s %d' % (x['product'], x['qty']) for x in e['products']),
                     e['qty'], e['spare'],
                     '; '.join('板 %d x%d' % (u['board'], u['qty'])
                               for u in e['use'])])
    for p in PRODS:
        for e in S['bricks']:
            c = next((x for x in e['products'] if x['product'] == p), None)
            if not c:
                continue
            rows.append(['按砖类型 by product', p, e['code'], kind[e['kind']],
                         '%g x %g' % (e['dims'][0], e['dims'][1]), p, c['qty'], c['spare'],
                         '; '.join('板 %d x%d' % (u['board'], u['qty'])
                                   for u in e['use'] if PROD[u['board']] == p)])
    for b in D['boards']:
        for e in S['bricks']:
            u = next((x for x in e['use'] if x['board'] == b['idx']), None)
            if not u:
                continue
            # no spare on a by-board row: see the docstring
            rows.append(['按板号 by board', '板 board %d' % b['idx'], e['code'], kind[e['kind']],
                         '%g x %g' % (e['dims'][0], e['dims'][1]), b['product'], u['qty'], '',
                         '板 %d' % b['idx']])
    return write(os.path.join(OUT, 'brick_schedule.csv'), head, rows)


def clip_cells(e):
    per = {}
    for u in e['use']:
        per[PROD[u['board']]] = per.get(PROD[u['board']], 0)+u['qty']
    return per


def clips():
    head = ['分组 GROUP', '分组值 GROUP VALUE', '件号 CODE', '类别 KIND', '名称 NAME',
            '长度 LENGTH mm', '孔数 HOLES', '孔距 PITCH mm', '砖类型 PRODUCT',
            '数量 QTY', '备料+15% ORDER', '用在 USED ON']

    def spec(e):
        return [e.get('length', 50 if e['kind'] == 'RAIL' else ''),
                e.get('holes', 2), e.get('pitch', '')]

    rows = []
    for e in S['clips']:
        per = clip_cells(e)
        rows.append(['按型号 by type', e['code'], e['code'], e['kind'], e['en']] + spec(e)
                    + ['; '.join('%s %d' % (k, per[k]) for k in sorted(per)),
                       e['qty'], sum(up(v) for v in per.values()),
                       '; '.join('%d x%d' % (u['board'], u['qty']) for u in e['use'])])
    for p in PRODS:
        for e in S['clips']:
            per = clip_cells(e)
            if p not in per:
                continue
            rows.append(['按砖类型 by product', p, e['code'], e['kind'], e['en']] + spec(e)
                        + [p, per[p], up(per[p]),
                           '; '.join('%d x%d' % (u['board'], u['qty']) for u in e['use']
                                     if PROD[u['board']] == p)])
    for b in D['boards']:
        for e in S['clips']:
            u = next((x for x in e['use'] if x['board'] == b['idx']), None)
            if not u:
                continue
            rows.append(['按板号 by board', '板 board %d' % b['idx'], e['code'], e['kind'],
                         e['en']] + spec(e) + [b['product'], u['qty'], '', '%d' % b['idx']])
    return write(os.path.join(OUT, 'clip_schedule.csv'), head, rows)


if __name__ == '__main__':
    q = bricks()
    r = clips()

    # regrouping must never change a total: the same check the page makes in the browser
    def tally(path, col):
        rows = list(csv.reader(io.open(path, encoding='utf-8-sig')))[1:]
        out = {}
        for row in rows:
            g = row[0].split(' ', 1)[-1]            # the English half; the console is cp1252
            out[g] = out.get(g, 0)+int(row[col])
        return out

    for path, col, want in ((q, 6, S['brick_total']), (r, 9, S['clip_total'])):
        got = tally(path, col)
        ok = set(got.values()) == {want}
        print('  %-22s %s   %s' % (os.path.basename(path),
                                   '  '.join('%s %d' % kv for kv in got.items()),
                                   'OK' if ok else 'DISAGREE, expected %d' % want))
        assert ok
