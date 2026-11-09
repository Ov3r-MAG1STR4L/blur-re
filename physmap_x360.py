"""Top-down point cloud of an X360 (BE) levelphysics: pick runs of coordinate-like floats, phase by min height variance."""
import sys, os, numpy as np
from PIL import Image
def points(path):
    b = open(path, 'rb').read(); b = b[:len(b) // 4 * 4]
    out = []
    for sh in range(4):
        f = np.frombuffer(b[sh:sh + (len(b) - sh) // 4 * 4], '>f4').astype(np.float64)
        a = np.abs(f); ok = np.isfinite(f) & (((a > 0.05) & (a < 30000)) | (f == 0))
        ok &= ~((f == 0) & np.roll(f == 0, 1) & np.roll(f == 0, -1))     # drop zero padding
        d = np.diff(np.concatenate([[0], ok.astype(np.int8), [0]]))
        for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            if e - s < 60: continue
            best = None
            for ph in range(3):
                n = (e - s - ph) // 3
                t = f[s + ph:s + ph + 3 * n].reshape(-1, 3)
                v = t[:, 1].std()
                if t[:, 0].std() > 5 and t[:, 2].std() > 5 and (best is None or v < best[0]): best = (v, t)
            if best is not None and best[0] < min(best[1][:, 0].std(), best[1][:, 2].std()): out.append(best[1])
    return np.concatenate(out) if out else np.zeros((0, 3))
def render(p, dst, size=1400):
    lo = np.percentile(p[:, [0, 2]], 0.5, axis=0); hi = np.percentile(p[:, [0, 2]], 99.5, axis=0)
    k = (size - 20) / max(hi - lo); img = np.zeros((size, size), np.float64)
    xy = ((p[:, [0, 2]] - lo) * k + 10).astype(int); m = (xy >= 0).all(1) & (xy < size).all(1)
    np.add.at(img, (xy[m, 1], xy[m, 0]), 1)
    img = np.log1p(img); img = (255 * (img / img.max()) ** 0.45).astype(np.uint8)
    rgb = np.stack([img // 3, img, np.minimum(255, img.astype(int) + 40).astype(np.uint8) * (img > 0)], -1)
    Image.fromarray(np.flipud(rgb).astype(np.uint8)).save(dst)
    return m.sum(), (hi - lo)
for f in sys.argv[2:]:
    n = os.path.basename(os.path.dirname(f)); p = points(f)
    if len(p) < 100: print(n, 'trop peu de points', len(p)); continue
    c, ext = render(p, os.path.join(sys.argv[1], n + '.png')); print(f'{n:16} {c:8d} points, {ext[0]:.0f} x {ext[1]:.0f} m')
