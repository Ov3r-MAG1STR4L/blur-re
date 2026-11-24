/* Check of the v16 camera up against the game's own GetLookQuat (Blur.exe mapped at its base, not run).
   Build and run (x86 tools, as build.bat):
     cl /nologo /O2 test_cam.c /link /BASE:0x30000000 /FIXED /DYNAMICBASE:NO && test_cam.exe "<path>\Blur.exe"
   Prints FAIL and returns 1 on any mismatch. */
#include "b2gravity.c"

static int fails = 0;
static void check(int ok, const char *what) { printf("%s  %s\n", ok ? "ok  " : "FAIL", what); fails += !ok; }

static float dot3(const float *a, const float *b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

int main(int argc, char **argv)
{
    HMODULE m;
    DWORD old;
    float out[4], R[3][3], ax[3], ay[3], az[3], q[4];
    static const float Y[3] = {0.f, 1.f, 0.f};
    int i, ok;
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 2) { printf("usage: test_cam <Blur.exe>\n"); return 2; }
    m = LoadLibraryExA(argv[1], NULL, DONT_RESOLVE_DLL_REFERENCES);   /* relocated by the loader if 0x400000 is taken */
    if (!m) { printf("Blur.exe not mapped\n"); return 2; }
    {   /* the image is mapped but not relocated: copy GetLookQuat (0x58B4D0..0x58BB7A, no relative call out) and
           point its absolute operands (4 constants, the _copysign import) at our own copies */
        static const unsigned abs_refs[5] = {0xE53328, 0xE62BD0, 0xE63B58, 0xE831F8, 0xE831FC};
        static void *cells[5];
        unsigned len = 0x58BB7A - GETLOOKQUAT, i2, r;
        unsigned char *src = (unsigned char *)m + (GETLOOKQUAT - 0x400000u);
        unsigned char *code = (unsigned char *)VirtualAlloc(NULL, len, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
        int patched = 0;
        (void)old;
        memcpy(code, src, len);
        for (r = 0; r < 5; r++) cells[r] = *(void **)((unsigned char *)m + (abs_refs[r] - 0x400000u));
        cells[0] = (void *)_copysign;
        for (i2 = 0; i2 + 4 <= len; i2++)
            for (r = 0; r < 5; r++)
                if (*(unsigned *)(code + i2) == abs_refs[r]) { *(void ***)(code + i2) = &cells[r]; patched++; }
        getlookquat = (unsigned)code;
        printf("GetLookQuat copied from %p, %d absolute operands redirected\n", (void *)src, patched);
    }

    quat_calibrate();
    check(quat_conv > 0, "convention found against the game's GetLookQuat");
    if (quat_conv <= 0) return 1;

    /* world up: our frame -> quaternion equals the game's for many directions */
    ok = 1;
    for (i = 0; i < 2000; i++) {
        float d[3] = {(float)(rand() % 2001 - 1000), (float)(rand() % 2001 - 1000), (float)(rand() % 2001 - 1000)};
        float g[4];
        if (fabsf(d[1]) > 0.98f * sqrtf(dot3(d, d)) || dot3(d, d) < 1.f) continue;
        ((lookquat_fn)getlookquat)(g, d);
        look_frame(d, Y, NULL, ax, ay, az);
        frame_quat(ax, ay, az, quat_conv, q);
        if (fabsf(g[0] * q[0] + g[1] * q[1] + g[2] * q[2] + g[3] * q[3]) < 0.9999f) ok = 0;
    }
    check(ok, "same quaternion as the game for 2000 directions (world up)");

    /* car on a wall (up = +x), looking along +z: camera up = +x, side axis _|_ up */
    {
        float U[3] = {1.f, 0.f, 0.f}, d[3] = {0.f, -0.2f, 1.f}, cax[3], cay[3], caz[3];
        look_frame(d, U, NULL, ax, ay, az);
        frame_quat(ax, ay, az, quat_conv, out);
        quat_mat(out, R);
        for (i = 0; i < 3; i++) {
            cax[i] = quat_conv == 1 ? R[0][i] : R[i][0];
            cay[i] = quat_conv == 1 ? R[1][i] : R[i][1];
            caz[i] = quat_conv == 1 ? R[2][i] : R[i][2];
        }
        check(fabsf(dot3(cax, U)) < 1e-4f && dot3(cay, U) > 0.9f && dot3(caz, d) > 0.f, "wall: camera up along the car's up");
    }

    /* top of a loop: view along the old up -> no degenerate frame (side axis kept) */
    {
        float xprev[3] = {1.f, 0.f, 0.f}, d[3] = {0.f, 1.f, 0.f};
        check(look_frame(d, Y, xprev, ax, ay, az) && fabsf(dot3(ax, d)) < 1e-4f, "loop top: side axis kept");
    }

    /* easing: camera on a car stuck to a wall, then on the ceiling (up opposite to the camera's), then back */
    {
        float obj[3] = {10.f, 5.f, 3.f};
        int s;
        armed = 1; cam_tau = 0.f;
        s = cam_slot(0x1234);
        veh_pos[0][0] = obj[0]; veh_pos[0][1] = obj[1]; veh_pos[0][2] = obj[2];
        veh_up[0][0] = 1.f; veh_up[0][1] = 0.f; veh_up[0][2] = 0.f; veh_on[0] = 1;
        cam_ease(s, obj);
        check(fabsf(cam_up[s][0] - 1.f) < 1e-4f && !world_up(s), "ease: follows the car's up (tau 0)");
        cam_tau = 0.3f; cam_up[s][0] = 0.f; cam_up[s][1] = 1.f; cam_up[s][2] = 0.f; cam_x[s][0] = cam_x[s][1] = cam_x[s][2] = 0.f;
        veh_up[0][0] = 0.f; veh_up[0][1] = -1.f;
        cam_t[s].QuadPart = 0;                       /* one 1/60 s frame (not the microseconds since the last call) */
        cam_ease(s, obj);
        check(cam_up[s][1] < 0.999f && fabsf(sqrtf(dot3(cam_up[s], cam_up[s])) - 1.f) < 1e-4f, "ease: opposite up starts turning");
        veh_on[0] = 0; cam_tau = 0.f;
        cam_ease(s, obj);
        check(world_up(s), "ease: back to world up off the surface");
    }
    printf(fails ? "%d FAILED\n" : "all ok\n", fails);
    return fails != 0;
}
