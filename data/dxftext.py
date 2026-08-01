# -*- coding: utf-8 -*-
"""How wide a string really is in the font the DXFs are written in.

Every sheet used the same guess: 1.05 of the cap height for a Han glyph, 0.62 for anything else.
It is close for a mixed sentence and badly wrong at the ends of the range - measured against
Microsoft YaHei's own metrics it is 26 % narrow on a run of Chinese and 31 % narrow on Latin
capitals, which is exactly where the long headings live.  So the panel titles on dxf/08 ran into
the next column, and check_dxf.py, using the same guess, said they did not.

ezdxf carries the font, so the width can be measured rather than estimated.  Widths are cached
because dxf/08 alone measures a few thousand strings.
"""
import io

from ezdxf.fonts import fonts

FONT = 'msyh.ttc'                  # the style every one of these drawings is written in
_F = {}
_W = {}


def _font(name):
    if name not in _F:
        _F[name] = fonts.make_font(name, 1.0)
    return _F[name]


def width(s, h, font=FONT):
    """the advance width of s set at cap height h"""
    k = (s, font)
    if k not in _W:
        _W[k] = _font(font).text_width(s)
    return _W[k]*h


def wrap(s, h, limit, indent='', font=FONT):
    """-> list of lines, none wider than limit, measured in the real font

    Breaks between words and between Han characters, since Chinese carries no spaces.  A line is
    never opened with closing punctuation.
    """
    toks, cur = [], ''
    for ch in s:
        if ord(ch) > 0x2E80:
            if cur:
                toks.append(cur); cur = ''
            toks.append(ch)
        elif ch == ' ':
            if cur:
                toks.append(cur); cur = ''
            toks.append(' ')
        else:
            cur += ch
    if cur:
        toks.append(cur)
    out, line, i = [], '', 0
    while i < len(toks):
        t = toks[i]
        if line and width(line+t, h, font) > limit:
            if t and t[0] in '。，、；：？！）》」』】':
                line += t; i += 1
            out.append(line.rstrip())
            line = indent
            while i < len(toks) and toks[i] == ' ':
                i += 1
            continue
        line += t; i += 1
    if line.strip() or not out:
        out.append(line.rstrip())
    return out


# ---------------------------------------------------------------------------------------------
# Saving a drawing so that it comes out the same twice.
#
# ezdxf stamps the wall-clock time into $TDCREATE and $TDUPDATE and mints a fresh $VERSIONGUID and
# $FINGERPRINTGUID on every write, so two runs over identical data produced two different files.
# That turned "site/downloads is byte for byte the master" into a check on whether pack_downloads
# happened to run last rather than on whether the two are the same drawing - and it was quietly
# false at the time this was written.  $TDUPDATE and the GUIDs are set during the write itself,
# so they are normalised in the file afterwards rather than on the document.
DXF_STAMP = '2461254.0'          # the day this branch was cut, in the Julian form DXF uses
DXF_GUID = '{00000000-0000-0000-0000-000000000000}'


def save(doc, path):
    doc.saveas(path)
    txt = io.open(path, encoding='utf-8', errors='surrogateescape').read().split('\n')
    for i, ln in enumerate(txt):
        v = ln.strip()
        if v in ('$TDCREATE', '$TDUPDATE', '$TDINDWG', '$TDUSRTIMER') and i+2 < len(txt):
            txt[i+2] = DXF_STAMP if v in ('$TDCREATE', '$TDUPDATE') else '0.0'
        elif v in ('$VERSIONGUID', '$FINGERPRINTGUID') and i+2 < len(txt):
            txt[i+2] = DXF_GUID
    io.open(path, 'w', encoding='utf-8', errors='surrogateescape',
            newline='').write('\n'.join(txt))
    return path
