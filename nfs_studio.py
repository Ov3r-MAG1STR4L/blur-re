"""NFS Studio (Projet J) : construire soi-même un circuit Blur à partir d'un lieu de Need for Speed Hot Pursuit Wii.

python nfs_studio.py   (ou « NFS Studio.bat » dans Jeux_WII)
Étapes (onglets) : 1. Lieu et textures -> 2. Circuit (tracé principal + chemins secondaires) -> 3. Bonus et départ
(débloqué quand le circuit est validé) -> 4. Vue 3D, options, construction, installation.
Annuler / rétablir : Ctrl+Z / Ctrl+Y (ou les boutons). Molette = zoom, bouton du milieu = déplacer la carte.
Un circuit par lieu, enregistré dans nfs_extracted/stm_work/world_<lieu>.json (world.json pour location11).
"""
import collections
import copy
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

import config
from tkinter import filedialog, messagebox, ttk

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_nfs_map as M  # noqa: E402
import nfs_atlas as A  # noqa: E402
import stm2obj  # noqa: E402

BLUR_TEST = config.BLUR_TEST
WORK = os.path.dirname(M.WORLD)

TUTO = """NFS STUDIO - DIDACTICIEL

ÉTAPE 1 - LIEU ET TEXTURES
  • « Lieu… » : choisis un fichier .stm de Hot Pursuit (Data/Environments/LocationN/...). Dubaï = location11.
  • Facultatif : « Vérifier textures (FIFO)… » avec une capture Dolphin (.dff) prise dans ce lieu
    (Outils > Lecteur FIFO > Enregistrer 1 image > Sauvegarder). Le journal affiche combien de matériaux
    sont identiques au vrai jeu (85 à 90 % attendus).

ÉTAPE 2 - CIRCUIT
  • Les routes de Hot Pursuit sont en gris, les anciens bonus en cercles orange.
  • Outil « Tracé principal » : clic gauche = ajouter un point dans le sens de la course, clic droit = retirer
    le dernier. Le circuit se referme tout seul (boucle).
  • « Recaler sur l'asphalte » : remet le tracé au milieu de la route, un point tous les 10 m.
  • Outil « Chemin secondaire » : clique près du tracé principal là où le raccourci part, puis le long du
    raccourci, et termine près du tracé principal là où il revient ; « Terminer le chemin » l'enregistre.
    Clic droit = retirer le dernier point du chemin en cours.
  • « Valider le circuit » débloque l'étape 3.

ÉTAPE 3 - BONUS ET DÉPART
  • Outil « Bonus Blur » : clic gauche = une rangée de bonus Blur, clic droit = retirer la plus proche.
    « Bonus aux emplacements HP » en pose une sur chaque ancien bonus.
  • Outil « Départ » : clic gauche = ligne de départ (la grille est placée derrière).

ÉTAPE 4 - VUE 3D ET CONSTRUCTION
  • « Vue 3D » : route, bâtiments, textures (couleurs moyennes), trajet IA, bonus ; cases à cocher.
  • Options : largeur, tours, recul de la grille, rayon du décor, distance d'affichage, taille des zones…
  • « Construire » (plusieurs minutes) puis « Installer dans Blur_test » (Blur fermé).
  • En jeu : course perso, lieu « NFS … ».

Raccourcis : Ctrl+Z annuler, Ctrl+Y rétablir, Ctrl+S enregistrer.
"""


def blur_running():
    return "blur.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower()


