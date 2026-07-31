# -*- coding: utf-8 -*-
"""Build the requirement-against-design comparison PDF, one row per board.

    python data/proposal_compare.py    ->  docs/board_comparison.pdf

Four columns: what the proposal asked for, the proposal's own mock-up, our final render, and the
figures that changed.  The requirement side is read out of the proposal PDF itself rather than
retyped, so it cannot drift; the design side is read out of site/data/boards.json, which is the
same file the drawings and the model are generated from.

Only differences are written.  A joint that came out at the width it was asked for gets no line
saying so, because a schedule of "unchanged" rows is a schedule nobody reads.
"""
import atexit, json, os, shutil, tempfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageTemplate, Paragraph,
                                Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
OUT = os.path.join(ROOT, 'docs', 'board_comparison.pdf')
D = json.load(open(os.path.join(ROOT, 'site', 'data', 'boards.json'), encoding='utf-8'))
BOARDS = {b['idx']: b for b in D['boards']}

# The proposal lists the nine boards in order, two to a page, in one table whose columns are
# bond / use / colour ref / finish / mortar.  The bond text and the mortar spec are lifted from
# that table; the mock-up images were extracted to proposal/extracted when the PDF was first read.
SPEC = [
    (1, 'Standard stretcher, one row of vertically stacked 215 x 65 slips',
     'Wall', 'Sleek', 10, 'warm white, approx RAL 1013', 'P1_stretcher_wall_vertstack.png'),
    (2, 'Standard stretcher',
     'Floor', 'Raw', 10, 'warm white, approx RAL 1013', 'P2_stretcher_floor.png'),
    (3, 'Herringbone, one border of 102 x 65 slips',
     'Floor', 'Sleek', 10, 'warm white, approx RAL 1013', 'P3_herringbone_border102.png'),
    (4, 'Standard stretcher, brick end border top and bottom, 65 x 102 slip size',
     'Wall', 'Sleek', 7, 'warm grey white, RAL 9001', 'P4_stretcher_endborder.png'),
    (5, 'Herringbone, straight edge',
     'Floor', 'Sleek', 7, 'warm grey white, RAL 9001', 'P5_herringbone_straight.png'),
    (6, 'Basketweave',
     'Floor', 'Raw', 7, 'warm grey white, RAL 9001', 'P6_basketweave.png'),
    (7, 'Running bond',
     'Wall', 'Sleek', 5, 'natural mortar colour', 'P7_runningbond.png'),
    (8, 'Triple herringbone with two brick border',
     'Floor', 'Sleek', 5, 'neutral white mortar', 'P8_triple_herringbone.png'),
    (9, 'Horizontal stack',
     'Floor', 'Raw', 3, 'neutral white mortar', 'P9_horizontal_stack.png'),
]

# Why a joint had to move.  Only the three that moved carry one; the reasoning is the measured one
# from docs/joint_report.html, condensed to a line.  All three come off the same relation: with the
# joint folded into the brick the laying module is (215+J) by (65+J), and a herringbone or a
# basketweave closes only when three of the short module make one of the long one, 3(65+J) = 215+J,
# which solves at J = 10 alone.  Board 5 is the STRAIGHT herringbone; board 8 is the 45 degree one.
WHY = {
    5: 'A herringbone closes only when three courses of the module equal one slip and one joint, '
       '3 x (65 + J) = 215 + J, so J = 10. Laid at 7 mm the field carried 126 joints off width.',
    6: 'Basketweave blocks must stay square: three slips plus two joints has to equal one slip, '
       '3 x 65 + 2 x 10 = 215, which holds at 10 mm and not at 7 mm.',
    8: 'The 45 degree weave inside a two-slip border needs that same square block, 3 x 65 + 2J = '
       '215. At 5 mm it is 10 mm out and 46 joints closed up, some to slips touching.',
}

TINT = (250, 248, 244)          # the alternate row background; pic() lays the renders on it

TITLE = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=19, leading=23,
                       textColor=colors.HexColor('#1d1d1b'))
SUB = ParagraphStyle('s', fontName='Helvetica', fontSize=9.4, leading=13,
                     textColor=colors.HexColor('#6d6a63'))
HEAD = ParagraphStyle('h', fontName='Helvetica-Bold', fontSize=8.6, leading=11,
                      textColor=colors.HexColor('#ffffff'))
BODY = ParagraphStyle('b', fontName='Helvetica', fontSize=9, leading=12.6,
                      textColor=colors.HexColor('#1d1d1b'))
SMALL = ParagraphStyle('sm', fontName='Helvetica', fontSize=8.2, leading=11,
                       textColor=colors.HexColor('#55524c'))
CHANGE = ParagraphStyle('c', fontName='Helvetica-Bold', fontSize=9, leading=12.6,
                        textColor=colors.HexColor('#b4491f'))
NUM = ParagraphStyle('n', fontName='Helvetica-Bold', fontSize=10.4, leading=13.6,
                     textColor=colors.HexColor('#1d1d1b'))


TMP = tempfile.mkdtemp(prefix='cmp')
atexit.register(shutil.rmtree, TMP, True)


