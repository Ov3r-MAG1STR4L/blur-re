#!/usr/bin/env python3
"""Minimal Lua 5.1 bytecode lister (the game's menu scripts, see blurui.py): functions, constants, instructions.
Header checked: '\\x1bLuaQ', little-endian, int 4, size_t 4, instruction 4, number 8 (double).
usage: luadis.py FILE.luac
"""
import struct, sys

OPS = ("MOVE LOADK LOADBOOL LOADNIL GETUPVAL GETGLOBAL GETTABLE SETGLOBAL SETUPVAL SETTABLE NEWTABLE SELF ADD SUB "
       "MUL DIV MOD POW UNM NOT LEN CONCAT JMP EQ LT LE TEST TESTSET CALL TAILCALL RETURN FORLOOP FORPREP TFORLOOP "
       "SETLIST CLOSE CLOSURE VARARG").split()
ABX = {"LOADK", "GETGLOBAL", "SETGLOBAL", "CLOSURE"}
ASBX = {"JMP", "FORLOOP", "FORPREP"}


class R:
    def __init__(self, b):
        self.b, self.o = b, 0

    def u8(self):
        self.o += 1
        return self.b[self.o - 1]

    def i32(self):
        self.o += 4
        return struct.unpack_from("<i", self.b, self.o - 4)[0]

    def f64(self):
        self.o += 8
        return struct.unpack_from("<d", self.b, self.o - 8)[0]

    def s(self):
        n = struct.unpack_from("<I", self.b, self.o)[0]
        self.o += 4
        v = self.b[self.o:self.o + n - 1].decode("latin-1") if n else None
        self.o += n
        return v


def function(r):
    f = {"source": r.s(), "line": r.i32(), "lastline": r.i32()}
    f["nups"], f["nparams"], f["vararg"], f["stack"] = r.u8(), r.u8(), r.u8(), r.u8()
    f["code"] = [r.i32() & 0xFFFFFFFF for _ in range(r.i32())]
    k = []
    for _ in range(r.i32()):
        t = r.u8()
        k.append(None if t == 0 else bool(r.u8()) if t == 1 else r.f64() if t == 3 else r.s())
    f["k"] = k
    f["protos"] = [function(r) for _ in range(r.i32())]
    f["lines"] = [r.i32() for _ in range(r.i32())]
    f["locals"] = [(r.s(), r.i32(), r.i32()) for _ in range(r.i32())]
    f["upvals"] = [r.s() for _ in range(r.i32())]
    return f


def rk(f, x):
    return repr(f["k"][x - 256]) if x >= 256 else f"r{x}"


def dump(f, path="main", out=print):
    out(f"-- function {path} (line {f['line']}, {f['nparams']} params)")
    for pc, ins in enumerate(f["code"]):
        op = OPS[ins & 0x3F]
        a, c, b = (ins >> 6) & 0xFF, (ins >> 14) & 0x1FF, (ins >> 23) & 0x1FF
        bx = ins >> 14
        if op in ABX:
            arg = f"{a} {bx}" + (f"  ; {f['k'][bx]!r}" if op != "CLOSURE" else f"  ; {path}.{bx}")
        elif op in ASBX:
            arg = f"{a} {bx - 131071}  ; -> {pc + 1 + bx - 131071}"
        elif op in ("GETTABLE", "SELF"):
            arg = f"{a} {b} {c}  ; [{rk(f, c)}]"
        elif op in ("SETTABLE",):
            arg = f"{a} {b} {c}  ; [{rk(f, b)}] = {rk(f, c)}"
        elif op in ("ADD", "SUB", "MUL", "DIV", "MOD", "POW", "EQ", "LT", "LE"):
            arg = f"{a} {b} {c}  ; {rk(f, b)} {rk(f, c)}"
        else:
            arg = f"{a} {b} {c}"
        out(f"  {pc:4} {op:9} {arg}")
    for i, p in enumerate(f["protos"]):
        dump(p, f"{path}.{i}", out)


def load(b):
    assert b[:5] == b"\x1bLuaQ" and b[6:12] == bytes([1, 4, 4, 4, 8, 0]), "not a Lua 5.1 LE chunk"
    r = R(b)
    r.o = 12
    return function(r)


if __name__ == "__main__":
    dump(load(open(sys.argv[1], "rb").read()))
