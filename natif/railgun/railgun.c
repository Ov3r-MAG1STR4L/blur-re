/* railgun.dll - the Bolt becomes a "Railgun" (one shot that goes through walls and vehicles), test copy only.

   Loaded by AMAX's d3d9.dll from amax\dlls (it loads *.dll and *.asi), like b2gravity. Blur.exe = AMAX's exe,
   addresses checked on it (2026-11-16, capstone, read only). Source names: BlurRebuilt (leaked code).
   A real 12th pickup type is not possible without rewriting the game: the pickup is identified everywhere by its
   enum E_PICKUP_TYPE (store, HUD, network, AI) and RaceLogicCore::GetPickupType returns the first PickupType of
   that enum. So the Railgun is the Bolt (E_PICKUP_TYPE_BLINDFIRE = 3) changed while this dll is loaded, its
   settings in pickups.bin (railgun_install.py). Patches, each applied only if the original bytes are there:
   1. C_VehicleComponent_Pickups::GetNumShotsAwarded 0x4699F0 (3 for the Bolt, 1 otherwise) -> always 1;
      its 3 inlined copies (0x470858, 0x47909A, 0x47BE36: "numShots = type" when type == 3) -> nop, the shot
      count stays at the 1 set just before.
   2. C_PickupBlindfireProjectile::Trigger 0xBEC540 (vehicle hit: RegisterHit then KillPickup(-1, HIT_VEHICLE)):
      the KillPickup call at 0xBECB2A is skipped for a Bolt projectile -> it flies on. CheckCanHit keeps a
      per-vehicle "already hit" flag (mVehiclesHitMajor), so each car is hit once per shot.
   3. C_PickupProjectile::CheckCollisions 0xBE6200: a wall hit explodes the projectile only if the thin ray also
      sees a wall (CheckIsValidWallCollision 0xBE4D10 called at 0xBE654B); for a Bolt it answers "no wall"
      -> no explosion, the ground-following ray puts it back on the ground behind the wall.
   Bolt projectile = vtable 0xEE1578 (C_PickupBlindfireProjectile, written by its constructor at 0xBEE5FA) or
   0xEE15D8 (the reversed Bolt, same code but PostDelayInitialise). Other projectiles are untouched.
   Still killed: out of the world (no ground under it, PreUpdateTwo), old age (Perks.Blindfire.LiveTime, 10 s),
   another pickup with more damage than its Health. Log: railgun.log next to the dll.
*/
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <share.h>

#define VT_BOLT      0xEE1578
#define VT_BOLT_REV  0xEE15D8
#define KILL_PICKUP  0xBA6AC0      /* C_PickupBase::KillPickup(int byVehicle, cause), thiscall, ret 8 */
#define WALL_CHECK   0xBE4D10      /* C_PickupProjectile::CheckIsValidWallCollision(result), thiscall, ret 4 */

static FILE *logfile = NULL;
static volatile LONG passes = 0, walls = 0;

static __declspec(naked) void kill_thunk(void)
{
    __asm {
        mov eax, [ecx]
        cmp eax, VT_BOLT
        je skip
        cmp eax, VT_BOLT_REV
        je skip
        mov eax, KILL_PICKUP
        jmp eax
    skip:
        lock inc passes
        ret 8
    }
}

static __declspec(naked) void wall_thunk(void)
{
    __asm {
        mov eax, [ecx]
        cmp eax, VT_BOLT
        je nowall
        cmp eax, VT_BOLT_REV
        je nowall
        mov eax, WALL_CHECK
        jmp eax
    nowall:
        lock inc walls
        xor eax, eax
        ret 4
    }
}

/* orig / repl: hex bytes; call_to != NULL: repl ignored, "E8 rel32" to call_to */
typedef struct { unsigned addr; int len; const char *orig; const char *repl; void *call_to; const char *what; } Patch;

static Patch patches[] = {
    {0x4699F0, 8, "57bf03000000b801", "b801000000c20400", NULL, "GetNumShotsAwarded -> 1"},
    {0x470858, 2, "8bfd", "9090", NULL, "inlined shot count 1"},
    {0x47909A, 2, "8bfd", "9090", NULL, "inlined shot count 2"},
    {0x47BE36, 2, "8bdf", "9090", NULL, "inlined shot count 3"},
    {0xBECB2A, 5, "e8919ffbff", NULL, NULL, "Trigger: no KillPickup on vehicle hit"},
    {0xBE654B, 5, "e8c0e7ffff", NULL, NULL, "CheckCollisions: walls ignored"},
};

static void say(const char *fmt, ...)
{
    va_list a;
    if (!logfile) return;
    va_start(a, fmt); vfprintf(logfile, fmt, a); va_end(a);
    fputc('\n', logfile); fflush(logfile);
}

static void unhex(const char *s, unsigned char *out, int n)
{
    int i;
    unsigned v;
    for (i = 0; i < n; i++) { sscanf_s(s + 2 * i, "%2x", &v); out[i] = (unsigned char)v; }
}

static int readable(const void *p, size_t n)
{
    MEMORY_BASIC_INFORMATION m;
    if (!p || !VirtualQuery(p, &m, sizeof m) || m.State != MEM_COMMIT) return 0;
    if (m.Protect & (PAGE_NOACCESS | PAGE_GUARD)) return 0;
    return (const char *)p + n <= (const char *)m.BaseAddress + m.RegionSize;
}

static void apply(void)
{
    unsigned char want[16], put[16];
    int i, n = sizeof patches / sizeof *patches;
    DWORD old;
    patches[4].call_to = (void *)kill_thunk;
    patches[5].call_to = (void *)wall_thunk;
    for (i = 0; i < n; i++) {                       /* all or nothing: check every site first */
        Patch *p = &patches[i];
        unhex(p->orig, want, p->len);
        if (!readable((void *)p->addr, p->len) || memcmp((void *)p->addr, want, p->len)) {
            say("bytes at 0x%X (%s) are not the expected ones (other Blur.exe?): NOTHING patched", p->addr, p->what);
            return;
        }
    }
    for (i = 0; i < n; i++) {
        Patch *p = &patches[i];
        unsigned char *site = (unsigned char *)p->addr;
        if (p->call_to) {
            put[0] = 0xE8;
            *(int *)(put + 1) = (int)((unsigned char *)p->call_to - (site + 5));
        } else {
            unhex(p->repl, put, p->len);
        }
        VirtualProtect(site, p->len, PAGE_EXECUTE_READWRITE, &old);
        memcpy(site, put, p->len);
        VirtualProtect(site, p->len, old, &old);
        FlushInstructionCache(GetCurrentProcess(), site, p->len);
        say("patched 0x%X: %s", p->addr, p->what);
    }
}

static DWORD WINAPI reporter(LPVOID unused)
{
    LONG lp = 0, lw = 0;
    (void)unused;
    for (;;) {                                      /* counts only: shows the hooks fire in game */
        Sleep(2000);
        if (passes != lp || walls != lw) {
            lp = passes; lw = walls;
            say("so far: %ld vehicle hit(s) passed through, %ld wall hit(s) ignored", lp, lw);
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH], *slash;
        HANDLE t;
        DisableThreadLibraryCalls(h);
        GetModuleFileNameA(h, path, sizeof path);
        slash = strrchr(path, '\\');
        if (slash) strcpy_s(slash + 1, sizeof path - (slash + 1 - path), "railgun.log");
        logfile = _fsopen(path, "w", _SH_DENYNO);   /* readable while the game runs */
        say("railgun loaded");
        apply();
        t = CreateThread(NULL, 0, reporter, NULL, 0, NULL);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
