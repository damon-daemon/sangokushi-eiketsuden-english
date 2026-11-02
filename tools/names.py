"""Names held in fields too small for English: officers, items, strategies.

  officers    SNDT/BDATA1.DTA: 384 x 16 B (name [6] SJIS, reading [8] half-width kana, ...); copied to
              the record 0x8010c6bc + id * 0x2c (+6, 7 B)
  items       program 0x8009a348: 183 x 20 B (name [13], data)
  strategies  program 0x800afdf8: 44 x 12 B (name [7], data)

The game passes pointers to these fields to the printers from about 100 places. So each field gets a
2-byte token (lead 0xf0 + n >> 7, trail 0x80 | n & 0x7f; n = id + the table's FIRST). It looks like a
2-byte character to everything that counts columns, and both string printers expand it where they would
draw a 2-byte glyph (hook below). Centring reads the pixel width from the blob (vwf.py).

tl/names/<kind>.json: one row per line, {"id": record, "en": English}.

usage:
    names.py show [TEXT]     records: number, Japanese, English
    names.py check
"""
import json, os, struct, sys

sys.path.insert(0, os.path.dirname(__file__))
import arc, asm, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BDATA = os.path.join(ROOT, 'extract', 'SNDT', 'BDATA1.DTA')
TL_NAMES = os.path.join(ROOT, 'tl', 'names')
COUNT, RECORD, NAME = 384, 16, 6
ITEMS = (0x8009a348, 183, 20, 13)       # address, count, stride, name field
STRATEGIES = (0x800afdf8, 44, 12, 7)
CITIES = (0x800ad154, 32, 21, 8)        # pointer to the LZ table (tools/arc.py), count, stride, name field
CITY_TABLES = 4                         # one table per world map (0x80022364 picks 0x800ad154 + map * 4); ids map * 32 + entry
NPCS = (0x800ad164, 256, 9, 8)          # town NPC kinds (speaker labels "Old Man", "Merchant"): LZ table, name 8 B + kind byte
FIRST = {'officers': 0, 'items': COUNT, 'strategies': COUNT + ITEMS[1], 'cities': COUNT + ITEMS[1] + STRATEGIES[1]}
FIRST['npcs'] = FIRST['cities'] + CITIES[1] * CITY_TABLES
TOTAL = FIRST['npcs'] + NPCS[1]
TOKEN = 0xf0                      # lead bytes 0xf0-0xf2: above every code of the font table (0xebe7)
MAX_PX = 98
PUTS1, PUTS2 = 0x80023680, 0x80023a24
GLYPH1, GLYPH2 = 0x80039b68, 0x80039da8
COL, COUNTER = 0x800ca778, 0x800ca774
_jp = None


def jp_name(i):
    global _jp
    if _jp is None:
        d = open(BDATA, 'rb').read()
        _jp = [d[r:r + NAME].split(b'\0')[0].decode('cp932', 'replace') for r in range(0, COUNT * RECORD, RECORD)]
    return _jp[i] if i < len(_jp) else '#%d' % i


def rows(kind):
    return {r['id']: r['en'] for r in json.load(open(os.path.join(TL_NAMES, kind + '.json'), encoding='utf-8'))}


def officers():
    return rows('officers')


def all_names():
    """{n: English} over the tables"""
    return {FIRST[k] + i: e for k in FIRST for i, e in rows(k).items()}


def en_name(i):
    return officers().get(i, '#%d' % i)


def token(i):
    return bytes([TOKEN + (i >> 7), 0x80 | i & 0x7f])


def bdata():
    """BDATA1.DTA with tokens in the name fields"""
    d = bytearray(open(BDATA, 'rb').read())
    en = officers()
    for i in range(COUNT):
        if i in en:
            d[i * RECORD:i * RECORD + NAME] = token(i).ljust(NAME, b'\0')
            d[i * RECORD + NAME] = 0             # kana reading: empty (shown beside the name)
    return bytes(d)


def patch_program(exe, base):
    """tokens in the name fields of the program tables"""
    for kind, (at, n, stride, field) in (('items', ITEMS), ('strategies', STRATEGIES)):
        en = rows(kind)
        for i in range(n):
            if i in en:
                o = at + i * stride - base
                exe[o:o + field] = token(FIRST[kind] + i).ljust(field, b'\0')


