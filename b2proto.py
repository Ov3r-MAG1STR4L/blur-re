#!/usr/bin/env python3
"""Graphics prototype (offline, nothing installed): one Dubai area of Blur2DubaiTest rendered with a small software
rasteriser, to compare ways of carrying Blur 2's look into Blur 1. Same camera, same geometry, per variant:

  REF  Blur 2 (shader Blur2/InspectionSurface, see b2bake): base x (A.rgb x B.z)^2 x exposure, + cubemap reflection
       from _MaterialTex (R mask, G gloss, B fresnel base) where _HasMaterial and _HasEnvironment
  A    original DXT textures only (Blur 1 unlit template default_NB_NL_NV, flat self light)
  B    textures + Blur 1 scene lighting (default_NB_NV: ambient + sun N.L, no baked light)
  C    textures + Blur 2 lightmap sampled at the VERTICES (Blur 1 vertex colour shader default_NB_NL): sharp tiled
       textures, light interpolated across each triangle
  D    C + the cubemap reflection of REF (what a material / ipr reflection could add)

usage: b2proto.py OUT_DIR [--box X0 X1 Z0 Z1] [--cam X Y Z] [--look X Y Z]
"""
import argparse, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b2bake  # noqa: E402

UNITY = r"C:\Users\sanqu\Jeux_WII\Blur2DubaiTest\Blur2DubaiTest_Data"
W, H = 640, 400
SUN = b2bake.SUN


def extract(box):
    """triangles in the box (game axes): [(P, N, uv0, uv1, material info)], textures, cubemap object"""
    import UnityPy
    from UnityPy.helpers.MeshHelper import MeshHandler
    import b2collision, b2decor
    env = UnityPy.load(UNITY)
    T, img, cube = [], {}, None

    def im(tp, mode):
        k = (tp.path_id, mode)
        if k not in img:
            img[k] = np.asarray(tp.read().image.convert(mode), np.float32) / 255
        return k
    for o in env.objects:
        if o.type.name == "Cubemap" and "envdefault" in o.peek_name():
            cube = o.read()
        if o.type.name != "MeshRenderer":
            continue
        r = o.read()
        go = r.m_GameObject.read()
        comps = [p.read() for p in (x.component if hasattr(x, "component") else x for x in go.m_Component)
                 if p.type.name in ("Transform", "MeshFilter")]
        tr = next(c for c in comps if c.object_reader.type.name == "Transform")
        mf = next((c for c in comps if c.object_reader.type.name == "MeshFilter"), None)
        if mf is None or not mf.m_Mesh.path_id or not b2decor.keep(go, tr, 4):
            continue
        h = MeshHandler(mf.m_Mesh.read())
        h.process()
        if not h.m_UV0:
            continue
        m = b2collision.world_matrix(tr)
        P = (np.array(h.m_Vertices, float).reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]) * [-1, 1, -1]
        inb = (P[:, 0] > box[0]) & (P[:, 0] < box[1]) & (P[:, 2] > box[2]) & (P[:, 2] < box[3])
        if not inb.any():
            continue
        N = (np.array(h.m_Normals, float).reshape(-1, 3) @ np.linalg.inv(m[:3, :3]) * [-1, 1, -1]
             if h.m_Normals else np.zeros_like(P))
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
        uv0 = np.array(h.m_UV0, float).reshape(-1, 2)
        uv1 = np.array(h.m_UV1, float).reshape(-1, 2) if h.m_UV1 else np.zeros_like(uv0)
        for sub, mp in zip(h.get_triangles(), r.m_Materials):
            if not mp.path_id:
                continue
            mat = mp.read()
            te, fl = dict(mat.m_SavedProperties.m_TexEnvs), dict(mat.m_SavedProperties.m_Floats)
            base = te.get("_BaseMap")
            if base is None or not base.m_Texture.path_id or base.m_Texture.read().m_Name.startswith("mdl_"):
                continue
            ok = lambda n: te.get(n) is not None and te[n].m_Texture.path_id
            dual = fl.get("_HasDualLightmap", 0) > .5 and ok("_Lightmap0Tex") and ok("_Lightmap1Tex") and h.m_UV1
            refl = fl.get("_HasMaterial", 0) > .5 and fl.get("_HasEnvironment", 0) > .5 and ok("_MaterialTex")
            info = dict(base=im(base.m_Texture, "RGBA"),
                        st=(base.m_Scale.x, base.m_Scale.y, base.m_Offset.x, base.m_Offset.y),
                        a=im(te["_Lightmap0Tex"].m_Texture, "RGB") if dual else None,
                        b=im(te["_Lightmap1Tex"].m_Texture, "RGB") if dual else None,
                        mat=im(te["_MaterialTex"].m_Texture, "RGB") if refl else None,
                        alpha=fl.get("_AlphaTest", 0) > .5, cut=fl.get("_Cutoff", .5))
            for t in np.array(sub, int).reshape(-1, 3):
                if inb[t].any():
                    T.append((P[t], N[t], uv0[t], uv1[t], info))
    return T, img, cube


