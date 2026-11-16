r"""python -m unittest tests.test_studios_http   (depuis blur_tools ; ~1 min) : les 3 vrais serveurs, sur d'autres
ports (BLURRE_PORT, sans navigateur), requêtes normales et malveillantes.
NFS Studio tourne sur des dossiers temporaires (BLURRE_STM_WORK, BLURRE_NFS_OUT, BLURRE_BLUR_TEST : faux Blur_test) :
enregistrement et installation complets sans toucher aux vrais fichiers. Reverse Studio et Tracés Blur 2 tournent sur
les vrais dossiers : seulement des requêtes refusées, et le test vérifie que rien n'a changé (empreintes).
"""
import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import config  # noqa: E402
import maplock  # noqa: E402

PORTS = {"nfs_web.py": 18765, "reverse_web.py": 18766, "b2track.py": 18767}
MARINA = os.path.join(config.JEUX, "blur2_aid", "dubai", "marina_trace.json")


def empreinte(*chemins):
    """hash du contenu de fichiers / dossiers (liste triée des fichiers et de leurs octets)"""
    h = hashlib.sha256()
    for c in chemins:
        fs = [c] if os.path.isfile(c) else sorted(os.path.join(d, f) for d, _, n in os.walk(c) for f in n)
        for f in fs:
            h.update(f.encode())
            h.update(open(f, "rb").read())
    return h.hexdigest()


def libre(port):
    try:
        socket.create_connection(("127.0.0.1", port), 0.5).close()
        return False
    except OSError:
        return True