def lz_table(exe, base, kind, table, k=0):
    """an LZ-packed name table with tokens, ready for its pointer: cities (town plate, map name), npcs.
    k = the table's number for kinds with several tables (pointer + 4 * k, ids from k * count)"""
    ptr, n, stride, field = table
    at = struct.unpack_from('<I', exe, ptr + 4 * k - base)[0]
    d = bytearray(arc.unpack(exe, at - base)[0])
    en = rows(kind)
    for i in range(n):
        if k * n + i in en:
            d[i * stride:i * stride + field] = token(FIRST[kind] + k * n + i).ljust(field, b'\0')
    return arc.pack(bytes(d))


def cities(exe, base, k):
    return lz_table(exe, base, 'cities', CITIES, k)


def npcs(exe, base):
    return lz_table(exe, base, 'npcs', NPCS)


def blob():
    """-> (bytes, widths offset): u16 offset[TOTAL] from the blob start, u8 px[TOTAL], strings"""
    en = all_names()
    head = TOTAL * 3
    head += head & 1
    offs, px, strs = [], [], bytearray()
    for i in range(TOTAL):
        s = en.get(i, '').encode('ascii')
        offs.append(head + len(strs))
        px.append(text.pixels(en.get(i, '')))
        strs += s + b'\0'
    out = struct.pack('<%dH' % TOTAL, *offs) + bytes(px)
    return out.ljust(head, b'\0') + bytes(strs), TOTAL * 2


def hook(base):
    """Replacements for the 2-byte glyph calls of the printers: a token prints its name, then col and
    the glyph counter step back because the printer adds 2 and 1 after the call."""
    def lines(tag, glyph, puts):
        return [
            tag + ':',
            ('srl', 't0', 'a0', 12),
            ('addiu', 't1', 'zero', 0xf),
            ('beq', 't0', 't1', tag + 'n'),
            ('addiu', 'sp', 'sp', -0x18),
            ('j', glyph),
            ('addiu', 'sp', 'sp', 0x18),
            tag + 'n:',
            ('sw', 'ra', 0x10, 'sp'),
            ('andi', 't0', 'a0', 0x7f),
            ('srl', 't1', 'a0', 1),
            ('andi', 't1', 't1', 0x780),
            ('or', 't0', 't0', 't1'),
            ('sll', 't0', 't0', 1),
            ('lui', 't1', asm.hi(base)),
            ('addu', 't1', 't1', 't0'),
            ('lhu', 'a0', asm.lo(base), 't1'),
            ('lui', 't1', asm.hi(base)),
            ('addiu', 't1', 't1', asm.lo(base)),
            ('jal', puts),
            ('addu', 'a0', 'a0', 't1'),
            ('lui', 't0', asm.hi(COL)),
            ('lhu', 't1', asm.lo(COL), 't0'),
            ('lhu', 't2', asm.lo(COUNTER), 't0'),
            ('addiu', 't1', 't1', -2),
            ('addiu', 't2', 't2', -1),
            ('sh', 't1', asm.lo(COL), 't0'),
            ('sh', 't2', asm.lo(COUNTER), 't0'),
            ('lw', 'ra', 0x10, 'sp'),
            ('nop',),
            ('jr', 'ra'),
            ('addiu', 'sp', 'sp', 0x18)]
    return lines('t1', GLYPH1, PUTS1) + lines('t2', GLYPH2, PUTS2)


SITES = [(0x8002374c, 0x0c00e6da, 't1'), (0x80023b08, 0x0c00e76a, 't2')]


def check():
    errs = []
    for kind, n in (('officers', COUNT), ('items', ITEMS[1]), ('strategies', STRATEGIES[1]),
                    ('cities', CITIES[1] * CITY_TABLES), ('npcs', NPCS[1])):
        en = rows(kind)
        if kind != 'cities':            # the city tables have unused filler entries
            errs += ['%s %d: no row' % (kind, i) for i in range(n) if i not in en]
        for i, e in en.items():
            if not 0 <= i < n:
                errs.append('%s %d: no such record' % (kind, i))
            errs += ['%s %d: %s' % (kind, i, x) for x in text.check(e)]
            if text.pixels(e) > MAX_PX:
                errs.append('%s %d: %r %d px > %d' % (kind, i, e, text.pixels(e), MAX_PX))
    return errs


def main():
    a = sys.argv[1:]
    if a[:1] == ['show']:           # officers
        en = officers()
        for i in range(COUNT):
            line = '%d\t%s\t%s' % (i, jp_name(i), en.get(i, ''))
            if len(a) < 2 or a[1] in line:
                print(line)
    elif a[:1] == ['check']:
        errs = check()
        print('\n'.join(errs + ['%d errors' % len(errs)]))
        sys.exit(1 if errs else 0)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
