"""python -m unittest tests.test_studio_safe   (depuis blur_tools) : protections communes des studios, sans réseau"""
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import studio_safe as S  # noqa: E402

P = 8765
OK = {"Host": "127.0.0.1:%d" % P}


class Refus(unittest.TestCase):
    def test_page_du_studio(self):
        self.assertIsNone(S.refus(dict(OK, Origin="http://127.0.0.1:%d" % P, **{"Sec-Fetch-Site": "same-origin"}), P, True))
        self.assertIsNone(S.refus({"Host": "localhost:%d" % P, "Origin": "http://localhost:%d" % P}, P, True))

    def test_script_local_sans_navigateur(self):      # curl, python : ni Origin ni Sec-Fetch-Site
        self.assertIsNone(S.refus(OK, P, True))

    def test_lecture_ouverte_depuis_un_lien(self):    # ouvrir la page depuis ailleurs reste possible (lecture)
        self.assertIsNone(S.refus(dict(OK, **{"Sec-Fetch-Site": "cross-site"}), P, False))

    def test_autre_site(self):
        self.assertIn("origine", S.refus(dict(OK, Origin="https://evil.example"), P, True))
        self.assertIn("origine", S.refus(dict(OK, Origin="null"), P, True))                 # iframe sandbox, file://
        self.assertIn("origine", S.refus(dict(OK, Origin="http://127.0.0.1:8766"), P, True))  # autre studio
        self.assertIn("autre site", S.refus(dict(OK, **{"Sec-Fetch-Site": "cross-site"}), P, True))  # <img>, <form>
        self.assertIn("autre site", S.refus(dict(OK, **{"Sec-Fetch-Site": "same-site"}), P, True))

    def test_dns_rebinding(self):
        self.assertIn("hôte", S.refus({"Host": "evil.example:%d" % P}, P, False))
        self.assertIn("hôte", S.refus({}, P, False))
        self.assertIn("hôte", S.refus({"Host": "127.0.0.1:1"}, P, False))


class Corps(unittest.TestCase):
    def h(self, body, n=None):
        return mock.Mock(headers={"Content-Length": str(len(body) if n is None else n)}, rfile=io.BytesIO(body))

    def test_json(self):
        self.assertEqual(S.lire_json(self.h(b'{"a": 1}')), {"a": 1})

    def test_invalide_trop_gros(self):
        with self.assertRaises(S.Refus):
            S.lire_json(self.h(b"{pas du json"))
        with self.assertRaises(S.Refus) as c:
            S.lire_json(self.h(b"", n=S.MAX_CORPS + 1))
        self.assertEqual(c.exception.code, 413)
        with self.assertRaises(S.Refus):
            S.lire_json(mock.Mock(headers={"Content-Length": "abc"}, rfile=io.BytesIO()))


