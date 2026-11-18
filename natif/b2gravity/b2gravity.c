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
#include <stdlib.h>
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
static float nprev[32][3];
/* v6: roll the car onto the surface. The wheels only look for ground under the car (2 m along -up), so a wall
   beside the car is never reached and nothing turns the car: it stays at ~30 deg, two wheels on the road
   (essai v5). Torque = t * m * 9.81 * (align * (up x n) - damp * w), w = angular velocity from the change of
   up between two frames (only its part across up). "align" / "damp" lines in b2gravity.txt
   (ponytail: tuned by hand in game; per-car inertia from the exe if one value does not fit every car). */
static float align_k = 1.5f, align_d = 0.6f, last_press = 0.f;
static float upprev[32][3];
static LARGE_INTEGER tprev[32];

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
   gravity: it adds m_dd.externalForce (car + 0x1468: [esi+0x13A0], added to the FORCE at [edi+0x24] where the
   gravity is taken off; v2 / v3 wrote car + 0x1474 = externalTorque by mistake, 2026-11-17), then its own gravity
   force.y -= mass * 9.81 (mass: car + 0x1D4) and a constant downforce C along the world vertical seen across the
   heading (cd = Y without its part along the heading), C = [car+0x740] * 9.81 * [[car+0x167C]+0x26C].
   car = [vehicle actor + 0x238] (m_pVehiclePhysics). externalForce is only rewritten in the air (CopyFromGravity),
   so on the ground the value written here stays for every physics step of the frame. */
#define CAR_EXT_FORCE 0x1468
#define CAR_EXT_TORQUE 0x1474
#define CAR_MASS      0x1D4

static float *ground_force(char *self)
{
    unsigned car = rd((unsigned)self + 0x238);
    if (!car || !readable((void *)(car + CAR_EXT_FORCE), 24) || !readable((void *)(car + 0x740), 4)) return NULL;
    return (float *)(car + CAR_EXT_FORCE);
}

/* d = unit direction of the wanted gravity (into the surface) */
static void wall_force(char *self, float *ext, const float *d, float g)
{
    unsigned car = rd((unsigned)self + 0x238), dyn = rd(car + 0x167C);
    float m = *(float *)(car + CAR_MASS), G = -g;                     /* G = 9.8 */
    float c = (dyn && readable((void *)(dyn + 0x26C), 4)) ? *(float *)(car + 0x740) * 9.81f * *(float *)(dyn + 0x26C) : 0.f;
    const float *h = (const float *)(self + 0xE4);                    /* heading (AZ row) */
    float cd[3] = {-h[1] * h[0], 1.f - h[1] * h[1], -h[1] * h[2]};    /* Y - (Y.h) h */
    float n = sqrtf(cd[0] * cd[0] + cd[1] * cd[1] + cd[2] * cd[2]);
    int i;
    if (m <= 0.f || m > 1e5f || !(c >= 0.f && c < 1e7f)) return;
    if (n > 1e-3f) { cd[0] /= n; cd[1] /= n; cd[2] /= n; }
    /* cancel the world gravity and the world-vertical downforce, push the same amounts along d */
    for (i = 0; i < 3; i++)
        ext[i] = c * (cd[i] + d[i]);              /* v4: gravity itself replaced at the source, only the downforce here */
}

/* v7: the speed-dependent downforce (car.cpp:731-737: force -AxisY * m * 9.81 * f(speed) while a front wheel is
   on the ground; f = Car::CalculateSpeedDependentDownforceFactor, 0x7C2F00, thiscall, no argument, only reads
   the car, result in st0; m = [car + 0x740] as at 0x7D20B1) grows with speed and, with the car on two wheels,
   pins it flat (essai v6: ~60 deg below 40 mph with nothing applied, stuck at 30 deg above). Here it is turned
   along -n (into the surface): ext += F * (up - press * n). "press" line in b2gravity.txt.
   ponytail: compensates even when the front wheels are off the ground (the game then skips it); short hops only. */
