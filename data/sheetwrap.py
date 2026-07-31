# -*- coding: utf-8 -*-
"""Break a bilingual line so it fits the width it is given, measured in the real font.

The three sheets are laid out in axes fractions, and a note or a title was simply written at a
point and left to run.  Where it ran past the column it belongs to, nothing clipped it:
bbox_inches='tight' grows the canvas instead, so the sheet quietly gets wider and the rules end up
stopping short of the text.  check_sheets.py finds that; this fixes it.

Two things make a plain textwrap useless here.  Chinese has no spaces, so a wrap on whitespace
either does not break at all or breaks a 60-character run in one place.  And the two scripts mix
the languages inside one sentence, so a character count is not a width either: a Han glyph is
about 1.7 times the advance of a Latin one at the same point size.

So the text is split into tokens - one Han character, or one run of Latin between spaces - each
token is measured once with the figure's own renderer, and the line is filled greedily.  A line is
never started with closing punctuation.
"""
NOBREAK_BEFORE = '。，、；：？！）》」』】%℃mm'      # never opens a line
_W = {}


def cellpx(ax, pad=6.0, safety=0.97):
    """pixels from where text starts in this axes to the right edge of its GRID CELL

    Not the axes width.  Two things pull those apart.  An aspect='equal' axes shrinks its box to
    fit the data and CENTRES it in the cell, so a 50 mm part in a wide column has a narrow box
    sitting in from the left: a title wrapped to the box comes out four lines deep with the column
    empty beside it, and a title wrapped to the cell WIDTH still runs out of the cell, because it
    starts at the box's left edge rather than the cell's.  What is available is the distance from
    where the text starts to where the column ends.

    safety covers the difference between summing token advances and what the renderer finally
    lays out; it is a couple of per cent on a mixed line.
    """
    fig = ax.figure
    ss = ax.get_subplotspec()
    if ss is None:
        return ax.get_window_extent().width*safety-pad
    ax.apply_aspect()                                    # the box is only settled at draw time
    cell = ss.get_position(fig).transformed(fig.transFigure)
    return (cell.x1-ax.get_window_extent().x0)*safety-pad


def _tokens(s):
    out, cur = [], ''
    for ch in s:
        if ord(ch) > 0x2E80:                  # Han, kana, and full-width punctuation
            if cur:
                out.append(cur); cur = ''
            out.append(ch)
        elif ch == ' ':
            if cur:
                out.append(cur); cur = ''
            out.append(' ')
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def _width(fig, tok, fontsize, family):
    k = (tok, fontsize, family, id(fig))
    if k not in _W:
        t = fig.text(0, 0, tok, fontsize=fontsize, family=family)
        try:
            _W[k] = t.get_window_extent(renderer=fig.canvas.get_renderer()).width
        finally:
            t.remove()
    return _W[k]


def wrap(fig, s, fontsize, px, family=None):
    """-> the same string with newlines inserted so no line is wider than px pixels

    Newlines already in s are kept: they are the author's own breaks and each part is wrapped on
    its own.
    """
    fig.canvas.draw()                          # a renderer has to exist to measure anything
    out = []
    for para in s.split('\n'):
        toks = _tokens(para)
        line, w, i = '', 0.0, 0
        while i < len(toks):
            t = toks[i]
            tw = _width(fig, t, fontsize, family) if t != ' ' else \
                _width(fig, 'i i', fontsize, family)-2*_width(fig, 'i', fontsize, family)
            if line and w+tw > px:
                # do not leave closing punctuation stranded at the head of the next line
                if t and t[0] in NOBREAK_BEFORE:
                    line += t; i += 1
                out.append(line.rstrip())
                line, w = '', 0.0
                if i < len(toks) and toks[i] == ' ':
                    i += 1
                continue
            line += t; w += tw; i += 1
        if line.strip() or not out:
            out.append(line.rstrip())
    return '\n'.join(out)