class Fichiers(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_ecriture_et_bak(self):
        f = os.path.join(self.d, "t.json")
        S.ecrire_json(f, {"v": 1})
        self.assertFalse(os.path.exists(f + ".bak"))
        S.ecrire_json(f, {"v": 2})
        self.assertEqual(json.load(open(f)), {"v": 2})
        self.assertEqual(json.load(open(f + ".bak")), {"v": 1})

    def test_echec_ne_tronque_pas(self):
        f = os.path.join(self.d, "t.json")
        S.ecrire_json(f, {"v": 1})
        with self.assertRaises(TypeError):
            S.ecrire_json(f, {"v": object()})          # non sérialisable : plante au milieu de l'écriture
        self.assertEqual(json.load(open(f)), {"v": 1})
        self.assertEqual(os.listdir(self.d), ["t.json"])  # ni .tmp ni .bak laissés

    def test_dans_dossier(self):
        self.assertTrue(S.dans_dossier(self.d, os.path.join(self.d, "a", "b.json")).endswith("b.json"))
        for mauvais in (os.path.join(self.d, "..", "x.json"), os.path.join(self.d + "_frere", "x"), "C:\\Windows\\win.ini"):
            with self.assertRaises(S.Refus):
                S.dans_dossier(self.d, mauvais)

    def test_perimes_deplaces_pas_supprimes(self):
        src, arc = os.path.join(self.d, "files"), os.path.join(self.d, "perimes")
        os.makedirs(os.path.join(src, "m"))
        for n in ("vieux.model", "m/neuf.model"):
            open(os.path.join(src, n), "w").write("x")
        old = time.time() - 3600
        os.utime(os.path.join(src, "vieux.model"), (old, old))
        self.assertEqual(S.ecarter_perimes(src, time.time() - 60, arc), ["vieux.model"])
        self.assertEqual(S.fichiers(src), [os.path.join("m", "neuf.model")])
        self.assertEqual(len(os.listdir(arc)), 1)                          # perimes\<date>\vieux.model
        self.assertTrue(os.path.isfile(os.path.join(arc, os.listdir(arc)[0], "vieux.model")))


class Installation(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.src, self.dst, self.bak = (os.path.join(self.d, n) for n in ("files", "Blur_test", "backup"))
        os.makedirs(os.path.join(self.src, "levels"))
        os.makedirs(os.path.join(self.dst, "levels"))
        open(os.path.join(self.dst, S.MARQUEUR), "w").write("test")
        open(os.path.join(self.src, "levels", "a.bin"), "wb").write(b"neuf")
        open(os.path.join(self.src, "b.bin"), "wb").write(b"ajout")
        open(os.path.join(self.dst, "levels", "a.bin"), "wb").write(b"original")

    def tearDown(self):
        shutil.rmtree(self.d)

    def lire(self, *p):
        return open(os.path.join(*p), "rb").read()

    def test_normal_puis_reinstallation(self):
        self.assertEqual(S.installer(self.src, self.dst, self.bak), (2, 1))
        self.assertEqual(self.lire(self.dst, "levels", "a.bin"), b"neuf")
        self.assertEqual(self.lire(self.bak, "levels", "a.bin"), b"original")
        open(os.path.join(self.src, "levels", "a.bin"), "wb").write(b"neuf2")
        self.assertEqual(S.installer(self.src, self.dst, self.bak), (2, 0))
        self.assertEqual(self.lire(self.bak, "levels", "a.bin"), b"original")    # la sauvegarde reste l'originale

    def test_pas_la_copie_de_test(self):            # ex. le jeu installé, joué en ligne
        os.remove(os.path.join(self.dst, S.MARQUEUR))
        with self.assertRaises(S.Refus):
            S.installer(self.src, self.dst, self.bak)
        self.assertEqual(self.lire(self.dst, "levels", "a.bin"), b"original")

    def test_sortie_vide_ou_fichier_vide(self):
        with self.assertRaises(S.Refus):
            S.installer(os.path.join(self.d, "rien"), self.dst, self.bak)
        open(os.path.join(self.src, "vide.bin"), "wb").close()
        with self.assertRaises(S.Refus):
            S.installer(self.src, self.dst, self.bak)
        self.assertEqual(self.lire(self.dst, "levels", "a.bin"), b"original")

    def test_copie_fautive_annule_tout(self):
        with mock.patch.object(S.filecmp, "cmp", side_effect=[True, False]):
            with self.assertRaises(S.Refus):
                S.installer(self.src, self.dst, self.bak)
        self.assertEqual(self.lire(self.dst, "levels", "a.bin"), b"original")
        self.assertFalse(os.path.exists(os.path.join(self.dst, "b.bin")))
        self.assertEqual([f for f in S.fichiers(self.dst) if f.endswith(".studio_tmp")], [])
        self.assertFalse(os.path.exists(self.bak))


class InstallationTraces(unittest.TestCase):
    """b2track.install (étape 0, 2026-11-10) : plus aucune remise automatique depuis la sauvegarde. Dossiers
    temporaires seulement (config.BLUR_TEST et BACKUP remplacés le temps du test) ; jamais le vrai Blur_test."""
    R = os.path.join("models", "objects", "flat_earth", "road_21_%02d.model")

    def ecrire(self, base, rel, b):
        os.makedirs(os.path.dirname(os.path.join(base, rel)), exist_ok=True)
        open(os.path.join(base, rel), "wb").write(b)

    def lire(self, base, rel):
        return open(os.path.join(base, rel), "rb").read()

    def test_map_avec_moins_de_routes(self):
        import b2track
        d = tempfile.mkdtemp()
        try:
            test, bak, out = (os.path.join(d, n) for n in ("Blur_test", "backup", "out"))
            files = os.path.join(out, "files")
            self.ecrire(test, S.MARQUEUR, b"t")
            self.ecrire(test, self.R % 1, b"etat_avant_01")             # présents avant toute installation
            self.ecrire(test, self.R % 2, b"etat_avant_02")
            # sauvegarde HÉRITÉE mélangée : un fichier d'une autre génération (road_21_09) que l'ancien code remettait
            self.ecrire(bak, self.R % 9, b"vieille_generation_09")
            self.ecrire(bak, "levels/flat_earth/level.levelrender", b"rendu_epoque_rio")
            for k in (1, 2, 3):                                          # 1re map : 3 routes
                self.ecrire(files, self.R % k, b"map1_%02d" % k)
            with mock.patch.object(b2track.config, "BLUR_TEST", test), mock.patch.object(b2track, "BACKUP", bak):
                r1 = b2track.install({"out": out})
                herite = {f: self.lire(bak, f) for f in S.fichiers(bak) if f != "_absents.json"}
                shutil.rmtree(files)
                self.ecrire(files, self.R % 1, b"map2_01")                # 2e map : 1 route seulement
                r2 = b2track.install({"out": out})
            self.assertIn("3 fichiers installés", r1)
            self.assertIn("1 fichiers installés", r2)
            self.assertNotIn("originaux remis", r2)                       # ancien message de la remise automatique
            # nouvelle route installée
            self.assertEqual(self.lire(test, self.R % 1), b"map2_01")
            # aucun fichier réintroduit depuis la sauvegarde : 02 et 03 restent ceux de la 1re map (pas « etat_avant »)
            self.assertEqual(self.lire(test, self.R % 2), b"map1_02")
            self.assertEqual(self.lire(test, self.R % 3), b"map1_03")
            self.assertFalse(os.path.exists(os.path.join(test, self.R % 9)))        # vieille génération pas copiée
            self.assertFalse(os.path.exists(os.path.join(test, "levels", "flat_earth", "level.levelrender")))
            self.assertFalse(os.path.exists(os.path.join(test, "_absents.json")))
            # rien de supprimé : les restes sont signalés
            self.assertIn("2 fichiers d'une installation précédente laissés en place", r2)
            self.assertIn("road_21_02", r2)
            self.assertIn("road_21_03", r2)
            # sauvegarde intacte : les fichiers hérités inchangés ; la 1re install n'a ajouté que les originaux écrasés
            self.assertEqual(herite[self.R % 9], b"vieille_generation_09")
            self.assertEqual(herite["levels/flat_earth/level.levelrender".replace("/", os.sep)], b"rendu_epoque_rio")
            self.assertEqual(self.lire(bak, self.R % 1), b"etat_avant_01")
            self.assertEqual(self.lire(bak, self.R % 2), b"etat_avant_02")
            self.assertEqual({f: self.lire(bak, f) for f in S.fichiers(bak) if f != "_absents.json"}, herite)
            self.assertEqual(json.load(open(os.path.join(bak, "_absents.json"))), [self.R % 3])
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
