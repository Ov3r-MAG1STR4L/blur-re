"""python -m unittest tests.test_studio_history   (depuis blur_tools) : noyau de l'historique, dossiers temporaires"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import studio_history as H  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="hist_test_")
        self.h = H.Historique(os.path.join(self.d, "historique"))
        self.src = os.path.join(self.d, "Blur_test")
        os.makedirs(self.src)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def ecrire(self, rel, b, base=None):
        p = os.path.join(base or self.src, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b)
        return p

    def objets(self):
        return sorted(f for _, _, fs in os.walk(self.h.objets) for f in fs)


class Stockage(Base):
    def test_dedoublonnage(self):
        a, b, c = self.ecrire("a", b"meme"), self.ecrire("b", b"meme"), self.ecrire("c", b"autre")
        self.assertEqual(self.h.stocker(a), self.h.stocker(b))
        self.h.stocker(c)
        self.assertEqual(len(self.objets()), 2)
        self.assertEqual(self.h.lire_objet(self.h.stocker(a)), b"meme")

    def test_objet_existant_jamais_ecrase(self):
        a = self.ecrire("a", b"contenu")
        sha = self.h.stocker(a)
        p = self.h._objet(sha)
        open(p, "wb").write(b"abime")                         # objet corrompu sur le disque
        with self.assertRaises(H.ObjetCorrompu):
            self.h.stocker(a)                                 # refus explicite, pas de réécriture silencieuse
        self.assertEqual(open(p, "rb").read(), b"abime")

    def test_corruption_et_objet_manquant(self):
        sha = self.h.stocker(self.ecrire("a", b"contenu"))
        open(self.h._objet(sha), "ab").write(b"!")
        with self.assertRaises(H.ObjetCorrompu):
            self.h.lire_objet(sha)
        os.remove(self.h._objet(sha))
        with self.assertRaises(H.ObjetManquant):
            self.h.lire_objet(sha)
        for mauvais in ("../../x", "a" * 64, "", None):
            with self.assertRaises(H.ErreurHistorique):
                self.h.lire_objet(mauvais)

    def test_ecriture_interrompue(self):
        a = self.ecrire("a", b"x" * 5000)
        with mock.patch.object(H.shutil, "copyfileobj", side_effect=OSError("disque plein")):
            with self.assertRaises(OSError):
                self.h.stocker(a)
        self.assertEqual(self.objets(), [])                   # ni objet ni .tmp laissé

    def test_fichier_modifie_pendant_la_copie(self):
        a = self.ecrire("a", b"avant")
        vrai = shutil.copyfileobj

        def copie_puis_change(src, dst, n):
            vrai(src, dst, n)
            dst.write(b"ajout")                               # le contenu copié ne correspond plus à l'empreinte
        with mock.patch.object(H.shutil, "copyfileobj", side_effect=copie_puis_change):
            with self.assertRaises(H.ObjetCorrompu):
                self.h.stocker(a)
        self.assertEqual(self.objets(), [])


class Versions(Base):
    def test_photo_lecture_differences(self):
        self.ecrire("levels/a.bin", b"a1")
        self.ecrire("levels/b.bin", b"b1")
        v1 = self.h.photographier(self.src, ["levels/a.bin", "levels/b.bin", "levels/c.bin"], "Tracés Blur 2",
                                  "installation", cible="Blur_test")
        self.assertIsNone(v1["fichiers"]["levels/c.bin"])     # absent noté
        self.ecrire("levels/a.bin", b"a2")                     # modifié
        os.remove(os.path.join(self.src, "levels", "b.bin"))   # retiré
        self.ecrire("levels/c.bin", b"c1")                     # ajouté
        v2 = self.h.photographier(self.src, ["levels/a.bin", "levels/b.bin", "levels/c.bin"], "NFS Studio",
                                  "installation", cible="Blur_test", precedente=v1["id"])
        self.assertEqual(self.h.differences(v1["id"], v2["id"]),
                         {"ajoutés": ["levels/c.bin"], "modifiés": ["levels/a.bin"], "retirés": ["levels/b.bin"]})
        lu = self.h.lire_version(v2["id"])
        self.assertEqual((lu["studio"], lu["operation"], lu["precedente"]), ("NFS Studio", "installation", v1["id"]))
        self.assertEqual(self.h.lire_objet(lu["fichiers"]["levels/a.bin"]), b"a2")
        self.assertEqual([v["id"] for v in self.h.liste_versions()], sorted([v1["id"], v2["id"]], reverse=True))
        self.assertEqual(self.h.verifier_version(v2["id"])["id"], v2["id"])

    def test_version_jamais_ecrasee(self):
        self.ecrire("a", b"1")
        v = self.h.photographier(self.src, ["a"], "s", "o")
        avant = open(os.path.join(self.h.versions, v["id"] + ".json"), "rb").read()
        with mock.patch.object(H.secrets, "token_hex", return_value=v["id"].split("-")[-1]), \
                mock.patch.object(H.datetime, "datetime", wraps=H.datetime.datetime) as dt:
            dt.now.return_value = H.datetime.datetime.strptime(v["id"][:15], "%Y%m%d-%H%M%S")
            self.ecrire("a", b"2")
            with self.assertRaises(H.ErreurHistorique):
                self.h.photographier(self.src, ["a"], "s", "o")   # même identifiant : refus
        self.assertEqual(open(os.path.join(self.h.versions, v["id"] + ".json"), "rb").read(), avant)
        self.assertEqual([f for f in os.listdir(self.h.versions) if f.endswith(".tmp")], [])

    def test_version_avec_objet_corrompu_ou_manquant(self):
        self.ecrire("a", b"1")
        v = self.h.photographier(self.src, ["a"], "s", "o")
        sha = v["fichiers"]["a"]
        open(self.h._objet(sha), "wb").write(b"2")
        with self.assertRaises(H.ObjetCorrompu):
            self.h.verifier_version(v["id"])
        os.remove(self.h._objet(sha))
        with self.assertRaises(H.ObjetManquant):
            self.h.verifier_version(v["id"])

    def test_version_precedente_inconnue_et_ids_invalides(self):
        self.ecrire("a", b"1")
        with self.assertRaises(H.ErreurHistorique):
            self.h.photographier(self.src, ["a"], "s", "o", precedente="inconnue")
        for vid in ("../x", "a/b", "", None):
            with self.assertRaises(H.ErreurHistorique):
                self.h.lire_version(vid)
        self.assertEqual(os.listdir(self.h.versions), [])

    def test_chemins_hors_dossier(self):
        dehors = self.ecrire("secret.txt", b"s", base=self.d)
        for rel in ("../secret.txt", "..\\secret.txt", "a/../../secret.txt", dehors, "C:\\Windows\\win.ini",
                    "/etc/passwd", "", "a//b", "./a", None, 3):
            with self.assertRaises(H.ErreurHistorique, msg=rel):
                self.h.photographier(self.src, [rel], "s", "o")
        self.assertEqual((self.objets(), os.listdir(self.h.versions)), ([], []))

    def test_lien_vers_l_exterieur(self):
        dehors = self.ecrire("secret.txt", b"s", base=self.d)
        try:
            os.symlink(dehors, os.path.join(self.src, "lien.txt"))
        except OSError:
            self.skipTest("liens symboliques non autorisés sur cette machine")
        with self.assertRaises(H.ErreurHistorique):
            self.h.photographier(self.src, ["lien.txt"], "s", "o")


class Journal(Base):
    def test_operation_complete_et_statuts(self):
        self.ecrire("a", b"1")
        with self.h.verrouiller("Tracés Blur 2", "installation") as vr:
            v1 = self.h.photographier(self.src, ["a"], vr.studio, "avant installation")
            op = self.h.commencer(vr, "installation", "Blur_test", avant=v1["id"])
            self.assertEqual(self.h.operations()[0]["statut"], "en_cours")
            self.assertEqual(self.h.interrompues(), [])       # couverte par un verrou vivant
            v2 = self.h.photographier(self.src, ["a"], vr.studio, "après installation", precedente=v1["id"])
            self.h.terminer(vr, op, apres=v2["id"])
            with self.assertRaises(H.ErreurHistorique):
                self.h.terminer(vr, op)                       # pas de seconde fin
            with self.assertRaises(H.ErreurHistorique):
                self.h.terminer(vr, "inconnue")
        o = self.h.operations()[0]
        self.assertEqual((o["statut"], o["studio"], o["fin"]["apres"]), ("terminée", "Tracés Blur 2", v2["id"]))
        self.assertEqual({v["id"]: v["statut"] for v in self.h.liste_versions()},
                         {v1["id"]: "terminée", v2["id"]: "terminée"})
        self.assertEqual(len(self.h.verifier_journal()), 2)

    def test_interruption_simulee(self):
        self.ecrire("a", b"1")
        vr = self.h.verrouiller("NFS Studio", "installation")
        v1 = self.h.photographier(self.src, ["a"], "NFS Studio", "avant")
        op = self.h.commencer(vr, "installation", "Blur_test", avant=v1["id"])
        vr.liberer()                                          # le processus « meurt » sans écrire la fin
        inter = self.h.interrompues()
        self.assertEqual([(o["op"], o["avant"]) for o in inter], [(op, v1["id"])])
        self.assertEqual(self.h.liste_versions()[0]["statut"], "en_cours")
        with self.h.verrouiller("Tracés Blur 2", "autre"):
            self.assertEqual(len(self.h.interrompues()), 1)   # un autre verrou ne la couvre pas

    def test_entree_jamais_modifiee(self):
        with self.h.verrouiller("s", "o") as vr:
            op = self.h.commencer(vr, "o", "c")
            self.h.terminer(vr, op)
        lignes = open(self.h.journal, encoding="utf-8").read().splitlines()
        e = json.loads(lignes[0])
        e["studio"] = "falsifié"
        lignes[0] = json.dumps(e, ensure_ascii=False, sort_keys=True)
        open(self.h.journal, "w", encoding="utf-8", newline="\n").write("\n".join(lignes) + "\n")
        with self.assertRaises(H.JournalAbime):
            self.h.verifier_journal()
        open(self.h.journal, "w", encoding="utf-8", newline="\n").write(lignes[1] + "\n")    # 1re ligne supprimée
        with self.assertRaises(H.JournalAbime):
            self.h.verifier_journal()

    def test_ligne_incomplete_refusee(self):
        with self.h.verrouiller("s", "o") as vr:
            self.h.commencer(vr, "o", "c")
            taille = os.path.getsize(self.h.journal)
            open(self.h.journal, "ab").write(b'{"type": "debut", "op": "coup')     # écriture coupée net
            with self.assertRaises(H.JournalAbime):
                self.h.commencer(vr, "o2", "c")
        brut = open(self.h.journal, "rb").read()
        self.assertTrue(brut.endswith(b'"op": "coup'))          # rien ajouté par-dessus, rien réparé en silence
        self.assertGreater(len(brut), taille)

    def test_sans_verrou_refuse(self):
        with self.assertRaises(H.ErreurHistorique):
            self.h.commencer(None, "o", "c")
        vr = self.h.verrouiller("s", "o")
        vr.liberer()
        with self.assertRaises(H.ErreurHistorique):
            self.h.commencer(vr, "o", "c")                    # verrou rendu : plus valable
        self.assertFalse(os.path.exists(self.h.journal))


class Verrouillage(Base):
    def test_concurrence_meme_processus(self):
        with self.h.verrouiller("NFS Studio", "installation"):
            with self.assertRaises(H.VerrouOccupe) as c:
                self.h.verrouiller("Tracés Blur 2", "installation")
            self.assertFalse(c.exception.orphelin)
            self.assertIn("NFS Studio / installation", str(c.exception))
        self.h.verrouiller("Tracés Blur 2", "installation").liberer()   # rendu : de nouveau libre

    def test_concurrence_autre_processus(self):
        code = ("import sys; sys.path.insert(0, %r); import studio_history as H; h = H.Historique(%r)\n"
                "try:\n    h.verrouiller('Reverse Studio', 'enregistrement')\n    print('OBTENU')\n"
                "except H.VerrouOccupe as e:\n    print('REFUS', e.orphelin)") % (HERE, self.h.racine)
        with self.h.verrouiller("NFS Studio", "installation"):
            r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.stdout.strip(), "REFUS False", r.stderr)

    def test_verrou_orphelin_signale_jamais_supprime(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()                                              # pid d'un processus terminé
        info = dict(studio="NFS Studio", operation="installation", pid=p.pid, date="2026-11-10T19:00:00", jeton="x")
        open(self.h.fichier_verrou, "w").write(json.dumps(info))
        with self.assertRaises(H.VerrouOccupe) as c:
            self.h.verrouiller("Tracés Blur 2", "installation")
        self.assertTrue(c.exception.orphelin)
        self.assertIn("orphelin", str(c.exception))
        self.assertEqual(json.load(open(self.h.fichier_verrou)), info)    # toujours là, intact

    def test_verrou_illisible_et_liberation_par_un_autre(self):
        open(self.h.fichier_verrou, "w").write("{abime")
        with self.assertRaises(H.VerrouOccupe) as c:
            self.h.verrouiller("s", "o")
        self.assertTrue(c.exception.orphelin)
        os.remove(self.h.fichier_verrou)
        vr = self.h.verrouiller("s", "o")
        faux = H.Verrou(self.h, dict(vr.info, jeton="autre"))
        with self.assertRaises(H.ErreurHistorique):
            faux.liberer()                                    # le verrou d'un autre n'est jamais retiré
        self.assertTrue(vr.detenu())
        vr.liberer()


if __name__ == "__main__":
    unittest.main()
