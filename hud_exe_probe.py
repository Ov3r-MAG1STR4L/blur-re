#!/usr/bin/env python3
"""Read-only check, in the shipped Blur.exe, of the HUD power-up icon code (2026-11-17). Patches nothing.

Finds and checks:
  * XT layout of UIPerkInfo (0x48 bytes in memory) and UiPerkDisplayParameters (16 entries, 0x480 bytes);
  * C_PerkDisplayParameters::GetPerkInfo (thiscall, 3 args, ret 0xC): its jump table and the Bolt ammo branches;
  * the 'index >= 100' tests in UIPerks::Render and UIPerks2::Render (vtable slot 10) and the V = pos.v +
    size.v * index arithmetic;
  * GetTextureParam bounds check.
Exits with an assertion error if any expected instruction is missing (other exe build).

usage: hud_exe_probe.py [Blur.exe]
"""
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files (x86)\Activision\Blur(TM)\Blur.exe"
SECTIONS = [(0x1000, 0xA51A00, 0x400), (0xA53000, 0x118200, 0xA51E00), (0xB6C000, 0x1AF000, 0xB6A000)]
GETPERKINFO = 0xC55320
TYPES = ["NONE(-1)", "Nitrous", "Shock", "Shunt", "Blindfire", "Barge", "Bomb", "Repair", "Shield", "Fan",
         "Stopwatch", "SuperShield"]

b = open(EXE, "rb").read()
md = Cs(CS_ARCH_X86, CS_MODE_32)


def v2o(v):
    r = v - 0x400000
    for va, size, raw in SECTIONS:
        if va <= r < va + size:
            return raw + r - va
    raise ValueError(hex(v))


def u32(v):
    return struct.unpack_from("<I", b, v2o(v))[0]


def cstr(v):
    o = v2o(v)
    return b[o:b.index(b"\0", o)].decode("latin1")


def dis(va, n):
    return list(md.disasm(b[v2o(va):v2o(va) + n], va))


def text_at(va, n):
    return [f"{i.mnemonic} {i.op_str}".strip() for i in dis(va, n)]


def xt_fields(table):
    """XT field records: (name ptr, type, 0, offset, flags), ended by a null name"""
    out, a = [], table
    while u32(a):
        out.append((cstr(u32(a)), u32(a + 12)))
        a += 20
    return out


def main():
    # 1. XT layout (records found by the string pointers, see POWERUPS_HUD.md §8)
    info = xt_fields(0x1105D20)
    params = xt_fields(0x1106068)
    print("UIPerkInfo fields      :", [(n, hex(o)) for n, o in info])
    print("UiPerkDisplayParameters:", [(n, hex(o)) for n, o in params])
    assert u32(0x1105CFC) == 0x48 and cstr(u32(0x1105CF8)) == "UIPerkInfo"
    assert u32(0x1105EEC) == 0x480 and cstr(u32(0x1105EE8)) == "UiPerkDisplayParameters"
    entry = {o: n for n, o in params}

    # 2. GetPerkInfo: mov eax, ecx / inc ecx / cmp ecx, 0xb / ja / jmp [ecx*4 + table]
    head = text_at(GETPERKINFO, 0x17)
    assert head[:5] == ["mov eax, ecx", "mov ecx, dword ptr [esp + 4]", "inc ecx", "cmp ecx, 0xb",
                        "ja 0xc553db"], head
    table = 0xC553E0
    print(f"\nGetPerkInfo {GETPERKINFO:#x} (thiscall this=&PerkDisplayParameters, type, amount, extraBoltMod; ret 0xc)")
    for k, t in enumerate(TYPES):
        target = u32(table + 4 * k)
        ins = dis(target, 8)[0]
        if target == 0xC553DB:
            what = "NULL (xor eax, eax)"
        elif ins.mnemonic == "add":
            what = entry[int(ins.op_str.split(", ")[1], 16)]
        elif ins.mnemonic == "ret":
            what = entry[0] + " (eax = this + 0)"
        else:
            what = f"{ins.mnemonic} {ins.op_str} (Bolt: by ammo, below)"
        print(f"  type {t:12} -> {target:#x}  {what}")
    print("  Blindfire branch:\n    " + "\n    ".join(text_at(0xC55355, 0x66)))

    # 3. 'index >= 100' in both renderers
    for name, vt, site, expect in (
            ("UIPerks::Render", 0xEE99F0, 0xC57FCE,
             ["mov ebx, dword ptr [ebp]", "cmp ebx, 0x64", "mov ecx, esi", "jge 0xc57fdc", "push 0",
              "jmp 0xc57fe1", "sub ebx, 0x64", "push 2"]),
            ("UIPerks2::Render", 0xEEAFF0, 0xC592B6,
             ["mov eax, dword ptr [edi]", "cmp eax, 0x64", "mov dword ptr [esp + 0x3c], eax", "mov ecx, esi",
              "jge 0xc592ce", "push 0", "call 0x74b270", "push 1", "jmp 0xc592dc",
              "sub dword ptr [esp + 0x3c], 0x64", "push 6", "call 0x74b270", "push 7"])):
        got = text_at(site, 0x40)[:len(expect)]
        assert got == expect, (name, got)
        print(f"\n{name}: vtable {vt:#x} slot 10 = {u32(vt + 40):#x}; test at {site:#x}:\n  " + "\n  ".join(got))
    uv = text_at(0xC580D9, 0x14)
    assert uv[:2] == ["cvtsi2ss xmm1, ebx", "fstp dword ptr [esp + 0x10]"] and "mulss xmm1, xmm0" in uv
    print("\nUIPerks UV (0xc580c4..0xc580f7): V = float(index) * [param+0x10] (size.v) + [param+8] (pos.v)")

    # 4. GetTextureParam bounds check
    gt = text_at(0x74B2FE, 0x1B)
    assert gt[1:5] == ["test eax, eax", "jl 0x74b319", "cmp eax, dword ptr [esi + 0x64]", "jge 0x74b319"], gt
    print("GetTextureParam 0x74b270: 0 <= n < count [gadget+0x64], else a static default param (texture 'null')")
    print("\nall checks passed")


if __name__ == "__main__":
    main()
