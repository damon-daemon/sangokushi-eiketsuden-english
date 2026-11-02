"""Plain Shift-JIS text that the program keeps LZ-packed (tools/arc.py): the officers' retreat lines
shown in battle when a unit is beaten (59 NUL-terminated lines, pointer 0x800ca188 -> 0x800ac1c0).
English goes in tl/text/retreat.txt as `n<TAB>English` (\\n = line break); the built blob replaces
the pointer. Untranslated lines stay Japanese.

usage: lztext.py show | check
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(__file__))
import arc, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'extract', 'SLPS_003.09')
TL = os.path.join(ROOT, 'tl', 'text', 'retreat.txt')
RETREAT = (0x800ca188, 59)              # pointer word, line count
WIDTH, LINES = text.WIDTH['talk'], text.PAGE['talk']


def lines(exe, base, table=RETREAT):
    """the Japanese lines of the packed table"""
    at = struct.unpack_from('<I', exe, table[0] - base)[0]
    d = arc.unpack(exe, at - base)[0]
    parts = d.split(b'\0')
    assert len(parts) == table[1] + 1 and parts[-1] == b'', (len(parts), parts[-1])
    return [p.decode('shift_jis') for p in parts[:-1]]


def load_tl(path=TL):
    out = {}
    if not os.path.exists(path):
        return out
    for n, line in enumerate(open(path, encoding='utf-8').read().splitlines(), 1):
        if line.strip() and not line.startswith('#'):
            k, tab, v = line.partition('\t')
            if not (tab and k.isdigit()):
                raise ValueError('%s line %d: expected n<TAB>English: %r' % (path, n, line))
            out[int(k)] = v.replace('\\n', '\n')
    return out


def check():
    en = load_tl()
    errs = []
    for i, e in sorted(en.items()):
        if not 0 <= i < RETREAT[1]:
            errs.append('retreat %d: no such line' % i)
        ls = e.split('\n')
        errs += ['retreat %d: %s' % (i, x) for l in ls for x in text.check(l)]
        if len(ls) > LINES:
            errs.append('retreat %d: %d lines > %d' % (i, len(ls), LINES))
        for l in ls:
            if text.pixels(l) > WIDTH:
                errs.append('retreat %d: %r %d px > %d' % (i, l, text.pixels(l), WIDTH))
    return errs


def retreat(exe, base):
    """the packed table with the English lines, ready for its pointer"""
    jp = lines(exe, base)
    en = load_tl()
    out = bytearray()
    for i, j in enumerate(jp):
        out += (en[i].encode('ascii') if i in en else j.encode('shift_jis')) + b'\0'
    return arc.pack(bytes(out))


def main():
    a = sys.argv[1:]
    exe = open(EXE, 'rb').read()
    base = 0x80010000 - 0x800
    if a[:1] == ['show']:
        en = load_tl()
        for i, j in enumerate(lines(exe, base)):
            print('%d\t%s\t%s' % (i, j.replace('\n', '\\n'), en.get(i, '').replace('\n', '\\n')))
    elif a[:1] == ['check']:
        errs = check()
        print('\n'.join(errs + ['%d errors' % len(errs)]))
        sys.exit(1 if errs else 0)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
