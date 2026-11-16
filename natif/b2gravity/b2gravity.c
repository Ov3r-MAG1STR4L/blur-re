/* b2gravity.dll - car-local gravity in wall-ride zones (Blur 2 Marina on Blur 1), test copy only.

   Loaded by AMAX's d3d9.dll from amax\dlls (it loads *.dll and *.asi). Blur.exe = AMAX's 1.2 exe
   (SHA-1 dcbd312a...), addresses below checked on it (2026-11-16):
   - C_VehicleActor::Update writes the car's own gravity every frame (source: VehicleActor.cpp l. 1585,
     m_GravityConstants.m_Gravity = (0, g_debugVehicleGravity, 0), given to its physics body by
     SetExternalConstants): at 0x453BEF, 35 bytes
        movss xmm0,[0x1126CE4] / xorps xmm1,xmm1 / movss [esi+0x7BC],xmm1 / [esi+0x7C0],xmm0 / [esi+0x7C4],xmm1
     esi = the vehicle actor. Those bytes become "call stub" + nops; the stub writes the gravity itself.
   - vehicle actor: +0xCC Mat43 rows (AX, AY = up, AZ, then position), +0x130 position, +0x13C velocity (m/s)
     (blur_live.py, on the race vehicle list R = [[[[0x11AA04C]+0xC90]+0x30]+0xA10], [R+0x1A0] vehicles,
     [R+0x68+i*0x10] objects). A vehicle not found in that list keeps the normal gravity.
   Rule (as Blur2DubaiTest's GravityBend, uKER): inside a zone box of b2gravity.txt and faster than MIN_SPEED,
   gravity = |g| along -up of the car (it stays on walls); elsewhere (0, g, 0) exactly as the game.
   b2gravity.txt (next to the dll): lines "minx miny minz maxx maxy maxz" (game axes), '#' comments;
   optional line "speed <m/s>". Log: b2gravity.log next to the dll.
*/
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>
#include <share.h>

#define SITE      0x453BEF
#define SITE_LEN  35
#define G_DEBUG   0x1126CE4       /* Vehicle.Gravity value (-9.8) */
#define APP       0x11AA04C

static const unsigned char ORIGINAL[SITE_LEN] = {
    0xF3,0x0F,0x10,0x05,0xE4,0x6C,0x12,0x01,             /* movss xmm0,[0x1126ce4] */
    0x0F,0x57,0xC9,                                      /* xorps xmm1,xmm1 */
    0xF3,0x0F,0x11,0x8E,0xBC,0x07,0x00,0x00,             /* movss [esi+0x7bc],xmm1 */
    0xF3,0x0F,0x11,0x86,0xC0,0x07,0x00,0x00,             /* movss [esi+0x7c0],xmm0 */
    0xF3,0x0F,0x11,0x8E,0xC4,0x07,0x00,0x00};            /* movss [esi+0x7c4],xmm1 */

#define MAX_ZONES 64
static float zones[MAX_ZONES][6];
static int nzones = 0;
static float min_speed = 13.9f;                          /* 50 km/h, as Blur2DubaiTest */
static char dir[MAX_PATH];
static FILE *logfile = NULL;
static int in_zone_last[32], applied[32];

static void say(const char *fmt, ...)
{
    va_list a;
    if (!logfile) return;
    va_start(a, fmt); vfprintf(logfile, fmt, a); va_end(a);
    fputc('\n', logfile); fflush(logfile);
}

static int readable(const void *p, size_t n)
{
    MEMORY_BASIC_INFORMATION m;
    if (!p || !VirtualQuery(p, &m, sizeof m) || m.State != MEM_COMMIT) return 0;
    if (m.Protect & (PAGE_NOACCESS | PAGE_GUARD)) return 0;
    return (const char *)p + n <= (const char *)m.BaseAddress + m.RegionSize;
}

static unsigned rd(unsigned a)
{
    return readable((void *)a, 4) ? *(unsigned *)a : 0;
}

