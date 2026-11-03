"""Chapter text MSG/EVMc_s.EVM: parse into entries, rebuild.

A file is a run of entries in story order, each referenced by a u16 byte offset from the paired
SCENARIO/EVDc_s.EVD (see notes/survey.md):
  plain     text NUL                       (title, narration, caption, choice)
  dialogue  {u16 speaker, text NUL}... ffff
Original text is compressed: bytes 0x20-0x72 stand for hiragana, 0x73-0x76 for punctuation. The
patched decompressor copies every single byte < 0x80, so a rebuilt file holds ASCII and SJIS
pairs (expand() turns kept Japanese into plain SJIS).

A rebuilt file starts with the old -> new offset table read by the hook at 0x8005ce98:
  u16 n, u16 old[n] (sorted), u16 new[n] (from the start of the file)
"""
import glob, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MSG = os.path.join(ROOT, 'extract', 'MSG')
EVD = os.path.join(ROOT, 'extract', 'SCENARIO')
MAX_SPEAKER = 0x180
BLOCK_MAX = 0xc00                        # bytes copied per text op (patch in build.py)
FILE_MAX = 0x800f7000 - 0x800ea000       # build.EVM_LOAD .. first used RAM above it (0x800f78e4); CD reads whole sectors
SNDT = os.path.join(ROOT, 'extract', 'SNDT')
NPC_LOAD = 0x80100a04                    # shared buffer, loader 0x80027f28
NPC_MAX = 0x80107204 - NPC_LOAD
NPC_TEXT_MAX = 0x101                     # stack copy 0x102 B at 0x80027ecc (with the NUL)
PUNCT = {0x73: '、', 0x74: '。', 0x75: '？', 0x76: '！'}


def files():
    return sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(MSG, 'EVM*.EVM'))) + npc_files()


def npc_files():
    return ['NPC%d' % i for i in range(1, 5)]


def is_npc(name):
    return name.startswith('NPC')


def disc_path(name):
    return 'SNDT/%s.MES' % name if is_npc(name) else 'MSG/%s.EVM' % name


def load(name):
    with open(os.path.join(SNDT, name + '.MES') if is_npc(name) else os.path.join(MSG, name + '.EVM'), 'rb') as f:
        return f.read()


def evd(name):
    with open(os.path.join(EVD, name.replace('EVM', 'EVD') + '.EVD'), 'rb') as f:
        return f.read()


def text_end(d, p):
    """offset of the NUL ending the text at p (SJIS pairs may hold no NUL)"""
    return d.index(0, p)


def parse(d):
    """-> [(offset, 'plain', raw) | (offset, 'talk', [(speaker, raw)...])]"""
    out, p = [], 0
    while p < len(d):
        start = p
        if p + 2 <= len(d) and d[p + 1] in (0, 1) and d[p] | d[p + 1] << 8 < MAX_SPEAKER:
            sp = []
            while d[p:p + 2] != b'\xff\xff':
                who = d[p] | d[p + 1] << 8
                assert who < MAX_SPEAKER, (start, p, who)
                e = text_end(d, p + 2)
                sp.append((who, d[p + 2:e]))
                p = e + 1
            p += 2
            out.append((start, 'talk', sp))
        else:
            e = text_end(d, p)
            out.append((start, 'plain', d[p:e]))
            p = e + 1
    return out


def parse_npc(d):
    """town NPC lines: plain SJIS, NUL-terminated; a u16 table in SNDT/IPPAN0.R3 gives the offsets"""
    out, p = [], 0
    while p < len(d):
        e = d.index(0, p)
        out.append((p, 'npc', d[p:e]))
        p = e + 1
    return out


def expand(raw):
    """compressed original text -> SJIS bytes the decompressor would output"""
    out, i = bytearray(), 0
    while i < len(raw):
        b = raw[i]
        i += 1
        if b < 0x20:
            out.append(b)
        elif b < 0x73:
            out += bytes((0x82, b + 0x7f))
        elif b < 0x80:
            if b in PUNCT:
                out += PUNCT[b].encode('cp932')
        else:
            out += raw[i - 1:i + 1]
            i += 1
    return bytes(out)


