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
#include <math.h>
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
static float rear_speed = 300.f, volume = 0.7f;        /* rear shot m/s; our sounds' master volume */
static float rear_offset = 4.5f;   /* m: a rear shot starts this far back from where a forward one starts */
static float duck_depth = 0.45f, duck_hold = 0.3f, duck_release = 1.0f;   /* Shunt-like ducking (player's shots) */
static volatile DWORD duck_t0 = 0;   /* GetTickCount of the player's last railgun (charge start) */
static volatile float duck_delay = 1.f;
static char dir[MAX_PATH];          /* folder of the dll: settings, sounds, log */
static FILE *logfile = NULL;
static volatile LONG passes = 0, walls = 0, shields = 0, fired = 0;

typedef struct { char *p; int pierced; DWORD last_wall; int rear; char *bal; unsigned uid; } Rail;   /* bal: Bolt Normal balancing */
#define MAX_RAILS 32
static Rail rails[MAX_RAILS];
static int next_is_rail = 0, next_shooter = -1;
static unsigned pending_uid;       /* unique id of the railgun being created */
static int armed[32];             /* an AI picked a railgun: its next Bolt shot is one */
static int in_trigger = 0;          /* a railgun's Trigger is running: the hit effects come from its level */
static void say(const char *fmt, ...);
static Rail *rail_of(void *p);

/* ---- 8. own effects: the railgun's PickupLevel (railgun_fx.py) hangs on the SuperShield type's Modified slot ---- */
#define GET_PICKUP_TYPE 0x4811A0    /* RLDatabase (0x1133220)::GetPickupType(enum), thiscall */
#define BASE_LEVEL_CONT 0xBA8D06
#define VLC_LEVEL_CONT  0x47417A
typedef char *(__fastcall *TypeFn)(void *db, void *edx, int type);

static char *rail_level(int rear)   /* RLPickupLevel*, NULL if the data has none (then the Bolt's effects stay) */
{
    static char *level[2];
    static int tried;
    if (!tried) {
        char *t = ((TypeFn)GET_PICKUP_TYPE)((void *)0x1133220, NULL, 10);
        int i;
        tried = 1;
        for (i = 0; i < 2 && t; i++) {                  /* XtHandle mModified +0x34 / mReverseModified +0x3C */
            char *h = t + 0x34 + 8 * i;
            unsigned table = *(unsigned *)h;
            if (table && *(unsigned short *)table == *(unsigned short *)(h + 4) && *(unsigned *)(table + 8))
                level[i] = (char *)(*(unsigned *)(table + 8) + *(unsigned short *)(h + 6));
        }
        if (!level[1]) level[1] = level[0];
        say(level[0] ? "railgun effects: own levels found" : "railgun effects: no own level (Bolt effects)");
    }
    return level[rear != 0];
}

static int in_trigger_rear = 0;
static char *__cdecl level_for(void *self) { Rail *r = rail_of(self); return r ? rail_level(r->rear) : NULL; }
static char *__cdecl level_for_hit(int type) { return in_trigger && type == 3 ? rail_level(in_trigger_rear) : NULL; }

static __declspec(naked) void base_level_thunk(void)  /* C_PickupBase::GetRLSubTypeLevel(sub), thiscall, ret 4 */
{
    __asm {
        push ecx
        push ecx
        call level_for
        add esp, 4
        pop ecx
        test eax, eax
        jz orig
        ret 4
    orig:
        push esi
        mov esi, ecx
        mov eax, [esi + 8]
        push BASE_LEVEL_CONT
        ret
    }
}

static __declspec(naked) void vlc_level_thunk(void)   /* C_VehicleComponent_Pickups::GetRLSubTypeLevel(type, sub), ret 8 */
{
    __asm {
        push ecx
        push dword ptr [esp + 8]
        call level_for_hit
        add esp, 4
        pop ecx
        test eax, eax
        jz orig
        ret 8
    orig:
        mov eax, [esp + 4]
        push eax
        mov ecx, 0x1133220
        push VLC_LEVEL_CONT
        ret
    }
}

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