/* index of `self` in the race vehicle list, -1 if not there */
static int vehicle_index(unsigned self)
{
    unsigned r = rd(APP), n, i;
    if (r) r = rd(r + 0xC90);
    if (r) r = rd(r + 0x30);
    if (r) r = rd(r + 0xA10);
    if (!r) return -1;
    n = rd(r + 0x1A0);
    if (n > 20) return -1;
    for (i = 0; i < n; i++)
        if (rd(r + 0x68 + i * 0x10) == self) return (int)i;
    return -1;
}

/* On the ground the racing physics (RacingPhysics::Car::EvaluateDerivative, Blur.exe 0x7D1FE4) ignores the body's
   gravity: it adds m_dd.externalForce (car + 0x1474: [esi+0x13AC], esi = car + 0xC8), then its own gravity
   force.y -= mass * 9.81 (mass: car + 0x1D4) and a constant downforce C along the world vertical seen across the
   heading (cd = Y without its part along the heading), C = [car+0x740] * 9.81 * [[car+0x167C]+0x26C].
   car = [vehicle actor + 0x238] (m_pVehiclePhysics). externalForce is only rewritten in the air (CopyFromGravity),
   so on the ground the value written here stays for every physics step of the frame. */
#define CAR_EXT_FORCE 0x1474
#define CAR_MASS      0x1D4

static float *ground_force(char *self)
{
    unsigned car = rd((unsigned)self + 0x238);
    if (!car || !readable((void *)(car + CAR_EXT_FORCE), 12) || !readable((void *)(car + 0x740), 4)) return NULL;
    return (float *)(car + CAR_EXT_FORCE);
}

static void wall_force(char *self, float *ext, const float *up, float len, float g)
{
    unsigned car = rd((unsigned)self + 0x238), dyn = rd(car + 0x167C);
    float m = *(float *)(car + CAR_MASS), G = -g;                     /* G = 9.8 */
    float c = (dyn && readable((void *)(dyn + 0x26C), 4)) ? *(float *)(car + 0x740) * 9.81f * *(float *)(dyn + 0x26C) : 0.f;
    const float *h = (const float *)(self + 0xE4);                    /* heading (AZ row) */
    float u[3] = {up[0] / len, up[1] / len, up[2] / len};
    float cd[3] = {-h[1] * h[0], 1.f - h[1] * h[1], -h[1] * h[2]};    /* Y - (Y.h) h */
    float n = sqrtf(cd[0] * cd[0] + cd[1] * cd[1] + cd[2] * cd[2]);
    int i;
    if (m <= 0.f || m > 1e5f || !(c >= 0.f && c < 1e7f)) return;
    if (n > 1e-3f) { cd[0] /= n; cd[1] /= n; cd[2] /= n; }
    /* cancel the world gravity and the world-vertical downforce, push the same amounts along -up */
    for (i = 0; i < 3; i++)
        ext[i] = m * G * ((i == 1 ? 1.f : 0.f) - u[i]) + c * (cd[i] - u[i]);
}

static void __stdcall gravity(char *self)
{
    float g = *(float *)G_DEBUG;
    float *out = (float *)(self + 0x7BC);
    float gx = 0.f, gy = g, gz = 0.f;
    int k = nzones ? vehicle_index((unsigned)self) : -1;
    if (k >= 0) {
        const float *p = (const float *)(self + 0x130), *v = (const float *)(self + 0x13C);
        const float *up = (const float *)(self + 0xD8);
        float speed = sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
        float len = sqrtf(up[0] * up[0] + up[1] * up[1] + up[2] * up[2]);
        int z, inside = 0;
        for (z = 0; z < nzones && !inside; z++)
            inside = p[0] >= zones[z][0] && p[1] >= zones[z][1] && p[2] >= zones[z][2]
                  && p[0] <= zones[z][3] && p[1] <= zones[z][4] && p[2] <= zones[z][5];
        int on = inside && speed > min_speed && len > 0.9f && len < 1.1f;
        float *ext = ground_force(self);
        if (on) {
            float s = g / len;                               /* g < 0: along -up, |g| long */
            gx = up[0] * s; gy = up[1] * s; gz = up[2] * s;
            if (ext) wall_force(self, ext, up, len, g);
        } else if (ext && k < 32 && applied[k]) {
            ext[0] = ext[1] = ext[2] = 0.f;                 /* back to the game's own forces */
        }
        if (k < 32) applied[k] = on && ext;
        if (k < 32 && inside != in_zone_last[k]) {
            in_zone_last[k] = inside;
            say("vehicle %d %s zone at (%.0f, %.0f, %.0f), %.0f km/h, up (%.2f, %.2f, %.2f)", k,
                inside ? "enters" : "leaves", p[0], p[1], p[2], speed * 3.6f, up[0], up[1], up[2]);
        }
    }
    out[0] = gx; out[1] = gy; out[2] = gz;
}

