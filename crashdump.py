#!/usr/bin/env python3
"""Read-only analysis of a Windows minidump of Blur.exe (WER LocalDumps, %LOCALAPPDATA%\\CrashDumps).

Prints: exception code and address, faulting module + offset, x86 registers, the instructions around the fault
(capstone, bytes taken from the dump), memory near the registers, the EBP chain and a stack scan for return
addresses (a value that points just after a CALL in a loaded module).

usage: crashdump.py DUMP.dmp [--stack N]
"""
import argparse
import struct

import capstone

CODES = {0xC0000005: "ACCESS_VIOLATION", 0xC0000094: "INT_DIVIDE_BY_ZERO", 0xC00000FD: "STACK_OVERFLOW",
         0x80000003: "BREAKPOINT", 0xC000001D: "ILLEGAL_INSTRUCTION", 0xC0000409: "STACK_BUFFER_OVERRUN"}
X86 = ["Edi", "Esi", "Ebx", "Edx", "Ecx", "Eax", "Ebp", "Eip", "SegCs", "EFlags", "Esp", "SegSs"]


class Dump:
    def __init__(self, path):
        self.d = d = open(path, "rb").read()
        assert d[:4] == b"MDMP", "not a minidump"
        n, rva = struct.unpack_from("<II", d, 8)
        self.streams = {}
        for k in range(n):
            t, size, at = struct.unpack_from("<III", d, rva + 12 * k)
            self.streams.setdefault(t, (size, at))
        self.arch = struct.unpack_from("<H", d, self.streams[7][1])[0] if 7 in self.streams else None
        self.mem = []                                          # (start, size, file offset)
        if 9 in self.streams:
            _, at = self.streams[9]
            count, base = struct.unpack_from("<QQ", d, at)
            for k in range(count):
                s, size = struct.unpack_from("<QQ", d, at + 16 + 16 * k)
                self.mem.append((s, size, base))
                base += size
        if 5 in self.streams:
            _, at = self.streams[5]
            for k in range(struct.unpack_from("<I", d, at)[0]):
                s, size, off = struct.unpack_from("<QII", d, at + 4 + 16 * k)
                self.mem.append((s, size, off))
        self.modules = []
        if 4 in self.streams:
            _, at = self.streams[4]
            for k in range(struct.unpack_from("<I", d, at)[0]):
                m = at + 4 + 108 * k
                base, size = struct.unpack_from("<QI", d, m)
                stamp, name_rva = struct.unpack_from("<II", d, m + 16)
                ln = struct.unpack_from("<I", d, name_rva)[0]
                self.modules.append((base, size, stamp, d[name_rva + 4:name_rva + 4 + ln].decode("utf-16-le")))

        self.images = {}                                       # module files, for code not in the dump

    def read(self, addr, n):
        for s, size, off in self.mem:
            if s <= addr and addr + n <= s + size:
                return self.d[off + addr - s:off + addr - s + n]
        for base, size, _, name in self.modules:               # code: from the module file (read only)
            if base <= addr and addr + n <= base + size and name.lower().endswith(".exe"):
                if name not in self.images:
                    import pefile
                    try:
                        self.images[name] = pefile.PE(name, fast_load=True).get_memory_mapped_image()
                    except OSError:
                        self.images[name] = None
                img = self.images[name]
                if img is not None and addr - base + n <= len(img):
                    return img[addr - base:addr - base + n]
        return None

    def module(self, addr):
        for base, size, _, name in self.modules:
            if base <= addr < base + size:
                return name, addr - base
        return None, None

    def where(self, addr):
        name, off = self.module(addr)
        return "%s+0x%x" % (name.split("\\")[-1], off) if name else "?"

    def exception(self):
        _, at = self.streams[6]
        tid = struct.unpack_from("<I", self.d, at)[0]
        code, flags, _, addr, nparams = struct.unpack_from("<IIQQI", self.d, at + 8)
        params = struct.unpack_from("<%dQ" % nparams, self.d, at + 8 + 32)
        csize, crva = struct.unpack_from("<II", self.d, at + 8 + 152)
        return tid, code, addr, params, self.d[crva:crva + csize]


def context_x86(ctx):
    return dict(zip(X86, struct.unpack_from("<12I", ctx, 156)))


def is_return(dump, value):
    """value just after a CALL instruction inside a loaded module"""
    if dump.module(value)[0] is None:
        return False
    b = dump.read(value - 7, 7)
    if b is None:
        return False
    return b[2] == 0xE8 or any(b[k] == 0xFF and (b[k + 1] & 0x38) == 0x10 for k in (1, 3, 4, 5))


def disasm(dump, addr, before=0x30, after=0x20):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    code = None
    for b in range(before, -1, -4):           # code pages near the fault may be partly missing
        code = dump.read(addr - b, b + after)
        if code is not None:
            before = b
            break
    if code is None:
        return ["  (code not in the dump)"]
    start = addr - before
    ins = []
    for skip in range(0, 16):                 # find a decoding that lands exactly on addr
        ins = list(md.disasm(code[skip:], start + skip))
        if any(i.address == addr for i in ins):
            break
    return ["%s %08x %-24s %s %s" % ("=>" if i.address == addr else "  ", i.address, i.bytes.hex(), i.mnemonic,
                                     i.op_str) for i in ins]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--stack", type=lambda v: int(v, 0), default=0x800, help="bytes of stack to scan")
    a = ap.parse_args()
    D = Dump(a.dump)
    tid, code, addr, params, ctx = D.exception()
    print("thread %d  exception 0x%08x %s at 0x%08x (%s)" % (tid, code, CODES.get(code, ""), addr, D.where(addr)))
    if code == 0xC0000005 and len(params) >= 2:
        print("  %s of address 0x%08x" % ({0: "read", 1: "write", 8: "execute"}.get(params[0], params[0]), params[1]))
    print("arch %s, context %d bytes" % ({0: "x86", 9: "amd64"}.get(D.arch, D.arch), len(ctx)))
    r = context_x86(ctx)
    print("registers: " + "  ".join("%s=%08x" % (k, r[k]) for k in X86 if not k.startswith("Seg")))
    for k in ("Eax", "Ebx", "Ecx", "Edx", "Esi", "Edi", "Ebp"):
        b = D.read(r[k], 16)
        print("  [%s] %s %s" % (k, D.where(r[k]), b.hex(" ") if b else "(not readable in the dump)"))
    print("code:")
    print("\n".join(disasm(D, r["Eip"])))
    print("EBP chain:")
    ebp = r["Ebp"]
    for _ in range(24):
        fr = D.read(ebp, 8)
        if fr is None:
            break
        nxt, ret = struct.unpack("<II", fr)
        print("  ebp %08x ret %08x %s" % (ebp, ret, D.where(ret)))
        if nxt <= ebp:
            break
        ebp = nxt
    print("stack scan (return addresses):")
    for k in range(0, a.stack, 4):             # word by word: the stack may span several dump ranges
        w = D.read(r["Esp"] + k, 4)
        if w is None:
            continue
        v = struct.unpack("<I", w)[0]
        if is_return(D, v):
            print("  esp+%04x %08x %s" % (k, v, D.where(v)))
    print("modules:")
    for base, size, stamp, name in D.modules[:40]:
        print("  %08x %08x %s" % (base, size, name))


if __name__ == "__main__":
    main()
