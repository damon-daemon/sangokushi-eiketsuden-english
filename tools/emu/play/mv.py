"""mv.py PREFIX KEY... : one checked player turn for Liu Bei (slot 0). Defangs enemies and heals Liu Bei (as walk.py), selects him,
presses the direction keys one by one reading the move preview (0x800ca4ac); if a key leaves the range (preview 00 ff / ff 00) it
cancels and exits 1 WITHOUT confirming (nothing else is pressed, so no stray Cross/Circle can reach the system ring). Otherwise
confirms, Waits (Down 250 ms on the ring), drains dialogue (PREFIX_N.png), ends the phase and waits for the enemy phase (PREFIX_eN.png).
Prints the position and script context at the end. KEY = Up Down Left Right."""
import os, sys, struct, subprocess, time
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, R + '/tools/emu'); os.chdir(R)
import ram
from gdbmem import G
U, REC, CTX, CUR, PREV = 0x8017957c, 0x8010c6bc, 0x80178880, 0x800ca488, 0x800ca4ac
PY, E, H = R + '/.venv/bin/python', R + '/tools/emu/', os.path.dirname(os.path.abspath(__file__))
pre, keys = sys.argv[1], sys.argv[2:]
def rd(va, n): return bytes(ram.shm()[va - 0x80000000: va - 0x80000000 + n])
def run(*a): return subprocess.run(a, capture_output=True, text=True).stdout
def hold(k, ms=60): run(PY, E + 'vpad.py', 'hold', k, str(ms)); time.sleep(0.6)
def pos(): b = rd(U, 14); return b[3], b[4]
def poke():
    g = G(); g.cmd('?')
    g.cmd('M%x,2:8a02' % (REC + 0x1c)); g.cmd('M%x,1:00' % (U + 10)); g.cmd('M%x,1:64' % (U + 12))
    for s in range(15, 40):
        b = rd(U + s*14, 14)
        if b[:2] != b'\xff\xff' and b[3] != 255 and b[9] != 4:
            g.cmd('M%x,1:01' % (U + s*14 + 12)); g.cmd('M%x,3:010101' % (REC + struct.unpack('<H', b[:2])[0]*0x2c + 0x19))
    g.resume()
def bad(p): return p in (b'\x00\xff', b'\xff\x00')
poke(); p0 = pos(); ctx0 = rd(CTX, 8)
run(PY, H + '/bt.py', 'goto', str(p0[0]), str(p0[1])); time.sleep(0.5)
if tuple(rd(CUR, 2)) != p0: sys.exit('cursor not on Liu Bei: %s' % rd(CUR, 2).hex())
hold('Circle', 120); time.sleep(1.5)
if bad(rd(PREV, 2)): sys.exit('select failed (preview %s)' % rd(PREV, 2).hex())
for k in keys:
    hold(k); p = rd(PREV, 2); print(k, 'preview', tuple(p), flush=True)
    if bad(p):
        hold('Cross', 120); time.sleep(1); print('cancelled at', k, 'pos', pos(), 'cur', rd(CUR, 2).hex()); sys.exit(1)   # one Cross: a second one on the free cursor opens the end-turn prompt
tgt = tuple(rd(PREV, 2))
hold('Circle', 120); time.sleep(3)
if pos() != tgt:
    print('move not taken: pos', pos(), 'target', tgt, 'cur', rd(CUR, 2).hex()); hold('Cross', 120); sys.exit(1)
print('moved to', pos(), flush=True)
hold('Down', 250); time.sleep(3)                      # ring: Wait
print('drain', run(PY, H + '/xp.py', 'drain', pre).strip(), 'ctx', rd(CTX, 8).hex(), flush=True)
if rd(CTX, 8) != ctx0: print('script moved on; not ending the phase'); sys.exit(0)
r = run(E + 'play/endphase.sh', 'nowait').strip().split('\n')[-1]
print(' ', r, run(PY, H + '/xp.py', 'wait', pre + '_e').strip(), flush=True)
print('end pos', pos(), 'ctx', rd(CTX, 8).hex())