class Studio:
    def __init__(self, root):
        self.root = root
        root.title("NFS Studio - circuit Hot Pursuit vers Blur")
        self.log_q = queue.Queue()
        self.state = dict(points=[], branches=[], pickups=[], start=None, validated=False)
        self.undo_stack, self.redo_stack = [], []
        self.branch = []
        self.road = np.zeros((0, 2))
        self.asphalt = np.zeros((0, 2))
        self.hp_pickups = []
        self.data3d = {}
        self.scale, self.ox, self.oz, self.drag = 0.25, 0.0, 0.0, (0, 0)
        self.tool = tk.StringVar(value="main")
        self.stm = tk.StringVar(value=M.STM)
        self.opt = {k: tk.DoubleVar(value=v) for k, v in (
            ("Largeur du circuit (m)", M.TRACK_WIDTH), ("Tours", 3), ("Recul de la grille (m)", A.GRID_GAP),
            ("Rayon du décor (m)", A.RADIUS), ("Distance d'affichage (m)", M.DECOR_DRAW), ("Zones (m)", A.ZONE),
            ("Sommets par modèle", A.VERTS), ("Lumière propre (0-255)", A.GLOW), ("Largeur chemins (m)", 30))}

        top = tk.Frame(root)
        top.pack(fill="x")
        tk.Button(top, text="↶ Annuler", command=self.undo).pack(side="left")
        tk.Button(top, text="↷ Rétablir", command=self.redo).pack(side="left")
        tk.Button(top, text="Enregistrer", command=self.save).pack(side="left", padx=6)
        tk.Button(top, text="Didacticiel", command=self.tutorial).pack(side="left")
        self.info = tk.Label(top, text="")
        self.info.pack(side="left", padx=10)
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="x")
        t1, t2, t3, t4 = (tk.Frame(self.tabs) for _ in range(4))
        for t, n in ((t1, "1. Lieu et textures"), (t2, "2. Circuit"), (t3, "3. Bonus et départ"),
                     (t4, "4. Vue 3D et construction")):
            self.tabs.add(t, text=n)
        self.tabs.tab(2, state="disabled")
        self.tabs.bind("<<NotebookTabChanged>>", self.tab_changed)
        tk.Entry(t1, textvariable=self.stm, width=80).pack(side="left", padx=4)
        tk.Button(t1, text="Lieu…", command=self.pick_stm).pack(side="left")
        tk.Button(t1, text="Charger", command=self.load).pack(side="left")
        tk.Button(t1, text="Vérifier textures (FIFO)…", command=self.check_fifo).pack(side="left", padx=8)
        for v, t in (("main", "Tracé principal"), ("branch", "Chemin secondaire")):
            tk.Radiobutton(t2, text=t, variable=self.tool, value=v).pack(side="left")
        tk.Button(t2, text="Terminer le chemin", command=self.end_branch).pack(side="left", padx=4)
        tk.Button(t2, text="Recaler sur l'asphalte", command=self.recenter).pack(side="left", padx=4)
        tk.Button(t2, text="Effacer le circuit", command=self.clear).pack(side="left")
        tk.Button(t2, text="Valider le circuit ➜", command=self.validate).pack(side="left", padx=10)
        for v, t in (("bonus", "Bonus Blur"), ("start", "Départ")):
            tk.Radiobutton(t3, text=t, variable=self.tool, value=v).pack(side="left")
        tk.Button(t3, text="Bonus aux emplacements HP", command=self.hp_bonus).pack(side="left", padx=6)
        tk.Button(t3, text="Retirer tous les bonus", command=self.clear_bonus).pack(side="left")
        tk.Button(t4, text="Vue 3D…", command=self.view3d).pack(side="left", padx=4)
        tk.Button(t4, text="Options…", command=self.options).pack(side="left")
        tk.Button(t4, text="Construire", command=self.build).pack(side="left", padx=10)
        tk.Button(t4, text="Installer dans Blur_test", command=self.install).pack(side="left")

        self.cv = tk.Canvas(root, width=1000, height=700, bg="white")
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Button-1>", self.left)
        self.cv.bind("<Button-3>", self.right)
        self.cv.bind("<MouseWheel>", self.wheel)
        self.cv.bind("<ButtonPress-2>", lambda e: setattr(self, "drag", (e.x, e.y)))
        self.cv.bind("<B2-Motion>", self.pan)
        root.bind("<Control-z>", lambda e: self.undo())
        root.bind("<Control-y>", lambda e: self.redo())
        root.bind("<Control-s>", lambda e: self.save())
        self.log = tk.Text(root, height=7)
        self.log.pack(fill="x")
        root.after(200, self.pump)
        self.load()

    # --- annuler / rétablir ---------------------------------------------------------------------------------
    def push(self):
        self.undo_stack.append(copy.deepcopy((self.state, self.branch)))
        self.undo_stack = self.undo_stack[-200:]
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy((self.state, self.branch)))
            self.state, self.branch = self.undo_stack.pop()
            self.after_state()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy((self.state, self.branch)))
            self.state, self.branch = self.redo_stack.pop()
            self.after_state()

    def after_state(self):
        self.tabs.tab(2, state="normal" if self.state["validated"] else "disabled")
        self.draw()

    # --- lieu ---------------------------------------------------------------------------------------------------
    def pick_stm(self):
        p = filedialog.askopenfilename(filetypes=[("Lieu Hot Pursuit", "*.stm")])
        if p:
            self.stm.set(p)
            self.load()

    def world_path(self):
        stem = os.path.splitext(os.path.basename(M.STM))[0].lower()
        return os.path.join(WORK, "world.json" if stem == "location11" else "world_%s.json" % stem)

    def load(self):
        M.STM = self.stm.get()
        M.WORLD = self.world_path()
        d = open(M.STM, "rb").read()
        road, asphalt = [], []
        for t, n, b in stm2obj.entries(d):
            if t != 6 or not n.lower().startswith("road"):
                continue
            try:
                pos, _, _ = stm2obj.mesh(b)
                road += pos
                for m in {s[0] for s in stm2obj.submeshes(b)}:
                    if (stm2obj.material_name(d, m) or "").lower().startswith("road_"):
                        asphalt += [pos[a] for f in stm2obj.mesh(b, m)[2] for a, _ in f]
            except (struct.error, ValueError, IndexError):
                pass
        R = np.array(road) if road else np.zeros((0, 3))
        M.HP_GROUND = float(np.percentile(R[:, 1], 5)) if len(R) else M.HP_GROUND   # route la plus basse -> sol Blur
        self.road = R[::3, [0, 2]]
        self.asphalt = np.unique(np.round(np.array(asphalt)[:, [0, 2]], 1), axis=0) if asphalt else self.road
        self.hp_pickups = []
        for m in re.finditer(rb"powerup[0-9]+\x00", d):
            x, y, z, one = struct.unpack_from(">4f", d, m.start() - 16)
            if abs(one - 1) < 1e-6 and abs(y) < 1000:          # (une fiche a des coordonnées aberrantes)
                self.hp_pickups.append((x, z))
        self.state = dict(points=[], branches=[], pickups=[], start=None, validated=False)
        if os.path.exists(M.WORLD):
            mp = json.load(open(M.WORLD))["locations"][0]["maps"][0]
            self.state["points"] = [(p["x"], p["z"]) for p in mp.get("points", [])]
            self.state["branches"] = [[(p["x"], p["z"]) for p in br["points"]] for br in mp.get("branches") or []]
            self.state["pickups"] = [(p["x"], p["z"]) for p in (mp.get("pickups") or [])]
            self.state["validated"] = len(self.state["points"]) > 2
            if mp.get("start_m") is not None and self.state["points"]:
                self.state["start"] = self.point_at(mp["start_m"])
        self.undo_stack, self.redo_stack, self.branch, self.data3d = [], [], [], {}
        if len(self.road):
            c = (self.road.min(0) + self.road.max(0)) / 2
            span = (self.road.max(0) - self.road.min(0)).max()
            self.scale = 680 / span
            self.ox, self.oz = c[0] - 500 / self.scale, c[1] + 350 / self.scale
        self.say("lieu chargé : %s ; %d points de route, %d anciens bonus HP, échelle %s, sol HP %.1f"
                 % (os.path.basename(M.STM), len(R), len(self.hp_pickups),
                    "/".join("%.1f" % (1 / s) for s in stm2obj.SCALE), M.HP_GROUND))
        self.after_state()

    def lengths(self, pts=None):
        pts = pts or self.state["points"]
        P = np.array(pts + pts[:1])
        return np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]

    def point_at(self, s):
        L = self.lengths()
        P = np.array(self.state["points"] + self.state["points"][:1])
        s %= L[-1]
        return (float(np.interp(s, L, P[:, 0])), float(np.interp(s, L, P[:, 1])))

    def arc(self, p):
        P = np.array(self.state["points"])
        return float(self.lengths()[int(np.argmin(np.hypot(*(P - p).T)))])

    # --- carte --------------------------------------------------------------------------------------------------
    def to_screen(self, x, z):
        return (x - self.ox) * self.scale, (self.oz - z) * self.scale

    def to_world(self, sx, sy):
        return sx / self.scale + self.ox, self.oz - sy / self.scale

    def draw(self):
        cv, st = self.cv, self.state
        cv.delete("all")
        for x, z in self.road[::2]:
            sx, sy = self.to_screen(x, z)
            cv.create_rectangle(sx, sy, sx + 1, sy + 1, outline="#b4b4b4")
        if len(st["points"]) > 1:
            cv.create_line(*[c for p in st["points"] + st["points"][:1] for c in self.to_screen(*p)], fill="red", width=2)
        for x, z in st["points"]:
            sx, sy = self.to_screen(x, z)
            cv.create_oval(sx - 2, sy - 2, sx + 2, sy + 2, fill="red", outline="")
        for br in st["branches"] + ([self.branch] if self.branch else []):
            if len(br) > 1:
                cv.create_line(*[c for p in br for c in self.to_screen(*p)], fill="#a020f0", width=2,
                               dash=(4, 2) if br is self.branch else None)
            for x, z in br:
                sx, sy = self.to_screen(x, z)
                cv.create_oval(sx - 2, sy - 2, sx + 2, sy + 2, fill="#a020f0", outline="")
        for x, z in self.hp_pickups:
            sx, sy = self.to_screen(x, z)
            cv.create_oval(sx - 7, sy - 7, sx + 7, sy + 7, outline="orange", width=3)
        for x, z in st["pickups"]:
            sx, sy = self.to_screen(x, z)
            cv.create_rectangle(sx - 5, sy - 5, sx + 5, sy + 5, fill="#2b7bff", outline="")
        if st["start"]:
            sx, sy = self.to_screen(*st["start"])
            cv.create_oval(sx - 6, sy - 6, sx + 6, sy + 6, fill="green", outline="")
            cv.create_text(sx, sy - 14, text="DÉPART", fill="green", font=("Arial", 10, "bold"))
        L = self.lengths()[-1] if len(st["points"]) > 1 else 0
        self.info.config(text="%d points, %.2f km, %d chemins secondaires, %d rangées de bonus%s" % (
            len(st["points"]), L / 1000, len(st["branches"]), len(st["pickups"]),
            "" if st["validated"] else "  (circuit non validé)"))

    def wheel(self, e):
        x, z = self.to_world(e.x, e.y)
        self.scale *= 1.2 if e.delta > 0 else 1 / 1.2
        self.ox, self.oz = x - e.x / self.scale, z + e.y / self.scale
        self.draw()

    def pan(self, e):
        self.ox -= (e.x - self.drag[0]) / self.scale
        self.oz += (e.y - self.drag[1]) / self.scale
        self.drag = (e.x, e.y)
        self.draw()

    def tab_changed(self, _):
        i = self.tabs.index("current")
        if i == 1 and self.tool.get() not in ("main", "branch"):
            self.tool.set("main")
        if i == 2 and self.tool.get() not in ("bonus", "start"):
            self.tool.set("bonus")

    def left(self, e):
        p = self.to_world(e.x, e.y)
        tool, tab = self.tool.get(), self.tabs.index("current")
        if tab == 1 and tool == "main":
            self.push()
            self.state["points"].append(p)
            self.state["validated"] = False
        elif tab == 1 and tool == "branch":
            self.push()
            self.branch.append(p)
        elif tab == 2 and tool == "bonus":
            self.push()
            self.state["pickups"].append(p)
        elif tab == 2 and tool == "start":
            self.push()
            self.state["start"] = p
        else:
            self.say("choisis l'onglet 2 (circuit) ou 3 (bonus / départ) pour dessiner")
        self.after_state()

    def right(self, e):
        p = np.array(self.to_world(e.x, e.y))
        tool, tab = self.tool.get(), self.tabs.index("current")
        self.push()
        if tab == 1 and tool == "main" and self.state["points"]:
            self.state["points"].pop()
            self.state["validated"] = False
        elif tab == 1 and tool == "branch" and self.branch:
            self.branch.pop()
        elif tab == 2 and tool == "bonus" and self.state["pickups"]:
            k = int(np.argmin([np.hypot(*(np.array(q) - p)) for q in self.state["pickups"]]))
            self.state["pickups"].pop(k)
        self.after_state()

    def end_branch(self):
        if len(self.branch) < 2 or len(self.state["points"]) < 3:
            messagebox.showinfo("NFS Studio", "Un chemin secondaire part du tracé principal et y revient :\n"
                                "dessine d'abord le tracé principal, puis au moins 2 points de chemin.")
            return
        self.push()
        self.state["branches"].append(self.branch)
        self.branch = []
        self.say("chemin secondaire ajouté (%d au total)" % len(self.state["branches"]))
        self.after_state()

    def clear(self):
        if messagebox.askyesno("NFS Studio", "Effacer le tracé principal et les chemins secondaires ?"):
            self.push()
            self.state.update(points=[], branches=[], validated=False)
            self.branch = []
            self.after_state()

    def validate(self):
        if len(self.state["points"]) < 3:
            messagebox.showwarning("NFS Studio", "Dessine d'abord le tracé principal (au moins 3 points).")
            return
        self.push()
        self.state["validated"] = True
        self.after_state()
        self.tabs.select(2)
        self.say("circuit validé : place les bonus et le départ")

    def hp_bonus(self):
        self.push()
        self.state["pickups"] += [p for p in self.hp_pickups if p not in self.state["pickups"]]
        self.after_state()

    def clear_bonus(self):
        self.push()
        self.state["pickups"] = []
        self.after_state()

    def recenter(self):
        """rééchantillonne tous les 10 m puis recentre entre les bords de l'asphalte (3 m max par passe)"""
        pts = self.state["points"]
        if len(pts) < 3:
            return
        from scipy.spatial import cKDTree
        self.push()
        L = self.lengths()
        P = np.array(pts + pts[:1])
        s = np.arange(0, L[-1], 10.0)
        C = np.c_[np.interp(s, L, P[:, 0]), np.interp(s, L, P[:, 1])]
        tree = cKDTree(self.asphalt)
        for _ in range(8):
            T = np.roll(C, -1, 0) - np.roll(C, 1, 0)
            T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
            N = np.c_[-T[:, 1], T[:, 0]]
            new = C.copy()
            for i, (c, t, n) in enumerate(zip(C, T, N)):
                r = self.asphalt[tree.query_ball_point(c, 32)] - c
                if len(r) < 4:
                    continue
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
        self.state["points"] = [tuple(map(float, c)) for c in C]
        self.say("circuit recalé : %d points" % len(C))
        self.after_state()

    # --- options, enregistrement, construction -------------------------------------------------------------
    def options(self):
        w = tk.Toplevel(self.root)
        w.title("Options")
        for r, (k, v) in enumerate(self.opt.items()):
            tk.Label(w, text=k).grid(row=r, column=0, sticky="w", padx=6, pady=2)
            tk.Entry(w, textvariable=v, width=10).grid(row=r, column=1, padx=6)
        tk.Button(w, text="OK", command=w.destroy).grid(row=len(self.opt), column=0, columnspan=2, pady=6)

    def apply_options(self):
        o = {k: v.get() for k, v in self.opt.items()}
        M.TRACK_WIDTH = o["Largeur du circuit (m)"]
        A.GRID_GAP = o["Recul de la grille (m)"]
        A.RADIUS = o["Rayon du décor (m)"]
        M.DECOR_DRAW = o["Distance d'affichage (m)"]
        A.ZONE = o["Zones (m)"]
        A.VERTS = int(min(52000, o["Sommets par modèle"]))
        A.GLOW = int(o["Lumière propre (0-255)"])
        return o

    def save(self):
        st = self.state
        if len(st["points"]) < 3:
            messagebox.showwarning("NFS Studio", "Dessine d'abord le tracé principal (au moins 3 points).")
            return False
        o = self.apply_options()
        stem = os.path.splitext(os.path.basename(M.STM))[0]
        w = json.load(open(M.WORLD)) if os.path.exists(M.WORLD) else \
            {"locations": [{"id": "nfs_" + stem.lower(), "name": "NFS " + stem, "maps": [
                {"id": "nfs_%s_1" % stem.lower(), "name": "NFS %s Loop" % stem}]}]}
        mp = w["locations"][0]["maps"][0]
        mp["points"] = [{"x": round(x, 2), "z": round(z, 2)} for x, z in st["points"]]
        total = float(self.lengths()[-1])
        mp["branches"] = []
        for br in st["branches"]:
            a, b = self.arc(br[0]), self.arc(br[-1])
            mp["branches"].append({"from_m": round(a, 1), "to_m": round(b if b > a else b + total, 1),
                                   "width": o["Largeur chemins (m)"],
                                   "points": [{"x": round(x, 2), "z": round(z, 2)} for x, z in br]})
        mp["pickups"] = [{"kind": "row", "x": round(x, 2), "z": round(z, 2)} for x, z in st["pickups"]]
        mp["width"] = M.TRACK_WIDTH
        mp["laps"] = int(o["Tours"])
        mp["auto_bridges"] = False
        mp["obstacles"] = False
        mp["scenery"] = {"ships": False, "cranes": False, "landmarks": False, "lamps": False, "billboards": False,
                         "chevrons": False, "signs": True, "buildings": False, "arch": True}
        if st["start"]:
            mp["start_m"] = mp["finish_m"] = round(self.arc(st["start"]), 1)
        json.dump(w, open(M.WORLD, "w"), indent=1)
        self.say("enregistré : " + M.WORLD)
        return True

    def run(self, fn, label):
        def work():
            try:
                fn()
                self.log_q.put(label + " : terminé")
            except Exception as ex:  # noqa: BLE001 - affiché à l'utilisateur
                self.log_q.put("%s : ERREUR %s" % (label, ex))
        threading.Thread(target=work, daemon=True).start()
        self.say(label + " : en cours…")

    def build(self):
        if not self.state["validated"]:
            messagebox.showwarning("NFS Studio", "Valide d'abord le circuit (onglet 2).")
            return
        if not self.save():
            return
        import builtins

        def work():
            orig = builtins.print
            builtins.print = lambda *a, **k: self.log_q.put(" ".join(map(str, a)))
            try:
                A.rebuild(auto_pickups=False)
            finally:
                builtins.print = orig
        self.run(work, "construction (plusieurs minutes)")

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
                out = os.path.join(WORK, "fifo_" + os.path.splitext(os.path.basename(p))[0] + ".csv")
                d5_fifo.main(M.STM, p, out)
                R = [r for r in csv.DictReader(open(out, encoding="utf-8")) if r["texture_vue"] != "?"]
                ok = sum(r["texture_vue"] == r["texture_attribuee_avant"] for r in R)
                self.log_q.put("%s : %d / %d matériaux identiques au jeu (détail : %s)"
                               % (os.path.basename(p), ok, len(R), out))
        self.run(work, "vérification FIFO")

    # --- vue 3D -------------------------------------------------------------------------------------------------
    def view3d(self):
        """aperçu 3D (matplotlib) : route, bâtiments, couleurs moyennes des textures, trajet IA, bonus"""
        if len(self.state["points"]) < 3:
            messagebox.showwarning("NFS Studio", "Dessine d'abord le circuit.")
            return
        if self.data3d:
            self._show3d()
        else:
            self.run(self._prep3d, "vue 3D (préparation)")

    def _prep3d(self):
        from scipy.spatial import cKDTree
        d = open(M.STM, "rb").read()
        tree = cKDTree(np.array(self.state["points"]))
        colour = {}
        tris = collections.defaultdict(list)
        rng = np.random.default_rng(1)
        for t, n, b in stm2obj.entries(d):
            if t != 6:
                continue
            try:
                pos, _, _ = stm2obj.mesh(b)
                P = np.array(pos)
                if not len(P) or tree.query(P[:, [0, 2]])[0].min() > A.RADIUS:
                    continue
                kind = "route" if n.lower().startswith("road") else "batiments"
                for m in {s[0] for s in stm2obj.submeshes(b)}:
                    tex = stm2obj.material_name(d, m)
                    key = tex or m
                    if key not in colour:
                        try:
                            colour[key] = (np.asarray(stm2obj.texture_image(d, tex).convert("RGB").resize((8, 8)))
                                           .reshape(-1, 3).mean(0) / 255) if tex else \
                                np.array(stm2obj.material_color(d, m)) / 255
                        except Exception:  # noqa: BLE001
                            colour[key] = np.array([0.6, 0.6, 0.6])
                    for f in stm2obj.mesh(b, m)[2]:
                        tris[kind].append((P[[a for a, _ in f]], colour[key]))
            except (struct.error, ValueError, IndexError):
                continue
        for k in tris:                                   # au plus 40 000 triangles par couche (fluidité)
            if len(tris[k]) > 40000:
                tris[k] = [tris[k][i] for i in rng.choice(len(tris[k]), 40000, replace=False)]
        self.data3d = tris
        self.root.after(0, self._show3d)

    def _show3d(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        w = tk.Toplevel(self.root)
        w.title("Vue 3D")
        show = {k: tk.BooleanVar(value=True) for k in ("Route", "Bâtiments", "Textures", "Trajet IA", "Bonus")}
        fig = Figure(figsize=(10, 7))
        ax = fig.add_subplot(111, projection="3d")
        canvas = FigureCanvasTkAgg(fig, w)

        def redraw():
            ax.clear()
            for key, kind in (("Route", "route"), ("Bâtiments", "batiments")):
                if show[key].get() and self.data3d.get(kind):
                    T = np.array([t for t, _ in self.data3d[kind]])
                    cols = [c for _, c in self.data3d[kind]] if show["Textures"].get() else \
                        ("#777777" if kind == "route" else "#c8c8c8")
                    ax.add_collection3d(Poly3DCollection(T[:, :, [0, 2, 1]], facecolors=cols, edgecolors="none"))
            ys = M.HP_GROUND + 2
            if show["Trajet IA"].get():
                P = np.array(self.state["points"] + self.state["points"][:1])
                ax.plot(P[:, 0], P[:, 1], np.full(len(P), ys), color="red", lw=2)
                for br in self.state["branches"]:
                    B = np.array(br)
                    ax.plot(B[:, 0], B[:, 1], np.full(len(B), ys), color="#a020f0", lw=2)
            if show["Bonus"].get():
                for (x, z), c in [(p, "#2b7bff") for p in self.state["pickups"]] + \
                                  [(p, "orange") for p in self.hp_pickups]:
                    ax.scatter([x], [z], [ys + 3], color=c, s=40)
            P = np.array(self.state["points"])
            lo, hi = P.min(0), P.max(0)
            r = (hi - lo).max() / 2 + 100
            c = (lo + hi) / 2
            ax.set_xlim(c[0] - r, c[0] + r)
            ax.set_ylim(c[1] - r, c[1] + r)
            ax.set_zlim(M.HP_GROUND - 20, M.HP_GROUND + 2 * r / 3)
            canvas.draw()
        bar = tk.Frame(w)
        bar.pack(fill="x")
        for k, v in show.items():
            tk.Checkbutton(bar, text=k, variable=v, command=redraw).pack(side="left")
        tk.Label(bar, text="  (glisser = tourner, clic droit glissé = zoom)").pack(side="left")
        canvas.get_tk_widget().pack(fill="both", expand=True)
        redraw()

    # --- divers -------------------------------------------------------------------------------------------------
    def tutorial(self):
        w = tk.Toplevel(self.root)
        w.title("Didacticiel")
        t = tk.Text(w, width=110, height=40, wrap="word")
        t.insert("1.0", TUTO)
        t.config(state="disabled")
        t.pack(fill="both", expand=True)

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
