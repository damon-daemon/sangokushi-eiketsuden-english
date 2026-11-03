"""Write the current build's EXE patches into the running emulator (GDB stub), so a save state from
an older build can be tested without a fresh boot. Only words that differ from the clean EXE.
Files on disc (EVM, MARK.TIM) are read by the game when it loads them; a state keeps those already
loaded, and moved files keep the sectors it found them at unless the sizes changed.

usage: .venv/bin/python tools/emu/inject.py      (headless emulator running, build done)
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, iso, progstr, setup
from gdbmem import G


def main():
    old = iso.Disc(setup.CLEAN)
    new = iso.Disc(build.OUT)
    a, b = old.file(iso.EXE_NAME, old.records()), new.file(iso.EXE_NAME, new.records())
    g = G()
    g.cmd('?')
    # the whole code range too: a word now equal to the clean EXE may differ from the older build in the state
    code = range(progstr.CODE_START - build.EXE_BASE, progstr.CODE_END - build.EXE_BASE, 0x200)
    for o in code:
        g.cmd('M%x,200:%s' % (o + build.EXE_BASE, b[o:o + 0x200].hex()))
    n, o = 0, 0x800
    while o < len(b):                     # runs of changed words (gaps < 16 B), <= 0x200 B a packet
        if b[o:o + 4] == a[o:o + 4]:
            o += 4
            continue
        e = o + 4
        while e < len(b) and e - o < 0x200 and b[e:e + 16] != a[e:e + 16]:
            e += 4
        g.cmd('M%x,%x:%s' % (o + build.EXE_BASE, e - o, b[o:e].hex()))
        n += (e - o) // 4
        o = e
    g.resume()
    print('injected %d program words' % n)


if __name__ == '__main__':
    main()