/* ---- 9. sounds: a small mixer on waveOut voices (several at once, no start delay, volume / pan per voice) ----
   The game thread only queues requests (sound + where); the audio thread plays them, and follows the flying
   railguns with their loop. Files next to the dll, 44.1 kHz 16-bit stereo (railgun_install.py). */
static int test_mode = 0;           /* railgun.txt "test 1": every Bolt the player picks up becomes a railgun */
static float impact_range = 300.f, loop_range = 400.f, fire_range = 400.f;   /* m: silent beyond */
enum { S_FIRE, S_FIRE_REAR, S_HIT_CAR, S_HIT_WALL, S_LOOP, S_LOOP_REAR, NSND };
static const char *snd_file[NSND] = {"railgun_fire.wav", "railgun_fire_rear.wav", "railgun_hit_car.wav",
                                     "railgun_hit_wall.wav", "railgun_loop.wav", "railgun_loop_rear.wav"};
static char *snd_data[NSND];
static DWORD snd_len[NSND];
#define NVOICE 16
#define BLOCK 1024                  /* frames per buffer: 23 ms */
#define NBUF 4                      /* ~90 ms queued: no underrun when the game is busy */
typedef struct { int snd, on, loop, rail, stop; DWORD pos, t; float l, r, cl, cr; } Voice;   /* cl/cr: gains now, ramped to l/r */
static Voice vc[NVOICE];
static HWAVEOUT mix_out;           /* our output (its volume = the whole application's) */
static volatile LONG q_head = 0, q_tail = 0;
static int q_snd[32];
static float q_at[32][3];
static int lan_on = 1;              /* 0 off, 1 default (spawn roll), 2 on in a custom race: no roll, 3 railgun only */
static volatile LONG draws = 0;

static const float *vehicle_pos(int i)   /* race vehicle list (blur_live.py): object +0x130 = position, +0xCC side */
{
    unsigned r = rd(APP), o;
    if (r) r = rd(r + 0xC90);
    if (r) r = rd(r + 0x30);
    if (r) r = rd(r + 0xA10);
    if (!r || i < 0 || i >= (int)rd(r + 0x1A0) || i > 20) return NULL;
    o = rd(r + 0x68 + i * 0x10);
    return o && rd(o + 0x130 + 8) ? (const float *)(o + 0x130) : NULL;
}

static int player_index(void)
{
    unsigned r = rd(APP);
    if (r) r = rd(r + 0xC90);
    if (r) r = rd(r + 0x30);
    if (r) r = rd(r + 0xA10);
    return r ? (int)(rd(r + 0x2EC) & 0xFF) : -1;
}

static void play_at(int snd, const float *at)  /* game thread: queue a sound heard from `at` */
{
    LONG h = q_head;
    if (!at || h - q_tail >= 32) return;
    q_snd[h & 31] = snd;
    memcpy(q_at[h & 31], at, sizeof q_at[0]);
    q_head = h + 1;
}

static float hear(const float *at, float range, float *pan)    /* audio thread: volume 0..1 and pan -1..+1 */
{
    const float *me = vehicle_pos(player_index()), *side;
    float d[3], dist;
    *pan = 0.f;
    if (!me || !at) return 0.f;
    side = me - (0x130 - 0xCC) / 4;                                /* AX row of the car's matrix */
    d[0] = at[0] - me[0]; d[1] = at[1] - me[1]; d[2] = at[2] - me[2];
    dist = sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
    if (!(dist < range)) return 0.f;                               /* also NaN */
    if (dist > 1.f) *pan = (d[0] * side[0] + d[1] * side[1] + d[2] * side[2]) / dist;
    return volume * powf(1.f - dist / range, 0.6f);                /* stays loud longer than a straight line */
}

static void gain(int v, float vol, float pan)
{
    if (v < 0) return;
    vc[v].l = vol * (pan > 0.f ? 1.f - 0.7f * pan : 1.f);
    vc[v].r = vol * (pan < 0.f ? 1.f + 0.7f * pan : 1.f);
}