static __declspec(naked) void stub(void)
{
    __asm {                                  /* every register kept: the game's code goes on after the call */
        pushad
        pushfd
        sub esp, 128
        movups [esp], xmm0
        movups [esp + 16], xmm1
        movups [esp + 32], xmm2
        movups [esp + 48], xmm3
        movups [esp + 64], xmm4
        movups [esp + 80], xmm5
        movups [esp + 96], xmm6
        movups [esp + 112], xmm7
        push esi
        call gravity
        movups xmm0, [esp]
        movups xmm1, [esp + 16]
        movups xmm2, [esp + 32]
        movups xmm3, [esp + 48]
        movups xmm4, [esp + 64]
        movups xmm5, [esp + 80]
        movups xmm6, [esp + 96]
        movups xmm7, [esp + 112]
        movss xmm0, dword ptr ds:[G_DEBUG]   /* as the replaced code leaves them: xmm0 = g, xmm1 = 0 */
        xorps xmm1, xmm1
        add esp, 128
        popfd
        popad
        ret
    }
}

static void load_zones(void)
{
    char path[MAX_PATH], line[256];
    FILE *f;
    sprintf_s(path, sizeof path, "%sb2gravity.txt", dir);
    if (fopen_s(&f, path, "r")) { say("no %s: patch active, no zone (normal gravity everywhere)", path); return; }
    while (fgets(line, sizeof line, f)) {
        float b[6], s;
        if (line[0] == '#') continue;
        if (sscanf_s(line, "speed %f", &s) == 1) { min_speed = s; continue; }
        if (nzones < MAX_ZONES && sscanf_s(line, "%f %f %f %f %f %f", b, b + 1, b + 2, b + 3, b + 4, b + 5) == 6) {
            memcpy(zones[nzones++], b, sizeof b);
            say("zone %d: x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f", nzones - 1, b[0], b[3], b[1], b[4], b[2], b[5]);
        }
    }
    fclose(f);
    say("%d zone(s), speed > %.1f m/s", nzones, min_speed);
}

static void patch(void)
{
    unsigned char *site = (unsigned char *)SITE;
    DWORD old;
    int i;
    if (!readable(site, SITE_LEN) || memcmp(site, ORIGINAL, SITE_LEN)) {
        say("bytes at 0x%X are not the expected ones (other Blur.exe?): NOT patched", SITE);
        return;
    }
    if (!VirtualProtect(site, SITE_LEN, PAGE_EXECUTE_READWRITE, &old)) { say("VirtualProtect failed"); return; }
    site[0] = 0xE8;                                                   /* call stub */
    *(int *)(site + 1) = (int)((unsigned char *)stub - (site + 5));
    for (i = 5; i < SITE_LEN; i++) site[i] = 0x90;
    VirtualProtect(site, SITE_LEN, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, SITE_LEN);
    say("patched 0x%X -> stub 0x%p", SITE, stub);
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        char path[MAX_PATH], *slash;
        DisableThreadLibraryCalls(h);
        GetModuleFileNameA(h, dir, sizeof dir);
        slash = strrchr(dir, '\\');
        if (slash) slash[1] = 0;
        sprintf_s(path, sizeof path, "%sb2gravity.log", dir);
        logfile = _fsopen(path, "w", _SH_DENYNO);          /* readable while the game runs */
        say("b2gravity loaded");
        load_zones();
        patch();
    }
    return TRUE;
}