def cube_faces(c):
    """the 6 faces (+x, -x, +y, -y, +z, -z) of a Unity cubemap as float RGB arrays, or None"""
    try:
        import texture2ddecoder
        sd = c.m_StreamData                        # streamed: 6 faces one after the other, each with its mips
        with open(os.path.join(UNITY, sd.path), "rb") as fh:
            fh.seek(sd.offset)
            data = fh.read(sd.size)
        assert c.m_TextureFormat == 10, c.m_TextureFormat               # DXT1
        n, top = len(data) // 6, c.m_Width * c.m_Height // 2
        faces = []
        for i in range(6):
            bgra = texture2ddecoder.decode_bc1(data[i * n:i * n + top], c.m_Width, c.m_Height)
            faces.append(np.frombuffer(bgra, np.uint8).reshape(c.m_Height, c.m_Width, 4)[:, :, 2::-1] / 255.0)
        return faces
    except Exception as e:  # noqa: BLE001 - variant D is then skipped, said in the output
        print("cubemap illisible:", e)
        return None


def sample_cube(faces, d):
    """directions d (n, 3) in UNITY axes -> RGB (nearest texel)"""
    ax = np.abs(d).argmax(1)
    out = np.zeros((len(d), 3), np.float32)
    for k in range(3):
        for sgn in (1, -1):
            m = (ax == k) & (np.sign(d[:, k]) == sgn)
            if not m.any():
                continue
            v = d[m] / np.abs(d[m, k:k + 1])
            u_, v_ = {0: (-sgn * v[:, 2], -v[:, 1]), 1: (v[:, 0], sgn * v[:, 2]), 2: (sgn * v[:, 0], -v[:, 1])}[k]
            F = faces[2 * k + (0 if sgn > 0 else 1)]
            h, w = F.shape[:2]
            out[m] = F[np.clip(((v_ + 1) / 2 * (h - 1)).astype(int), 0, h - 1),
                       np.clip(((u_ + 1) / 2 * (w - 1)).astype(int), 0, w - 1)]
    return out


def raster(T, cam, look, fov=60.0):
    """G-buffer: triangle index + perspective-correct barycentrics per pixel"""
    f = look - cam
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    foc = (W / 2) / np.tan(np.radians(fov / 2))
    tid = -np.ones((H, W), int)
    bary = np.zeros((H, W, 3), np.float32)
    zbuf = np.full((H, W), np.inf, np.float32)
    for i, (P, *_rest) in enumerate(T):
        q = P - cam
        z = q @ f
        if (z < 0.5).any():
            continue
        sx = W / 2 + foc * (q @ r) / z
        sy = H / 2 - foc * (q @ u) / z
        x0, x1 = max(int(sx.min()), 0), min(int(np.ceil(sx.max())), W - 1)
        y0, y1 = max(int(sy.min()), 0), min(int(np.ceil(sy.max())), H - 1)
        if x0 > x1 or y0 > y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        (ax, bx, cx), (ay, by, cy) = sx, sy
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        l3 = 1 - l1 - l2
        ins = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not ins.any():
            continue
        w = np.stack([l1 / z[0], l2 / z[1], l3 / z[2]], -1)
        zz = 1 / w.sum(-1)
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        win = ins & (zz < sub)
        sub[win] = zz[win]
        tid[y0:y1 + 1, x0:x1 + 1][win] = i
        bary[y0:y1 + 1, x0:x1 + 1][win] = (w * zz[..., None])[win]
    return tid, bary


def tex(img, k, uv, wrap=True):
    I = img[k]
    h, w = I.shape[:2]
    uv = uv % 1 if wrap else np.clip(uv, 0, 1)
    return I[((1 - uv[:, 1]) * (h - 1)).astype(int), (uv[:, 0] * (w - 1)).astype(int)]


