"""step.py TARGET_SLOT PREFIX: Liu Bei moves (one key) toward a hex adjacent to the target, Waits, drains dialogue"""
import os, sys, struct, subprocess, time
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, R + '/tools/emu'); os.chdir(R)
import ram
U = 0x8017957c
def rd(va, n): return bytes(ram.shm()[va - 0x80000000: va - 0x80000000 + n])
def pos(s): b = rd(U + s*14, 14); return b[3], b[4], b[9]
def nb(x, y):   # odd-r: odd rows shifted right
    if y & 1: return {(x,y-1),(x+1,y-1),(x-1,y),(x+1,y),(x,y+1),(x+1,y+1)}
    return {(x-1,y-1),(x,y-1),(x-1,y),(x+1,y),(x-1,y+1),(x,y+1)}
t = int(sys.argv[1]); pre = sys.argv[2]
lx, ly, _ = pos(0); tx, ty, tg = pos(t)
print('liu', (lx, ly), 'target', (tx, ty), 'gone' if tg == 4 else '')
keys = []
if (tx, ty) not in nb(lx, ly):
    # one step: pick the neighbour of Liu Bei nearest to the target's neighbours
    best = min(nb(lx, ly), key=lambda h: min(abs(h[0]-a)+abs(h[1]-b) for a, b in nb(tx, ty)))
    dx, dy = best[0]-lx, best[1]-ly
    keys = ['Up' if dy < 0 else 'Down'] if dy else ['Left' if dx < 0 else 'Right']
    print('step', best, keys)
subprocess.run([R + '/tools/emu/play/route.sh', '0'] + keys)
time.sleep(1); print('liu now', pos(0)[:2])
subprocess.run([R + '/.venv/bin/python', R + '/tools/emu/vpad.py', 'hold', 'Down', '250'], stdout=subprocess.DEVNULL); time.sleep(3)
subprocess.run([R + '/.venv/bin/python', os.path.dirname(os.path.abspath(__file__)) + '/xp.py', 'drain', pre])
time.sleep(3)
subprocess.run([R + '/.venv/bin/python', os.path.dirname(os.path.abspath(__file__)) + '/xp.py', 'drain', pre + 'b'])
print('target slot', rd(U + t*14, 14).hex(' '))
