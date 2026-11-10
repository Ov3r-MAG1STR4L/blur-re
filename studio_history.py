r"""Historique commun des studios (NFS Studio, Reverse Studio, Tracés Blur 2) : noyau de stockage et de versions.

Indépendant des serveurs et de leurs pages (intégration : étape 3). Un historique = un dossier racine :
  objets\<2 premiers>\<sha256>   contenu d'un fichier, stocké une seule fois ; jamais réécrit ; vérifié à chaque lecture
  versions\<id>.json             photo complète d'un ensemble de fichiers : {chemin relatif: sha256 | null (absent)},
                                 date, studio, opération, cible (dossier photographié), version précédente.
                                 Immuable : écrite d'un coup, jamais remplacée.
  journal.jsonl                  opérations, une ligne ajoutée par événement (debut / fin), jamais réécrite. Chaque
                                 ligne porte l'empreinte de la précédente (« prec ») : ligne modifiée, supprimée au
                                 milieu ou déplacée détectée. La chaîne seule ne voit PAS une fin coupée ni un ancien
                                 journal entier : rôle des ancres.
  ancre.json + %LOCALAPPDATA%\blurre\ancres\<clé>.json
                                 deux copies de {n lignes validées, empreinte de la ligne n} ; écrites après chaque
                                 ligne (externe puis locale, remplacement atomique). Absentes, illisibles, divergentes,
                                 ou journal plus court / différent : JournalAbime, tout est bloqué. Jamais
                                 reconstruites automatiquement : reancrer() est manuel, confirmé et tracé.
  verrou                         créé de façon exclusive par l'opération en cours {studio, operation, pid, date} ;
                                 un verrou dont le processus n'existe plus est SIGNALÉ (orphelin), jamais supprimé ici.
Statut d'une opération (et des versions qu'elle produit) : « en_cours » tant que le journal n'a pas sa ligne « fin »,
puis « terminée » ; une opération sans fin alors qu'aucun verrou vivant ne la couvre = interrompue.
Tests : tests\test_studio_history.py (dossiers temporaires uniquement).
"""
import ctypes
import datetime
import hashlib
import json
import os
import secrets
import shutil

import studio_safe as SAFE


class ErreurHistorique(SAFE.Refus):
    """toutes les erreurs du noyau : message explicite, code HTTP pour les studios"""
    def __init__(self, message, code=409):
        super().__init__(message, code)


class ObjetManquant(ErreurHistorique):
    pass


class ObjetCorrompu(ErreurHistorique):
    pass


class JournalAbime(ErreurHistorique):
    pass


class VerrouOccupe(ErreurHistorique):
    def __init__(self, info, orphelin):
        self.info, self.orphelin = info, orphelin
        quoi = "%s / %s (pid %s, depuis %s)" % (info.get("studio"), info.get("operation"), info.get("pid"),
                                               info.get("date"))
        super().__init__(("verrou orphelin : %s ; son processus n'existe plus. Vérifier l'état puis supprimer le "
                          "fichier verrou à la main" if orphelin else "opération déjà en cours : %s") % quoi)


def maintenant():
    return datetime.datetime.now().isoformat(timespec="seconds")


def empreinte_fichier(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as fh:
        for bloc in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def chemin_relatif(rel):
    """chemin relatif normalisé (séparateur « / ») ou ErreurHistorique : pas d'absolu, de lecteur, de « .. », de vide"""
    if not isinstance(rel, str) or not rel.strip():
        raise ErreurHistorique("chemin vide ou invalide : %r" % (rel,), 400)
    r = rel.replace("\\", "/")
    parts = r.split("/")
    if r.startswith("/") or ":" in r or any(p in ("", ".", "..") for p in parts):
        raise ErreurHistorique("chemin refusé (absolu, lecteur, « . » ou « .. ») : %r" % (rel,), 400)
    return "/".join(parts)


def pid_vivant(pid):
    """Windows : OpenProcess + GetExitCodeProcess (STILL_ACTIVE = 259) ; ailleurs : os.kill(pid, 0)"""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)               # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _creer_sans_ecraser(tmp, final):
    """tmp devient final, refus si final existe (os.link échoue si la cible existe ; tmp retiré ensuite)"""
    try:
        os.link(tmp, final)
    finally:
        os.remove(tmp)


