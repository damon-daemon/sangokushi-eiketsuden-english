"""Battle helper: bt.py units | hp SLOT VAL | weaken [HP] | cursor X Y   (headless emulator running)"""
import json, os, struct, sys, time
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, R + '/tools/emu'); sys.path.insert(0, R + '/tools')
import ram
from gdbmem import G
UNITS, REC, CUR = 0x8017957c, 0x8010c6bc, 0x800ca488
names = {r['id']: r['en'] for r in json.load(open(R + '/tl/names/officers.json'))}

def mem(): return ram.shm()
def rd(m, va, n): return m[va - 0x80000000: va - 0x80000000 + n]

def units(m):
    out = []
    for s in range(40):
        b = rd(m, UNITS + s * 14, 14)
        rid = struct.unpack_from('<H', b)[0]
        if rid == 0xffff: continue
        rec = rd(m, REC + rid * 0x2c, 0x2c)
        hp = struct.unpack_from('<H', rec, 0x1c)[0]
        out.append((s, rid, names.get(rid, '?'), b[3], b[4], hp, rec[0x20]))
    return out

def write(va, data):
    g = G(); g.cmd('?'); g.cmd('M%x,%x:%s' % (va, len(data), data.hex())); g.resume()

cmd = sys.argv[1]
m = mem()
if cmd == 'units':
    for s, rid, n, x, y, hp, lv in units(m):
        print('%2d %s rec %3d %-16s x %2d y %2d hp %3d lv %d' % (s, 'P' if s < 15 else 'E', rid, n, x, y, hp, lv))
elif cmd == 'hp':
    s, v = int(sys.argv[2]), int(sys.argv[3])
    rid = struct.unpack_from('<H', rd(m, UNITS + s * 14, 2))[0]
    write(REC + rid * 0x2c + 0x1c, struct.pack('<H', v))
elif cmd == 'weaken':
    v = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    g = G(); g.cmd('?')
    for s, rid, n, x, y, hp, lv in units(m):
        if s >= 15 and hp > 0:
            g.cmd('M%x,2:%s' % (REC + rid * 0x2c + 0x1c, struct.pack('<H', v).hex()))
    g.resume()
elif cmd == 'cursor':
    write(CUR, bytes([int(sys.argv[2]), int(sys.argv[3])]))
elif cmd == 'goto':      # move the map cursor with pad presses until it is at X Y (feedback from RAM)
    import subprocess
    tx, ty = int(sys.argv[2]), int(sys.argv[3])
    def cur():
        m = mem(); b = rd(m, CUR, 2)
        if b == b'\x00\xff': b = rd(m, 0x800ca4ac, 2)
        return b[0], b[1]
    for _ in range(60):
        x, y = cur()
        if (x, y) == (tx, ty): break
        if x != tx: d = 'Left' if x > tx else 'Right'
        else: d = 'Up' if y > ty else 'Down'
        subprocess.run([R + '/.venv/bin/python', R + '/tools/emu/vpad.py', 'hold', d, '40'], stdout=subprocess.DEVNULL)
        time.sleep(0.45)
    print('cursor', cur())
elif cmd == 'move':      # move SLOT X Y: select the unit at the cursor (must be on it), move to X Y (retrying nearer hexes), Wait, end turn
    import subprocess
    slot, tx, ty = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    def pos():
        b = rd(mem(), UNITS + slot * 14, 14); return b[3], b[4]
    def press(k, ms=120):
        subprocess.run([R + '/.venv/bin/python', R + '/tools/emu/vpad.py', 'hold', k, str(ms)], stdout=subprocess.DEVNULL); time.sleep(0.6)
    ux, uy = pos()
    press('Circle'); time.sleep(0.8)                       # move mode
    for tries in range(4):
        subprocess.run([sys.executable, __file__, 'goto', str(tx), str(ty)], stdout=subprocess.DEVNULL)
        press('Circle'); time.sleep(1.5)
        if pos() != (ux, uy): break
        tx += (ux > tx) - (ux < tx); ty += (uy > ty) - (uy < ty)   # one hex back toward the unit
    print('moved to', pos())
    press('Down', 250); time.sleep(1.0)                    # ring: Wait
    press('Cross'); time.sleep(1.0); press('Circle'); time.sleep(1.0)   # Cross = End all units' commands?, Circle = Yes
