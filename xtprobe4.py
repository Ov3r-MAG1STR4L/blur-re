import struct
from blurxt import XT

x = XT(r"C:\Users\sanqu\Jeux_WII\blur_extracted\gamedata\gamedata\xt\amax.bin")
b = x.b; d = x.data
foff, fcnt = x.sec[2]
F = [struct.unpack_from("<HHHH", b, foff + 8 * i) for i in range(fcnt)]
toff, tcnt = x.sec[0]
T = [struct.unpack_from("<HHHHHH", b, toff + 12 * i) for i in range(tcnt)]
print("type7", T[7])
first = T[7][2]
print("fields of type 7 (first idx per type table col 2 =", first, ")")
for i in range(0, 74):
    print(i, F[i])
# find 620-stride regions
best = []
step = 620
for start in range(0, len(d) - step * 4, 4):
    same = sum(d[start + k] == d[start + step + k] for k in range(0, 200))
    if same > 150: best.append(start)
print("candidate record starts:", [hex(s) for s in best[:20]], len(best))