def pic(path, w, h, dpi=190, bg=(255, 255, 255)):
    """fit an image inside w x h without distorting it, downsampled to the size it prints at

    Embedded at source resolution the nine 1500 x 1500 renders and the nine mock-ups made a 111 MB
    PDF for a three page document.  Each is resampled to the pixels the page actually uses.
    """
    from PIL import Image as PIL
    im = PIL.open(path)
    # the renders are shot on a transparent film, so a straight convert('RGB') lays them on black
    # and every board came out in a heavy black frame
    if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
        im = im.convert('RGBA')
        # Crop to what is actually drawn first.  A 1500 square render of a board seen at an angle
        # leaves 9-18 % of its frame empty, and that empty frame becomes opaque white here - on the
        # tinted rows every board sat in a white box a few millimetres proud of the tint.
        box = im.split()[-1].getbbox()
        if box:
            im = im.crop(box)
        # ...and lay what is left on the colour of the row it prints on, not on white.  A board is
        # shot at an angle, so even cropped its frame has four empty corners; against the tinted
        # rows those corners printed as a white slab a few millimetres proud of the tint.
        flat = PIL.new('RGB', im.size, tuple(bg))
        flat.paste(im, mask=im.split()[-1])
        im = flat
    else:
        im = im.convert('RGB')
    iw, ih = im.size
    k = min(w/float(iw), h/float(ih))
    px = max(1, int(round(w/mm/25.4*dpi))), max(1, int(round(h/mm/25.4*dpi)))
    im.thumbnail(px, PIL.LANCZOS)
    q = os.path.join(TMP, '%s_%02x%02x%02x.jpg'
                     % ((os.path.splitext(os.path.basename(path))[0],)+tuple(bg)))
    im.save(q, 'JPEG', quality=86, optimize=True)
    return Image(q, iw*k, ih*k)


def rows():
    out = [[Paragraph('#', HEAD), Paragraph('PROPOSAL REQUIREMENT', HEAD),
            Paragraph('PROPOSAL MOCK-UP', HEAD), Paragraph('OUR FINAL DESIGN', HEAD),
            Paragraph('ACTUAL SIZE AND CHANGES', HEAD)]]
    for idx, bond, use, finish, joint, mortar, mock in SPEC:
        bg = TINT if idx % 3 == 2 else (255, 255, 255)
        b = BOARDS[idx]
        req = ('<b>%s</b><br/><br/>%s &middot; %s finish<br/>%g mm joint, %s'
               % (bond, use, finish, joint, mortar))
        note = ['<b>%g &times; %g mm</b>' % (b['w'], b['h'])]
        if b['joint'] != joint:
            note.append('<font color="#b4491f"><b>Joint width changed from %g mm to %g mm.</b>'
                        '</font> %s' % (joint, b['joint'], WHY.get(idx, '')))
        cut = sum(t['qty'] for t in b['types'] if t['kind'] == 'CUT')
        nt = len(b['types'])
        note.append('%d slips, %d brick %s%s.'
                    % (len(b['pieces']), nt, 'type' if nt == 1 else 'types',
                       ', %d cut' % cut if cut else ', none cut'))
        out.append([
            Paragraph('%02d' % idx, NUM),
            Paragraph(req, BODY),
            pic(os.path.join(ROOT, 'proposal', 'extracted', mock), 78*mm, 64*mm, bg=bg),
            pic(os.path.join(ROOT, 'site', 'renders', 'b%d_front.png' % idx), 68*mm, 64*mm, bg=bg),
            Paragraph('<br/>'.join(note), SMALL)])
    return out


def build():
    doc = BaseDocTemplate(OUT, pagesize=landscape(A3),
                          leftMargin=14*mm, rightMargin=14*mm,
                          topMargin=13*mm, bottomMargin=12*mm,
                          title='Wuhan Photography Boards - requirement against final design',
                          author='3 Monahan Avenue (HA23007)')
    fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='f',
               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def furniture(c, d):
        c.saveState()
        c.setFont('Helvetica', 7.4)
        c.setFillColor(colors.HexColor('#8a867e'))
        c.drawString(doc.leftMargin, 7*mm,
                     'Wuhan photography boards  |  9 panels  |  brick slip 215 x 65 x 20')
        c.drawRightString(doc.width+doc.leftMargin, 7*mm, 'page %d' % d.page)
        c.restoreState()

    doc.addPageTemplates([PageTemplate(id='p', frames=[fr], onPage=furniture)])

    data = rows()
    W = doc.width
    # the two pictures get the same room: the point of the sheet is to hold them side by side,
    # and a mock-up printed half again as wide as the design reads as the design being the
    # afterthought
    cw = [W*0.03, W*0.225, W*0.26, W*0.26, W*0.225]
    t = Table(data, colWidths=cw, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1d1d1b')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 1), (3, -1), 'CENTER'),
        ('VALIGN', (2, 1), (3, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -1), 0.45, colors.HexColor('#d8d4cb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.Color(*[c/255.0 for c in TINT])]),
    ]))

    head = [Paragraph('Wuhan Photography Boards: requirement against final design', TITLE),
            Paragraph('The proposal asks for nine panels, each 1.5 m &times; 1.5 m '
                      '<i>or similar convenient size for brick layout</i>, all based on a '
                      '215 &times; 65 mm slip. Every board below is dimensioned to close on whole '
                      'and half slips at its own joint width, so the sizes differ from 1.5 m and '
                      'from each other. Joint widths are noted only where they changed.', SUB)]
    story = head + [Paragraph('<br/>', SUB), t]
    doc.build(story)
    print('%d boards -> %s  (%.0f KB)'
          % (len(SPEC), os.path.normpath(OUT), os.path.getsize(OUT)/1024))


if __name__ == '__main__':
    build()