typedef float (__fastcall *speed_df_fn)(void *car, void *unused);
static float press_k = 1.f;

static float speed_downforce(char *self)
{
    unsigned car = rd((unsigned)self + 0x238);
    float m, f;
    if (!car || !readable((void *)(car + 0x740), 4)) return 0.f;
    m = *(float *)(car + 0x740);
    f = ((speed_df_fn)0x7C2F00)((void *)car, NULL);
    if (!(m > 0.f && m < 1e5f) || !(f >= 0.f && f < 100.f)) return 0.f;
    return m * 9.81f * f;
}

/* v6: torque rolling the car onto the surface (see align_k) */
static void align_torque(char *self, int k, float *ext, const float *up, const float *n, float t)
{
    unsigned car = rd((unsigned)self + 0x238);
    float m = *(float *)(car + CAR_MASS), c[3], w[3] = {0.f, 0.f, 0.f}, s;
    LARGE_INTEGER now, fq;
    int i, fresh = k < 0 || k >= 32 || !applied[k];
    QueryPerformanceCounter(&now); QueryPerformanceFrequency(&fq);
    if (m <= 0.f || m > 1e5f) return;
    c[0] = up[1] * n[2] - up[2] * n[1]; c[1] = up[2] * n[0] - up[0] * n[2]; c[2] = up[0] * n[1] - up[1] * n[0];
    if (!fresh) {
        float dt = (float)(now.QuadPart - tprev[k].QuadPart) / (float)fq.QuadPart;
        const float *u0 = upprev[k];
        if (dt > 0.004f && dt < 0.1f) {                              /* w across up = (u0 x up) / dt */
            w[0] = (u0[1] * up[2] - u0[2] * up[1]) / dt; w[1] = (u0[2] * up[0] - u0[0] * up[2]) / dt;
            w[2] = (u0[0] * up[1] - u0[1] * up[0]) / dt;
        }
    }
    if (k >= 0 && k < 32) { upprev[k][0] = up[0]; upprev[k][1] = up[1]; upprev[k][2] = up[2]; tprev[k] = now; }
    s = t * m * 9.81f;
    for (i = 0; i < 3; i++) ext[3 + i] = s * (align_k * c[i] - align_d * w[i]);
}

/* Collision surfaces of the zones (b2gravity.bin from b2gravity_zones.py: "B2GV", u32 n, n x (x y z nx ny nz)),
   in a hash grid of CELL m: the nearest point within RAY m gives the surface normal under the car, as the raycast
   of Blur 2's CeilingRidingControl (GravityBend surfaces). */
#define CELL 4.0f
#define RAY 4.0f
#define SMOOTH 3.0f
#define NBUCKET (1 << 18)
static float *pts = NULL;
static int npts = 0, *nextp = NULL, head[NBUCKET];
/* Blur 2 nov 10: MinSpeedThresholdMph / MaxSpeedThresholdMph = 40 / 70. v8: 15 / 35 by default ("mph_min" /
   "mph_max" in b2gravity.txt): essai v7, Blur 1 already flattens the car from ~20 mph, while nothing of ours
   acted below 40. */
static float mph_min = 15.f, mph_max = 35.f;
/* v8: in a zone, on a surface, above 1 m/s: Blur 1's anti-wall-riding is lifted whatever the speed
   (Fix2 off, wheels along car -up); only the gravity / torque / downforce wait for mph_min. */
static int wallon[32];

static unsigned bucket(int x, int y, int z)
{
    return ((unsigned)x * 73856093u ^ (unsigned)y * 19349663u ^ (unsigned)z * 83492791u) & (NBUCKET - 1);
}

