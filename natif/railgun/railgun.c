/* railgun.dll - "Railgun" power-up for Blur 1 PC, test copy only (v2, 2026-11-16).

   Loaded by AMAX's d3d9.dll from amax\dlls. Blur.exe = AMAX's exe; addresses checked on it with capstone (read
   only), names from the leaked source (BlurRebuilt). A 12th pickup enum is out of reach, but the game has a cut
   one with everything wired: SuperShield (E_PICKUP_TYPE_SUPER_SHIELD = 10: own PickupType in pickups.bin, own HUD
   entry in ui.bin, own name in common.loc, 1 shot, fired through the normal path). The Railgun takes its place;
   the Bolt stays the normal Bolt.
   1. Spawn: PickupPositionActor::SetRandomPickupType skips SuperShield ("cmp ebp, 0Ah" at 0xB5B497): a thunk lets
      it through with probability `spawn` (railgun.txt) per draw.
   2. AI cannot use type 10 (cPerkSkillUsage knows types 0-7): when an AI picks one up (PickupPickedUp handler,
      GetNumShotsAwarded call at 0x47CC60, msg type at [edi+0x14], component vehicle index [ecx+0x2C]) it gets a
      Bolt instead. Player index: byte [[[[[0x11AA04C]+0xC90]+0x30]+0xA10]+0x2EC].
   3. Firing: C_PickupsManager::CreatePickup switch (0xBAADBA, table 0xBAB5D8): entry 10 (SuperShield,
      0xBAB400) -> a thunk that flags "next Bolt is a railgun" and goes to the Bolt case (0xBAAF59, which honours
      Normal / Reversed). The Bolt constructor 0xBEE5D0 (called at 0xBAAF9F, 0xBAB083 and from the reversed Bolt's
      constructor at 0xBEED50) is wrapped: a flagged one is remembered and gets the railgun's speed (+0x158),
      radius (+0x150), height (+0x154), fall rate (+0x15C), health (+0xB0, C_PickupBase::mHealth).
      The same thunk sets the firing delay (PickupCreationStruct +0x10; sub-type +4, 2 = reversed): `delay` forward,
      `rear_delay` backward (faster: a defensive shot), and remembers the direction for the sound.
   4. Trigger (vehicle hit, vtable [18] of both Bolt vtables 0xEE1578 / 0xEE15D8 -> 0xBEC540) wrapped for a railgun:
      the Bolt balancing data it shares ([+0x56C] -> DamageInflicted at +0x1C) holds the railgun damage only during
      the call (damage = base x falloff[pierced]), a hit is seen by the autopsy byte +0xF0 (set to the target), then
      a shield is downed: logic actor (0xB915D0 on [[0x11AA04C]+0xC90]+0x50) mShieldTime +0xBC > 0 -> mShieldHealth
      +0xC0 = 0 (C_PickupShield::Update kills the shield). KillPickup at 0xBECB2A is skipped: it flies on.
   5. Walls: CheckIsValidWallCollision call at 0xBE654B answers "no wall" for a railgun; a wall counts as pierced
      once per WALL_GAP_MS.
   6. Mines, Shunts, Bolts: C_PickupBase::GetDamageToApply 0xBA8CC0 returns `crush` for a railgun (they die), and
      its health is huge (they do not stop it).
   7. Sound: railgun_fire.wav forward, railgun_fire_rear.wav backward (railgun_install.py: charge during the
      delay, then the shot) played by
      Windows when a railgun is created; only the player fires them, so no 3D / game audio is needed.
   Log: railgun.log. Settings: railgun.txt next to the dll ("key value" lines, '#' comments).
*/
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <share.h>
#include <mmsystem.h>
#pragma comment(lib, "winmm.lib")