def demarrer(script, env=None):
    """lance le serveur et attend qu'IL réponde. Refus si le port est déjà pris : le test parlerait à un autre
    serveur, avec la vraie configuration (incident du 2026-11-10 : installation réelle dans Blur_test)"""
    port = PORTS[script]
    if not libre(port):
        raise RuntimeError("port %d déjà occupé : arrêter l'autre serveur avant les tests" % port)
    e = dict(os.environ, BLURRE_PORT=str(port), BLURRE_NO_BROWSER="1", **(env or {}))
    p = subprocess.Popen([sys.executable, script], cwd=HERE, env=e, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(240):
        try:
            socket.create_connection(("127.0.0.1", port), 0.5).close()
            time.sleep(1)
            if p.poll() is not None:            # un autre processus a pris le port entre-temps
                raise RuntimeError("%s s'est arrêté : %s" % (script, p.stderr.read().decode(errors="replace")[-800:]))
            return p
        except OSError:
            if p.poll() is not None:
                raise RuntimeError("%s s'est arrêté : %s" % (script, p.stderr.read().decode(errors="replace")[-800:]))
            time.sleep(0.5)
    arreter(p)
    raise RuntimeError(script + " ne répond pas")


def arreter(p):
    """arrête le serveur et attend sa fin (sinon il peut survivre au test et garder le port)"""
    p.kill()
    p.wait(10)
    p.stderr.close()


def req(port, method, path, body=None, host=None, origin="page", site=None, raw=None, headers=None):
    """origin="page" = Origin de la page du studio (comme fetch dans la page) ; None = pas d'Origin (script local)"""
    h = {"Host": host or "127.0.0.1:%d" % port}
    if origin == "page":
        h["Origin"] = "http://127.0.0.1:%d" % port
    elif origin:
        h["Origin"] = origin
    if site:
        h["Sec-Fetch-Site"] = site
    h.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    out = r.read()
    c.close()
    try:
        out = json.loads(out)
    except ValueError:
        pass
    return r.status, out


class Commun:
    """attaques communes aux 3 serveurs ; ECRIT = un POST qui écrirait s'il passait"""
    port = None
    ECRIT = None

    def test_dns_rebinding(self):
        self.assertEqual(req(self.port, "GET", "/", host="evil.example:%d" % self.port)[0], 403)

    def test_autre_site_refuse(self):
        path, body = self.ECRIT
        for kw in (dict(origin="https://evil.example"), dict(origin="null"),
                   dict(origin="http://127.0.0.1:18766" if self.port != 18766 else "http://127.0.0.1:18765"),
                   dict(origin=None, site="cross-site"), dict(origin=None, site="same-site")):
            self.assertEqual(req(self.port, "POST", path, body, **kw)[0], 403, kw)

    def test_json_invalide(self):
        path, _ = self.ECRIT
        st, out = req(self.port, "POST", path, raw=b"{pas du json")
        self.assertIn(st, (400, 404), out)


class NFS(Commun, unittest.TestCase):
    port = PORTS["nfs_web.py"]
    ECRIT = ("/api/world", {"locations": [{"maps": []}]})

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="nfs_test_")
        cls.work, cls.out, cls.test = (os.path.join(cls.tmp, n) for n in ("stm_work", "out", "Blur_test"))
        cls.files = os.path.join(cls.out, "files")
        os.makedirs(cls.work)
        os.makedirs(os.path.join(cls.files, "levels"))
        os.makedirs(os.path.join(cls.test, "levels"))
        cls.world = json.load(open(os.path.join(config.STM_WORK, "world.json")))
        cls.world["locations"][0]["name"] = "TEST_TEMPORAIRE"        # marque : prouve que le serveur lit le dossier temporaire
        json.dump(cls.world, open(os.path.join(cls.work, "world.json"), "w"))
        open(os.path.join(cls.files, "levels", "a.bin"), "wb").write(b"neuf")
        open(os.path.join(cls.test, "levels", "a.bin"), "wb").write(b"original")
        cls.p = demarrer("nfs_web.py", dict(BLURRE_STM_WORK=cls.work, BLURRE_NFS_OUT=cls.files,
                                            BLURRE_BLUR_TEST=cls.test))
        w = req(cls.port, "GET", "/api/world")[1]
        if not (isinstance(w, dict) and w["locations"][0]["name"] == "TEST_TEMPORAIRE"):
            arreter(cls.p)
            raise RuntimeError("le serveur NFS ne lit pas le dossier temporaire : tests arrêtés avant tout envoi")

    @classmethod
    def tearDownClass(cls):
        arreter(cls.p)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def journal(self, mot, delai=30):
        for _ in range(delai * 2):
            log = req(self.port, "GET", "/api/log")[1]
            if any(mot in l for l in log):
                return log
            time.sleep(0.5)
        self.fail("pas de « %s » dans le journal : %s" % (mot, log[-5:]))

    def test_normal_page_lieux_circuit(self):
        self.assertEqual(req(self.port, "GET", "/")[0], 200)
        st, loc = req(self.port, "GET", "/api/locations")
        self.assertEqual(st, 200)
        self.assertTrue(loc["all"])
        self.assertEqual(req(self.port, "GET", "/api/world")[1], self.world)

    def test_normal_enregistrement_et_bak(self):
        w = json.loads(json.dumps(self.world))
        w["locations"][0]["name"] = "essai"
        self.assertEqual(req(self.port, "POST", "/api/world", w), (200, {"ok": True}))
        f = os.path.join(self.work, "world.json")
        self.assertEqual(json.load(open(f))["locations"][0]["name"], "essai")
        self.assertTrue(os.path.isfile(f + ".bak"))
        self.assertEqual(req(self.port, "POST", "/api/world", self.world)[0], 200)

    def test_circuit_invalide_refuse(self):
        f = os.path.join(self.work, "world.json")
        avant = empreinte(f)
        for mauvais in ({"x": 1}, [], {"locations": "abc"}, {"locations": []}, {"locations": [{"maps": 3}]}):
            self.assertEqual(req(self.port, "POST", "/api/world", mauvais)[0], 400, mauvais)
        self.assertEqual(empreinte(f), avant)

    def test_lieu_hors_liste_et_cache(self):
        for stm in (r"C:\Windows\win.ini", r"..\..\config.py", os.path.join(HERE, "config.py")):
            st, out = req(self.port, "GET", "/api/load?stm=" + stm)
            self.assertEqual(st, 400, out)
        self.assertEqual(req(self.port, "GET", "/api/load?stm=x", origin=None, site="cross-site")[0], 403)  # <img>
        for p in ("/cache/../world.json", "/cache/..%2Fworld.json", "/cache/..%5Cworld.json",
                  "/cache/%2E%2E/%2E%2E/config.py", "/cache/C:%5CWindows%5Cwin.ini"):
            self.assertEqual(req(self.port, "GET", p)[0], 404, p)

    def test_corps_trop_gros(self):
        st, _ = req(self.port, "POST", "/api/world", raw=b"{}", headers={"Content-Length": str(10 ** 9)})
        self.assertEqual(st, 413)

    def test_installation_protegee(self):
        os.remove(os.path.join(self.test, "COPIE_DE_TEST_HORS_LIGNE.txt")) if os.path.exists(
            os.path.join(self.test, "COPIE_DE_TEST_HORS_LIGNE.txt")) else None
        self.assertEqual(req(self.port, "POST", "/api/install", origin="https://evil.example")[0], 403)
        self.assertEqual(req(self.port, "POST", "/api/install")[0], 200)
        self.journal("pas la copie de test")                                    # sans fichier témoin : refus
        self.assertEqual(open(os.path.join(self.test, "levels", "a.bin"), "rb").read(), b"original")
        open(os.path.join(self.test, "COPIE_DE_TEST_HORS_LIGNE.txt"), "w").write("test")
        time.sleep(0.5)
        self.assertEqual(req(self.port, "POST", "/api/install")[0], 200)
        log = self.journal("installation :")
        if any("Blur tourne" in l for l in log):
            self.skipTest("Blur est ouvert : installation réelle non testée")
        self.assertEqual(open(os.path.join(self.test, "levels", "a.bin"), "rb").read(), b"neuf")
        self.assertEqual(open(os.path.join(self.out, "backup_studio", "levels", "a.bin"), "rb").read(), b"original")