static int start(int snd, float vol, float pan, int rail)  /* a free voice, else the oldest one-shot */
{
    int v, best = -1;
    if (!snd_data[snd]) return -1;
    for (v = 0; v < NVOICE; v++) {
        if (vc[v].on && vc[v].rail >= 0) continue;
        if (!vc[v].on) { best = v; break; }
        if (best < 0 || vc[v].t < vc[best].t) best = v;
    }
    if (best < 0) return -1;
    v = best;
    vc[v].snd = snd; vc[v].pos = 0; vc[v].loop = rail >= 0; vc[v].rail = rail; vc[v].t = GetTickCount();
    vc[v].stop = 0; vc[v].cl = vc[v].cr = 0.f;      /* fades in over the first block */
    gain(v, vol, pan);
    vc[v].on = 1;
    return v;
}

/* Ducking as the Shunt's: its audio entity sends events to the game's final submix (finalsubmix.dat
   PerkShuntFireEventInput -> ShuntFireVolume / ShuntFireTimer; finalperksubmix.dat PerkShuntChargeEventInput ->
   ShuntChargeFilterCutOff), from the same graph that plays its sounds, so it cannot be had without them. Here: the
   whole application's volume (waveOutSetVolume acts per application since Vista: the game's sounds too) goes down
   during the player's charge, stays down a moment after the shot, then comes back; our own sounds are scaled back up
   so they keep their level. 1.0 = no ducking. */
static float duck_gain(void)
{
    float t, d = duck_delay;
    if (!duck_t0) return 1.f;
    t = (GetTickCount() - duck_t0) / 1000.f;
    if (t < d) return 1.f - duck_depth * t / d;
    if (t < d + duck_hold) return 1.f - duck_depth;
    if (t < d + duck_hold + duck_release) return 1.f - duck_depth * (1.f - (t - d - duck_hold) / duck_release);
    return 1.f;
}

static void mix(short *dst)         /* sums every voice into one block (16-bit stereo), our own volume per voice */
{
    static float acc[BLOCK * 2];
    float g = duck_gain(), comp = 1.f / g;
    int v, f;
    memset(acc, 0, sizeof acc);
    for (v = 0; v < NVOICE; v++) {
        const short *src;
        DWORD frames;
        if (!vc[v].on) continue;
        src = (const short *)snd_data[vc[v].snd];
        frames = snd_len[vc[v].snd] / 4;
        {
            float tl = vc[v].stop ? 0.f : vc[v].l, tr = vc[v].stop ? 0.f : vc[v].r;
            float dl = (tl - vc[v].cl) / BLOCK, dr = (tr - vc[v].cr) / BLOCK, gl = vc[v].cl, gr = vc[v].cr;
            for (f = 0; f < BLOCK; f++) {
                if (vc[v].pos >= frames) {
                    if (!vc[v].loop) { vc[v].on = 0; break; }
                    vc[v].pos = 0;
                }
                gl += dl; gr += dr;
                acc[2 * f] += src[2 * vc[v].pos] * gl;
                acc[2 * f + 1] += src[2 * vc[v].pos + 1] * gr;
                vc[v].pos++;
            }
            vc[v].cl = tl; vc[v].cr = tr;
            if (vc[v].stop) vc[v].on = 0;               /* faded out over this block */
        }
    }
    for (f = 0; f < BLOCK * 2; f++) {            /* compensation, soft knee above 0.8 of full scale */
        float x = acc[f] * comp, a = x < 0.f ? -x : x;
        if (a > 26214.f) x = (x < 0.f ? -1.f : 1.f) * (26214.f + 6553.f * tanhf((a - 26214.f) / 6553.f));
        dst[f] = (short)x;
    }
    {
        static float last = 1.f;
        if (g != last && (g == 1.f || last - g > 0.01f || g - last > 0.01f)) {
            waveOutSetVolume(mix_out, ((DWORD)(g * 0xFFFF) << 16) | (DWORD)(g * 0xFFFF));
            last = g;
        }
    }
}

