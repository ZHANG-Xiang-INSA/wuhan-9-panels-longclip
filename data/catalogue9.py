# -*- coding: utf-8 -*-
"""The one brick catalogue: B01..B12, assigned over all nine boards at once.

panels9_types.classify() numbers a board's own types T01, T02, ... in its own order, so the same
number means a different brick on a different board: board 3's T04 is an 11/65/76/161/215 field
piece and board 8's T04 is a 65/92/150/215 one.  That numbering is fine inside one board and wrong
everywhere else, so every drawing, model and schedule carries the B code instead and the T code
stays where it belongs, as the per-board sort order behind it.

This lives on its own because four producers need the catalogue and three of them run before
site_export.py, which used to be where the B codes were minted:

    step 1  panels9_build.py    dxf/05, and its per-board layer names
    step 2  clips9_build.py     the pocket clip note, which names the brick it is cut to
    step 4  panels9_sheet.py    S7
    step 6  site_export.py      boards.json, and through it 07, 08, the textures, the models,
                                the schedules and the page

All four already hold all nine boards and call classify() themselves, so all four get the same
answer from the same geometry.  Nothing here reads a file.
"""

KORD = {'WHOLE': 0, 'STD': 1, 'CUT': 2}


def norm(t):
    """a classify() type reduced to the fields the catalogue groups on, rounded the way
    boards.json rounds them - so grouping does not depend on which producer asked"""
    return dict(code=t['code'], kind=t['kind'], qty=t['qty'], label=t['label'],
                area=round(t['area']), nsides=t['nsides'],
                dims=[round(t['dims'][0], 1), round(t['dims'][1], 1)])


def gkey(t):
    # A rectangle can arrive by either path and gets a different label each way: the border
    # generator labels it "147.5 x 65" and the herringbone labels the same kind of piece with its
    # edge signature, "65/65/140/140".  Keying on the label would file one product under two rows.
    # A polygon whose area fills its bounding box is a rectangle, whatever the label says.
    rect = abs(t['area'] - t['dims'][0]*t['dims'][1]) < 1.5
    if rect:
        return ('r', tuple(sorted(t['dims'])), t['kind'] == 'CUT')
    return ('f', t['label'])


def catalogue(per_board):
    """per_board is [(board index, [type, ...]), ...] for ALL NINE boards, types as norm() leaves
    them.  Nine boards, because a code that is assigned from fewer is a different code.

    -> (entries, code)
       entries  the ordered catalogue, one dict per B code, carrying use=[{board, code, qty}]
                with the B code in it - the T code has done its job by then and saying "3.T03"
                beside a row already headed B04 is the second numbering this file exists to remove
       code     {(board index, T code): B code}, which is how a producer relabels its own types
    """
    cat = {}
    for idx, types in per_board:
        for t in types:
            e = cat.setdefault(gkey(t), dict(kind=t['kind'], label=t['label'], dims=t['dims'],
                                             nsides=t['nsides'], area=t['area'], qty=0, use=[]))
            e['qty'] += t['qty']
            e['use'].append(dict(board=idx, code=t['code'], qty=t['qty']))
    entries = sorted(cat.values(), key=lambda e: (KORD[e['kind']], -e['qty'], e['label']))
    for i, e in enumerate(entries):
        e['code'] = 'B%02d' % (i+1)
    code = {(u['board'], u['code']): e['code'] for e in entries for u in e['use']}
    for e in entries:
        for u in e['use']:
            u['code'] = e['code']
    return entries, code


def of(per_board):
    """just the map, for a producer that only needs to relabel"""
    return catalogue(per_board)[1]
