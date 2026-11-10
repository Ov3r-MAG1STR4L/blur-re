r"""Protections communes aux studios web locaux (NFS Studio, Reverse Studio, Tracés Blur 2).

Les trois serveurs restent indépendants ; chacun appelle ces fonctions :
- refus(headers, port, ecriture) : requêtes d'autres sites (CSRF) et DNS rebinding ;
- lire_json(handler) : corps POST borné en taille, JSON valide ;
- ecrire_json(chemin, obj) : écriture atomique (fichier temporaire puis renommage), ancienne version en .bak ;
- dans_dossier(base, chemin) : un chemin reste dans son dossier (pas de « .. », pas de lien vers ailleurs) ;
- ecarter_perimes(dossier, t0, archive) : fichiers non réécrits par la dernière construction mis de côté (pas supprimés) ;
- installer(src, dst, sauvegarde) : copie dans Blur_test en deux temps (copie vérifiée à côté, puis renommage),
  originaux remplacés gardés une fois pour toutes, refus si dst n'est pas la copie de test.
Tests : tests\test_studio_safe.py (unitaires) et tests\test_studios_http.py (les 3 serveurs, requêtes malveillantes).
"""
import filecmp
import json
import os
import shutil
import tempfile
import time

MAX_CORPS = 64 * 1024 * 1024            # 64 Mo : un tracé ou un world.json pèse quelques centaines de Ko
MARQUEUR = "COPIE_DE_TEST_HORS_LIGNE.txt"   # présent seulement dans Blur_test (make_test_copy.ps1)


class Refus(Exception):
    """erreur montrée telle quelle dans la page, avec son code HTTP"""
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


def refus(headers, port, ecriture):
    """None si la requête est acceptée, sinon la raison.
    Toujours : Host = 127.0.0.1:port ou localhost:port (un site qui ferait pointer son propre nom vers 127.0.0.1 --
    DNS rebinding -- envoie son nom dans Host). Pour ce qui écrit ou lance quelque chose : Origin, si présent, = la page
    du studio ; Sec-Fetch-Site, si présent, = same-origin ou none. Un navigateur envoie toujours Origin sur un POST
    venu d'un autre site, et les navigateurs récents Sec-Fetch-Site sur toute requête (y compris <img>, <form>)."""
    hotes = {"127.0.0.1:%d" % port, "localhost:%d" % port}
    if (headers.get("Host") or "").lower() not in hotes:
        return "hôte refusé : %s" % headers.get("Host")
    if ecriture:
        origine = headers.get("Origin")
        if origine is not None and origine.lower() not in {"http://" + h for h in hotes}:
            return "origine refusée : %s" % origine
        site = headers.get("Sec-Fetch-Site")
        if site is not None and site not in ("same-origin", "none"):
            return "requête venue d'un autre site refusée (%s)" % site
    return None


def lire_json(handler):
    try:
        n = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        raise Refus("Content-Length invalide")
    if n > MAX_CORPS:
        raise Refus("corps trop gros (%d octets)" % n, 413)
    try:
        return json.loads(handler.rfile.read(n) or b"null")
    except ValueError as ex:
        raise Refus("JSON invalide : %s" % ex)


def ecrire_json(chemin, obj, bak=True, **dump):
    """chemin remplacé d'un coup par un fichier complet ; l'ancien gardé en chemin.bak (copie : chemin existe toujours)"""
    dossier = os.path.dirname(os.path.abspath(chemin))
    os.makedirs(dossier, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dossier, prefix=".studio_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(obj, fh, **(dump or {"indent": 1}))
            fh.flush()
            os.fsync(fh.fileno())
        if bak and os.path.exists(chemin):
            shutil.copy2(chemin, chemin + ".bak")
        os.replace(tmp, chemin)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def dans_dossier(base, chemin):
    """chemin absolu réel s'il est dans base (liens résolus), sinon Refus"""
    b, p = os.path.realpath(base), os.path.realpath(chemin)
    if os.path.commonpath([b, p]) != b:
        raise Refus("chemin hors de son dossier : %s" % chemin, 403)
    return p


def fichiers(dossier):
    return sorted(os.path.relpath(os.path.join(d, f), dossier) for d, _, fs in os.walk(dossier) for f in fs)


def ecarter_perimes(dossier, t0, archive):
    r"""fichiers de dossier non réécrits depuis t0 (restes d'une construction précédente) déplacés dans
    archive\<date>\ (rien n'est supprimé) -> liste des chemins relatifs déplacés"""
    vieux = [r for r in fichiers(dossier) if os.path.getmtime(os.path.join(dossier, r)) < t0 - 2]
    if vieux:
        dest = os.path.join(archive, time.strftime("%Y-%m-%d_%H-%M-%S"))
        for r in vieux:
            os.makedirs(os.path.dirname(os.path.join(dest, r)), exist_ok=True)
            shutil.move(os.path.join(dossier, r), os.path.join(dest, r))
    return vieux


def installer(src, dst, sauvegarde):
    """copie tous les fichiers de src dans dst. 1) vérifications : dst est la copie de test (MARQUEUR), src non vide,
    aucun fichier vide ; 2) chaque fichier copié à côté de sa destination (.studio_tmp) et comparé octet par octet ;
    un échec annule tout (dst inchangé) ; 3) originaux de dst gardés dans sauvegarde (une seule fois : la 1re version
    gardée reste l'originale), puis les copies renommées à leur place. -> (fichiers installés, originaux sauvegardés)"""
    if not os.path.isfile(os.path.join(dst, MARQUEUR)):
        raise Refus("%s n'est pas la copie de test (pas de %s) : installation refusée" % (dst, MARQUEUR), 409)
    liste = fichiers(src)
    if not liste:
        raise Refus("rien à installer dans %s : construire d'abord" % src, 409)
    vides = [r for r in liste if os.path.getsize(os.path.join(src, r)) == 0]
    if vides:
        raise Refus("fichiers vides dans la sortie, installation refusée : %s" % vides[:5], 409)
    prets = []
    try:
        for r in liste:
            s, d = os.path.join(src, r), dans_dossier(dst, os.path.join(dst, r))
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copyfile(s, d + ".studio_tmp")
            prets.append((r, d))
            if not filecmp.cmp(s, d + ".studio_tmp", shallow=False):
                raise Refus("copie différente de l'original : %s (rien n'a été installé)" % r, 500)
    except BaseException:
        for _, d in prets:
            if os.path.exists(d + ".studio_tmp"):
                os.remove(d + ".studio_tmp")
        raise
    # sauvegarde\_absents.json : fichiers qui n'existaient pas dans dst avant la 1re installation (ajoutés par nous :
    # jamais pris pour des originaux lors d'une installation suivante)
    fa = os.path.join(sauvegarde, "_absents.json")
    absents = set(json.load(open(fa))) if os.path.isfile(fa) else set()
    gardes, n_abs = 0, len(absents)
    for r, d in prets:
        b = os.path.join(sauvegarde, r)
        if not os.path.exists(b) and r not in absents:
            if os.path.exists(d):
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copy2(d, b)
                gardes += 1
            else:
                absents.add(r)
        os.replace(d + ".studio_tmp", d)
    if len(absents) != n_abs:
        ecrire_json(fa, sorted(absents))
    return len(prets), gardes
