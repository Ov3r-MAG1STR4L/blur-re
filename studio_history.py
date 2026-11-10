r"""Historique commun des studios (NFS Studio, Reverse Studio, Tracés Blur 2) : noyau de stockage et de versions.

Indépendant des serveurs et de leurs pages (intégration : étape 3). Un historique = un dossier racine :
  objets\<2 premiers>\<sha256>   contenu d'un fichier, stocké une seule fois ; jamais réécrit ; vérifié à chaque lecture
  versions\<id>.json             photo complète d'un ensemble de fichiers : {chemin relatif: sha256 | null (absent)},
                                 date, studio, opération, cible (dossier photographié), version précédente.
                                 Immuable : écrite d'un coup, jamais remplacée.
  journal.jsonl                  opérations, une ligne ajoutée par événement (debut / fin), jamais réécrite. Chaque
                                 ligne porte l'empreinte de la précédente (« prec ») : modification, suppression ou
                                 troncature détectées par verifier_journal().
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


class Historique:
    def __init__(self, racine):
        self.racine = os.path.abspath(racine)
        self.objets = os.path.join(self.racine, "objets")
        self.versions = os.path.join(self.racine, "versions")
        self.journal = os.path.join(self.racine, "journal.jsonl")
        self.fichier_verrou = os.path.join(self.racine, "verrou")
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
        """photo des fichiers `chemins` (relatifs à base) : contenus stockés, absents notés null -> version (dict)"""
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

    def verifier_journal(self):
        """chaque ligne : JSON valide, « prec » = empreinte de la ligne précédente, n = rang -> entrées"""
        prec, out = "debut", []
        for i, ligne in enumerate(self._lignes()):
            try:
                e = json.loads(ligne)
            except ValueError:
                raise JournalAbime("journal abîmé : ligne %d illisible" % (i + 1))
            if e.get("prec") != prec or e.get("n") != i:
                raise JournalAbime("journal abîmé : ligne %d modifiée, supprimée ou déplacée (chaîne rompue)" % (i + 1))
            prec = hashlib.sha256(ligne.encode("utf-8")).hexdigest()
            out.append(e)
        return out

    def _ajouter(self, entree):
        entrees = self.verifier_journal()
        prec = hashlib.sha256(open(self.journal, "rb").read().splitlines()[-1]).hexdigest() if entrees else "debut"
        ligne = json.dumps(dict(entree, n=len(entrees), prec=prec), ensure_ascii=False, sort_keys=True)
        with open(self.journal, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(ligne + "\n")
            fh.flush()
            os.fsync(fh.fileno())

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
