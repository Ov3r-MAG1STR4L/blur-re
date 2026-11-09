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
    """Top-down, coloured by height (blue low -> yellow high) on a light background, 2 px dots."""
    lo = np.percentile(p[:, [0, 2]], 0.5, axis=0); hi = np.percentile(p[:, [0, 2]], 99.5, axis=0)
    k = (size - 20) / max(hi - lo)
    xy = ((p[:, [0, 2]] - lo) * k + 10).astype(int); m = (xy >= 0).all(1) & (xy < size - 1).all(1)
    y = p[m, 1]; ylo, yhi = np.percentile(y, [2, 98]); t = np.clip((y - ylo) / max(yhi - ylo, 1e-6), 0, 1)
    stops = np.array([[30, 60, 160], [0, 160, 160], [60, 170, 60], [230, 200, 40], [200, 60, 30]], float)
    c = np.array([np.interp(t, np.linspace(0, 1, len(stops)), stops[:, i]) for i in range(3)]).T
    img = np.full((size, size, 3), 245, np.uint8)
    order = np.argsort(y)                                    # higher points drawn last
    for dx in (0, 1):
        for dy in (0, 1):
            img[xy[m][order, 1] + dy, xy[m][order, 0] + dx] = c[order]
    Image.fromarray(np.flipud(img)).save(dst)
    return m.sum(), (hi - lo)
for f in sys.argv[2:]:
    n = os.path.basename(os.path.dirname(f)); p = points(f)
    if len(p) < 100: print(n, 'trop peu de points', len(p)); continue
    c, ext = render(p, os.path.join(sys.argv[1], n + '.png')); print(f'{n:16} {c:8d} points, {ext[0]:.0f} x {ext[1]:.0f} m')