#define APP          0x11AA04C
#define VT_BOLT      0xEE1578
#define VT_BOLT_REV  0xEE15D8
#define TRIGGER      0xBEC540
#define KILL_PICKUP  0xBA6AC0
#define WALL_CHECK   0xBE4D10
#define BOLT_CTOR    0xBEE5D0
#define BOLT_CASE    0xBAAF59
#define DMG_TO_APPLY_CONT 0xBA8CC9
#define GET_LOGIC_ACTOR   0xB915D0
#define SHOTS_AWARDED     0x4699F0
#define SPAWN_IGNORE 0xB5B4A1
#define WALL_GAP_MS  150            /* ponytail: wall dedupe by time; a per-frame count if thick buildings miscount */

/* settings (railgun.txt) */
static float speed = 600.f, radius = 0.8f, height = 0.3f, fallrate = 2.f, spawn = 0.35f;
static float base_damage = 50.f, falloff[3] = {1.5f, 1.0f, 0.5f};
static int crush = 9999;

static float front_delay = 1.0f, rear_delay = 0.5f;   /* s between the button and the shot */
static char sound[2][MAX_PATH];     /* railgun_fire.wav / railgun_fire_rear.wav next to the dll: charge + shot */
static FILE *logfile = NULL;
static volatile LONG passes = 0, walls = 0, shields = 0, fired = 0;

typedef struct { char *p; int pierced; DWORD last_wall; } Rail;
#define MAX_RAILS 32
static Rail rails[MAX_RAILS];
static int next_is_rail = 0;

static void say(const char *fmt, ...)
{
    va_list a;
    if (!logfile) return;
    va_start(a, fmt); vfprintf(logfile, fmt, a); va_end(a);
    fputc('\n', logfile); fflush(logfile);
}

static unsigned rd(unsigned a)
{
    MEMORY_BASIC_INFORMATION m;
    if (!a || !VirtualQuery((void *)a, &m, sizeof m) || m.State != MEM_COMMIT || (m.Protect & (PAGE_NOACCESS | PAGE_GUARD)))
        return 0;
    return *(unsigned *)a;
}

static Rail *rail_of(void *p)
{
    int i;
    for (i = 0; i < MAX_RAILS; i++) if (rails[i].p == p) return &rails[i];
    return NULL;
}

static int __cdecl is_rail(void *p) { return rail_of(p) != NULL; }

static int __cdecl is_human(int vehicle)
{
    unsigned r = rd(APP);
    if (r) r = rd(r + 0xC90);
    if (r) r = rd(r + 0x30);
    if (r) r = rd(r + 0xA10);
    return r && vehicle == (int)(rd(r + 0x2EC) & 0xFF);
}

static int __cdecl spawn_roll(void) { return rand() < (int)(spawn * RAND_MAX); }

/* ---- 3. creation ---- */
static void __cdecl after_ctor(char *self)
{
    Rail *r = rail_of(self);
    if (r) r->p = NULL;                              /* pooled memory: a normal Bolt may reuse a railgun's slot */
    int rear = next_is_rail == 2;
    if (!next_is_rail) return;
    next_is_rail = 0;
    if (!(r = rail_of(NULL))) { say("more than %d railguns alive: this one is a plain Bolt", MAX_RAILS); return; }
    r->p = self; r->pierced = 0; r->last_wall = 0;
    *(float *)(self + 0x150) = radius;
    *(float *)(self + 0x154) = height;
    *(float *)(self + 0x158) = speed;
    *(float *)(self + 0x15C) = fallrate;
    *(float *)(self + 0xB0) = 1e9f;
    InterlockedIncrement(&fired);
    if (sound[rear][0])                              /* only the player fires railguns (AIs get Bolts) */
        PlaySoundA(sound[rear], NULL, SND_ASYNC | SND_FILENAME | SND_NODEFAULT);
}

/* PickupCreationStruct (esi in CreatePickup): +0 type, +4 sub-type (2 = reversed), +0x10 delay before the shot */
static void __cdecl super_setup(char *info)
{
    int rear = *(int *)(info + 4) == 2;
    next_is_rail = rear ? 2 : 1;
    *(float *)(info + 0x10) = rear ? rear_delay : front_delay;
}

