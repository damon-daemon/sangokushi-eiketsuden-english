"""English encoder and wrapper for the chapter text (evm.py).

English (tl/): plain ASCII; '\\n' forces a line break, a blank line ('\\n\\n') starts a new page.
build wraps every line at the box width (pixels). The game pages by itself (PAGE lines per box
page). Typographic quotes, dashes and ellipses are folded to ASCII; '%' and '\\' (other than \\n)
are refused.
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
from vwf import width as pixels

WIDTH = {'talk': 232, 'plain': 232, 'npc': 232}
PAGE = {'talk': 3, 'plain': 4, 'npc': 3}
FOLD = {'‘': "'", '’': "'", '“': '"', '”': '"', '—': '--', '–': '-', '…': '...', ' ': ' '}


def fold(en):
    return ''.join(FOLD.get(c, c) for c in en)


def check(en):
    """-> list of problems with an English segment"""
    errs = []
    s = fold(en)
    bad = sorted(set(c for c in s if not ' ' <= c <= '~'))
    if bad:
        errs.append('non-ASCII characters %r' % ''.join(bad))
    if re.search(r'%|\\(?!n)', s):
        errs.append('reserved character (% or \\ other than \\n)')
    return errs


def _lines(words, width):
    out, line = [], []
    for w in words:
        if line and pixels(' '.join(line + [w])) > width:
            out.append(line)
            line = [w]
        else:
            line.append(w)
    out.append(line)
    return out


def wrap(en, width, page):
    """one tl record -> lines joined by real newlines; a blank line pads to the next page"""
    out = []
    for p in fold(en).split('\\n'):
        words = p.split()
        if not words:
            out += [''] * (-len(out) % page)
            continue
        out += [' '.join(ln) for ln in _lines(words, width)]
    while out and not out[-1]:
        out.pop()
    return '\n'.join(out)


def encode(en, kind):
    return wrap(en, WIDTH[kind], PAGE[kind]).encode('ascii')
