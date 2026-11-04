"""Variable-width English text: our proportional font (pixfont.py) in the EXE's ASCII font slot and
a pixel cursor in the printer.

Every glyph is its own sprite at any x (survey.md). The hook on the single-byte draw of both
putchars keeps the pen in pixels: it draws at the pen when the text continues (col and row as it
left them), else at col * 8 + indent, then moves the pen by the glyph's width and sets col to the
pen rounded up to 8 px. So col stays true for the putchars' own wrap check. An explicit position
(0x80023038) ends the run, so columns of a table line up.

Line function 0x8001b280 (boxes): cut by 1 column per single byte -> up to LINE_MAX bytes (English
is wrapped by pixels at build time), centring by pixel width.

  font(exe, base) writes the font; width(text) -> pixels; code(at) -> (bytes, patch function)
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(__file__))
import asm, pixfont

ASCII_FONT = 0x8009c054           # 96 glyphs x 16 B, 8x16 1bpp
FONT_TOP = 1                      # blank rows above the 12-row pixfont cell
FONT_LEFT = 1                     # blank columns left of it (see font)
# Outline pass 0x80039854 (only caller: the 8-px glyph path 0x8003a0a8) runs its vertical pass on 8-px rows but
# its horizontal pass on 16-px rows (8 rows x 15 pairs), so column 7 of a row and column 0 of the next were
# treated as neighbours: stray outline dots at the right edge of glyphs (issue #1). Now 16 rows x 7 pairs.
OUTLINE_FIX = [(0x80039920, 0x2c42000f, 0x2c420007), (0x80039934, 0x2c420008, 0x2c420010)]
DRAW1, DRAW2 = 0x8003a10c, 0x8003a2e0
SETPOS = 0x80023038
LINE_MAX = 0x50                   # buffer 88 B
GLYPH_LIMIT = 192                 # sprite pool 0x80125ce4, DR_MOVE pool 0x800ceeb0

_G = pixfont.glyphs()
WIDTHS = bytes(_G[chr(c)][1] if chr(c) in _G else 8 for c in range(0x20, 0x80))


def font():
    """Glyphs one column in from the left (FONT_LEFT): the outline pass gives each ink pixel a dark border
    pixel on every side, and column 0 has none to its left."""
    out = bytearray()
    for c in range(0x20, 0x80):
        rows = _G[chr(c)][0] if chr(c) in _G else bytes(12)
        assert not any(r & ((1 << FONT_LEFT) - 1) for r in rows), 'glyph %r too wide for the cell' % chr(c)
        rows = bytes(r >> FONT_LEFT for r in rows)
        out += bytes(FONT_TOP) + rows + bytes(16 - FONT_TOP - len(rows))
    return bytes(out)


def width(s):
    """Pixel width of an ASCII string (padding spaces before a digit are drawn at digit width: see DIGIT_PAD)."""
    px, spaces, lead = 0, 0, True
    for c in s:
        px += WIDTHS[ord(c) - 0x20]
        if c == ' ':
            spaces += 1
        else:
            if c.isdigit() and spaces:
                px += (spaces if lead else spaces - 1) * DIGIT_PAD
            spaces, lead = 0, False
    return px


LASTCOL, LASTROW, PEN, INDENT, NEWCOL, SPACES, LEAD = 0, 2, 4, 6, 8, 10, 12
# "%3d" fields: a space is 3 px, a digit 6, so padded numbers would not line up in tables. The hook counts
# the spaces drawn since the last other glyph and, when a digit follows, widens the padding ones to digit
# width: every space of the run but the first, or all of them when the run starts the line (" 4 325").
# A single word space before a number ("You got 200 gold!") stays narrow.
DIGIT_PAD = WIDTHS[ord('0') - 0x20] - WIDTHS[0]
# big text 0x80016864 (map / officer cards): 16-px glyphs on one sprite. The English is drawn at run time
# into BIG_TILES glyphs of the font space, then printed by the codes of those glyphs.
BIG_INDEX, BIG_TILES = 845, 12
FONT_16, FONT_CODES, GLYPH2 = 0x8009c654, 0x800a9594, 0x80039da8
BIG_FONT = FONT_16 + BIG_INDEX * 32
DATA_SIZE = 14


def _code(st, widths, name_px, name_offs):
    S = lambda off: asm.lo(st + off)
    H = asm.hi(st)
    assert asm.hi(st + DATA_SIZE) == H
    return [
        'draw1:',
        ('lui', 't9', asm.hi(DRAW1)),
        ('b', 'draw'),
        ('addiu', 't9', 't9', asm.lo(DRAW1)),
        'draw2:',
        ('lui', 't9', asm.hi(DRAW2)),
        ('addiu', 't9', 't9', asm.lo(DRAW2)),
        'draw:',                          # a0 char, a1 = col * 8, a2 = row * 8, a3 = glyph index
        ('lui', 't0', H),
        ('lhu', 't1', S(LASTCOL), 't0'),
        ('lhu', 't2', S(LASTROW), 't0'),
        ('srl', 't3', 'a1', 3),
        ('bne', 't1', 't3', 'fresh'),
        ('nop',),
        ('bne', 't2', 'a2', 'fresh'),
        ('nop',),
        ('lhu', 'a1', S(PEN), 't0'),
        ('b', 'pen'),
        ('nop',),
        'fresh:',
        ('lhu', 't1', S(INDENT), 't0'),
        ('sh', 'zero', S(INDENT), 't0'),
        ('addu', 'a1', 'a1', 't1'),
        ('sh', 'zero', S(SPACES), 't0'),
        ('addiu', 't5', 'zero', 1),
        ('sh', 't5', S(LEAD), 't0'),      # the run starts the line: all its spaces before a digit are padding
        'pen:',
        ('andi', 't1', 'a0', 0xff),
        ('lhu', 't4', S(SPACES), 't0'),   # spaces drawn since the last other glyph in this run
        ('addiu', 't5', 't1', -0x20),
        ('beqz', 't5', 'space'),
        ('addiu', 't5', 't1', -0x30),
        ('sltiu', 't5', 't5', 10),
        ('beqz', 't5', 'nodigit'),
        ('sh', 'zero', S(SPACES), 't0'),
        ('lhu', 't5', S(LEAD), 't0'),
        ('beqz', 't4', 'nodigit'),        # no space before the digit
        ('nop',),
        ('bnez', 't5', 'pad'),            # leading spaces: all of them
        ('nop',),
        ('addiu', 't4', 't4', -1),        # a word space before a number: only the extra spaces
        'pad:',
        ('sll', 't6', 't4', 1),           # pen += spaces * DIGIT_PAD (3)
        ('addu', 't6', 't6', 't4'),
        ('addu', 'a1', 'a1', 't6'),
        'nodigit:',
        ('b', 'glyph'),
        ('sh', 'zero', S(LEAD), 't0'),
        'space:',
        ('addiu', 't4', 't4', 1),
        ('sh', 't4', S(SPACES), 't0'),
        'glyph:',
        ('lui', 't2', asm.hi(widths - 0x20)),
        ('addu', 't2', 't2', 't1'),
        ('lbu', 't1', asm.lo(widths - 0x20), 't2'),
        ('nop',),
        ('addu', 't1', 't1', 'a1'),
        ('sh', 't1', S(PEN), 't0'),
        ('addiu', 't1', 't1', 7),
        ('srl', 't1', 't1', 3),
        ('sh', 't1', S(NEWCOL), 't0'),
        ('sh', 't1', S(LASTCOL), 't0'),
        ('sh', 'a2', S(LASTROW), 't0'),
        ('sltiu', 't1', 'a3', GLYPH_LIMIT),   # past the pools: no sprite, no memory damage
        ('beqz', 't1', 'skip'),
        ('nop',),
        ('jr', 't9'),
        ('nop',),
        'skip:',
        ('jr', 'ra'),
        ('nop',),

        'setpos:',                        # 0x80023038 starts here: a new run
        ('addiu', 't1', 'zero', -1),
        ('sh', 't1', S(LASTROW), 't0'),
        ('lui', 'v0', 0x6666),
        ('j', SETPOS + 8),
        ('ori', 'v0', 'v0', 0x6667),

        'pixw:',                          # a0 = text -> v0 = pixels
        ('addu', 'v0', 'zero', 'zero'),
        'next:',
        ('lbu', 't0', 0, 'a0'),
        ('addiu', 'a0', 'a0', 1),
        ('beqz', 't0', 'ret'),
        ('sltiu', 't1', 't0', 0x80),
        ('beqz', 't1', 'pair'),
        ('sltiu', 't1', 't0', 0x20),
        ('bnez', 't1', 'ctl'),
        ('lui', 't2', asm.hi(widths - 0x20)),
        ('addu', 't2', 't2', 't0'),
        ('lbu', 't1', asm.lo(widths - 0x20), 't2'),
        ('b', 'next'),
        ('addu', 'v0', 'v0', 't1'),
        'pair:',
        ('sltiu', 't1', 't0', 0xf0),
        ('bnez', 't1', 'kanji'),
        ('lbu', 't1', 0, 'a0'),           # a name token (names.py)
        ('andi', 't0', 't0', 0xf),
        ('sll', 't0', 't0', 7),
        ('andi', 't1', 't1', 0x7f),
        ('addu', 't0', 't0', 't1'),
        ('lui', 't2', asm.hi(name_px)),
        ('addu', 't2', 't2', 't0'),
        ('lbu', 't1', asm.lo(name_px), 't2'),
        ('addiu', 'a0', 'a0', 1),
        ('b', 'next'),
        ('addu', 'v0', 'v0', 't1'),
        'kanji:',
        ('addiu', 'a0', 'a0', 1),
        ('b', 'next'),
        ('addiu', 'v0', 'v0', 16),
        'ctl:',
        ('addiu', 't1', 'zero', 0x1b),
        ('bne', 't0', 't1', 'next'),      # ESC + 2 bytes: no width
        ('nop',),
        ('b', 'next'),
        ('addiu', 'a0', 'a0', 2),
        'ret:',
        ('jr', 'ra'),
        ('nop',),

        'listw:',                         # a0 = text -> v0 = columns of 8 px, rounded up
        ('addu', 't7', 'ra', 'zero'),
        ('jal', 'pixw'),
        ('nop',),
        ('addiu', 'v0', 'v0', 7),
        ('jr', 't7'),
        ('srl', 'v0', 'v0', 3),

        'boxlen:',                        # a0 = text -> v0 = the larger of its bytes and its columns of 8 px:
        ('addu', 't7', 'ra', 'zero'),     # boxes padded for the button icons keep their size, a token gets room
        ('addu', 't6', 'a0', 'zero'),
        ('jal', 'pixw'),
        ('addu', 't8', 'a0', 'zero'),
        ('addiu', 'v0', 'v0', 15),       # one spare column: the wrap check fires when the pen reaches the last column ("Wei X/u")
        ('srl', 'v0', 'v0', 3),
        'blen:',
        ('lbu', 't0', 0, 't8'),
        ('addiu', 't8', 't8', 1),
        ('bnez', 't0', 'blen'),
        ('nop',),
        ('subu', 't8', 't8', 't6'),
        ('addiu', 't8', 't8', -1),
        ('sltu', 't0', 'v0', 't8'),
        ('beqz', 't0', 'bret'),
        ('nop',),
        ('addu', 'v0', 't8', 'zero'),
        'bret:',
        ('jr', 't7'),
        ('nop',),

        'biglen:',                        # a0 = text -> v0 = bytes as the Japanese would have (2 per tile)
        ('addu', 't7', 'ra', 'zero'),
        ('jal', 'pixw'),
        ('nop',),
        ('addiu', 'v0', 'v0', 15),
        ('srl', 'v0', 'v0', 4),
        ('jr', 't7'),
        ('sll', 'v0', 'v0', 1),

        'bigtext:',                       # a0 = text -> v0 = tiles; draws into BIG_FONT
        ('lui', 'a1', asm.hi(BIG_FONT)),
        ('addiu', 'a1', 'a1', asm.lo(BIG_FONT)),
        ('addiu', 'a2', 'zero', BIG_TILES * 32),
        'bclr:',
        ('addiu', 'a2', 'a2', -1),
        ('addu', 't0', 'a1', 'a2'),
        ('bnez', 'a2', 'bclr'),
        ('sb', 'zero', 0, 't0'),
        ('addu', 'v0', 'zero', 'zero'),   # pen
        ('addu', 't9', 'zero', 'zero'),   # where to go on after a token's name
        'bnext:',
        ('lbu', 't0', 0, 'a0'),
        ('addiu', 'a0', 'a0', 1),
        ('bnez', 't0', 'bhave'),
        ('nop',),
        ('beqz', 't9', 'bdone'),
        ('addu', 'a0', 't9', 'zero'),
        ('b', 'bnext'),
        ('addu', 't9', 'zero', 'zero'),
        'bhave:',
        ('sltiu', 't1', 't0', 0x80),
        ('bnez', 't1', 'bascii'),
        ('sltiu', 't1', 't0', 0xf0),
        ('bnez', 't1', 'bkanji'),
        ('lbu', 't1', 0, 'a0'),           # a name token
        ('andi', 't0', 't0', 0xf),
        ('sll', 't0', 't0', 7),
        ('andi', 't1', 't1', 0x7f),
        ('addu', 't0', 't0', 't1'),
        ('sll', 't0', 't0', 1),
        ('lui', 't2', asm.hi(name_offs)),
        ('addu', 't2', 't2', 't0'),
        ('lhu', 't3', asm.lo(name_offs), 't2'),
        ('addiu', 't9', 'a0', 1),
        ('lui', 't4', asm.hi(name_offs)),
        ('addiu', 't4', 't4', asm.lo(name_offs)),
        ('b', 'bnext'),
        ('addu', 'a0', 't3', 't4'),
        'bkanji:',                        # no glyph here: a blank of the same width
        ('addiu', 'a0', 'a0', 1),
        ('b', 'bnext'),
        ('addiu', 'v0', 'v0', 16),
        'bascii:',
        ('sltiu', 't1', 't0', 0x20),
        ('bnez', 't1', 'bnext'),
        ('lui', 't2', asm.hi(widths - 0x20)),
        ('addu', 't2', 't2', 't0'),
        ('lbu', 't5', asm.lo(widths - 0x20), 't2'),
        ('sltiu', 't1', 'v0', BIG_TILES * 16 - 8),
        ('beqz', 't1', 'badv'),
        ('addiu', 't1', 't0', -0x20),
        ('sll', 't1', 't1', 4),
        ('lui', 't2', asm.hi(ASCII_FONT)),
        ('addiu', 't2', 't2', asm.lo(ASCII_FONT)),
        ('addu', 't2', 't2', 't1'),
        ('srl', 't3', 'v0', 3),
        ('andi', 't4', 'v0', 7),
        ('srl', 't6', 't3', 1),           # byte of the first column: tile * 32 + side
        ('sll', 't6', 't6', 5),
        ('andi', 't1', 't3', 1),
        ('addu', 't6', 't6', 't1'),
        ('addiu', 't3', 't3', 1),
        ('srl', 't8', 't3', 1),           # the byte after it, maybe in the next tile
        ('sll', 't8', 't8', 5),
        ('andi', 't1', 't3', 1),
        ('addu', 't8', 't8', 't1'),
        ('lui', 'a1', asm.hi(BIG_FONT)),
        ('addiu', 'a1', 'a1', asm.lo(BIG_FONT)),
        ('addu', 't6', 't6', 'a1'),
        ('addu', 't8', 't8', 'a1'),
        ('addiu', 'a2', 'zero', 16),
        'brow:',
        ('lbu', 't1', 0, 't2'),
        ('addiu', 't2', 't2', 1),
        ('srlv', 'a3', 't1', 't4'),
        ('lbu', 'v1', 0, 't6'),
        ('nop',),
        ('or', 'v1', 'v1', 'a3'),
        ('sb', 'v1', 0, 't6'),
        ('addiu', 'a3', 'zero', 8),
        ('subu', 'a3', 'a3', 't4'),
        ('sllv', 'a3', 't1', 'a3'),
        ('lbu', 'v1', 0, 't8'),
        ('nop',),
        ('or', 'v1', 'v1', 'a3'),
        ('sb', 'v1', 0, 't8'),
        ('addiu', 't6', 't6', 2),
        ('addiu', 'a2', 'a2', -1),
        ('bnez', 'a2', 'brow'),
        ('addiu', 't8', 't8', 2),
        'badv:',
        ('b', 'bnext'),
        ('addu', 'v0', 'v0', 't5'),
        'bdone:',
        ('addiu', 'v0', 'v0', 15),
        ('jr', 'ra'),
        ('srl', 'v0', 'v0', 4),

        'centre:',                        # a0 = line, a1 = box columns -> v0 = columns to add;
        ('addu', 't7', 'ra', 'zero'),     # the rest (0-7 px) goes to the indent of the next glyph
        ('jal', 'pixw'),
        ('sll', 't6', 'a1', 3),
        ('subu', 't6', 't6', 'v0'),
        ('sra', 't6', 't6', 1),
        ('lui', 't0', H),
        ('beqz', 'v0', 'none'),
        ('andi', 't1', 't6', 7),
        ('sh', 't1', S(INDENT), 't0'),
        'none:',
        ('jr', 't7'),
        ('sra', 'v0', 't6', 3)]


def _big_loop(lab):
    """the glyph loop of 0x80016864 (36 words from 0x800168b8): s2 = tiles drawn, s7 = 2 * tiles"""
    at, end = 0x800168b8, 0x80016948
    lines = [
        ('jal', lab['bigtext']),
        ('addu', 'a0', 's0', 'zero'),
        ('sll', 's7', 'v0', 1),
        ('sll', 'v0', 's1', 4),
        ('addiu', 's1', 'v0', 0x100),
        ('addu', 's0', 'zero', 'zero'),
        'loop:',
        ('sll', 'v0', 's2', 1),
        ('sltu', 't0', 'v0', 's7'),
        ('beqz', 't0', end),
        ('lui', 't0', asm.hi(FONT_CODES + BIG_INDEX * 2)),
        ('addu', 't0', 't0', 'v0'),
        ('lhu', 'a0', asm.lo(FONT_CODES + BIG_INDEX * 2), 't0'),
        ('addiu', 'a1', 'zero', 0x140),
        ('addu', 'a2', 'zero', 'zero'),
        ('andi', 'a3', 's2', 0xffff),
        ('addiu', 's2', 's2', 1),
        ('addiu', 'v0', 'zero', 0x80),
        ('sw', 'v0', 0x10, 'sp'),
        ('sw', 's3', 0x14, 'sp'),
        ('andi', 'v0', 's1', 0xffff),
        ('sw', 'v0', 0x18, 'sp'),
        ('jal', GLYPH2),
        ('nop',),
        ('b', 'loop'),
        ('nop',)]
    code = asm.assemble(at, lines)
    n = len(code) // 4
    assert at + len(code) <= end
    words = struct.unpack('<%dI' % n, code)
    return [('raw', w) for w in words] + [('nop',)] * (36 - n)


def _card_loop(lab):
    """the glyph loop of the title card 0x8003a538 (49 words from 0x8003a558): s0 = tiles, s1 = drawn"""
    at, end = 0x8003a558, 0x8003a61c
    lines = [
        ('sll', 'v0', 'a1', 0x10),
        ('sra', 's4', 'v0', 0x10),
        ('ori', 's3', 'zero', 0x80),
        ('ori', 's2', 'zero', 0x300),
        ('jal', lab['bigtext']),
        ('addu', 'a0', 's0', 'zero'),
        ('addu', 's0', 'v0', 'zero'),
        ('addu', 's1', 'zero', 'zero'),
        'loop:',
        ('beq', 's1', 's0', end),
        ('sll', 't0', 's1', 1),
        ('lui', 't1', asm.hi(FONT_CODES + BIG_INDEX * 2)),
        ('addu', 't0', 't0', 't1'),
        ('lhu', 'a0', asm.lo(FONT_CODES + BIG_INDEX * 2), 't0'),
        ('andi', 'a3', 's1', 0xffff),
        ('beqz', 's4', 'flat'),
        ('ori', 'a1', 'zero', 0x140),
        ('sll', 'v0', 'a3', 2),
        ('subu', 'v0', 's2', 'v0'),
        ('sll', 'v1', 'a3', 4),
        ('addiu', 'v1', 'v1', 0x100),
        ('andi', 'v0', 'v0', 0xffff),
        ('andi', 'v1', 'v1', 0xffff),
        ('sw', 'v0', 0x14, 'sp'),
        ('b', 'draw'),
        ('sw', 'v1', 0x18, 'sp'),
        'flat:',
        ('ori', 'v0', 'zero', 0x100),
        ('sw', 's2', 0x14, 'sp'),
        ('sw', 'v0', 0x18, 'sp'),
        'draw:',
        ('sw', 's3', 0x10, 'sp'),
        ('addu', 'a2', 'zero', 'zero'),
        ('jal', GLYPH2),
        ('addiu', 's1', 's1', 1),
        ('b', 'loop'),
        ('nop',)]
    code = asm.assemble(at, lines)
    n = len(code) // 4
    assert at + len(code) <= end
    return [('raw', x) for x in struct.unpack('<%dI' % n, code)] + [('nop',)] * (49 - n)


def _sites(lab):
    """[(address, original words, new instructions)] of the program patches"""
    def col(va):
        # after the draw: lui v1 / lhu v1, col / addiu v0, v0, 1 / addiu v1, v1, 1 -> col = NEWCOL.
        # The next instruction is shared with the 2-byte path: leave it alone. va = the lui v1
        return (va, [0x3c03800d, 0x9463a778, 0x24420001, 0x24630001], [
            ('lui', 'v1', lab['H']),
            ('lhu', 'v1', lab['NEWCOL'], 'v1'),
            ('addiu', 'v0', 'v0', 1),
            ('nop',)])
    return [
        (0x800237a0, [0x0c00e843], [('jal', lab['draw1'])]),
        (0x80023b70, [0x0c00e8b8], [('jal', lab['draw2'])]),
        col(0x800237b0),
        col(0x80023b80),
        (0x80023f6c, [0x0c00e8b8], [('jal', lab['draw2'])]),      # third printer (captions, Turn box)
        col(0x80023f7c),
        (SETPOS, [0x3c026666, 0x34426667], [('j', lab['setpos']), ('lui', 't0', lab['H'])]),
        # list window 0x8001c18c: its inline strlen sized the frame in bytes (a name token is 2)
        (0x8001c218, [0x90620000, 0x00000000, 0x10400009, 0x00008021, 0x26100001, 0x320200ff, 0x00621021, 0x90420000, 0x00000000, 0x1440fffb, 0x26100001, 0x2610ffff], [
            ('jal', lab['listw']),
            ('addu', 'a0', 'v1', 'zero'),
            ('addu', 's0', 'v0', 'zero')] + [('nop',)] * 9),
        # centring / box width by strlen: now columns of 8 px (a token counted 2, English 8 px a byte)
        *[(va, [0x0c0226d8], [('jal', lab['listw'])]) for va in (0x80025b08, 0x80028758, 0x80035254, 0x80036838, 0x80036bb8, 0x80054c20, 0x80059718, 0x800597ec, 0x80059b5c, 0x80068798, 0x80069e9c)],
        (0x800168b8, [0x0c0226d8, 0x02002021, 0x92040000, 0x00000000, 0x1080001f, 0x0040b821, 0x00111100, 0x24510100, 0x2482ff80, 0x304200ff, 0x2c420020, 0x14400006, 0x34050140, 0x24820020, 0x304200ff, 0x2c42001d, 0x1040000e, 0x00000000, 0x26100001, 0x00003021, 0x3247ffff, 0x26520001, 0x92030000, 0x34020080, 0xafa20010, 0x3222ffff, 0x00042200, 0xafb30014, 0xafa20018, 0x0c00e76a, 0x00642025, 0x26100001, 0x92040000, 0x00000000, 0x1480ffe6, 0x2482ff80], _big_loop(lab)),
        (0x8003a558, [0x92040000, 0x00000000, 0x1080002e, 0x00008821, 0x00051400, 0x0002a403, 0x34130080, 0x34120300, 0x2482ff80, 0x304200ff, 0x2c420020, 0x14400005, 0x24820020, 0x304200ff, 0x2c42001d, 0x1040001c, 0x00000000, 0x26100001, 0x92030000, 0x00041200, 0x1280000e, 0x00622025, 0x3227ffff, 0x00071080, 0x02421023, 0x00071900, 0x24630100, 0x34050140, 0x00003021, 0x3042ffff, 0x3063ffff, 0xafb30010, 0xafa20014, 0x0800e980, 0xafa30018, 0x34050140, 0x00003021, 0x3227ffff, 0x34020100, 0xafb30010, 0xafb20014, 0xafa20018, 0x0c00e76a, 0x26310001, 0x26100001, 0x92040000, 0x00000000, 0x1480ffd9, 0x2482ff80], _card_loop(lab)),
        *[(va, [0x0c0226d8], [('jal', lab['boxlen'])]) for va in (0x8001c868, 0x8004d0b4)],      # message box, enemy-phase caption
        (0x800307a8, [0x0c0226d8], [('jal', lab['biglen'])]),
        (0x800685fc, [0x0c0226d8], [('jal', lab['biglen'])]),
        (0x80068efc, [0x0c0226d8], [('jal', lab['biglen'])]),
        (0x8001b2c4, [0x322900ff], [('addiu', 't1', 'zero', LINE_MAX)]),
        (0x8001b3dc, [0x0c0226d8, 0x27a40010, 0x322300ff, 0x304200ff, 0x00621823, 0x000317c2, 0x00621821,
                      0x00031843, 0x02439021], [
            ('andi', 'a1', 's1', 0xff),
            ('jal', lab['centre']),
            ('addiu', 'a0', 'sp', 0x10),
            ('addu', 's2', 's2', 'v0'),
            ('nop',), ('nop',), ('nop',), ('nop',), ('nop',)]),
    ]


def code(at, name_px, name_offs):
    """-> (bytes for `at`, patch(exe, exe_base)); name_px, name_offs = widths and start of the names.py blob"""
    st = at
    widths = st + DATA_SIZE
    code_at = widths + len(WIDTHS)
    code_at += -code_at % 4
    lines = _code(st, widths, name_px, name_offs)
    lab = asm.labels(code_at, lines)
    lab['H'], lab['NEWCOL'] = asm.hi(st), asm.lo(st + NEWCOL)
    data = bytes(DATA_SIZE) + WIDTHS
    data += bytes(code_at - at - len(data)) + asm.assemble(code_at, lines)

    def patch(exe, exe_base):
        for va, old, new in _sites(lab):
            o = va - exe_base
            assert list(struct.unpack_from('<%dI' % len(old), exe, o)) == old, 'unexpected code at %#x' % va
            c = b''.join(struct.pack('<I', n[1]) if n[0] == 'raw' else asm.assemble(va + 4 * i, [n]) for i, n in enumerate(new))
            assert len(c) == 4 * len(old), hex(va)
            exe[o:o + len(c)] = c
        for va, old, new in OUTLINE_FIX:
            o = va - exe_base
            assert struct.unpack_from('<I', exe, o)[0] == old, 'unexpected code at %#x' % va
            struct.pack_into('<I', exe, o, new)
        f = font()
        exe[ASCII_FONT - exe_base:ASCII_FONT - exe_base + len(f)] = f
    return data, patch
