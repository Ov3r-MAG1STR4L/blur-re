"""NFS Studio (Projet J) : construire soi-même un circuit Blur à partir d'un lieu de Need for Speed Hot Pursuit Wii.

python nfs_studio.py
1. Lieu : fichier .stm (Data/Environments/LocationN/locationNM.stm).
2. Vérifier les textures : une ou plusieurs captures FIFO Dolphin (.dff) -> taux d'accord matériau / texture.
3. Carte vue de dessus (routes en gris, anciens bonus HP en orange) :
   - mode « Circuit » : clic gauche = ajouter un point, clic droit = retirer le dernier ;
     « Recaler sur l'asphalte » rééchantillonne tous les 10 m et recentre entre les bords de la route ;
   - mode « Bonus Blur » : clic gauche = poser une rangée, clic droit = retirer la plus proche ;
   - mode « Départ » : clic gauche = ligne de départ.
   Molette = zoom, glisser avec le bouton du milieu = déplacer.
4. Construire : carte entière en modèles « atlas » par zone (nfs_atlas), collision HP, hauteurs, Map Builder.
5. Installer dans Blur_test (refusé si Blur tourne).
Le circuit est enregistré dans world.json (nfs_extracted/stm_work) : on peut fermer et reprendre.
"""
import json
import os
import queue
import re
import shutil
import struct
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_nfs_map as M  # noqa: E402
import stm2obj  # noqa: E402

BLUR_TEST = r"C:\Users\sanqu\Jeux_WII\Blur_test"


def blur_running():
    out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower()
    return "blur.exe" in out