def shade(T, img, faces, tid, bary, cam):
    """{variant: RGB float image}"""
    out = {k: np.full((H, W, 3), (0.72, 0.78, 0.86), np.float32) for k in ("REF", "A", "B", "C", "D")}
    flat = np.flatnonzero(tid >= 0)
    order = np.argsort(tid.ravel()[flat], kind="stable")
    ids = tid.ravel()[flat][order]
    cuts = np.flatnonzero(np.diff(ids)) + 1
    E = b2bake.EXPOSURE
    enc = lambda c: np.clip(c, 0, 1) ** (1 / 2.2)
    for grp in np.split(flat[order], cuts):
        P, N, uv0, uv1, inf = T[tid.ravel()[grp[0]]]
        py, px = np.unravel_index(grp, tid.shape)
        L = bary[py, px]
        st = inf["st"]
        u0 = L @ (uv0 * st[:2] + st[2:])
        base = tex(img, inf["base"], u0)
        if inf["alpha"]:
            keep = base[:, 3] >= inf["cut"]
            py, px, L, u0, base = py[keep], px[keep], L[keep], u0[keep], base[keep]
            if not len(py):
                continue
        lin = base[:, :3] ** 2.2
        n = L @ N
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        if inf["a"] is not None:
            u1 = L @ uv1
            ind = (tex(img, inf["a"], u1, False) * tex(img, inf["b"], u1, False)[:, 2:3]) ** 2 * E
            va = tex(img, inf["a"], uv1, False)
            vtx = (va * tex(img, inf["b"], uv1, False)[:, 2:3]) ** 2 * E
            empty = np.abs(va - (0.86, 0.71, 1.0)).sum(1) < 0.15     # vertex on the page's empty (mauve) padding
            if empty.any():
                vtx[empty] = vtx[~empty].mean(0) if (~empty).any() else ind.mean(0)
            ind_v = L @ vtx                                       # Blur 1 vertex colours: per-vertex light
        else:                                                     # no lightmap: Blur 2's analytic branch
            ind = ind_v = np.repeat((1.25 * np.clip(n @ SUN, 0, 1) + 0.32)[:, None], 3, 1)
        sunlit = (0.45 + 0.75 * np.clip(n @ SUN, 0, 1))[:, None]  # Blur 1 lit shader: ambient + sun
        refl = np.zeros_like(lin)
        amt = np.zeros((len(L), 1), np.float32)
        if inf["mat"] is not None and faces is not None:
            M = tex(img, inf["mat"], u0)
            v = L @ P - cam
            v /= np.linalg.norm(v, axis=1, keepdims=True)
            ndv = (n * v).sum(1)
            fres = np.clip(ndv + 1, 0, 1) ** 2 * np.clip(1.4 * M[:, 1] + .3, 0, 1)
            amt = (M[:, 0] * (M[:, 2] + (1 - M[:, 2]) * fres))[:, None]
            env = sample_cube(faces, (v - 2 * ndv[:, None] * n) * [-1, 1, -1])   # game -> Unity axes
            refl = (env ** 2.2) ** 2 * 8
        ref = lin * ind
        out["REF"][py, px] = enc(ref + amt * (refl - ref))
        out["A"][py, px] = base[:, :3]
        out["B"][py, px] = enc(lin * sunlit)
        c = lin * ind_v
        out["C"][py, px] = enc(c)
        out["D"][py, px] = enc(c + amt * (refl - c))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--box", type=float, nargs=4, default=(-1130, -1030, -770, -660))
    ap.add_argument("--cam", type=float, nargs=3, default=(-1215, 45, -600))
    ap.add_argument("--look", type=float, nargs=3, default=(-1080, 50, -715))
    a = ap.parse_args()
    T, img, cube = extract(a.box)
    faces = cube_faces(cube) if cube is not None else None
    print(len(T), "triangles,", len(img), "textures, cubemap", "ok" if faces else "absent")
    cam, look = np.array(a.cam, float), np.array(a.look, float)
    tid, bary = raster(T, cam, look)
    print("pixels couverts %.0f %%" % (100 * (tid >= 0).mean()))
    out = shade(T, img, faces, tid, bary, cam)
    from PIL import Image, ImageDraw
    os.makedirs(a.out, exist_ok=True)
    sheet = Image.new("RGB", (W * 3, H * 2), "white")
    for k, name in enumerate(("REF", "A", "B", "C", "D")):
        im = Image.fromarray((out[name] * 255).astype(np.uint8))
        ImageDraw.Draw(im).text((8, 8), name, fill=(255, 0, 0))
        im.save(os.path.join(a.out, "proto_%s.png" % name))
        sheet.paste(im, ((k % 3) * W, (k // 3) * H))
    sheet.save(os.path.join(a.out, "proto_planche.png"))
    print("->", a.out)


if __name__ == "__main__":
    main()