def show(raw, plain_sjis=False):
    """display form of original text: Unicode, control bytes as \\n or <xx>"""
    b, out, i = raw if plain_sjis else expand(raw), [], 0
    while i < len(b):
        c = b[i]
        if c == 0x0d and b[i + 1:i + 2] == b'\n':
            i += 1
            continue
        if c == 0x0a:
            out.append('\\n')
            i += 1
        elif c < 0x20 or c == 0x7f:
            out.append('<%02x>' % c)
            i += 1
        elif c < 0x80 or 0xa0 <= c < 0xe0:
            out.append(bytes((c,)).decode('cp932', 'replace'))
            i += 1
        else:
            try:
                out.append(b[i:i + 2].decode('cp932'))
            except UnicodeDecodeError:
                out.append('<%02x%02x>' % (c, b[i + 1]))
            i += 2
    return ''.join(out)


def rebuild(entries, en=None):
    """entries from parse(); en: {(n, k or None): bytes} replaces text (already encoded).
    -> file bytes with the offset table in front"""
    en = en or {}
    body, olds, news = bytearray(), [], []
    for n, (off, kind, val) in enumerate(entries):
        olds.append(off)
        news.append(len(body))
        if kind == 'npc':
            t = en.get((n, None), val)
            assert len(t) < NPC_TEXT_MAX, 'line %d: %d bytes' % (n, len(t))
            body += t + b'\0'
        elif kind == 'plain':
            body += en.get((n, None), expand(val)) + b'\0'
        else:
            start = len(body)
            for k, (who, raw) in enumerate(val):
                body += struct.pack('<H', who) + en.get((n, k), expand(raw)) + b'\0'
            body += b'\xff\xff'
            assert len(body) - start <= BLOCK_MAX, 'block %d: %d bytes' % (n, len(body) - start)
    head = 2 + 4 * len(entries)
    assert olds == sorted(olds)
    out = struct.pack('<H', len(olds)) + struct.pack('<%dH' % len(olds), *olds)
    out += struct.pack('<%dH' % len(news), *(head + x for x in news)) + bytes(body)
    limit = NPC_MAX if entries[0][1] == 'npc' else FILE_MAX
    assert len(out) <= limit and head + news[-1] < 0x10000, 'file: %d bytes' % len(out)
    return out


if __name__ == '__main__':
    from collections import Counter
    tot = Counter()
    ctl = Counter()
    lines = Counter()
    maxw = Counter()
    for name in files():
        if is_npc(name):
            continue
        d = load(name)
        es = parse(d)
        ev = evd(name)
        u16s = set(struct.unpack_from('<%dH' % (len(ev) // 2), ev)) | set(struct.unpack_from('<%dH' % ((len(ev) - 1) // 2), ev, 1))
        miss = [e[0] for e in es if e[0] not in u16s]
        assert b''.join(b'' for _ in ()) == b''
        nt = sum(e[1] == 'talk' for e in es)
        tot['plain'] += len(es) - nt
        tot['talk'] += nt
        rb = rebuild(es)
        print(name, len(d), len(es), 'talk', nt, 'miss', miss, 'rebuilt', len(rb))
        for off, kind, val in es:
            for who, raw in ([(None, val)] if kind == 'plain' else val):
                b = expand(raw)
                i = 0
                while i < len(b):
                    if b[i] < 0x20:
                        ctl[b[i]] += 1
                    i += 2 if b[i] >= 0x80 else 1
                ls = show(raw).split('\\n')
                lines[(kind, len(ls))] += 1
                maxw[kind] = max(maxw[kind], *(len(x) for x in ls))
    print(tot, 'ctl', {hex(k): v for k, v in ctl.items()})
    print(sorted(lines.items()))
    print(maxw)
