"""NFS Studio en mode diagnostic P1, isolé : port 8799, page = copie de web/index.html modifiée à la volée
(rien n'est écrit dans le dépôt). Les POST sont refusés (aucune construction, aucun enregistrement du circuit).
Paramètres d'URL : old=1 (alphaTest 0.3 partout, avant la phase A), alpha=0 (sans alphaTest), near=N (plan proche), side=front (faces arrière cachées),
color=mat (une couleur par groupe), logdepth=1.
usage : python p1_studio.py BLUR_TOOLS"""
import os
import sys

tools = sys.argv[1]
del sys.argv[1:]
sys.path.insert(0, tools)
os.chdir(tools)
import nfs_web as W  # noqa: E402

DIAG = r"""
const Q = new URLSearchParams(location.search);
const D_SIDE = Q.get('side') === 'front' ? THREE.FrontSide : THREE.DoubleSide;
const D_NEAR = +(Q.get('near') || 1), D_COLOR = Q.get('color') === 'mat';
"""


def page():
    s = open(os.path.join(tools, "web", "index.html"), encoding="utf-8").read()
    rep = [
        ("import { OrbitControls } from 'three/addons/controls/OrbitControls.js';",
         "import { OrbitControls } from 'three/addons/controls/OrbitControls.js';" + DIAG),
        ("new THREE.WebGLRenderer({ antialias: true })",
         "new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: Q.get('logdepth') === '1' })"),
        ("new THREE.PerspectiveCamera(55, 1, 1, 20000)", "new THREE.PerspectiveCamera(55, 1, D_NEAR, 20000)"),
        ("return new THREE.MeshBasicMaterial({ map: tx, side: THREE.DoubleSide, alphaTest: (info.envmap || [])[i] ? 0 : 0.3 });",
         "return D_COLOR ? new THREE.MeshBasicMaterial({ color: new THREE.Color().setHSL((i * 0.618) % 1, 0.7, 0.5), side: D_SIDE })"
         " : new THREE.MeshBasicMaterial({ map: tx, side: D_SIDE, alphaTest: Q.get('old') === '1' ? 0.3"
         " : Q.get('alpha') === '0' ? 0 : (info.envmap || [])[i] ? 0 : 0.3 });"),
        ("<title>", "<title>[DIAG P1] "),
        ("controls.screenSpacePanning = true;",
         "controls.screenSpacePanning = true; window.__v = { camera, controls, scene, renderer, THREE };"),
    ]
    for a, b in rep:
        assert s.count(a) == 1, a
        s = s.replace(a, b)
    return s.encode("utf-8")


class H(W.Handler):
    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            b = page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return None
        return super().do_GET()

    def do_POST(self):
        return self.send_error(403, "diagnostic : lecture seule")


W.ThreadingHTTPServer(("127.0.0.1", 8799), H).serve_forever()