class Reverse(Commun, unittest.TestCase):
    port = PORTS["reverse_web.py"]
    ECRIT = ("/api/edits", {"name": "x", "edits": {}})

    @classmethod
    def setUpClass(cls):
        cls.avant = empreinte(maplock.EDITS, maplock.LOCKS)
        cls.p = demarrer("reverse_web.py")

    @classmethod
    def tearDownClass(cls):
        arreter(cls.p)
        assert empreinte(maplock.EDITS, maplock.LOCKS) == cls.avant, "edits / locks modifiés par le test !"

    def test_normal(self):
        st, out = req(self.port, "GET", "/api/routes")
        self.assertEqual(st, 200)
        self.assertTrue(out["routes"])
        self.assertEqual(req(self.port, "GET", "/")[0], 200)

    def test_noms_hors_liste(self):
        for name in (r"..\..\..\blur_tools\config", "../../x", "C:\\Windows\\x", "", None, 3):
            for path, body in (("/api/edits", {"name": name, "edits": {"a": 1}}),
                               ("/api/cams", {"name": name, "cams": {"vista": [1]}}),
                               ("/api/unlock", {"name": name}), ("/api/lock", {"name": name})):
                self.assertEqual(req(self.port, "POST", path, body)[0], 404, (path, name))
        for p in ("/api/route?name=..%2F..%2Fx", "/api/cams?name=..%5Cx", "/thumb?name=x", "/api/route"):
            self.assertEqual(req(self.port, "GET", p)[0], 404, p)
        self.assertEqual(empreinte(maplock.EDITS, maplock.LOCKS), self.avant)


class Traces(Commun, unittest.TestCase):
    port = PORTS["b2track.py"]
    ECRIT = ("/save?map=dubai4", {"points": [], "branches": []})

    @classmethod
    def setUpClass(cls):
        cls.avant = empreinte(MARINA)
        cls.p = demarrer("b2track.py")

    @classmethod
    def tearDownClass(cls):
        arreter(cls.p)
        assert empreinte(MARINA) == cls.avant, "marina_trace.json modifié par le test !"

    def test_normal(self):
        st, maps = req(self.port, "GET", "/maps")
        self.assertEqual(st, 200)
        self.assertIn("dubai4", [m["key"] for m in maps])
        self.assertEqual(req(self.port, "GET", "/build")[0], 200)

    def test_maps_hors_liste(self):
        for p in ("/data?map=..%2F..%2Fx", "/drive?map=C:%5Cx", "/png?map=x", "/data"):
            self.assertIn(req(self.port, "GET", p)[0], (400, 404), p)
        self.assertEqual(req(self.port, "POST", "/save?map=../x", {"points": []})[0], 404)

    def test_traces_invalides(self):
        bon = {"x": 0, "z": 0, "w": 30, "h": 0}
        for t in ({"points": []}, {"points": [bon] * 3}, {"points": [bon] * 3, "branches": [{"points": []}]},
                  {"points": [bon] * 3, "branches": [], "areas": [{"id": "z", "pts": []}]},
                  {"points": [{"x": "a"}] * 3, "branches": []}, [1, 2], "texte"):
            self.assertEqual(req(self.port, "POST", "/save?map=dubai4", t)[0], 400, t)
        self.assertEqual(req(self.port, "POST", "/save?map=dubai4", raw=b"{}",
                             headers={"Content-Length": str(10 ** 9)})[0], 413)
        self.assertEqual(empreinte(MARINA), self.avant)

    def test_installer_sans_construire(self):
        self.assertEqual(req(self.port, "POST", "/install?map=dubai4")[0], 400)
        self.assertEqual(req(self.port, "POST", "/build?map=odessa")[0], 400)       # tracé seul : pas de construction


if __name__ == "__main__":
    unittest.main()
