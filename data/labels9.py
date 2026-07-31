"""Chinese and English wording for the board drawings, kept in one place so the sheet and the DXF
cannot say different things.  Each label carries both languages on one line, Chinese first, so a
row stays one row instead of doubling the height of every schedule."""

BOND = {
    1: ('顺砖错缝，底部一道立砖', 'Stretcher bond, one soldier course at the base'),
    2: ('顺砖错缝', 'Stretcher bond'),
    3: ('45 度人字纹，顶部一道收边', 'Herringbone at 45 deg, one border course at the top'),
    4: ('顺砖错缝，上下各两道收边', 'Stretcher bond, two border courses top and bottom'),
    5: ('正交人字纹，与板边平齐', 'Herringbone square to the board edge'),
    6: ('编织纹，每组三片', 'Basketweave, three slips per block'),
    # the proposal's own word is kept in English; running bond IS stretcher bond, and both this
    # board and board 2 come out of the same half-lap generator.  The Chinese said 通缝, which
    # means the joints line up - that is board 9's pattern, not this one.
    7: ('顺砖错缝', 'Running bond'),
    8: ('45 度编织纹，外圈双层边框', 'Basketweave at 45 deg inside a two-slip border'),
    9: ('横向叠砌', 'Horizontal stack bond'),
}
USE = {'Wall': '墙面', 'Floor': '地面'}
FIN = {'Sleek': '细面', 'Raw': '粗面'}

SHEET_TITLE = ('武汉摄影展板　九种排布、砖型表与提案原图对照',
               'Wuhan photography boards - nine layouts, brick schedule and proposal reference')
MOCKUP = '提案原图  proposal mock-up'
HDR = ('编号', '数量', '说明  DESCRIPTION')


def bond(idx):
    zh, en = BOND[idx]
    return zh, en


def describe(ty):
    """one schedule line for a brick type"""
    if ty['kind'] == 'WHOLE':
        return '整砖片 whole slip  %s' % ty['label']
    if ty['kind'] == 'STD':
        return '标准件 standard  %s' % ty['label']
    return '切割件 cut, %d 边 sides  %s mm  (外接框 bbox %.0f x %.0f, %.0f mm2)' % (
        ty['nsides'], ty['label'], ty['dims'][0], ty['dims'][1], ty['area'])


def header(P, ntypes, ncutt, nw, ns, nc, npc):
    """the summary block above each schedule"""
    return [
        '%s %s / %s %s' % (USE[P['use']], P['use'], FIN[P['finish']], P['finish']),
        '板面 board %g x %g mm     灰缝 joint %g mm     砖片 slip 215 x 65 x 20'
        % (P['Wd'], P['Ht'], P['J']),
        '共 %d 片 pieces:  整砖 %d whole,  标准件 %d standard,  切割件 %d cut'
        % (npc, nw, ns, nc),
        '砖型 %d 种 brick types,  其中 %d 种需切割 need cutting' % (ntypes, ncutt),
    ]


def counts(types):
    nw = sum(t['qty'] for t in types if t['kind'] == 'WHOLE')
    ns = sum(t['qty'] for t in types if t['kind'] == 'STD')
    nc = sum(t['qty'] for t in types if t['kind'] == 'CUT')
    return nw, ns, nc, sum(1 for t in types if t['kind'] == 'CUT')