static __declspec(naked) void super_case(void)
{
    __asm {
        push ecx
        push edx
        push esi
        call super_setup
        add esp, 4
        pop edx
        pop ecx
        mov eax, BOLT_CASE
        jmp eax
    }
}

static __declspec(naked) void ctor_wrap(void)       /* thiscall, 6 stack args, ret 0x18 */
{
    __asm {
        push ecx
        push dword ptr [esp + 0x1C]
        push dword ptr [esp + 0x1C]
        push dword ptr [esp + 0x1C]
        push dword ptr [esp + 0x1C]
        push dword ptr [esp + 0x1C]
        push dword ptr [esp + 0x1C]
        mov eax, BOLT_CTOR
        call eax
        pop ecx
        push eax
        push ecx
        call after_ctor
        add esp, 4
        pop eax
        ret 0x18
    }
}

/* ---- 4. vehicle hit ---- */
typedef void (__fastcall *TriggerFn)(void *self, void *edx, int idx);       /* thiscall through fastcall */
typedef char *(__fastcall *ActorFn)(void *layer, void *edx, int idx);

static void __fastcall trigger_hook(char *self, void *edx, int idx)
{
    Rail *r = rail_of(self);
    char *bal;
    int old;
    (void)edx;
    if (!r) { ((TriggerFn)TRIGGER)(self, NULL, idx); return; }
    bal = (char *)rd((unsigned)self + 0x56C);
    old = bal ? *(int *)(bal + 0x1C) : 0;
    if (bal) *(int *)(bal + 0x1C) = (int)(base_damage * falloff[r->pierced < 2 ? r->pierced : 2] + 0.5f);
    *(unsigned char *)(self + 0xF0) = 0xFE;
    ((TriggerFn)TRIGGER)(self, NULL, idx);
    if (bal) *(int *)(bal + 0x1C) = old;
    if (*(unsigned char *)(self + 0xF0) != 0xFE) {   /* the hit was registered */
        unsigned layer = rd(APP);
        char *actor;
        if (layer) layer = rd(layer + 0xC90);
        actor = layer ? ((ActorFn)GET_LOGIC_ACTOR)((void *)rd(layer + 0x50), NULL, idx) : NULL;
        if (actor && *(float *)(actor + 0xBC) > 0.f) {
            *(float *)(actor + 0xC0) = 0.f;
            InterlockedIncrement(&shields);
        }
        r->pierced++;
        InterlockedIncrement(&passes);
    }
}

static __declspec(naked) void kill_thunk(void)      /* replaces "call KillPickup" at the end of Trigger */
{
    __asm {
        push ecx
        push ecx
        call is_rail
        add esp, 4
        pop ecx
        test eax, eax
        jnz skip
        mov eax, KILL_PICKUP
        jmp eax
    skip:
        ret 8
    }
}

/* ---- 5. walls ---- */
static int __cdecl wall_hit(void *self)
{
    Rail *r = rail_of(self);
    DWORD now;
    if (!r) return 0;
    now = GetTickCount();
    if (now - r->last_wall > WALL_GAP_MS) { r->pierced++; InterlockedIncrement(&walls); }
    r->last_wall = now;
    return 1;
}

static __declspec(naked) void wall_thunk(void)
{
    __asm {
        push ecx
        push ecx
        call wall_hit
        add esp, 4
        pop ecx
        test eax, eax
        jnz nowall
        mov eax, WALL_CHECK
        jmp eax
    nowall:
        xor eax, eax
        ret 4
    }
}

/* ---- 6. other pickups ---- */
static __declspec(naked) void dmg_thunk(void)       /* entry of GetDamageToApply (9 bytes replaced) */
{
    __asm {
        push ecx
        push ecx
        call is_rail
        add esp, 4
        pop ecx
        test eax, eax
        jz normal
        mov eax, crush
        ret
    normal:
        mov eax, [ecx + 8]
        push eax
        mov ecx, 0x1133220
        mov eax, DMG_TO_APPLY_CONT
        jmp eax
    }
}