def dossier_ancres_defaut():
    """%LOCALAPPDATA%\\blurre\\ancres (hors de Jeux_WII) ; None si la variable manque"""
    base = os.environ.get("LOCALAPPDATA")
    return os.path.join(base, "blurre", "ancres") if base else None


class Historique:
    def __init__(self, racine, ancres=None):
        """ancres : dossier de la 2e copie de l'ancre (défaut %LOCALAPPDATA%\\blurre\\ancres ; tests : temporaire).
        Rien n'est écrit hors de racine avant la 1re ligne du journal."""
        self.racine = os.path.abspath(racine)
        self.objets = os.path.join(self.racine, "objets")
        self.versions = os.path.join(self.racine, "versions")
        self.journal = os.path.join(self.racine, "journal.jsonl")
        self.fichier_verrou = os.path.join(self.racine, "verrou")
        self.ancre_locale = os.path.join(self.racine, "ancre.json")
        dossier = ancres if ancres is not None else dossier_ancres_defaut()
        cle = hashlib.sha256(os.path.normcase(os.path.realpath(self.racine)).encode("utf-8")).hexdigest()[:24]
        self.ancre_externe = os.path.join(dossier, cle + ".json") if dossier else None
        for d in (self.objets, self.versions):
            os.makedirs(d, exist_ok=True)

    # ---- objets
    def _objet(self, sha):
        if not (isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)):
            raise ErreurHistorique("empreinte invalide : %r" % (sha,), 400)
        return os.path.join(self.objets, sha[:2], sha)

    def stocker(self, chemin):
        """copie le fichier dans les objets -> sha256. Déjà présent : vérifié, jamais réécrit (corrompu = refus)."""
        sha = empreinte_fichier(chemin)
        final = self._objet(sha)
        if os.path.exists(final):
            self.verifier_objet(sha)
            return sha
        os.makedirs(os.path.dirname(final), exist_ok=True)
        tmp = "%s.%s.tmp" % (final, secrets.token_hex(4))
        try:
            with open(chemin, "rb") as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
                dst.flush()
                os.fsync(dst.fileno())
            if empreinte_fichier(tmp) != sha:
                raise ObjetCorrompu("%s a changé pendant sa copie dans l'historique" % chemin)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        try:
            _creer_sans_ecraser(tmp, final)
        except FileExistsError:                 # écrit entre-temps par une autre opération : on vérifie le sien
            self.verifier_objet(sha)
        return sha

    def verifier_objet(self, sha):
        p = self._objet(sha)
        if not os.path.isfile(p):
            raise ObjetManquant("objet absent de l'historique : %s" % sha)
        if empreinte_fichier(p) != sha:
            raise ObjetCorrompu("objet corrompu (empreinte différente) : %s" % sha)
        return p

    def lire_objet(self, sha):
        """contenu vérifié (lu une fois, haché, puis rendu : pas de fenêtre entre vérification et lecture)"""
        p = self._objet(sha)
        if not os.path.isfile(p):
            raise ObjetManquant("objet absent de l'historique : %s" % sha)
        data = open(p, "rb").read()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ObjetCorrompu("objet corrompu (empreinte différente) : %s" % sha)
        return data

    # ---- versions
    def photographier(self, base, chemins, studio, operation, cible=None, precedente=None):
        """photo des fichiers `chemins` (relatifs à base) : contenus stockés, absents notés null -> version (dict).
        Refusée si l'intégrité de l'historique n'est pas garantie ; 1re donnée d'un historique vierge : les deux
        ancres (n = 0) sont écrites d'abord, pour qu'un historique « vierge » ne contienne vraiment rien."""
        self.etat_integrite()
        if not os.path.exists(self.ancre_locale):
            self._ecrire_ancres(0, "debut")
        fichiers = {}
        for rel in chemins:
            r = chemin_relatif(rel)
            try:                                       # aussi un lien qui mène hors de base (chemin réel)
                p = SAFE.dans_dossier(base, os.path.join(base, *r.split("/")))
            except SAFE.Refus as ex:
                raise ErreurHistorique(str(ex), 403)
            fichiers[r] = self.stocker(p) if os.path.isfile(p) else None
        if precedente is not None:
            self.lire_version(precedente)
        v = dict(id="%s-%s" % (datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), secrets.token_hex(3)),
                 date=maintenant(), studio=studio, operation=operation, cible=cible or os.path.abspath(base),
                 precedente=precedente, fichiers=dict(sorted(fichiers.items())))
        final = os.path.join(self.versions, v["id"] + ".json")
        tmp = final + ".%s.tmp" % secrets.token_hex(4)
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(v, fh, indent=1, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        try:
            _creer_sans_ecraser(tmp, final)
        except FileExistsError:
            raise ErreurHistorique("la version %s existe déjà : jamais écrasée" % v["id"])
        return v

    def lire_version(self, vid):
        if not (isinstance(vid, str) and vid and all(c.isalnum() or c == "-" for c in vid)):
            raise ErreurHistorique("identifiant de version invalide : %r" % (vid,), 400)
        p = os.path.join(self.versions, vid + ".json")
        if not os.path.isfile(p):
            raise ErreurHistorique("version inconnue : %s" % vid, 404)
        try:
            return json.load(open(p, encoding="utf-8"))
        except ValueError:
            raise ErreurHistorique("version illisible (fichier abîmé) : %s" % vid, 500)

    def liste_versions(self):
        """versions, plus récentes d'abord, avec le statut de l'opération qui les a produites"""
        etat = self.statuts()
        out = []
        for f in sorted(os.listdir(self.versions), reverse=True):
            if f.endswith(".json"):
                v = self.lire_version(f[:-5])
                v["statut"] = etat.get(v["id"], "terminée")    # photo hors opération : complète dès son écriture
                out.append(v)
        return out

    def verifier_version(self, vid):
        """tous les objets de la version présents et intacts -> version ; sinon ObjetManquant / ObjetCorrompu"""
        v = self.lire_version(vid)
        for sha in v["fichiers"].values():
            if sha is not None:
                self.verifier_objet(sha)
        return v

    def differences(self, avant, apres):
        """{ajoutés, modifiés, retirés} entre deux versions (id ou dict) ; un fichier noté absent compte comme absent"""
        a = {k: s for k, s in (avant if isinstance(avant, dict) else self.lire_version(avant))["fichiers"].items() if s}
        b = {k: s for k, s in (apres if isinstance(apres, dict) else self.lire_version(apres))["fichiers"].items() if s}
        return dict(ajoutés=sorted(set(b) - set(a)), retirés=sorted(set(a) - set(b)),
                    modifiés=sorted(k for k in set(a) & set(b) if a[k] != b[k]))

    # ---- journal
    def _lignes(self):
        if not os.path.exists(self.journal):
            return []
        brut = open(self.journal, "rb").read()
        if brut and not brut.endswith(b"\n"):
            raise JournalAbime("journal abîmé : dernière ligne incomplète (écriture interrompue) dans %s ; aucune "
                               "opération n'est possible avant examen" % self.journal)
        return brut.decode("utf-8").splitlines()

    def _chaine(self):
        """(entrées, empreintes des lignes) : chaque ligne JSON valide, « prec » = empreinte de la précédente, n = rang.
        Ne prouve PAS que la fin du journal est là (voir ancres)."""
        prec, out, emp = "debut", [], []
        for i, ligne in enumerate(self._lignes()):
            try:
                e = json.loads(ligne)
            except ValueError:
                raise JournalAbime("journal abîmé : ligne %d illisible" % (i + 1))
            if e.get("prec") != prec or e.get("n") != i:
                raise JournalAbime("journal abîmé : ligne %d modifiée, supprimée ou déplacée (chaîne rompue)" % (i + 1))
            prec = hashlib.sha256(ligne.encode("utf-8")).hexdigest()
            out.append(e)
            emp.append(prec)
        return out, emp

    # ---- ancres : {n, empreinte de la ligne n} validés, en deux copies (racine\ancre.json et %LOCALAPPDATA%)
    def _lire_ancre(self, chemin, nom):
        if chemin is None:
            raise JournalAbime("emplacement de l'ancre %s inconnu (variable LOCALAPPDATA absente) : opérations "
                               "bloquées" % nom)
        try:
            a = json.load(open(chemin, encoding="utf-8"))
        except FileNotFoundError:
            if not os.path.isdir(os.path.dirname(chemin)) and os.path.exists(os.path.dirname(chemin)):
                raise JournalAbime("emplacement de l'ancre %s inaccessible : %s" % (nom, os.path.dirname(chemin)))
            return None
        except (OSError, ValueError) as ex:
            raise JournalAbime("ancre %s illisible (%s) : %s ; jamais reconstruite automatiquement, voir "
                               "docs/SECURITE_STUDIOS.md (réancrage)" % (nom, type(ex).__name__, chemin))
        if not (isinstance(a, dict) and isinstance(a.get("n"), int) and a["n"] >= 0
                and isinstance(a.get("empreinte"), str)):
            raise JournalAbime("ancre %s illisible (contenu inattendu) : %s" % (nom, chemin))
        return a

    def _ecrire_ancre(self, chemin, ancre):
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        tmp = "%s.%s.tmp" % (chemin, secrets.token_hex(4))
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(ancre, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, chemin)                # remplacement atomique : l'ancienne ou la nouvelle, jamais un mélange
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def _ecrire_ancres(self, n, empreinte, **extra):
        """externe puis locale : une coupure entre les deux laisse des ancres divergentes = blocage (voulu)"""
        a = dict(n=n, empreinte=empreinte, date=maintenant(), racine=self.racine, **extra)
        self._ecrire_ancre(self.ancre_externe, a)
        self._ecrire_ancre(self.ancre_locale, a)

    def etat_integrite(self):
        """contrôle complet -> (entrées, empreintes, n validé). JournalAbime si l'intégrité n'est pas garantie :
        chaîne rompue, ligne incomplète, ancre absente / illisible / inaccessible, ancres divergentes, lignes validées
        disparues, journal différent de celui ancré (ancien état), plus d'une ligne non ancrée."""
        entrees, emp = self._chaine()
        loc = self._lire_ancre(self.ancre_locale, "locale")
        ext = self._lire_ancre(self.ancre_externe, "externe")
        if loc is None and ext is None:
            vierge = not entrees and not os.path.exists(self.journal) and not any(
                f.endswith(".json") for f in os.listdir(self.versions))
            if vierge:
                return entrees, emp, 0
            raise JournalAbime("ancres absentes alors que l'historique contient des données : jamais reconstruites "
                               "automatiquement ; réancrage manuel nécessaire après examen")
        if loc is None or ext is None:
            raise JournalAbime("ancre %s absente (l'autre existe) : opérations bloquées ; réancrage manuel après "
                               "examen" % ("locale" if loc is None else "externe (%s)" % self.ancre_externe))
        if (loc["n"], loc["empreinte"]) != (ext["n"], ext["empreinte"]):
            raise JournalAbime("ancres divergentes (locale : %d lignes, externe : %d) : écriture interrompue entre "
                               "les deux, ou dossier remplacé ; opérations bloquées, réancrage manuel après examen"
                               % (loc["n"], ext["n"]))
        n = loc["n"]
        if len(entrees) < n:
            raise JournalAbime("lignes validées disparues : le journal en a %d, l'ancre en garantit %d (troncature, "
                               "suppression ou ancien journal)" % (len(entrees), n))
        if n and emp[n - 1] != loc["empreinte"]:
            raise JournalAbime("le journal ne correspond pas à l'ancre (ligne %d différente) : journal remplacé par un "
                               "autre état" % n)
        if len(entrees) > n + 1:
            raise JournalAbime("%d lignes non ancrées (une seule est possible après une coupure) : opérations "
                               "bloquées" % (len(entrees) - n))
        return entrees, emp, n

    def verifier_journal(self):
        """entrées du journal, seulement si son intégrité est garantie (chaîne + ancres), sinon JournalAbime"""
        return self.etat_integrite()[0]

    def _ajouter(self, entree):
        """ordre : (1) contrôle, (2) ancres avancées sur une ligne laissée non ancrée par une coupure, (3) ligne ajoutée
        + fsync, (4) ancre externe, (5) ancre locale. Coupure après 3 ou pendant 4 : une ligne d'avance, acceptée et
        ancrée à l'ajout suivant ; entre 4 et 5 : ancres divergentes, blocage."""
        entrees, emp, n = self.etat_integrite()
        if len(entrees) == n + 1:
            self._ecrire_ancres(len(entrees), emp[-1])
        prec = emp[-1] if emp else "debut"
        ligne = json.dumps(dict(entree, n=len(entrees), prec=prec), ensure_ascii=False, sort_keys=True)
        with open(self.journal, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(ligne + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._ecrire_ancres(len(entrees) + 1, hashlib.sha256(ligne.encode("utf-8")).hexdigest())

    def reancrer(self, verrou, motif, confirmation):
        """MANUEL : accepte le journal tel qu'il est (chaîne intacte exigée) comme nouvelle référence, après examen.
        confirmation = empreinte de sa dernière ligne (donnée par apercu_reancrage), motif obligatoire. Ajoute une
        ligne « reancrage » (anciennes ancres, motif) puis écrit les deux ancres. Rien d'autre n'est modifié."""
        self._exiger(verrou)
        if not (isinstance(motif, str) and motif.strip()):
            raise ErreurHistorique("réancrage : motif obligatoire", 400)
        apercu = self.apercu_reancrage()
        if confirmation != apercu["empreinte"]:
            raise ErreurHistorique("réancrage refusé : confirmation différente de l'empreinte de la dernière ligne "
                                   "(%s)" % apercu["empreinte"], 400)
        ligne = json.dumps(dict(type="reancrage", op="reancrage-" + secrets.token_hex(3), date=maintenant(),
                                studio=verrou.studio, motif=motif, ancienne_locale=apercu["locale"],
                                ancienne_externe=apercu["externe"], n=apercu["lignes"], prec=apercu["empreinte"]),
                           ensure_ascii=False, sort_keys=True)
        with open(self.journal, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(ligne + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._ecrire_ancres(apercu["lignes"] + 1, hashlib.sha256(ligne.encode("utf-8")).hexdigest(),
                            reancrage=motif)

    def apercu_reancrage(self):
        """ce que le réancrage accepterait : lignes, empreinte de la dernière, contenu des deux ancres actuelles
        (illisible / absente indiqué). Chaîne rompue ou ligne incomplète = refus : on n'ancre pas un journal abîmé."""
        _, emp = self._chaine()
        out = dict(lignes=len(emp), empreinte=emp[-1] if emp else "debut")
        for nom, chemin in (("locale", self.ancre_locale), ("externe", self.ancre_externe)):
            try:
                out[nom] = self._lire_ancre(chemin, nom)
            except JournalAbime as ex:
                out[nom] = {"erreur": str(ex)}
        return out

    def commencer(self, verrou, operation, cible, avant=None, details=None):
        """ligne « debut » d'une opération (verrou détenu exigé) -> id d'opération"""
        self._exiger(verrou)
        if avant is not None:
            self.lire_version(avant)
        op = "%s-%s" % (datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), secrets.token_hex(3))
        self._ajouter(dict(type="debut", op=op, date=maintenant(), studio=verrou.studio, operation=operation,
                           cible=cible, avant=avant, details=details or {}, pid=os.getpid(),
                           jeton=verrou.info["jeton"]))
        return op

    def terminer(self, verrou, op, apres=None, resultat="ok", details=None):
        self._exiger(verrou)
        entrees = self.verifier_journal()
        debut = [e for e in entrees if e["op"] == op and e["type"] == "debut"]
        if not debut:
            raise ErreurHistorique("opération inconnue : %s" % op, 404)
        if any(e["op"] == op and e["type"] == "fin" for e in entrees):
            raise ErreurHistorique("opération déjà terminée : %s (une entrée n'est jamais réécrite)" % op)
        if apres is not None:
            self.lire_version(apres)
        self._ajouter(dict(type="fin", op=op, date=maintenant(), studio=verrou.studio, apres=apres,
                           resultat=resultat, details=details or {}))

    def operations(self):
        """opérations (début + fin éventuelle), plus récentes d'abord"""
        ops = {}
        for e in self.verifier_journal():
            if e["type"] == "debut":
                ops[e["op"]] = dict(e, statut="en_cours", fin=None)
            elif e["op"] in ops:
                ops[e["op"]].update(statut="terminée", fin=e)
        return sorted(ops.values(), key=lambda o: o["n"], reverse=True)

    def statuts(self):
        """{id de version: statut de l'opération qui la cite (avant / après)}"""
        s = {}
        for o in self.operations():
            for vid in (o.get("avant"), (o["fin"] or {}).get("apres")):
                if vid:
                    s.setdefault(vid, o["statut"])
        return s

    def interrompues(self):
        """opérations sans fin que plus aucun processus vivant ne couvre : leur verrou (jeton) a disparu ou est orphelin"""
        info = self.lire_verrou()
        vivant = info.get("jeton") if info and pid_vivant(info.get("pid")) else None
        return [o for o in self.operations() if o["statut"] == "en_cours" and (vivant is None or o.get("jeton") != vivant)]

    # ---- verrou
    def lire_verrou(self):
        try:
            return json.load(open(self.fichier_verrou, encoding="utf-8"))
        except FileNotFoundError:
            return None
        except ValueError:
            return {"studio": "?", "operation": "?", "pid": None, "date": "?", "illisible": True}

    def verrouiller(self, studio, operation):
        """verrou exclusif (O_CREAT | O_EXCL) -> Verrou ; occupé = VerrouOccupe (orphelin si le pid est mort)"""
        info = dict(studio=studio, operation=operation, pid=os.getpid(), date=maintenant(), jeton=secrets.token_hex(8))
        try:
            fd = os.open(self.fichier_verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            autre = self.lire_verrou() or {}
            raise VerrouOccupe(autre, orphelin=not pid_vivant(autre.get("pid")))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(info, fh)
            fh.flush()
            os.fsync(fh.fileno())
        return Verrou(self, info)

    def _exiger(self, verrou):
        if not isinstance(verrou, Verrou) or verrou.historique is not self or not verrou.detenu():
            raise ErreurHistorique("opération refusée : le verrou de l'historique n'est pas détenu")


class Verrou:
    def __init__(self, historique, info):
        self.historique, self.info, self.studio = historique, info, info["studio"]

    def detenu(self):
        v = self.historique.lire_verrou()
        return bool(v) and v.get("jeton") == self.info["jeton"]

    def liberer(self):
        """retire le verrou seulement s'il est bien le nôtre (même jeton)"""
        if not self.detenu():
            raise ErreurHistorique("verrou non détenu : rien retiré")
        os.remove(self.historique.fichier_verrou)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.detenu():
            self.liberer()
