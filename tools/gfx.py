"""Redraw the kanji labels of MARK.TIM entry 1 (stat plates, 3 x 4 cells of 32x16, 4bpp, drawn from
VRAM (960, 176)) in English with the VWF font. Build time only; own font, no Koei pixels stored.

  python tools/gfx.py preview out.png     before/after, grey by palette index
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(__file__))
import arc, pixfont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK_FILE = 2
LABEL_ENTRY = 1
LABEL_W, CELL_W, CELL_H = 96, 32, 16
# row by row: 攻撃 防御 耐久 / 策略 武力 統率 / 知力 経験 武器 / 防具 馬 金
LABELS = ['Atk', 'Def', 'HP', 'Strat', 'War', 'Ldr', 'Int', 'Exp', 'Wpn', 'Arm', 'Horse', 'Gold']


def get(u, x, y):
    b = u[y * (LABEL_W // 2) + x // 2]
    return b >> 4 if x & 1 else b & 15


def put(u, x, y, i):
    o = y * (LABEL_W // 2) + x // 2
    u[o] = (u[o] & 0x0f) | (i << 4) if x & 1 else (u[o] & 0xf0) | i


def text_width(s, g):
    return sum(g[c][1] for c in s) - pixfont.SPACING


def labels(data):
    """decompressed entry -> the same with English plates"""
    u = bytearray(data)
    g = pixfont.glyphs()
    for n, s in enumerate(LABELS):
        cx, cy = (n % 3) * CELL_W, (n // 3) * CELL_H
        fill = get(u, cx + 3, cy + 3)              # plate colour, just inside the frame
        hist = {}
        for y in range(cy + 2, cy + CELL_H - 2):
            for x in range(cx + 2, cx + CELL_W - 2):
                i = get(u, x, y)
                if i != fill:
                    hist[i] = hist.get(i, 0) + 1
                put(u, x, y, fill)
        ink = max(hist, key=hist.get)              # the kanji's colour
        w = text_width(s, g)
        assert w <= CELL_W - 4, s
        x = cx + (CELL_W - w) // 2
        y0 = cy + 3
        for c in s:
            rows, adv = g[c]
            for r, bits in enumerate(rows):
                for b in range(8):
                    if bits & (0x80 >> b):
                        put(u, x + b, y0 + r, ink)
            x += adv
    return bytes(u)


def build_mark(exe, data):
    """MARK.TIM contents -> new contents; exe's offset table (bytearray) follows"""
    va = arc.table_va(exe, MARK_FILE)
    of = arc.offsets(exe, MARK_FILE, len(data))
    a, b = of[LABEL_ENTRY], of[LABEL_ENTRY + 1]
    new = arc.pack(labels(arc.unpack(data, a)[0]))
    delta = len(new) - (b - a)
    at = va - arc.EXE_BASE
    for n in range(LABEL_ENTRY + 1, len(of)):
        struct.pack_into('<I', exe, at + 4 * n, of[n] + delta)
    return data[:a] + new + data[b:]


def preview(path):
    from PIL import Image
    exe = open(os.path.join(ROOT, 'extract', 'SLPS_003.09'), 'rb').read()
    d = open(os.path.join(ROOT, 'extract', 'MARK.TIM'), 'rb').read()
    of = arc.offsets(exe, MARK_FILE, len(d))
    old = arc.unpack(d, of[LABEL_ENTRY])[0]
    new = arc.unpack(arc.pack(labels(old)), 0)[0]
    im = Image.new('L', (LABEL_W * 2 + 4, 64), 0)
    for k, u in enumerate((old, new)):
        for y in range(64):
            for x in range(LABEL_W):
                im.putpixel((x + k * (LABEL_W + 4), y), get(u, x, y) * 17)
    im.resize((im.width * 4, im.height * 4), 0).save(path)


if __name__ == '__main__':
    preview(sys.argv[2])