static void load_surfaces(void)
{
    char path[MAX_PATH], magic[4];
    FILE *f;
    int i;
    sprintf_s(path, sizeof path, "%sb2gravity.bin", dir);
    if (fopen_s(&f, path, "rb")) { say("no b2gravity.bin: car-up rule"); return; }
    if (fread(magic, 1, 4, f) != 4 || memcmp(magic, "B2GV", 4) || fread(&npts, 4, 1, f) != 1 || npts <= 0
        || npts > 4000000) { say("bad b2gravity.bin"); fclose(f); npts = 0; return; }
    pts = (float *)malloc((size_t)npts * 6 * sizeof(float));
    nextp = (int *)malloc((size_t)npts * sizeof(int));
    if (!pts || !nextp || fread(pts, 6 * sizeof(float), npts, f) != (size_t)npts) {
        say("b2gravity.bin: read failed"); fclose(f); npts = 0; return;
    }
    fclose(f);
    for (i = 0; i < NBUCKET; i++) head[i] = -1;
    for (i = 0; i < npts; i++) {
        unsigned b = bucket((int)floorf(pts[6 * i] / CELL), (int)floorf(pts[6 * i + 1] / CELL), (int)floorf(pts[6 * i + 2] / CELL));
        nextp[i] = head[b];
        head[b] = i;
    }
    say("%d surface points", npts);
}

/* normal (unit, towards the car) of the nearest surface point within RAY m on the floor side of the car
   (Blur 2 casts its ray below the car: a tunnel ceiling or an overpass must not win); 0 if none */