static void load_sounds(void)
{
    int i;
    for (i = 0; i < NSND; i++) {                   /* RIFF: "fmt " 44.1 kHz 16-bit stereo, then "data" */
        char path[MAX_PATH], *b = NULL, *c;
        long n = 0;
        FILE *f;
        sprintf_s(path, sizeof path, "%s%s", dir, snd_file[i]);
        if (!fopen_s(&f, path, "rb")) {
            fseek(f, 0, SEEK_END); n = ftell(f); fseek(f, 0, SEEK_SET);
            b = (char *)malloc(n);
            if (b && fread(b, 1, n, f) != (size_t)n) n = 0;
            fclose(f);
        }
        for (c = b ? b + 12 : NULL; c && c + 8 <= b + n; c += 8 + *(DWORD *)(c + 4)) {
            if (!memcmp(c, "fmt ", 4) && (*(WORD *)(c + 10) != 2 || *(DWORD *)(c + 12) != 44100 || *(WORD *)(c + 22) != 16))
                break;
            if (!memcmp(c, "data", 4)) { snd_data[i] = c + 8; snd_len[i] = *(DWORD *)(c + 4); break; }
        }
        say(snd_data[i] ? "sound %s: %.1f s" : "sound %s: missing or not 44.1 kHz 16-bit stereo", snd_file[i],
            snd_len[i] / 176400.0);
    }
}

/* the flying railguns' loops. Projectile (C_PickupBase): +0x24 killed, +0x28 active (after the delay), +0x80
   position (mMatrix.AW, copied each frame by the Bolt's Update 0xBE9F50). Read only, from this thread. */
static void loops(void)
{
    static int lv[MAX_RAILS] = {-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
                                -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1};
    int i;
    for (i = 0; i < MAX_RAILS; i++) {
        char *p = rails[i].p;
        int alive = p && (rd((unsigned)p + 0x28) & 0xFF) && !(rd((unsigned)p + 0x24) & 0xFF) && rd((unsigned)p + 0x80 + 8);
        float pan = 0.f, vol = alive ? hear((const float *)(p + 0x80), loop_range, &pan) : 0.f;
        static float from[MAX_RAILS][3];
        static DWORD t0[MAX_RAILS];
        if (alive && lv[i] < 0) { memcpy(from[i], p + 0x80, sizeof from[i]); t0[i] = GetTickCount(); }
        if (alive && t0[i] && GetTickCount() - t0[i] >= 300) {     /* flight check: where did it go in 0.3 s? */
            const float *at = (const float *)(p + 0x80);
            say("railgun %s: moved %.0f %.0f %.0f m in %lu ms (y = height), speed %.0f", rails[i].rear ? "rear" : "front",
                at[0] - from[i][0], at[1] - from[i][1], at[2] - from[i][2], GetTickCount() - t0[i], *(float *)(p + 0x158));
            t0[i] = 0;
        }
        if (alive && lv[i] < 0) lv[i] = start(rails[i].rear ? S_LOOP_REAR : S_LOOP, vol, pan, i);
        else if (alive) gain(lv[i], vol, pan);
        else if (lv[i] >= 0) { vc[lv[i]].stop = 1; vc[lv[i]].rail = -1; lv[i] = -1; }
    }
}

static DWORD WINAPI audio(LPVOID unused)
{
    static short buf[NBUF][BLOCK * 2];
    static WAVEHDR hdr[NBUF];
    WAVEFORMATEX fmt = {WAVE_FORMAT_PCM, 2, 44100, 44100 * 4, 4, 16, 0};
    HWAVEOUT out;
    HANDLE ev = CreateEventA(NULL, FALSE, FALSE, NULL);
    int b;
    (void)unused;
    load_sounds();
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);
    if (waveOutOpen(&out, WAVE_MAPPER, &fmt, (DWORD_PTR)ev, 0, CALLBACK_EVENT) != MMSYSERR_NOERROR || !(mix_out = out)) {
        say("no sound output (waveOutOpen failed)");
        return 0;
    }
    for (b = 0; b < NBUF; b++) {
        hdr[b].lpData = (char *)buf[b];
        hdr[b].dwBufferLength = sizeof buf[b];
        waveOutPrepareHeader(out, &hdr[b], sizeof hdr[b]);
        hdr[b].dwFlags |= WHDR_DONE;
    }
    for (;;) {                                      /* refill each finished buffer: requests, loops, then mix */
        for (b = 0; b < NBUF; b++) {
            if (!(hdr[b].dwFlags & WHDR_DONE)) continue;
            while (q_tail != q_head) {
                int k = q_snd[q_tail & 31];
                float pan, range = k == S_HIT_CAR || k == S_HIT_WALL ? impact_range : fire_range;
                float vol = hear(q_at[q_tail & 31], range, &pan);
                if (vol > 0.f) start(k, vol, pan, -1);
                q_tail++;
            }
            loops();
            mix(buf[b]);
            hdr[b].dwFlags &= ~WHDR_DONE;
            waveOutWrite(out, &hdr[b], sizeof hdr[b]);
        }
        WaitForSingleObject(ev, 20);
    }
}