/* ---- 1. spawn ---- */
static __declspec(naked) void spawn_thunk(void)     /* replaces "cmp ebp,0Ah / je ignore" */
{
    __asm {
        cmp ebp, 0xA
        jne keep
        push eax
        push ecx
        push edx
        call spawn_roll
        test eax, eax
        pop edx
        pop ecx
        pop eax
        jnz keep
        mov dword ptr [esp], SPAWN_IGNORE
    keep:
        ret
    }
}

/* ---- 2. AI pick-up ---- */
static __declspec(naked) void pick_thunk(void)      /* replaces "call GetNumShotsAwarded" in the PickedUp handler */
{
    __asm {
        cmp dword ptr [esp + 4], 0xA
        jne go
        push eax
        push ecx
        push edx
        push dword ptr [ecx + 0x2C]
        call is_human
        add esp, 4
        test eax, eax
        pop edx
        pop ecx
        pop eax
        jnz go
        mov dword ptr [esp + 4], 3
        mov dword ptr [edi + 0x14], 3
    go:
        mov eax, SHOTS_AWARDED
        jmp eax
    }
}

/* ---- patching ---- */
typedef struct { unsigned addr; int len; const char *orig; int kind; void *to; const char *what; } Patch;
enum { CALL, JMP, PTR, RAW };   /* CALL / JMP: E8 / E9 rel32 + nops; PTR: 4-byte pointer; RAW: `to` = hex string */

static Patch patches[] = {
    {0xB5B497, 5, "83fd0a7405", CALL, NULL, "SetRandomPickupType: SuperShield (railgun) allowed"},
    {0x47CC60, 5, "e88bcdfeff", CALL, NULL, "PickedUp: an AI gets a Bolt instead"},
    {0xBAB600, 4, "00b4ba00", PTR, NULL, "CreatePickup: SuperShield -> railgun Bolt"},
    {0xBAAF9F, 5, "e82c360400", CALL, NULL, "Bolt constructor call 1"},
    {0xBAB083, 5, "e848350400", CALL, NULL, "Bolt constructor call 2"},
    {0xBEED50, 5, "e87bf8ffff", CALL, NULL, "Bolt constructor call (reversed Bolt)"},
    {0xEE15C0, 4, "40c5be00", PTR, NULL, "Bolt vtable: Trigger"},
    {0xEE1620, 4, "40c5be00", PTR, NULL, "reversed Bolt vtable: Trigger"},
    {0xBECB2A, 5, "e8919ffbff", CALL, NULL, "Trigger: no KillPickup for a railgun"},
    {0xBE654B, 5, "e8c0e7ffff", CALL, NULL, "CheckCollisions: walls ignored by a railgun"},
    {0xBA8CC0, 9, "8b410850b920321301", JMP, NULL, "GetDamageToApply: railgun crushes pickups"},
};

static void unhex(const char *s, unsigned char *out, int n)
{
    int i;
    unsigned v;
    for (i = 0; i < n; i++) { sscanf_s(s + 2 * i, "%2x", &v); out[i] = (unsigned char)v; }
}

static void apply(void)
{
    void *to[] = {(void *)spawn_thunk, (void *)pick_thunk, (void *)super_case, (void *)ctor_wrap, (void *)ctor_wrap,
                  (void *)ctor_wrap, (void *)trigger_hook, (void *)trigger_hook, (void *)kill_thunk, (void *)wall_thunk,
                  (void *)dmg_thunk};
    unsigned char want[16], put[16];
    int i, n = sizeof patches / sizeof *patches;
    DWORD old;
    for (i = 0; i < n; i++) {                       /* all or nothing: check every site first */
        Patch *p = &patches[i];
        p->to = to[i];
        unhex(p->orig, want, p->len);
        if (!rd(p->addr) || memcmp((void *)p->addr, want, p->len)) {
            say("bytes at 0x%X (%s) are not the expected ones (other Blur.exe?): NOTHING patched", p->addr, p->what);
            return;
        }
    }
    for (i = 0; i < n; i++) {
        Patch *p = &patches[i];
        unsigned char *site = (unsigned char *)p->addr;
        memset(put, 0x90, sizeof put);
        if (p->kind == PTR) {
            *(void **)put = p->to;
        } else {
            put[0] = p->kind == CALL ? 0xE8 : 0xE9;
            *(int *)(put + 1) = (int)((unsigned char *)p->to - (site + 5));
        }
        VirtualProtect(site, p->len, PAGE_EXECUTE_READWRITE, &old);
        memcpy(site, put, p->len);
        VirtualProtect(site, p->len, old, &old);
        FlushInstructionCache(GetCurrentProcess(), site, p->len);
        say("patched 0x%X: %s", p->addr, p->what);
    }
}

