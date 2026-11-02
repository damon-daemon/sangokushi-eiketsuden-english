"""Rebuild track 1 of the disc with the translation and produce a patch.

Output: build/sangokushi_eiketsuden_en_track1.bin, a copy of the audio track 2 and a .cue next to
them (boots in an emulator), and build/sangokushi_eiketsuden_en.xdelta (clean track 1 -> English
track 1; the audio track is not changed).

usage: .venv/bin/python tools/build.py [clean_track1.bin] [out_track1.bin]
"""
import os, shutil, struct, subprocess, sys

sys.path.insert(0, os.path.dirname(__file__))
import asm, evm, gfx, iso, lztext, names, progstr, setup, tl, vwf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'sangokushi_eiketsuden_en_track1.bin')
EXE_BASE = 0x80010000 - 0x800            # file offset of an address = va - EXE_BASE
FIXED = (iso.EXE_NAME,)                  # must keep its place
# Free space: tail of the 16x16 font 0x8009c654-0x800a9594 (glyphs in SJIS order: rare kanji and
# the custom glyphs). All of it is free once no Japanese is left.
POOL, POOL_END = 0x800a4000, 0x800a9594
STRINGS = 0x8009f000                     # moved strings (progstr), up to POOL
EVM_LOAD_OLD, EVM_LOAD = 0x800fa4e4, 0x800face4


def poke(exe, va, words):
    for i, w in enumerate(words):
        struct.pack_into('<I', exe, va - EXE_BASE + 4 * i, w)


def peek(exe, va, n):
    return list(struct.unpack_from('<%dI' % n, exe, va - EXE_BASE))


def expect(exe, va, words):
    assert peek(exe, va, len(words)) == words, 'unexpected code at %#x' % va


def put(exe, va, code):
    exe[va - EXE_BASE:va - EXE_BASE + len(code)] = code


def remap_code(at, load):
    """a0 = old offset -> a0 = address of the entry (table: evm.rebuild)"""
    return asm.assemble(at, [
        ('lui', 't0', asm.hi(load)),
        ('addiu', 't0', 't0', asm.lo(load)),
        ('lhu', 't1', 0, 't0'),
        ('addiu', 't2', 't0', 2),
        ('addu', 'v0', 'zero', 'zero'),
        ('addu', 'v1', 't1', 'zero'),
        'loop:',
        ('beq', 'v0', 'v1', 'miss'),
        ('addu', 't3', 'v0', 'v1'),
        ('srl', 't3', 't3', 1),
        ('sll', 't4', 't3', 1),
        ('addu', 't4', 't4', 't2'),
        ('lhu', 't4', 0, 't4'),
        ('nop',),
        ('beq', 't4', 'a0', 'found'),
        ('sltu', 't4', 't4', 'a0'),
        ('beqz', 't4', 'less'),
        ('nop',),
        ('b', 'loop'),
        ('addiu', 'v0', 't3', 1),
        'less:',
        ('b', 'loop'),
        ('addu', 'v1', 't3', 'zero'),
        'found:',
        ('sll', 't3', 't3', 1),
        ('addu', 't3', 't3', 't2'),
        ('sll', 't1', 't1', 1),
        ('addu', 't3', 't3', 't1'),
        ('lhu', 'a0', 0, 't3'),
        ('nop',),
        'miss:',
        ('jr', 'ra'),
        ('addu', 'a0', 'a0', 't0')])


