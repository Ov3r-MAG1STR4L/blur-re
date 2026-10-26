#!/usr/bin/env python3
"""Read-only: find the log strings a Lua plugin keeps in Blur's memory ("<TAG>#<n>#...#ALLEND", e.g. musicctl's
MCALL) and print the most recent one. print_api output is visible nowhere, Lua strings live in the game's memory.
usage: read_luamarks.py [TAG]        (default MCALL)
"""
import re, sys
import pymem, pymem.memory


def main(tag="MCALL"):
    pm = pymem.Pymem("Blur.exe")
    pat = re.compile(re.escape(tag.encode()) + rb"#(\d+)#(.*?)#ALLEND", re.S)
    best = (-1, b"")
    seen = {}
    addr = 0
    while addr < 0x7FFF0000:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, addr)
        except Exception:
            break
        size = mbi.RegionSize or 0x1000
        if mbi.State == 0x1000 and mbi.Protect & 0x66 and not mbi.Protect & 0x100:   # committed, readable
            try:
                data = pm.read_bytes(addr, size)
                for m in pat.finditer(data):
                    seen[int(m.group(1))] = m.group(2)
                    if int(m.group(1)) > best[0]:
                        best = (int(m.group(1)), m.group(2))
            except Exception:
                pass
        addr += size
    print(f"{tag} #{best[0]}" if best[0] >= 0 else f"no {tag} string found")
    print(best[1].decode("latin-1"))
    if "--all" in sys.argv:        # every copy still in memory (older strings not yet collected)
        for n in sorted(seen):
            print(n, seen[n].decode("latin-1").strip().splitlines()[-1:])


if __name__ == "__main__":
    main(*[a for a in sys.argv[1:] if a != "--all"])
