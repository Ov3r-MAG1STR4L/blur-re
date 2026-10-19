import io, struct, sys
import numpy as np
from PIL import Image
from blurmodel import dds_header
from blurtex import records


def smooth(b, start, w, h, fourcc, crop=128):
    bs = 8 if fourcc == b"DXT1" else 16
    # decode only the first `crop` rows worth of blocks to keep it fast and comparable
    rows = min(h, crop)
    n = ((w + 3) // 4) * ((rows + 3) // 4) * bs
    dds = dds_header(w, rows, 1, fourcc) + b[start:start + n]
    try:
        a = np.asarray(Image.open(io.BytesIO(dds)).convert("L"), dtype=np.int32)
    except Exception:
        return 1e9
    return float(np.abs(np.diff(a, axis=1)).mean() + np.abs(np.diff(a, axis=0)).mean())


for path in sys.argv[1:]:
    b = open(path, "rb").read()
    R = [r for r in records(b) if r["kind"] == "level" and r["w"] >= 256]
    print(path.split("\\")[-1])
    for r in R[:8]:
        p = r["p"]
        res = sorted((smooth(b, p + 20 + k, r["w"], r["h"], r["fourcc"]), k) for k in range(0, 64))
        s0, k0 = res[0]
        print("  w", r["w"], "p", hex(p), "best start=p+20+%d" % k0, "abs", hex(p + 20 + k0), "mod16", (p + 20 + k0) % 16,
              "score", round(s0, 1), "next", [(round(s, 1), k) for s, k in res[1:3]])