static int surface_normal(const float *p, const float *up, float *n)
{
    int cx = (int)floorf(p[0] / CELL), cy = (int)floorf(p[1] / CELL), cz = (int)floorf(p[2] / CELL), dx, dy, dz;
    int best = -1;
    float bd = RAY * RAY;
    for (dx = -1; dx <= 1; dx++) for (dy = -1; dy <= 1; dy++) for (dz = -1; dz <= 1; dz++) {
        int i;
        for (i = head[bucket(cx + dx, cy + dy, cz + dz)]; i >= 0; i = nextp[i]) {
            const float *q = pts + 6 * i;
            float a = q[0] - p[0], b = q[1] - p[1], c = q[2] - p[2], d2 = a * a + b * b + c * c;
            if (a * up[0] + b * up[1] + c * up[2] > 0.5f) continue;      /* above the car floor */
            if (d2 < bd) { bd = d2; best = i; }
        }
    }
    if (best < 0) return 0;
    {   /* v3.2: mean of the points up to SMOOTH m farther than the nearest one, each turned towards the car,
           weighted by closeness, those disagreeing with the nearest normal left out (railings, barriers) */
        const float *q = pts + 6 * best;
        float s = (p[0] - q[0]) * q[3] + (p[1] - q[1]) * q[4] + (p[2] - q[2]) * q[5] >= 0.f ? 1.f : -1.f;
        float n0[3], lim = sqrtf(bd) + SMOOTH, l;
        n0[0] = q[3] * s; n0[1] = q[4] * s; n0[2] = q[5] * s;
        n[0] = n[1] = n[2] = 0.f;
        for (dx = -1; dx <= 1; dx++) for (dy = -1; dy <= 1; dy++) for (dz = -1; dz <= 1; dz++) {
            int i;
            for (i = head[bucket(cx + dx, cy + dy, cz + dz)]; i >= 0; i = nextp[i]) {
                const float *r = pts + 6 * i;
                float a = r[0] - p[0], b = r[1] - p[1], c = r[2] - p[2], dd = sqrtf(a * a + b * b + c * c), w, si;
                if (dd > lim || a * up[0] + b * up[1] + c * up[2] > 0.5f) continue;
                si = -(a * r[3] + b * r[4] + c * r[5]) >= 0.f ? 1.f : -1.f;
                if ((r[3] * n0[0] + r[4] * n0[1] + r[5] * n0[2]) * si < 0.5f) continue;
                w = 1.f / (dd + 0.5f);
                n[0] += w * r[3] * si; n[1] += w * r[4] * si; n[2] += w * r[5] * si;
            }
        }
        l = sqrtf(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
        if (l < 1e-4f) { n[0] = n0[0]; n[1] = n0[1]; n[2] = n0[2]; }
        else { n[0] /= l; n[1] /= l; n[2] /= l; }
    }
    return 1;
}

/* "Vehicle.GamePhysicsMechanics.InFlightDownForce.Enable" (Debug::Bool, value byte 0x1127CF4, tested by
   C_VehicleActor::UpdateDownForce at 0x43C665): once the front wheels leave the ground, the game pushes the car
   down the WORLD vertical (amax.bin AmaxVehicleDefaults.flightControl: inFlightDownForce 200 000, after 0.01 s,
   for 3 s). Off while any car is bent onto a surface, back to its own value otherwise. */
#define AIR_DOWNFORCE_ON 0x1127CF4
/* v5: "Vehicle.GamePhysicsMechanics.WallRiding.EnableFix2" (Debug::Bool object 0x1212A60, value byte +0x24,
   read by C_RaceLogicLayer::ProcessCollisions at 0xB99AC3): body contacts with |n.y| < 0.25 become walls
   (Anisotropic_Wall material, horizontal normal) plus a drag of speed x 450 -> the car "sticks" to the wall.
   Off while any car is bent, like the in-flight downforce. Global: every car in the race gets normal wall
   contacts during that time. */
#define WALL_FIX2_ON 0x1212A84
/* v5: RacingPhysics::Car::m_bEnableWallRiding (car + 0x12D5: set by Car::EnableWallRiding at 0x7BFA00, never
   called; tested by Car::CreateGravityCache at 0x7BFECD). False: the wheels look for ground along the WORLD
   vertical and only keep triangles with n.y > 0.25, so a wall never carries the wheels (two wheels on the road,
   the body rubbing the wall). True: along -up of the car. Set per car while it is bent. */
#define CAR_WALLRIDE 0x12D5
static DWORD last_status = 0;
static int air_saved = -1, fix2_saved = -1;

static void flag_switch(unsigned addr, int any, int *saved, const char *name)
{
    unsigned char *sw = (unsigned char *)addr;
    if (any) {
        if (*saved < 0) { *saved = *sw; *sw = 0; say("%s off (was %d)", name, *saved); }
    } else if (*saved >= 0) {
        *sw = (unsigned char)*saved; say("%s back to %d", name, *saved); *saved = -1;
    }
}

static void air_downforce_switch(void)
{
    int i, any = 0;
    for (i = 0; i < 32; i++) any |= applied[i] | wallon[i];
    flag_switch(AIR_DOWNFORCE_ON, any, &air_saved, "in-flight downforce");
    flag_switch(WALL_FIX2_ON, any, &fix2_saved, "wall-riding fix2");
}

/* wheels look for ground under the car (on) or under the world (off) */
static void car_wallride(char *self, int k, int on)
{
    unsigned car = rd((unsigned)self + 0x238);
    unsigned char *f = car ? (unsigned char *)(car + CAR_WALLRIDE) : NULL;
    if (!f || !readable(f, 1) || *f == (unsigned char)(on != 0)) return;
    *f = (unsigned char)(on != 0);
    say("vehicle %d wheels: ground along %s", k, on ? "car -up" : "world -Y");
}

static void remember(char *self, int k, float gx, float gy, float gz, int bent);

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
        float n[3], t = (speed * 2.23694f - mph_min) / (mph_max - mph_min), d[3];
        int surf = inside && (npts ? surface_normal(p, up, n) : (len > 0.9f && len < 1.1f));
        int on = surf && t > 0.f;
        float *ext = ground_force(self);
        if (on) {
            float l;
            if (!npts) { n[0] = up[0] / len; n[1] = up[1] / len; n[2] = up[2] / len; }   /* old rule */
            if (t > 1.f) t = 1.f;
            if (k < 32 && applied[k]) {                      /* temporal smoothing (no sudden swings) */
                float m0 = 0.75f, l2;
                n[0] = m0 * nprev[k][0] + (1.f - m0) * n[0]; n[1] = m0 * nprev[k][1] + (1.f - m0) * n[1];
                n[2] = m0 * nprev[k][2] + (1.f - m0) * n[2];
                l2 = sqrtf(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
                if (l2 > 1e-4f) { n[0] /= l2; n[1] /= l2; n[2] /= l2; }
            }
            if (k < 32) { nprev[k][0] = n[0]; nprev[k][1] = n[1]; nprev[k][2] = n[2]; }
            d[0] = -n[0] * t; d[1] = -(1.f - t) - n[1] * t; d[2] = -n[2] * t;           /* down -> into the surface */
            l = sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
            if (l < 1e-3f) { d[0] = 0.f; d[1] = -1.f; d[2] = 0.f; l = 1.f; }
            d[0] /= l; d[1] /= l; d[2] /= l;
            gx = -g * d[0]; gy = -g * d[1]; gz = -g * d[2];                              /* |g| along d */
            if (ext) {
                float u[3] = {up[0] / len, up[1] / len, up[2] / len};
                wall_force(self, ext, d, g);
                if (len > 0.5f) {
                    float F = speed_downforce(self) * t;
                    int i;
                    align_torque(self, k, ext, u, n, t);
                    for (i = 0; i < 3; i++) ext[i] += F * (u[i] - press_k * n[i]);
                    last_press = F;
                }
            }
            if (k < 32 && !applied[k])
                say("vehicle %d bent at (%.0f, %.0f, %.0f) %.0f km/h: surface normal (%.2f, %.2f, %.2f), t %.2f",
                    k, p[0], p[1], p[2], speed * 3.6f, n[0], n[1], n[2], t);
        } else if (ext && k < 32 && applied[k]) {
            ext[0] = ext[1] = ext[2] = 0.f;                 /* back to the game's own forces */
            ext[3] = ext[4] = ext[5] = 0.f;                 /* torque: written by v2 / v3 */
        }
        if (k < 32) applied[k] = on && ext;
        if (k < 32) wallon[k] = surf && speed > 1.f;
        car_wallride(self, k, surf && speed > 1.f);
        if (k < 32 && inside != in_zone_last[k]) {
            in_zone_last[k] = inside;
            say("vehicle %d %s zone at (%.0f, %.0f, %.0f), %.0f km/h, up (%.2f, %.2f, %.2f)", k,
                inside ? "enters" : "leaves", p[0], p[1], p[2], speed * 3.6f, up[0], up[1], up[2]);
        }
        if (k == 0 && inside && GetTickCount() - last_status > 500) {          /* player: state every 0.5 s */
            last_status = GetTickCount();
            say("  v0 (%.0f, %.0f, %.0f) %.0f km/h up (%.2f, %.2f, %.2f) %s t %.2f g (%.1f, %.1f, %.1f)"
                " n (%.2f, %.2f, %.2f) torque %.0f press %.0f N",
                p[0], p[1], p[2], speed * 3.6f, up[0], up[1], up[2],
                on ? "surface" : (t > 0.f ? "NO SURFACE within 4 m" : "too slow"), t, gx, gy, gz,
                on ? n[0] : 0.f, on ? n[1] : 0.f, on ? n[2] : 0.f,
                (on && ext) ? sqrtf(ext[3] * ext[3] + ext[4] * ext[4] + ext[5] * ext[5]) : 0.f, on ? last_press : 0.f);
        }
    }
    out[0] = gx; out[1] = gy; out[2] = gz;
    if (k >= 0 && k < 32) remember(self, k, gx, gy, gz, applied[k]);
    air_downforce_switch();
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

/* ---- v4 (2026-11-17): Blur 1's own gravity REPLACED, not compensated ----------------------------------------
   Each car's gravity (the vector written into the actor by the Update hook) is kept here per physics car, and:
   - on the ground: RacingPhysics::Car::EvaluateDerivative applies force -= mass * 9.81 * Y (ApplyGravity, inline,
     102 bytes at 0x7D202C, esi = car + 0xC8, edi = derivative, force at +0x24, mass at esi + 0x10C): replaced by
     force += mass * gravity of that car;
   - on take-off: Car::EndFrame pushes once AddForce(mass * (0, -1, 0) * 9.81) on the Gravity body (call 0x48B4E0 at
     0x7C5272, thiscall, ret 4, esi = car): skipped for a car whose gravity is bent.
   Unknown car: exactly (0, -9.81, 0), as the game. */
#define SITE_GRAV     0x7D202C
#define SITE_GRAV_END 0x7D2092
#define SITE_PUSH     0x7C5272
#define ADDFORCE      0x48B4E0
static const unsigned char ORIGINAL_GRAV[102] = {
    0xF2,0x0F,0x51,0x0D,0x38,0x3C,0xE6,0x00,0xF3,0x0F,0x10,0x86,0x0C,0x01,0x00,0x00,0xF3,0x0F,0x59,0x05,0xD0,0xD3,
    0xEA,0x00,0xF2,0x0F,0x5A,0xD1,0x0F,0x28,0xCF,0xF3,0x0F,0x5E,0xCA,0x0F,0x28,0xD1,0xF3,0x0F,0x59,0xD6,0x0F,0x28,
    0xE0,0xF3,0x0F,0x59,0xE1,0xF3,0x0F,0x10,0x4F,0x24,0x0F,0x28,0xDA,0xF3,0x0F,0x59,0xD8,0xF3,0x0F,0x5C,0xCB,0xF3,
    0x0F,0x11,0x4F,0x24,0xF3,0x0F,0x10,0x4F,0x28,0xF3,0x0F,0x5C,0xCC,0xF3,0x0F,0x11,0x4F,0x28,0xF3,0x0F,0x10,0x4F,
    0x2C,0xF3,0x0F,0x59,0xC2,0xF3,0x0F,0x5C,0xC8,0xF3,0x0F,0x11,0x4F,0x2C};
static const unsigned char ORIGINAL_PUSH[5] = {0xE8, 0x69, 0x62, 0xCC, 0xFF};

static unsigned car_of[32];                 /* physics car of the vehicle k */
static float car_grav[32][3];               /* its gravity (m/s2) this frame */
static int car_bent[32];
static int skip_push;

static void remember(char *self, int k, float gx, float gy, float gz, int bent)
{
    float l = sqrtf(gx * gx + gy * gy + gz * gz);
    car_of[k] = rd((unsigned)self + 0x238);
    car_bent[k] = bent;
    if (bent && l > 1e-3f) { car_grav[k][0] = gx / l * 9.81f; car_grav[k][1] = gy / l * 9.81f; car_grav[k][2] = gz / l * 9.81f; }
    else { car_grav[k][0] = 0.f; car_grav[k][1] = -9.81f; car_grav[k][2] = 0.f; }
}

static int car_slot(unsigned car)
{
    int i;
    for (i = 0; i < 32; i++) if (car_of[i] == car) return i;
    return -1;
}

static void __stdcall apply_gravity(char *rb, float *der)
{
    float m = *(float *)(rb + 0x10C);
    int s = car_slot((unsigned)(rb - 0xC8));
    if (s >= 0) {
        der[9] += m * car_grav[s][0]; der[10] += m * car_grav[s][1]; der[11] += m * car_grav[s][2];   /* +0x24 */
    } else {
        der[10] -= m * 9.81f;
    }
}

static void __stdcall push_check(unsigned car)
{
    int s = car_slot(car);
    skip_push = s >= 0 && car_bent[s];
}

static __declspec(naked) void stub_grav(void)
{
    __asm {
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
        push edi
        push esi
        call apply_gravity
        movups xmm0, [esp]
        movups xmm1, [esp + 16]
        movups xmm2, [esp + 32]
        movups xmm3, [esp + 48]
        movups xmm4, [esp + 64]
        movups xmm5, [esp + 80]
        movups xmm6, [esp + 96]
        movups xmm7, [esp + 112]
        add esp, 128
        popfd
        popad
        ret
    }
}

static __declspec(naked) void stub_push(void)
{
    __asm {                                  /* [esp] return, [esp+4] force vector, ecx = Gravity body, esi = car */
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
        call push_check
        movups xmm0, [esp]
        movups xmm1, [esp + 16]
        movups xmm2, [esp + 32]
        movups xmm3, [esp + 48]
        movups xmm4, [esp + 64]
        movups xmm5, [esp + 80]
        movups xmm6, [esp + 96]
        movups xmm7, [esp + 112]
        add esp, 128
        popfd
        popad
        cmp dword ptr [skip_push], 0
        jne skip
        mov eax, ADDFORCE
        jmp eax                              /* AddForce returns to the game with its own ret 4 */
    skip:
        ret 4
    }
}

static int patch_bytes(unsigned addr, const unsigned char *orig, int len, void *target, unsigned resume)
{
    unsigned char *site = (unsigned char *)addr;
    DWORD old;
    int i;
    if (!readable(site, len) || memcmp(site, orig, len)) { say("bytes at 0x%X not the expected ones: NOT patched", addr); return 0; }
    if (!VirtualProtect(site, len, PAGE_EXECUTE_READWRITE, &old)) { say("VirtualProtect failed at 0x%X", addr); return 0; }
    site[0] = 0xE8;
    *(int *)(site + 1) = (int)((unsigned char *)target - (site + 5));
    i = 5;
    if (resume) {                            /* jmp over the rest of the replaced block */
        site[5] = 0xE9;
        *(int *)(site + 6) = (int)((unsigned char *)resume - (site + 10));
        i = 10;
    }
    for (; i < len; i++) site[i] = 0x90;
    VirtualProtect(site, len, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, len);
    say("patched 0x%X (%d bytes)", addr, len);
    return 1;
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
        if (sscanf_s(line, "align %f", &s) == 1) { align_k = s; continue; }
        if (sscanf_s(line, "damp %f", &s) == 1) { align_d = s; continue; }
        if (sscanf_s(line, "press %f", &s) == 1) { press_k = s; continue; }
        if (sscanf_s(line, "mph_min %f", &s) == 1) { mph_min = s; continue; }
        if (sscanf_s(line, "mph_max %f", &s) == 1) { mph_max = s; continue; }
        if (nzones < MAX_ZONES && sscanf_s(line, "%f %f %f %f %f %f", b, b + 1, b + 2, b + 3, b + 4, b + 5) == 6) {
            memcpy(zones[nzones++], b, sizeof b);
            say("zone %d: x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f", nzones - 1, b[0], b[3], b[1], b[4], b[2], b[5]);
        }
    }
    fclose(f);
    if (mph_max <= mph_min + 1.f) mph_max = mph_min + 1.f;
    say("%d zone(s), gravity %.0f..%.0f mph, align %.2f damp %.2f press %.2f", nzones, mph_min, mph_max, align_k,
        align_d, press_k);
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
        logfile = _fsopen(path, "a", _SH_DENYNO);          /* readable while the game runs; one block per launch */
        {
            SYSTEMTIME st;
            GetLocalTime(&st);
            say("==== %04d-%02d-%02d %02d:%02d:%02d b2gravity loaded", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
        }
        load_zones();
        load_surfaces();
        patch();
        patch_bytes(SITE_GRAV, ORIGINAL_GRAV, 102, stub_grav, SITE_GRAV_END);
        patch_bytes(SITE_PUSH, ORIGINAL_PUSH, 5, stub_push, 0);
    }
    return TRUE;
}