def patch_exe(exe):
    # decompressor 0x8005ced0: single bytes 0x20-0x72 stood for hiragana, 0x73-0x76 for
    # punctuation; copy every single byte < 0x80 so ASCII reaches the printer
    expect(exe, 0x8005cef4, [0x2c620073, 0x10400009, 0x2c620080])
    poke(exe, 0x8005cef4, [0x2c620080, 0x1040002c, 0])
    expect(exe, 0x8005cf08, [0x2463827f, 0x00031202, 0xa0a20000, 0x24a50001])
    poke(exe, 0x8005cf08, [0, 0, 0, 0])
    # text loader 0x8005ce20: file loaded higher, leaving 0xc00 B for the block copy at 0x800fa0e4
    expect(exe, 0x8005ce6c, [0x3c058010, 0x24a5a4e4])
    put(exe, 0x8005ce6c, asm.assemble(0x8005ce6c, [('lui', 'a1', asm.hi(EVM_LOAD)), ('addiu', 'a1', 'a1', asm.lo(EVM_LOAD))]))
    code = remap_code(POOL, EVM_LOAD)
    put(exe, POOL, code)
    npc_remap = POOL + len(code)
    code = remap_code(npc_remap, evm.NPC_LOAD)
    put(exe, npc_remap, code)
    at = npc_remap + len(code)
    # town lines 0x80027e80: table offset -> remap (SNDT/IPPAN0.R3 stays as it is)
    expect(exe, 0x80027ee8, [0x3c028010, 0x24420a04, 0x00031a00, 0x00832025, 0x0c0183fb, 0x00822021])
    put(exe, 0x80027ee8, asm.assemble(0x80027ee8, [
        ('sll', 'v1', 'v1', 8),
        ('jal', npc_remap),
        ('or', 'a0', 'a0', 'v1'),
        ('nop',),
        ('jal', 0x80060fec),
        ('nop',)]))
    names.patch_program(exe, EXE_BASE)
    nblob, name_px = names.blob()
    nat = at
    put(exe, nat, nblob)
    at = nat + len(nblob)
    at += -at % 4
    hook = names.hook(nat)
    hcode = asm.assemble(at, hook)
    lab = asm.labels(at, hook)
    put(exe, at, hcode)
    for va, old, tag in names.SITES:
        expect(exe, va, [old])
        put(exe, va, asm.assemble(va, [('jal', lab[tag])]))
    at += len(hcode)
    tables = [(names.CITIES[0] + 4 * k, lambda k=k: names.cities(exe, EXE_BASE, k)) for k in range(names.CITY_TABLES)]
    tables += [(names.NPCS[0], lambda: names.npcs(exe, EXE_BASE)), (lztext.RETREAT[0], lambda: lztext.retreat(exe, EXE_BASE))]
    for ptr, fn in tables:
        code = fn()
        put(exe, at, code)
        struct.pack_into('<I', exe, ptr - EXE_BASE, at)
        at += len(code)
        at += -at % 4
    vcode, vpatch = vwf.code(at, nat + name_px, nat)
    put(exe, at, vcode)
    assert at + len(vcode) <= POOL_END
    vpatch(exe, EXE_BASE)
    # unit panel 0x8004fa58: the name's room ended at the LV icon; icon and level 2 columns to the right
    assert exe[0x800ac166 - EXE_BASE] == 7
    exe[0x800ac166 - EXE_BASE] = 9
    expect(exe, 0x8004fbb8, [0x26840009])
    poke(exe, 0x8004fbb8, [0x2684000b])
    # battle title 0x80047ce0: the copy of the map name stopped at the first ASCII byte and kept a
    # Roman numeral for after " Battle"; now the whole name is copied ("Xuchang 1 Battle")
    expect(exe, 0x80047d08, [2422472704, 0, 746717312, 339738654, 637861894, 872808583, 344326158, 0, 2422341633, 0, 608370604, 742522883, 272629768, 0, 2422341632, 610467841, 2745303056, 2422341632, 610467841, 134291295, 2745303057, 2422341632, 610467841, 2694971392, 614793217, 2422341632, 610467841, 2694971392, 614793217, 2422472704, 0, 746717312, 272695269, 0, 2694840320])
    line = [
        ('addiu', 'a1', 's0', 6),
        ('sb', 'zero', 0x10, 'sp'),
        'copy:',
        ('lbu', 'a0', 0, 'v1'),
        ('addiu', 'v1', 'v1', 1),
        ('sb', 'a0', 0, 'a1'),
        ('bnez', 'a0', 'copy'),
        ('addiu', 'a1', 'a1', 1),
        ('b', 0x80047d94),
        ('nop',)]
    put(exe, 0x80047d08, asm.assemble(0x80047d08, line))
    # shop plate: town name in col 2, shop name from col 9 (was 8)
    expect(exe, 0x80037ae0, [0x34040008])
    poke(exe, 0x80037ae0, [0x34040009])
    expect(exe, 0x8005ce98, [0x3222ffff, 0x3c048010, 0x2484a4e4, 0x00442021])
    put(exe, 0x8005ce98, asm.assemble(0x8005ce98, [
        ('jal', POOL),
        ('andi', 'a0', 's1', 0xffff),
        ('nop',),
        ('nop',)]))
    expect(exe, 0x8005ceb0, [0x34060400])
    poke(exe, 0x8005ceb0, [0x34060000 | evm.BLOCK_MAX])


