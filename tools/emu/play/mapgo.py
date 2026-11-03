"""mapgo.py CITY_ID: walk the free world-map cursor onto city CITY_ID (records 0x8010c354, 27 B, x +0x18, y +0x19; cursor
u16 pair 0x800ca440 = position * 2) with RAM feedback, 40 ms taps. Prints the final cursor and the city name token."""
import os, sys, subprocess, time, struct
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, R + '/tools/emu'); os.chdir(R)
import ram
PY = R + '/.venv/bin/python'
cid = int(sys.argv[1]) % 32            # cities.json ids are table*32 + index; the live records hold the current map's 32
def cur(): m = ram.shm(); return struct.unpack_from('<HH', m, 0xca440)
def city(i): m = ram.shm(); r = m[0x10c354 + i*27: 0x10c354 + (i+1)*27]; return r[0x18], r[0x19], r[0x1a]
tx, ty, fl = city(cid); tx *= 2; ty *= 2
print('target', tx, ty, 'flag', fl, 'cursor', cur(), flush=True)
for n in range(120):
    x, y = cur()
    if (x, y) == (tx, ty): break
    k = ('Right' if tx > x else 'Left') if abs(tx - x) >= abs(ty - y) else ('Down' if ty > y else 'Up')
    subprocess.run([PY, 'tools/emu/vpad.py', 'hold', k, '40'], stdout=subprocess.DEVNULL); time.sleep(0.35)
print('cursor', cur(), 'taps', n)