/* custom race switch, called from Lua through package.loadlib (amax\plugins\railgun\railgun.lua): lua_CFunctions
   with no argument read and no result */
__declspec(dllexport) int __cdecl railgun_on(void *L) { (void)L; lan_on = 2; say("custom race: Railgun ON"); return 0; }
__declspec(dllexport) int __cdecl railgun_only(void *L) { (void)L; lan_on = 3; say("custom race: Railgun ONLY"); return 0; }
__declspec(dllexport) int __cdecl railgun_off(void *L) { (void)L; lan_on = 0; say("custom race: Railgun OFF"); return 0; }

/* pick-up: an AI cannot use type 10 (cPerkSkillUsage knows 0-7): it gets a 1-shot Bolt fired as a railgun;
   test mode: the player's Bolts become railguns. Returns the shots to award, or -1 for the game's own count. */
static int __cdecl pick(int vehicle, int *type)
{
    if (*type == 10 && !is_human(vehicle)) {
        *type = 3;
        if (vehicle >= 0 && vehicle < 32) armed[vehicle] = 1;
        return 1;
    }
    if (*type == 3 && test_mode && is_human(vehicle)) *type = 10;
    return -1;
}

static int __cdecl spawn_roll(void) { return lan_on >= 2 || (lan_on && rand() < (int)(spawn * RAND_MAX)); }

/* ---- 3. creation ---- */
static void __cdecl before_ctor(char *self)         /* pooled memory: a new Bolt may reuse a railgun's slot */
{
    Rail *r = rail_of(self);
    if (r) r->p = NULL;
}

static void overrides(char *self, Rail *r)
{
    *(float *)(self + 0x150) = radius;
    *(float *)(self + 0x154) = height;
    *(float *)(self + 0x158) = speed;
    *(float *)(self + 0x15C) = fallrate;
    *(float *)(self + 0xB0) = 1e9f;
    *(char **)(self + 0x56C) = r->bal;               /* the reversed Bolt puts its Reversed balancing here */
    if (rail_level(r->rear) && *(unsigned *)(rail_level(r->rear) + 0x1C))
        *(unsigned *)(self + 0x570) = *(unsigned *)(rail_level(r->rear) + 0x1C);   /* mpBlindfireSFX */
    if (r->rear) *(float *)(self + 0x158) = rear_speed;      /* seen in the mirror: at 600 m/s it is gone in 1-2 frames */
}

static void __cdecl after_ctor(char *self)
{
    Rail *r;
    int rear = next_is_rail == 2;
    if (!next_is_rail) return;
    next_is_rail = 0;
    if (!(r = rail_of(NULL))) { say("more than %d railguns alive: this one is a plain Bolt", MAX_RAILS); return; }
    r->p = self; r->pierced = 0; r->last_wall = 0; r->rear = rear; r->uid = rd((unsigned)self + 0x14);
    r->bal = (char *)rd((unsigned)self + 0x56C);    /* the Bolt's Normal balancing (damage is read there) */
    overrides(self, r);
    InterlockedIncrement(&fired);
    if (is_human(next_shooter)) {
        play_at(rear ? S_FIRE_REAR : S_FIRE, vehicle_pos(next_shooter)); duck_delay = rear ? rear_delay : front_delay; duck_t0 = GetTickCount(); }
}

