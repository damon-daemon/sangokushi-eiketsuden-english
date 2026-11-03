"""auto.py PREFIX [MAXPHASES] [TARGET_RID]: with a target record id only the 3 nearest units act, against it. Play a battle for testing (headless emulator, free cursor, player phase). Each phase: enemies' troop % (slot +12) = 1,
players' = 100, players' War/Ldr = 255, guards chase (slot +10 = 0, +11 = 1); each player unit attacks an adjacent enemy or walks toward the nearest; end phase.
Stops when the script block changes or no enemy lives. Every distinct text-box frame goes to PREFIX_N.png + contact sheet; tapped through."""
import os, struct, subprocess, sys, time
from PIL import Image, ImageChops
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, R + '/tools/emu'); os.chdir(R)
import ram
from gdbmem import G
PY, E = R + '/.venv/bin/python', R + '/tools/emu/'
U, REC, CTX, CUR = 0x8017957c, 0x8010c6bc, 0x80178880, 0x800ca488
pre, maxp = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40
nshot = [0]; last = [None]
trid = int(sys.argv[3]) if len(sys.argv) > 3 else None

def run(*a): return subprocess.run(a, capture_output=True, text=True).stdout
def hold(k, ms=60): run(PY, E + 'vpad.py', 'hold', k, str(ms))
def rd(va, n): return bytes(ram.shm()[va - 0x80000000: va - 0x80000000 + n])
def ctx(): return rd(CTX, 6)
def units():
    out = []
    for s in range(40):
        b = rd(U + s * 14, 14)
        if b[:2] == b"\xff\xff" or b[3] == 255 or b[9] == 4: continue      # +9 = 4: gone from the map
        hp = struct.unpack('<H', rd(REC + struct.unpack('<H', b[:2])[0] * 0x2c + 0x1c, 2))[0]
        if hp: out.append((s, b[3], b[4], struct.unpack('<H', b[:2])[0]))
    return out
def poke():
    g = G(); g.cmd('?')
    for s, x, y, rid in units():
        a = U + s * 14
        if s < 15:
            g.cmd('M%x,1:64' % (a + 12)); g.cmd('M%x,2:ffff' % (REC + rid * 0x2c + 0x19))
        else:
            g.cmd('M%x,1:01' % (a + 12)); g.cmd('M%x,1:00' % (a + 10)); g.cmd('M%x,1:01' % (a + 11))
    g.resume()
def shot():
    p = pre + '_tmp.png'; run(E + 'hshot.sh', p); return Image.open(p).convert('RGB')
def box(im):
    for lo, hi in ((20, 60), (60, 120), (170, 230)):
        n = t = 0
        for y in range(lo, hi, 4):
            for x in range(70, 280, 6):
                r, g, b = im.getpixel((x, y)); t += 1; n += r > 90 and g < 45 and b < 45
        if n / t > .5: return True
    return False
def card(im):      # blue win-terms card
    n = t = 0
    for y in range(60, 130, 6):
        for x in range(60, 260, 8):
            r, g, b = im.getpixel((x, y)); t += 1; n += b > 80 and r < 70 and g < 80
    return n / t > .6
def settle():
    """battle intro: tap through boxes and the win-terms card until the map stays still, no box"""
    prev, same = None, 0
    for _ in range(150):
        im = shot()
        if box(im) or card(im):
            keep(im); hold('Circle', 40); same = 0; prev = None; time.sleep(1.5); continue
        d = prev is not None and sum(ImageChops.difference(im, prev).convert('L').point(lambda v: 255 if v > 24 else 0).histogram()[255:]) < 300
        same = same + 1 if d else 0
        prev = im
        if same >= 4 and sum(im.convert('L').histogram()[40:]) > 40000 and [u for u in units() if u[0] >= 15]: break
        time.sleep(1.5)
def keep(im):
    if last[0] is not None and sum(ImageChops.difference(im, last[0]).convert('L').point(lambda v: 255 if v > 24 else 0).histogram()[255:]) < 1500: return
    last[0] = im; nshot[0] += 1; im.save('%s_%d.png' % (pre, nshot[0]))
def drain():
    """tap through any open text box, keeping frames; True if there was one"""
    any_ = False
    for _ in range(60):
        im = shot()
        if not box(im): break
        keep(im); any_ = True; hold('Circle', 40); time.sleep(1.2)
    return any_
def done(c0): return ctx() != c0 or not [u for u in units() if u[0] >= 15]
def dirs(dx, dy):
    k, ax, ay = [], abs(dx), abs(dy)         # the longer axis first, alternating: straight lines run into terrain
    while ax or ay:
        if ax >= ay: k.append('Left' if dx < 0 else 'Right'); ax -= 1
        else: k.append('Up' if dy < 0 else 'Down'); ay -= 1
    return k

settle()
c0 = ctx(); print('ctx', c0.hex(), flush=True)
for phase in range(maxp):
    drain(); poke()
    us = [u for u in units() if u[0] < 15]
    boss = [u for u in units() if u[0] >= 15 and u[3] == trid]
    if boss: us = sorted(us, key=lambda u: abs(u[1] - boss[0][1]) + abs(u[2] - boss[0][2]))[:3]
    for s, x, y, rid in us:
        if done(c0): break
        en = [u for u in units() if u[0] >= 15]
        t = min(boss or en, key=lambda u: abs(u[1] - x) + abs(u[2] - y))
        dx, dy = t[1] - x, t[2] - y; d = abs(dx) + abs(dy)
        if d == 1:
            run(E + 'play/atk.sh', str(s), '--', dirs(dx, dy)[0])
            print('p', phase, 'slot', s, 'hit', t[0], flush=True)
        else:
            keys = dirs(dx, dy)
            # stop one hex short of the target, walk at most 8 steps
            keys = keys[:-1][:8]
            run(E + 'play/route.sh', str(s), *keys)
            hold('Down', 250); time.sleep(1.5)     # ring: Wait
            print('p', phase, 'slot', s, 'walk', keys, flush=True)
        drain()
    if done(c0): break
    r = run(E + 'play/endphase.sh', 'nowait').strip().split('\n')[-1]
    print('phase', phase, r, len([u for u in units() if u[0] >= 15]), 'enemies', flush=True)
    while drain(): time.sleep(2)
    if done(c0): break
time.sleep(4); drain()
try: os.remove(pre + '_tmp.png')
except OSError: pass
print(run(PY, E + 'play/sheet.py', pre), 'ctx', ctx().hex(), 'enemies', len([u for u in units() if u[0] >= 15]))
