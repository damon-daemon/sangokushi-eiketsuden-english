"""Translation files of the chapter text MSG/EVM*.EVM and town lines SNDT/NPC*.MES: show, apply,
check, stats; used by build.py.

tl/evm/EVMc_s.txt (NPC1.txt ...) holds the English (no Japanese) of one file:

    # comment (a line starting with #)
    @<n>        plain entry n (evm.parse order)
    @<n>.<k>    speech k of dialogue entry n (the speaker is kept from the original)
    English text, possibly over several physical lines (joined with spaces); \\n = line break,
    \\n\\n = new page.

See text.py for the character set and the wrapping. A segment without English takes the English
of a segment with the same Japanese (translation memory, explicit wins); one with neither keeps
its Japanese.

usage:
    tl.py show  EVM0_0 [from] [to] [--todo]  # Japanese segments (from/to = entry numbers)
    tl.py apply EVM0_0 batch.txt             # validate a batch, merge it into tl/evm/EVM0_0.txt
    tl.py check [EVM0_0]                     # validate everything in tl/
    tl.py stats
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
import evm, names as officers, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TL = os.path.join(ROOT, 'tl')
TL_EVM = os.path.join(TL, 'evm')
_REC = re.compile(r'@(\d+)(?:\.(\d+))?\s*$')


class Script:
    """One EVM file: entries and segments."""

    def __init__(self, name, data=None):
        self.name = name
        d = data if data is not None else evm.load(name)
        self.entries = evm.parse_npc(d) if evm.is_npc(name) else evm.parse(d)
        self.segs = {}                  # (n, k or None) -> Japanese (display form)
        self.who = {}                   # (n, k) -> speaker id
        for n, (_, kind, val) in enumerate(self.entries):
            if kind == 'npc':
                self.segs[n, None] = evm.show(val, True)
            elif kind == 'plain':
                self.segs[n, None] = evm.show(val)
            else:
                for k, (who, raw) in enumerate(val):
                    self.segs[n, k] = evm.show(raw)
                    self.who[n, k] = who

    def kind(self, key):
        return self.entries[key[0]][1]

    def build(self, en):
        """{key: English} -> rebuilt file bytes"""
        return evm.rebuild(self.entries, {k: text.encode(e, self.kind(k)) for k, e in en.items()})


def names():
    return evm.files()


def load(name):
    return Script(name)


def key_str(k):
    return '@%d' % k[0] if k[1] is None else '@%d.%d' % k


def order(k):
    return k[0], k[1] or 0


def head(sc, k):
    if k in sc.who:
        return '%s talk [%s]' % (key_str(k), officers.en_name(sc.who[k]))
    return '%s %s' % (key_str(k), sc.kind(k))


def dump(sc, f, a=0, z=None, skip=()):
    n = 0
    for k, jp in sorted(sc.segs.items(), key=lambda i: order(i[0])):
        if k[0] >= a and (z is None or k[0] <= z) and k not in skip:
            f.write('%s\n%s\n\n' % (head(sc, k), jp))
            n += 1
    return n


def tl_path(name):
    return os.path.join(TL_EVM, name + '.txt')


def parse_tl(path):
    """-> {(n, k or None): English}"""
    out, key, buf = {}, None, []

    def flush():
        if key is not None:
            out[key] = ' '.join(x.strip() for x in buf if x.strip())
    if not os.path.exists(path):
        return out
    for ln in open(path, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if ln.startswith('#'):
            continue
        m = _REC.match(ln)
        if m:
            flush()
            key, buf = (int(m.group(1)), None if m.group(2) is None else int(m.group(2))), []
            if key in out:
                raise ValueError('%s: %s twice' % (path, key_str(key)))
        elif key is not None:
            buf.append(ln)
        elif ln.strip():
            raise ValueError('%s: text before the first @ line: %r' % (path, ln))
    flush()
    return out


def write_tl(name, recs):
    os.makedirs(TL_EVM, exist_ok=True)
    with open(tl_path(name), 'w', encoding='utf-8') as f:
        for k in sorted(recs, key=order):
            f.write('%s\n%s\n\n' % (key_str(k), recs[k]))


def load_tls():
    return {n: parse_tl(tl_path(n)) for n in names()}


def memory(scripts, tls):
    """{Japanese segment: English} from every explicit segment"""
    tm = {}
    for n, recs in tls.items():
        for k, en in recs.items():
            if k in scripts[n].segs:
                tm.setdefault(scripts[n].segs[k], en)
    return tm


def english(scripts=None, tls=None):
    """-> ({name: rebuilt EVM bytes, all files}, translated count, errors). Every file is rebuilt:
    the patched decompressor no longer expands the original 1-byte hiragana."""
    scripts = scripts or {n: load(n) for n in names()}
    tls = tls if tls is not None else load_tls()
    tm = memory(scripts, tls)
    out, errs, done = {}, [], 0
    for n, sc in scripts.items():
        recs = tls.get(n, {})
        errs += ['%s %s: no such segment' % (n, key_str(k)) for k in recs if k not in sc.segs]
        en = {}
        for k, jp in sc.segs.items():
            e = recs.get(k, tm.get(jp))
            if e is None:
                continue
            es = text.check(e)
            if es:
                errs += ['%s %s: %s' % (n, key_str(k), x) for x in es]
                continue
            en[k] = e
        done += len(en)
        try:
            out[n] = sc.build(en)
        except AssertionError as e:
            errs.append('%s: %s' % (n, e))
    return out, done, errs


def show(name, a=0, z=None, todo=False):
    scripts = {n: load(n) for n in names()}
    tls = load_tls()
    sc, recs, tm = scripts[name], tls[name], memory(scripts, tls)
    skip = {k for k, jp in sc.segs.items() if k in recs or jp in tm} if todo else ()
    dump(sc, sys.stdout, a, z, skip)


def apply(name, batch):
    sc = load(name)
    new = parse_tl(batch)
    errs = []
    for k, en in new.items():
        if k not in sc.segs:
            errs.append('%s: no such segment in %s' % (key_str(k), name))
        else:
            errs += ['%s: %s' % (key_str(k), x) for x in text.check(en)]
    if errs:
        sys.exit('\n'.join(errs) + '\n%d errors, nothing written' % len(errs))
    recs = parse_tl(tl_path(name))
    recs.update(new)
    write_tl(name, recs)
    print('%s: %d segments merged (%d in file)' % (name, len(new), len(recs)))


def check(only=None):
    scripts = {n: load(n) for n in names()}
    tls = load_tls()
    if only:
        tls = {n: (v if n == only else {}) for n, v in tls.items()}
    out, done, errs = english(scripts, tls)
    for n, t in tls.items():                 # @0 = save-slot title, 30-byte field
        if n.startswith('EVM') and (0, None) in t and len(t[(0, None)]) > 29:
            errs.append('%s @0: save-slot title longer than 29 characters' % n)
    big = sorted(((len(d), n) for n, d in out.items()), reverse=True)[:3]
    print('largest: ' + ', '.join('%s %d' % (n, s) for s, n in big) + ' (limit %d)' % evm.FILE_MAX)
    print('\n'.join(errs))
    print('%d segments translated, %d errors' % (done, len(errs)))
    return not errs


def stats():
    scripts = {n: load(n) for n in names()}
    tls = load_tls()
    tm = memory(scripts, tls)
    tot = done = 0
    for n, sc in scripts.items():
        t = len(sc.segs)
        d = sum(1 for k, jp in sc.segs.items() if k in tls[n] or jp in tm)
        tot, done = tot + t, done + d
        if d:
            print('%s: %4d / %4d' % (n, d, t))
    print('total: %d / %d segments (%.1f%%)' % (done, tot, 100.0 * done / max(tot, 1)))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == 'show':
        nums = [int(x) for x in a[2:] if not x.startswith('--')]
        show(a[1], *(nums + [0, None])[:2], todo='--todo' in a)
    elif a[0] == 'apply':
        apply(a[1], a[2])
    elif a[0] == 'check':
        sys.exit(0 if check(a[1] if len(a) > 1 else None) else 1)
    elif a[0] == 'stats':
        stats()
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