def build_files(disc, recs):
    """{iso path: bytes} of every rebuilt file"""
    evms, done, errs = tl.english()
    if errs:
        sys.exit('\n'.join(errs) + '\n%d errors in tl/ (tools/tl.py check)' % len(errs))
    print('text: %d English segments in %d files' % (done, len(evms)))
    errs = names.check()
    if errs:
        sys.exit('\n'.join(errs))
    out = {evm.disc_path(n): d for n, d in evms.items()}
    out['SNDT/BDATA1.DTA'] = names.bdata()
    exe = bytearray(disc.file(iso.EXE_NAME, recs))
    clean = {'PROG': bytes(exe)}
    patch_exe(exe)
    # archive loader 0x8001e4cc cut the file's LBA to a signed 16 bits; a moved file is past 32767
    expect(exe, 0x8001e5ac, [0x00021400, 0x00021403])
    poke(exe, 0x8001e5ac, [0, 0])
    out['MARK.TIM'] = gfx.build_mark(exe, disc.file('MARK.TIM', recs))
    n, moved, pool, extra = progstr.apply({'PROG': exe}, clean, progstr.resident())
    assert STRINGS + len(extra) <= vwf.BIG_FONT
    put(exe, STRINGS, bytes(extra))
    print('progstr: %d strings (%d moved), %d bytes in the font space, %d free' % (n, moved, len(extra), pool.room()))
    out[iso.EXE_NAME] = bytes(exe)
    return out


def write(clean, out, files):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    moved = iso.write_image(clean, out, files)
    print('rebuilt %s%s' % (out, ' (moved: %s)' % ', '.join(moved) if moved else ''))
    if set(moved) & set(FIXED):
        sys.exit('%s moved on the disc' % ', '.join(set(moved) & set(FIXED)))
    iso.verify(out, files)
    audio = []
    for t, src in enumerate(setup.AUDIO, 2):
        dst = out.replace('_track1.bin', '_track%d.bin' % t)
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            shutil.copyfile(src, dst)
        audio.append(dst)
    iso.write_cue(out.replace('_track1.bin', '.cue'), out, audio)
    patch = os.path.join(os.path.dirname(out), 'sangokushi_eiketsuden_en.xdelta')
    try:
        subprocess.run(['xdelta3', '-e', '-f', '-9', '-S', 'djw', '-B', str(1 << 28), '-s', clean, out, patch], check=True)
        print('patch %s (%d bytes)' % (patch, os.path.getsize(patch)))
    except FileNotFoundError:
        print('xdelta3 not installed; skipped patch')
    return moved


def main():
    args = sys.argv[1:]
    clean = args[0] if args else setup.CLEAN
    out = args[1] if len(args) > 1 else OUT
    disc = iso.Disc(clean)
    write(clean, out, build_files(disc, disc.records()))


if __name__ == '__main__':
    main()
