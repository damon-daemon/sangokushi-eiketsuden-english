"""xp.py stats VAL | hp SLOT VAL | drain PREFIX : session helpers on top of auto.py pieces"""
import os, sys, struct, subprocess, time
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, R + '/tools/emu'); os.chdir(R)
import ram
from gdbmem import G
from PIL import Image, ImageChops
U, REC = 0x8017957c, 0x8010c6bc
PY, E = R + '/.venv/bin/python', R + '/tools/emu/'
def rd(va, n): return bytes(ram.shm()[va - 0x80000000: va - 0x80000000 + n])
def run(*a): return subprocess.run(a, capture_output=True, text=True).stdout
def hold(k, ms=60): run(PY, E + 'vpad.py', 'hold', k, str(ms))
def shot(p): run(E + 'hshot.sh', p); return Image.open(p).convert('RGB')
def box(im):
    for lo, hi in ((20, 60), (60, 120), (170, 230)):
        n = t = 0
        for y in range(lo, hi, 4):
            for x in range(70, 280, 6):
                r, g, b = im.getpixel((x, y)); t += 1; n += r > 90 and g < 45 and b < 45
        if n / t > .5: return True
    return False
cmd = sys.argv[1]
if cmd == 'stats':
    v = int(sys.argv[2]); g = G(); g.cmd('?')
    for s in range(15):
        b = rd(U + s * 14, 14)
        if b[:2] == b'\xff\xff': continue
        rid = struct.unpack('<H', b[:2])[0]
        g.cmd('M%x,2:%02x%02x' % (REC + rid * 0x2c + 0x19, v, v))
    g.resume()
elif cmd == 'hp':
    s, v = int(sys.argv[2]), int(sys.argv[3]); rid = struct.unpack('<H', rd(U + s * 14, 2))[0]
    g = G(); g.cmd('?'); g.cmd('M%x,2:%s' % (REC + rid * 0x2c + 0x1c, struct.pack('<H', v).hex())); g.cmd('M%x,1:64' % (U + s * 14 + 12)); g.resume()
elif cmd == 'drain':      # tap through text boxes, keep distinct frames PREFIX_N.png
    pre = sys.argv[2]; n = 0; last = None
    for _ in range(80):
        im = shot(pre + '_tmp.png')
        if not box(im): break
        if last is None or sum(ImageChops.difference(im, last).convert('L').point(lambda v: 255 if v > 24 else 0).histogram()[255:]) >= 1500:
            n += 1; im.save('%s_%d.png' % (pre, n)); last = im
        hold('Circle', 40); time.sleep(1.2)
    print('frames', n)
elif cmd == 'chase':
    g = G(); g.cmd('?')
    for s in sys.argv[2:]:
        a = U + int(s) * 14; g.cmd('M%x,1:00' % (a + 10)); g.cmd('M%x,1:01' % (a + 11))
    g.resume()
elif cmd == 'slots':
    for s in sys.argv[2:]: print(s, rd(U + int(s) * 14, 14).hex(' '))
elif cmd == 'wait':       # wait for the enemy phase: drain boxes (frames PREFIX_N), until units+cursor stable for 5 polls
    pre = sys.argv[2]; n = 0; last = None; same = 0; prev = None
    def snap(): return rd(U, 40 * 14) + rd(0x800ca488, 2)
    for _ in range(100):
        im = shot(pre + '_tmp.png')
        if box(im):
            if last is None or sum(ImageChops.difference(im, last).convert('L').point(lambda v: 255 if v > 24 else 0).histogram()[255:]) >= 1500:
                n += 1; im.save('%s_%d.png' % (pre, n)); last = im
            hold('Circle', 40); time.sleep(1.2); same = 0; continue
        s = snap(); same = same + 1 if s == prev else 0; prev = s
        if same >= 4: break
        time.sleep(3)
    print('frames', n, 'cursor', rd(0x800ca488, 2).hex())
elif cmd == 'defang':     # enemies: War/Ldr/Int = 1, troop % = 1
    g = G(); g.cmd('?')
    for s in range(15, 40):
        b = rd(U + s * 14, 14)
        if b[:2] != b'\xff\xff' and b[3] != 255 and b[9] != 4:
            g.cmd('M%x,1:01' % (U + s * 14 + 12)); g.cmd('M%x,3:010101' % (REC + struct.unpack('<H', b[:2])[0] * 0x2c + 0x19))
    g.resume()