static void load_settings(const char *dir)
{
    char path[MAX_PATH], line[256], key[64];
    float v[3];
    FILE *f;
    sprintf_s(path, sizeof path, "%srailgun.txt", dir);
    if (!fopen_s(&f, path, "r")) {
        while (fgets(line, sizeof line, f)) {
            int k;
            if (line[0] == '#' || sscanf_s(line, "%63s", key, (unsigned)sizeof key) != 1) continue;
            k = sscanf_s(line, "%*s %f %f %f", v, v + 1, v + 2);
            if (k < 1) continue;
            if (!strcmp(key, "speed")) speed = v[0];
            else if (!strcmp(key, "radius")) radius = v[0];
            else if (!strcmp(key, "height")) height = v[0];
            else if (!strcmp(key, "fallrate")) fallrate = v[0];
            else if (!strcmp(key, "spawn")) spawn = v[0];
            else if (!strcmp(key, "delay")) front_delay = v[0];
            else if (!strcmp(key, "rear_delay")) rear_delay = v[0];
            else if (!strcmp(key, "damage")) base_damage = v[0];
            else if (!strcmp(key, "crush")) crush = (int)v[0];
            else if (!strcmp(key, "falloff") && k == 3) memcpy(falloff, v, sizeof v);
        }
        fclose(f);
    }
    say("settings: delay %.2f s, rear %.2f s, speed %.0f radius %.2f height %.2f fallrate %.2f spawn %.2f damage %.0f x %.2f/%.2f/%.2f crush %d",
        front_delay, rear_delay, speed, radius, height, fallrate, spawn, base_damage, falloff[0], falloff[1], falloff[2], crush);
}

static DWORD WINAPI reporter(LPVOID unused)
{
    LONG a = 0, b = 0, c = 0, d = 0;
    (void)unused;
    for (;;) {                                      /* counts only: shows the hooks fire in game */
        Sleep(2000);
        if (fired != a || passes != b || walls != c || shields != d) {
            a = fired; b = passes; c = walls; d = shields;
            say("so far: %ld railgun(s) fired, %ld vehicle hit(s), %ld wall(s) pierced, %ld shield(s) downed", a, b, c, d);
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        char dir[MAX_PATH], path[MAX_PATH], *slash;
        HANDLE t;
        DisableThreadLibraryCalls(h);
        GetModuleFileNameA(h, dir, sizeof dir);
        slash = strrchr(dir, '\\');
        if (slash) slash[1] = 0;
        sprintf_s(path, sizeof path, "%srailgun.log", dir);
        logfile = _fsopen(path, "w", _SH_DENYNO);   /* readable while the game runs */
        say("railgun v2 loaded");
        srand(GetTickCount());
        load_settings(dir);
        sprintf_s(sound[0], MAX_PATH, "%srailgun_fire.wav", dir);
        sprintf_s(sound[1], MAX_PATH, "%srailgun_fire_rear.wav", dir);
        for (int i = 0; i < 2; i++)
            if (GetFileAttributesA(sound[i]) == INVALID_FILE_ATTRIBUTES) { say("no %s: no sound", sound[i]); sound[i][0] = 0; }
        apply();
        t = CreateThread(NULL, 0, reporter, NULL, 0, NULL);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