/* PickupCreationStruct (esi in CreatePickup): +0 type, +4 sub-type (2 = reversed), +0x10 delay before the shot */
static void __cdecl super_setup(char *info)
{
    int rear = *(int *)(info + 4) == 2;
    next_is_rail = rear ? 2 : 1;
    if (rear) *(int *)(info + 4) = 0;               /* forward Bolt class, turned in its PostDelayInitialise */
    next_shooter = *(int *)(info + 8);
    pending_uid = *(unsigned *)(info + 0x14);
    *(float *)(info + 0x10) = rear ? rear_delay : front_delay;
}

static void __cdecl bolt_setup(char *info)          /* a Bolt fired by an AI that picked a railgun */
{
    int f = *(int *)(info + 8);
    if (f >= 0 && f < 32 && armed[f] && !is_human(f)) { armed[f] = 0; super_setup(info); }
}

static __declspec(naked) void bolt_case(void)
{
    __asm {
        push ecx
        push edx
        push esi
        call bolt_setup
        add esp, 4
        pop edx
        pop ecx
        mov eax, BOLT_CASE
        jmp eax
    }
}

/* C_PickupBlindfireProjectile::PostDelayInitialise(Mat43 *m, sfx), vtable [2], thiscall ret 8; Mat43 = 4 rows of
   3 floats (AX, AY, AZ, AW). The game's reversed Bolt only negates AZ (a mirrored matrix, 0xBEEDE0): a rear
   railgun is a forward one turned half a turn (AX and AZ negated, a true rotation). */
#define BOLT_PDI 0xBEE6C0
typedef void (__fastcall *PdiFn)(void *self, void *edx, const float *m, void *sfx);