class Studio:
    def __init__(self, root):
        self.root = root
        root.title("NFS Studio - circuit Hot Pursuit vers Blur")
        self.log_q = queue.Queue()
        self.points, self.pickups, self.start = [], [], None
        self.road = np.zeros((0, 2))
        self.asphalt = np.zeros((0, 2))
        self.hp_pickups = []
        self.scale, self.ox, self.oz = 0.25, 0.0, 0.0
        self.drag = (0, 0)
        self.mode = tk.StringVar(value="circuit")
        self.stm = tk.StringVar(value=M.STM)

        bar = tk.Frame(root)
        bar.pack(fill="x")
        tk.Entry(bar, textvariable=self.stm, width=70).pack(side="left", padx=4)
        tk.Button(bar, text="Lieu…", command=self.pick_stm).pack(side="left")
        tk.Button(bar, text="Charger", command=self.load).pack(side="left")
        tk.Button(bar, text="Vérifier textures (FIFO)…", command=self.check_fifo).pack(side="left", padx=8)
        modes = tk.Frame(root)
        modes.pack(fill="x")
        for v, t in (("circuit", "Circuit"), ("bonus", "Bonus Blur"), ("depart", "Départ")):
            tk.Radiobutton(modes, text=t, variable=self.mode, value=v).pack(side="left")
        tk.Button(modes, text="Recaler sur l'asphalte", command=self.recenter).pack(side="left", padx=6)
        tk.Button(modes, text="Effacer le circuit", command=self.clear).pack(side="left")
        tk.Button(modes, text="Enregistrer", command=self.save).pack(side="left", padx=6)
        tk.Button(modes, text="Construire", command=self.build).pack(side="left")
        tk.Button(modes, text="Installer dans Blur_test", command=self.install).pack(side="left", padx=6)
        self.info = tk.Label(modes, text="")
        self.info.pack(side="left", padx=8)

        self.cv = tk.Canvas(root, width=1000, height=760, bg="white")
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Button-1>", self.left)
        self.cv.bind("<Button-3>", self.right)
        self.cv.bind("<MouseWheel>", self.wheel)
        self.cv.bind("<ButtonPress-2>", lambda e: setattr(self, "drag", (e.x, e.y)))
        self.cv.bind("<B2-Motion>", self.pan)
        self.log = tk.Text(root, height=8)
        self.log.pack(fill="x")
        root.after(200, self.pump)
        self.load()

    # --- données -----------------------------------------------------------------------------------------------
    def pick_stm(self):
        p = filedialog.askopenfilename(filetypes=[("Lieu Hot Pursuit", "*.stm")])
        if p:
            self.stm.set(p)

    def load(self):
        M.STM = self.stm.get()
        d = open(M.STM, "rb").read()
        road, asphalt = [], []
        for t, n, b in stm2obj.entries(d):
            if t != 6 or not n.startswith("ROAD"):
                continue
            try:
                pos, _, _ = stm2obj.mesh(b)
                road += pos[::3]
                for m in {s[0] for s in stm2obj.submeshes(b)}:
                    if (stm2obj.material_name(d, m) or "").lower().startswith("road_"):
                        asphalt += [pos[a] for f in stm2obj.mesh(b, m)[2] for a, _ in f]
            except (struct.error, ValueError, IndexError):
                pass
        self.road = np.array(road)[:, [0, 2]] if road else np.zeros((0, 2))
        self.asphalt = np.unique(np.round(np.array(asphalt)[:, [0, 2]], 1), axis=0) if asphalt else self.road
        self.hp_pickups = []
        for m in re.finditer(rb"powerup[0-9]+\x00", d):
            x, y, z, one = struct.unpack_from(">4f", d, m.start() - 16)
            if abs(one - 1) < 1e-6 and abs(y) < 1000:          # (une fiche a des coordonnées aberrantes)
                self.hp_pickups.append((x, z))
        if os.path.exists(M.WORLD):
            mp = json.load(open(M.WORLD))["locations"][0]["maps"][0]
            self.points = [(p["x"], p["z"]) for p in mp.get("points", [])]
            self.pickups = [(p["x"], p["z"]) for p in (mp.get("pickups") or [])]
            if mp.get("start_m") is not None and self.points:
                self.start = self.point_at(mp["start_m"])
        if len(self.road):
            c = (self.road.min(0) + self.road.max(0)) / 2
            span = (self.road.max(0) - self.road.min(0)).max()
            self.scale = 720 / span
            self.ox, self.oz = c[0] - 500 / self.scale, c[1] + 380 / self.scale
        self.say("lieu chargé : %d points de route, %d anciens bonus HP" % (len(self.road), len(self.hp_pickups)))
        self.draw()

    def lengths(self):
        P = np.array(self.points + self.points[:1])
        return np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]

    def point_at(self, s):
        L = self.lengths()
        P = np.array(self.points + self.points[:1])
        s = s % L[-1]
        return (float(np.interp(s, L, P[:, 0])), float(np.interp(s, L, P[:, 1])))

    # --- vue ----------------------------------------------------------------------------------------------------
    def to_screen(self, x, z):
        return (x - self.ox) * self.scale, (self.oz - z) * self.scale

    def to_world(self, sx, sy):
        return sx / self.scale + self.ox, self.oz - sy / self.scale

    def draw(self):
        cv = self.cv
        cv.delete("all")
        for x, z in self.road[::2]:
            sx, sy = self.to_screen(x, z)
            cv.create_rectangle(sx, sy, sx + 1, sy + 1, outline="#b0b0b0")
        if len(self.points) > 1:
            pts = [c for p in self.points + self.points[:1] for c in self.to_screen(*p)]
            cv.create_line(*pts, fill="red", width=2)
        for x, z in self.points:
            sx, sy = self.to_screen(x, z)
            cv.create_oval(sx - 2, sy - 2, sx + 2, sy + 2, fill="red", outline="")
        for x, z in self.hp_pickups:
            sx, sy = self.to_screen(x, z)
            cv.create_oval(sx - 7, sy - 7, sx + 7, sy + 7, outline="orange", width=3)
        for x, z in self.pickups:
            sx, sy = self.to_screen(x, z)
            cv.create_rectangle(sx - 5, sy - 5, sx + 5, sy + 5, fill="#2b7bff", outline="")
        if self.start:
            sx, sy = self.to_screen(*self.start)
            cv.create_text(sx, sy - 14, text="DÉPART", fill="green", font=("Arial", 10, "bold"))
            cv.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill="green", outline="")
        L = self.lengths()[-1] if len(self.points) > 1 else 0
        self.info.config(text="%d points, %.2f km, %d rangées de bonus" % (len(self.points), L / 1000, len(self.pickups)))

    def wheel(self, e):
        x, z = self.to_world(e.x, e.y)
        self.scale *= 1.2 if e.delta > 0 else 1 / 1.2
        self.ox, self.oz = x - e.x / self.scale, z + e.y / self.scale
        self.draw()

    def pan(self, e):
        dx, dy = e.x - self.drag[0], e.y - self.drag[1]
        self.ox -= dx / self.scale
        self.oz += dy / self.scale
        self.drag = (e.x, e.y)
        self.draw()

    def left(self, e):
        p = self.to_world(e.x, e.y)
        if self.mode.get() == "circuit":
            self.points.append(p)
        elif self.mode.get() == "bonus":
            self.pickups.append(p)
        else:
            self.start = p
        self.draw()

    def right(self, e):
        p = np.array(self.to_world(e.x, e.y))
        if self.mode.get() == "circuit" and self.points:
            self.points.pop()
        elif self.mode.get() == "bonus" and self.pickups:
            k = int(np.argmin([np.hypot(*(np.array(q) - p)) for q in self.pickups]))
            self.pickups.pop(k)
        self.draw()

    def clear(self):
        if messagebox.askyesno("NFS Studio", "Effacer tout le tracé du circuit ?"):
            self.points = []
            self.draw()

    # --- tracé --------------------------------------------------------------------------------------------------
    def recenter(self):
        """rééchantillonne tous les 10 m puis recentre chaque point entre les bords de l'asphalte (3 m max par
        passe : ne saute pas sur une route voisine)"""
        if len(self.points) < 3:
            return
        from scipy.spatial import cKDTree
        L = self.lengths()
        P = np.array(self.points + self.points[:1])
        s = np.arange(0, L[-1], 10.0)
        C = np.c_[np.interp(s, L, P[:, 0]), np.interp(s, L, P[:, 1])]
        tree = cKDTree(self.asphalt)
        for _ in range(8):
            T = np.roll(C, -1, 0) - np.roll(C, 1, 0)
            T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
            N = np.c_[-T[:, 1], T[:, 0]]
            new = C.copy()
            for i, (c, t, n) in enumerate(zip(C, T, N)):
                near = self.asphalt[tree.query_ball_point(c, 32)]
                if len(near) < 4:
                    continue
                r = near - c
                lat = np.sort((r @ n)[np.abs(r @ t) < 4])
                if len(lat) < 4:
                    continue
                lo = hi = lat[np.abs(lat).argmin()]
                for v in lat[lat < lo][::-1]:
                    if lo - v > 3:
                        break
                    lo = v
                for v in lat[lat > hi]:
                    if v - hi > 3:
                        break
                    hi = v
                new[i] = c + n * float(np.clip((lo + hi) / 2, -3, 3))
            C = (np.roll(new, 1, 0) + 2 * new + np.roll(new, -1, 0)) / 4
        self.points = [tuple(map(float, c)) for c in C]
        self.say("circuit recalé : %d points" % len(self.points))
        self.draw()

    def save(self):
        if len(self.points) < 3:
            messagebox.showwarning("NFS Studio", "Dessine d'abord le circuit (au moins 3 points).")
            return False
        w = json.load(open(M.WORLD)) if os.path.exists(M.WORLD) else \
            {"locations": [{"id": "nfs_dubai", "name": "NFS Dubai", "maps": [{"id": "nfs_dubai_1", "name": "Dubai Loop"}]}]}
        mp = w["locations"][0]["maps"][0]
        mp["points"] = [{"x": round(x, 2), "z": round(z, 2)} for x, z in self.points]
        mp["pickups"] = [{"kind": "row", "x": round(x, 2), "z": round(z, 2)} for x, z in self.pickups]
        mp["width"] = M.TRACK_WIDTH
        mp.setdefault("laps", 3)
        mp["auto_bridges"] = False
        mp["obstacles"] = False
        mp["scenery"] = {"ships": False, "cranes": False, "landmarks": False, "lamps": False, "billboards": False,
                         "chevrons": False, "signs": True, "buildings": False, "arch": True}
        if self.start:
            P = np.array(self.points)
            k = int(np.argmin(np.hypot(*(P - self.start).T)))
            mp["start_m"] = mp["finish_m"] = round(float(self.lengths()[k]), 1)
        json.dump(w, open(M.WORLD, "w"), indent=1)
        self.say("enregistré : " + M.WORLD)
        return True

    # --- construction / vérification ---------------------------------------------------------------------------
    def run(self, fn, label):
        def work():
            try:
                fn()
                self.log_q.put(label + " : terminé")
            except Exception as ex:  # noqa: BLE001 - affiché à l'utilisateur
                self.log_q.put("%s : ERREUR %s" % (label, ex))
        threading.Thread(target=work, daemon=True).start()
        self.say(label + " : en cours (plusieurs minutes)…")

    def build(self):
        if not self.save():
            return
        import builtins
        import nfs_atlas

        def work():
            orig = builtins.print
            builtins.print = lambda *a, **k: self.log_q.put(" ".join(map(str, a)))
            try:
                nfs_atlas.rebuild(auto_pickups=False)
            finally:
                builtins.print = orig
        self.run(work, "construction")

    def install(self):
        if blur_running():
            messagebox.showwarning("NFS Studio", "Blur tourne : ferme-le avant d'installer.")
            return

        def work():
            n = 0
            for root, _, files in os.walk(M.OUT):
                for f in files:
                    src = os.path.join(root, f)
                    dst = os.path.join(BLUR_TEST, os.path.relpath(src, M.OUT))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(src, dst)
                    if open(src, "rb").read() != open(dst, "rb").read():
                        raise IOError("copie différente : " + dst)
                    n += 1
            self.log_q.put("%d fichiers installés et vérifiés dans %s" % (n, BLUR_TEST))
        self.run(work, "installation")

    def check_fifo(self):
        paths = filedialog.askopenfilenames(filetypes=[("Capture FIFO Dolphin", "*.dff")])
        if not paths:
            return
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "nfs_diag"))
        import csv
        import d5_fifo

        def work():
            for p in paths:
                out = os.path.join(os.path.dirname(M.WORLD), "fifo_" + os.path.splitext(os.path.basename(p))[0] + ".csv")
                d5_fifo.main(M.STM, p, out)
                R = [r for r in csv.DictReader(open(out, encoding="utf-8")) if r["texture_vue"] != "?"]
                ok = sum(r["texture_vue"] == r["texture_attribuee_avant"] for r in R)
                self.log_q.put("%s : %d / %d matériaux identiques au jeu (détail : %s)"
                               % (os.path.basename(p), ok, len(R), out))
        self.run(work, "vérification FIFO")

    def say(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def pump(self):
        while not self.log_q.empty():
            self.say(self.log_q.get())
        self.root.after(200, self.pump)


if __name__ == "__main__":
    tk_root = tk.Tk()
    Studio(tk_root)
    tk_root.mainloop()
