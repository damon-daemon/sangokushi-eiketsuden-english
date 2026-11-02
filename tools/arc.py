"""The root *.TIM files: archives of LZ-compressed (or raw) entries; the offsets are in the program.

Loader 0x8001e4cc(file, entry, buf, ?): file index into the name table 0x80099ec8, offsets
from table 0x80099eec[file] (u32, entry n = offs[n]..offs[n+1]). Decompressor 0x80067bd0.

Stream: a u16 bit window (MSB first, refilled from the byte stream with LE words as bits are used)
and, in the same byte stream, flag bytes (MSB first, 8 tokens each). Flag 1 = literal byte.
Flag 0 = copy, length code + distance code from the window. Length code 0x01fc in the window = end.
"""
import struct

EXE_BASE = 0x80010000 - 0x800
NAMES = ['HEX', 'KAO', 'MARK', 'MMAP', 'MP', 'STILL', 'SIRO', 'MPKAO', 'TITLE']
NAME_TAB, OFF_TAB = 0x80099ec8, 0x80099eec


def table_va(exe, file):
    return struct.unpack_from('<I', exe, OFF_TAB - EXE_BASE + 4 * file)[0]


def offsets(exe, file, size):
    """entry offsets in the archive, with the final one (= size or the table's own end mark)"""
    at = table_va(exe, file) - EXE_BASE
    out = []
    while True:
        v = struct.unpack_from('<I', exe, at)[0]
        if out and v <= out[-1] or v > size:
            break
        out.append(v)
        at += 4
        if v == size:
            break
    return out


def unpack(d, at=0, limit=0x100000):
    """-> (bytes, end offset); raises on data that is not a valid stream"""
    p = at
    win = 0
    have = 0
    cur = 0

    def bits(n):
        nonlocal win, have, cur, p
        win = (win << n) & 0xffff
        if have < n:
            n -= have
            win |= (cur & ((1 << have) - 1)) << n
            cur = d[p] | d[p + 1] << 8
            p += 2
            have = 16 - n
            win |= (cur >> have) & ((1 << n) - 1)
        else:
            have -= n
            win |= (cur >> have) & ((1 << n) - 1)
    bits(16)
    out = bytearray()
    while True:
        flags = d[p]
        p += 1
        for _ in range(8):
            if flags & 0x80:
                out.append(d[p])
                p += 1
            else:
                v = win
                if v & 0x8000:
                    ln, n = 1, 0
                elif v & 0x4000:
                    ln, n = (v & 0x6000) >> 13, 2
                elif v & 0x2000:
                    ln, n = (v & 0x3800) >> 11, 4
                elif v & 0x1000:
                    ln, n = (v & 0x1e00) >> 9, 6
                elif v & 0x800:
                    ln, n = (v & 0xf80) >> 7, 8
                elif v & 0x400:
                    ln, n = (v & 0x7e0) >> 5, 10
                elif v & 0x200:
                    ln, n = (v & 0x3f8) >> 3, 12
                else:
                    ln, n = ((v & 0x1fc) >> 2) | 0x80, 13
                    if ln == 0xff:
                        return bytes(out), p
                if n:
                    bits(n)
                v = win & 0x7fff
                if v < 0x800:
                    dist, n = (v & 0x600) >> 9, 7
                elif v < 0xc00:
                    dist, n = ((v & 0x300) >> 8) | 4, 8
                elif v < 0x1800:
                    dist, n = (((v - 0xc00) & 0xf80) >> 7) + 8, 9
                elif v < 0x3000:
                    dist, n = (((v - 0x1800) & 0x1fc0) >> 6) + 0x20, 10
                elif v < 0x4000:
                    dist, n = ((v & 0x1fff) | 0x1000) >> 5, 11
                elif v < 0x5000:
                    dist, n = ((v & 0x1fff) | 0x1000) >> 4, 12
                elif v < 0x6000:
                    dist, n = ((v & 0x1fff) | 0x1000) >> 3, 13
                elif v < 0x7000:
                    dist, n = ((v & 0x1fff) | 0x1000) >> 2, 14
                else:
                    dist, n = ((v & 0x1fff) | 0x1000) >> 1, 15
                bits(n)
                src = len(out) - dist - 1
                if src < 0:
                    raise ValueError('bad distance')
                for i in range(ln + 1):
                    out.append(out[src + i])
                if len(out) > limit:
                    raise ValueError('too long')
            flags = flags << 1 & 0xff


def pack(data):
    """literal-only stream (9/8 of the size), which the game's decompressor reads as it is"""
    out = bytearray(b'\xfc\x01')
    for i in range(0, len(data), 8):
        chunk = data[i:i + 8]
        out.append(0xff if len(chunk) == 8 else (0xff00 >> len(chunk)) & 0xff)
        out += chunk
    if len(data) % 8 == 0:
        out.append(0)
    return bytes(out)


def pack_runs(data):
    """literals plus runs of one byte (a match at distance 0, 3-255 bytes): for tables that are mostly padding"""
    tokens, i = [], 0
    while i < len(data):
        n = 1
        while i + n < len(data) and data[i + n] == data[i] and n < 255:
            n += 1
        if i and data[i - 1] == data[i] and n >= 3:
            tokens.append(n)
            i += n
        else:
            tokens.append(data[i:i + 1])
            i += 1
    tokens.append(None)
    # the match codes as one bit string: k zeros + the length - 1 in k + 1 bits (k = 7: its top bit implied), then the distance code
    code = ''
    for t in tokens:
        if isinstance(t, int):
            k = (t - 1).bit_length() - 1
            code += '0' * k + format(t - 1, 'b')[k == 7:] + '000000'
    code += format(0x01fc, '016b') + '0' * 32
    # bytes in the order the decoder fetches them: a word of the bit string whenever its window needs one
    out, word, have = bytearray(), 0, 0

    def take(n):
        nonlocal word, have
        if have < n:
            n -= have
            out.extend(int(code[word:word + 16], 2).to_bytes(2, 'little'))
            word += 16
            have = 16 - n
        else:
            have -= n
    take(16)
    for g in range(0, len(tokens), 8):
        group = tokens[g:g + 8]
        out.append(sum(0x80 >> j for j, t in enumerate(group) if isinstance(t, bytes)))
        for t in group:
            if isinstance(t, bytes):
                out += t
            elif t is not None:
                k = (t - 1).bit_length() - 1
                if k:
                    take(min(2 * k, 13))
                take(7)
    assert unpack(bytes(out))[0] == data
    return bytes(out)