static void __fastcall pdi_hook(char *self, void *edx, const float *m, void *sfx)
{
    Rail *r = rail_of(self);
    float c[12];
    int i;
    (void)edx;
    if (r && r->rear && m) {
        memcpy(c, m, sizeof c);
        for (i = 0; i < 3; i++) { c[9 + i] -= rear_offset * c[6 + i]; c[i] = -c[i]; c[6 + i] = -c[6 + i]; }
        m = c;
    }
    ((PdiFn)BOLT_PDI)(self, NULL, m, sfx);
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
        push ecx
        call before_ctor
        add esp, 4
        pop ecx
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
    bal = r->bal;
    old = bal ? *(int *)(bal + 0x1C) : 0;
    if (bal) *(int *)(bal + 0x1C) = (int)(base_damage * falloff[r->pierced < 2 ? r->pierced : 2] + 0.5f);
    *(unsigned char *)(self + 0xF0) = 0xFE;
    in_trigger = 1;
    in_trigger_rear = r->rear;
    ((TriggerFn)TRIGGER)(self, NULL, idx);
    in_trigger = 0;
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
        play_at(S_HIT_CAR, vehicle_pos(idx));
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
static int __cdecl wall_hit(void *self, const char *result)
{
    Rail *r = rail_of(self);
    DWORD now;
    if (!r) return 0;
    now = GetTickCount();
    if (now - r->last_wall > WALL_GAP_MS) {
        r->pierced++;
        InterlockedIncrement(&walls);
        play_at(S_HIT_WALL, result ? (const float *)(result + 0x10) : NULL);
    }
    r->last_wall = now;
    return 1;
}

static __declspec(naked) void wall_thunk(void)
{
    __asm {
        push ecx
        push dword ptr [esp + 8]
        push ecx
        call wall_hit
        add esp, 8
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
        jne other
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
    other:                                              /* railgun only: every other type is refused */
        cmp lan_on, 3
        jne keep
        mov dword ptr [esp], SPAWN_IGNORE
        ret
    }
}

/* A position's own type filter (level data: ConstantShuffle +0xE3, ShuffleTypes +0x108, what Map Builder sets per
   position) is tested on ONE byte at 0xB5B4B8 ("test byte [edi+0x108], 1 << type"): types 8+ never pass, so the
   railgun was refused wherever a map filters. Rule: the railgun may appear wherever the position allows the Bolt
   (bit 3). Replaces "mov eax, 1" at 0xB5B4AF (start of that test). */
#define SHUFFLE_OK  0xB5B517
#define SHUFFLE_NO  0xB5B6C4
static __declspec(naked) void shuffle_thunk(void)
{
    __asm {
        cmp ebp, 0xA
        jne normal
        cmp lan_on, 3                                   /* railgun only: every position */
        je any_pos
        test byte ptr [edi + 0x108], 8
        jz refuse
    any_pos:
        lock inc draws
        mov dword ptr [esp], SHUFFLE_OK
        ret
    refuse:
        mov dword ptr [esp], SHUFFLE_NO
        ret
    normal:
        mov eax, 1
        ret
    }
}

/* The game's own pickup sounds (Audio::InterfaceController 0x111D1E8 ::SendMessageToSubsystem 0x535770, thiscall
   (subsystem, message, value, msg*), ret 0x10; 9 = pickups) also play the Bolt's fire / flight / hit sounds for a
   railgun under ours ("muddy, triggered many times"). Messages that carry a railgun's unique id (PickupCreationStruct
   +0x14, C_PickupBase +0x14) among their first words are dropped. */
static int __cdecl rail_msg(const unsigned *msg)
{
    int i, k;
    if (!msg || !rd((unsigned)msg) || !rd((unsigned)(msg + 12))) return 0;
    for (i = 1; i <= 12; i++) {
        unsigned u = msg[i];
        if (!u || u == 0xFFFFFFFF) continue;
        if (u == pending_uid) return 1;
        for (k = 0; k < MAX_RAILS; k++)
            if (rails[k].p && rails[k].uid == u) return 1;
    }
    return 0;
}

#define AUDIO_CONT 0x535776
#define AUDIO_SKIP 0x53579E
static __declspec(naked) void audio_msg_thunk(void)  /* entry of SendMessageToSubsystem (6 bytes replaced) */
{
    __asm {
        cmp dword ptr [esp + 4], 9
        jne orig
        push ecx
        push dword ptr [esp + 0x14]
        call rail_msg
        add esp, 4
        pop ecx
        test eax, eax
        jz orig
        ret 0x10
    orig:
        mov eax, [ecx]
        test eax, eax
        jz skip
        push AUDIO_CONT
        ret
    skip:
        push AUDIO_SKIP
        ret
    }
}

/* ---- 2. AI pick-up ---- */
static __declspec(naked) void pick_thunk(void)      /* replaces "call GetNumShotsAwarded" in the PickedUp handler */
{
    __asm {
        push ecx
        push edx
        lea eax, [esp + 0xC]
        push eax
        push dword ptr [ecx + 0x2C]
        call pick
        add esp, 8
        pop edx
        pop ecx
        push eax
        mov eax, [esp + 8]
        mov [edi + 0x14], eax
        pop eax
        test eax, eax
        js normal
        ret 4
    normal:
        mov eax, SHOTS_AWARDED
        jmp eax
    }
}

/* ---- patching ---- */
typedef struct { unsigned addr; int len; const char *orig; int kind; void *to; const char *what; } Patch;
enum { CALL, JMP, PTR, RAW };   /* CALL / JMP: E8 / E9 rel32 + nops; PTR: 4-byte pointer; RAW: `to` = hex string */

static Patch patches[] = {
    {0xB5B497, 5, "83fd0a7405", CALL, NULL, "SetRandomPickupType: SuperShield (railgun) allowed"},
    {0xB5B4AF, 5, "b801000000", CALL, NULL, "SetRandomPickupType: railgun where the position allows the Bolt"},
    {0x535770, 6, "8b0185c07428", JMP, NULL, "SendMessageToSubsystem: no Bolt sounds for a railgun"},
    {0x47CC60, 5, "e88bcdfeff", CALL, NULL, "PickedUp: an AI gets a Bolt instead (test mode: player Bolt -> railgun)"},
    {0xBAB600, 4, "00b4ba00", PTR, NULL, "CreatePickup: SuperShield -> railgun Bolt"},
    {0xBAAF9F, 5, "e82c360400", CALL, NULL, "Bolt constructor call 1"},
    {0xBAB083, 5, "e848350400", CALL, NULL, "Bolt constructor call 2"},
    {0xBEED50, 5, "e87bf8ffff", CALL, NULL, "Bolt constructor call (reversed Bolt)"},
    {0xEE15C0, 4, "40c5be00", PTR, NULL, "Bolt vtable: Trigger"},
    {0xEE1620, 4, "40c5be00", PTR, NULL, "reversed Bolt vtable: Trigger"},
    {0xBECB2A, 5, "e8919ffbff", CALL, NULL, "Trigger: no KillPickup for a railgun"},
    {0xBE654B, 5, "e8c0e7ffff", CALL, NULL, "CheckCollisions: walls ignored by a railgun"},
    {0xBA8CC0, 9, "8b410850b920321301", JMP, NULL, "GetDamageToApply: railgun crushes pickups"},
    {0xBA8D00, 6, "568bf18b4608", JMP, NULL, "C_PickupBase::GetRLSubTypeLevel: railgun level (charge, flash)"},
    {0x474170, 10, "8b44240450b920321301", JMP, NULL, "VLC GetRLSubTypeLevel: railgun level during its hits"},
    {0xEE1580, 4, "c0e6be00", PTR, NULL, "Bolt vtable: PostDelayInitialise (rear railgun turned around)"},
    {0xBAB5E4, 4, "59afba00", PTR, NULL, "CreatePickup: Bolt case (an AI's railgun)"},
};

static void unhex(const char *s, unsigned char *out, int n)
{
    int i;
    unsigned v;
    for (i = 0; i < n; i++) { sscanf_s(s + 2 * i, "%2x", &v); out[i] = (unsigned char)v; }
}

static void apply(void)
{
    void *to[] = {(void *)spawn_thunk, (void *)shuffle_thunk, (void *)audio_msg_thunk, (void *)pick_thunk, (void *)super_case, (void *)ctor_wrap, (void *)ctor_wrap,
                  (void *)ctor_wrap, (void *)trigger_hook, (void *)trigger_hook, (void *)kill_thunk, (void *)wall_thunk,
                  (void *)dmg_thunk, (void *)base_level_thunk, (void *)vlc_level_thunk, (void *)pdi_hook,
                  (void *)bolt_case};
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

static void load_settings(void)
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
            else if (!strcmp(key, "test")) test_mode = v[0] != 0;
            else if (!strcmp(key, "impact_range")) impact_range = v[0];
            else if (!strcmp(key, "loop_range")) loop_range = v[0];
            else if (!strcmp(key, "fire_range")) fire_range = v[0];
            else if (!strcmp(key, "rear_speed")) rear_speed = v[0];
            else if (!strcmp(key, "volume")) volume = v[0];
            else if (!strcmp(key, "duck")) duck_depth = v[0];
            else if (!strcmp(key, "rear_offset")) rear_offset = v[0];
            else if (!strcmp(key, "duck_release")) duck_release = v[0];
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
    LONG a = 0, b = 0, c = 0, d = 0, e = 0;
    (void)unused;
    for (;;) {                                      /* counts only: shows the hooks fire in game */
        Sleep(2000);
        if (fired != a || passes != b || walls != c || shields != d || draws != e) {
            a = fired; b = passes; c = walls; d = shields; e = draws;
            say("so far: %ld railgun(s) fired, %ld vehicle hit(s), %ld wall(s) pierced, %ld shield(s) downed, "
                "%ld filtered spawn draw(s) allowed it", a, b, c, d, e);
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
        GetModuleFileNameA(h, dir, sizeof dir);
        slash = strrchr(dir, '\\');
        if (slash) slash[1] = 0;
        sprintf_s(path, sizeof path, "%srailgun.log", dir);
        logfile = _fsopen(path, "w", _SH_DENYNO);   /* readable while the game runs */
        say("railgun v7 loaded");
        srand(GetTickCount());
        load_settings();
        if (test_mode) say("TEST MODE: every Bolt the player picks up becomes a railgun");
        t = CreateThread(NULL, 0, audio, NULL, 0, NULL);
        if (t) CloseHandle(t);
        apply();
        t = CreateThread(NULL, 0, reporter, NULL, 0, NULL);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
