"""Read-only full-process scan helpers (committed, readable regions)."""
import ctypes, ctypes.wintypes as W

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", W.DWORD),
                ("RegionSize", ctypes.c_size_t), ("State", W.DWORD), ("Protect", W.DWORD), ("Type", W.DWORD)]

def regions(pm):
    k32, a, m = ctypes.windll.kernel32, 0, MBI()
    while a < 0x7FFF0000 and k32.VirtualQueryEx(pm.process_handle, ctypes.c_void_p(a), ctypes.byref(m), ctypes.sizeof(m)):
        base, size = m.BaseAddress or 0, m.RegionSize
        if m.State == 0x1000 and m.Protect & 0xEE and not m.Protect & 0x100:     # committed, readable, no guard
            yield base, size
        a = base + size

def scan(pm, needles):
    """needles: {bytes: label} -> list of (addr, label)"""
    out = []
    for base, size in regions(pm):
        try:
            b = pm.read_bytes(base, size)
        except Exception:
            continue
        for n, lab in needles.items():
            k = b.find(n)
            while k >= 0:
                out.append((base + k, lab)); k = b.find(n, k + 1)
    return out
