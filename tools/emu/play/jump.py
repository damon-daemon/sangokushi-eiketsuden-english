"""jump.py CHAPTER [SECTION]: at the next script op, set chapter + section and run the end of the game's "next chapter" op (0x8005ec04: clears
scene + pc, loads the EVD, chapter init). Test shortcut: party and flags stay as they are. Headless emulator running; the op loop only
runs while a script does, so tap Circle during a talk while this waits (or start it just before a scripted scene).
"""
import os, struct, sys
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, R + '/tools/emu')
from gdbmem import G, wait_break
CTX, JOIN, NEXT = 0x80178880, 0x8005fcd0, 0x8005ec04
ch = int(sys.argv[1]); sec = int(sys.argv[2]) if len(sys.argv) > 2 else 0
g = G(); g.cmd('?')
pkt, r = wait_break(g, JOIN, 60)
print(pkt, 's3=%08x pc=%08x' % (r['r19'], r['pc']))
assert r['r19'] == CTX
g.cmd('M%x,4:%s' % (CTX, struct.pack('<HH', ch, sec).hex()))
h = g.cmd('g')
h = h[:37 * 8] + struct.pack('<I', NEXT).hex() + h[38 * 8:]
print(g.cmd('G' + h))
print('pc now %08x' % __import__('gdbmem').regs(g)['pc'])
g.resume()
# third argument K [ENTRY]: then, at the next op, run entry ENTRY of block K directly (ctx+4 = K, +6 = 0, +0x1a8 = ENTRY + 1, script pc = entry code;
# ending a scene with pc ffff does not work: it runs from offset 0 of the EVD as code)
if len(sys.argv) > 3:
    k = int(sys.argv[3]); e = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    g = G(); g.cmd('?')
    pkt, r = wait_break(g, JOIN, 60)
    evd = g.read(0x80107210, 0x3000)
    base = struct.unpack_from('<H', evd, k * 2)[0]
    code = base + struct.unpack_from('<H', evd, base + e * 10 + 8)[0]
    print('block', k, 'base', base, 'pc', code)
    # EVD_POKE=off:hex (env): patch the loaded EVD first, e.g. to drop an op 05 (map mode: hands the cursor to the player, the script then waits for a map event)
    import os
    if os.environ.get('EVD_POKE'):
        off, hx = os.environ['EVD_POKE'].split(':')
        g.cmd('M%x,%x:%s' % (0x80107210 + int(off), len(hx) // 2, hx))
    g.cmd('M%x,4:%s' % (CTX + 4, struct.pack('<HH', k, 0).hex()))
    g.cmd('M%x,2:%s' % (CTX + 0x1a8, struct.pack('<H', e + 1).hex()))
    g.cmd('M%x,2:%s' % (CTX + 0x1b4, struct.pack('<H', code).hex()))
    g.resume()
