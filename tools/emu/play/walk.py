"""walk.py TX TY PREFIX [MAXTURNS]: each turn: enemies' troop % = 1, Liu Bei healed + status cleared, Liu Bei walks up to 6 keys
toward (TX,TY) (route.sh retries on blocked hexes), Waits, drains dialogue (frames PREFIX_tN_M.png), ends the phase, waits.
Stops when Liu Bei stands on (TX,TY), the script sub-phase changes, or MAXTURNS."""
import os, sys, struct, subprocess, time
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, R + '/tools/emu'); os.chdir(R)
import ram
from gdbmem import G
U, REC, CTX = 0x8017957c, 0x8010c6bc, 0x80178880
PY, E, H = R + '/.venv/bin/python', R + '/tools/emu/', os.path.dirname(os.path.abspath(__file__))
tx, ty, pre = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; maxt = int(sys.argv[4]) if len(sys.argv) > 4 else 12
def rd(va, n): return bytes(ram.shm()[va - 0x80000000: va - 0x80000000 + n])
def run(*a): return subprocess.run(a, capture_output=True, text=True).stdout
def pos(s): b = rd(U + s*14, 14); return b[3], b[4]
def poke():
    g = G(); g.cmd('?')
    g.cmd('M%x,2:8a02' % (REC + 0x1c)); g.cmd('M%x,1:00' % (U + 10)); g.cmd('M%x,1:64' % (U + 12))
    for s in range(15, 40):
        b = rd(U + s*14, 14)
        if b[:2] != b'\xff\xff' and b[3] != 255 and b[9] != 4:
            g.cmd('M%x,1:01' % (U + s*14 + 12)); g.cmd('M%x,3:010101' % (REC + struct.unpack('<H', b[:2])[0]*0x2c + 0x19))
    g.resume()
def keys(alt=0):
    lx, ly = pos(0); k = []; dx, dy = tx - lx, ty - ly
    while (dx or dy) and len(k) < 6:
        xfirst = (abs(dx) >= abs(dy)) if alt == 0 else (alt == 1 and dx != 0 or dy == 0)
        if alt == 2 and dy: xfirst = False
        if xfirst: k.append('Left' if dx < 0 else 'Right'); dx -= (1 if dx > 0 else -1)
        else: k.append('Up' if dy < 0 else 'Down'); dy -= (1 if dy > 0 else -1)
    return k
sub0 = rd(CTX, 8)
for t in range(maxt):
    poke(); k = keys(); print('turn', t, 'liu', pos(0), 'keys', k, flush=True)
    if not k: break
    p0 = pos(0)
    for alt in (0, 1, 2):
        if alt:
            run(E + 'hpress.sh', '/dev/null', 'Z'); time.sleep(1.5); k = keys(alt); print('  retry keys', k, flush=True)
        run(E + 'play/route.sh', '0', *k); time.sleep(1)
        if pos(0) != p0: break
        run(PY, E + 'play/bt.py', 'goto', str(p0[0]), str(p0[1])); time.sleep(1); run(E + 'hpress.sh', '/dev/null', 'X'); time.sleep(2.5)
        run(E + 'hshot.sh', '%s_range_t%d_%d.png' % (pre, t, alt)); run(E + 'hpress.sh', '/dev/null', 'Z'); time.sleep(1.5)
        run(E + 'play/route.sh', '0')      # stay, ring open
        if alt == 2: break
        run(E + 'hpress.sh', '/dev/null', 'Z'); time.sleep(1.5)
    print(' moved to', pos(0), flush=True)
    run(PY, E + 'vpad.py', 'hold', 'Down', '250'); time.sleep(3)
    run(PY, H + '/xp.py', 'drain', '%s_t%d' % (pre, t)); time.sleep(2)
    print(' drained', run(PY, H + '/xp.py', 'drain', '%s_t%db' % (pre, t)).strip(), 'ctx', rd(CTX, 8).hex(), flush=True)
    if rd(CTX, 8) != sub0 or pos(0) == (tx, ty): break
    r = run(E + 'play/endphase.sh', 'nowait').strip().split('\n')[-1]
    print(' ', r, run(PY, H + '/xp.py', 'wait', '%s_e%d' % (pre, t)).strip(), flush=True)
    if rd(CTX, 8) != sub0: break
print('end liu', pos(0), 'ctx', rd(CTX, 8).hex())
