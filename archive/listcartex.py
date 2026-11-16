import glob, os
from blurtex import records

GENERIC = ("paintdent", "tyre", "breakdisc", "smashedglass", "carbonfibre", "cali_", "DefaultColour", "uk_12")
for f in sorted(glob.glob(r"C:\Users\sanqu\Jeux_WII\blur_extracted\root\models\vehicles\*.model")):
    b = open(f, "rb").read()
    names = []
    for r in records(b):
        n = r["name"]
        if n and not n.startswith(GENERIC) and n not in names:
            names.append("%s(%dx%d)" % (n, r["w"], r["h"]) if r["kind"] == "inline" or r["w"] <= 16 else n)
    print(os.path.basename(f)[:-6].ljust(38), ", ".join(names))
