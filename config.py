"""Chemins de la chaîne NFS Studio, en un seul endroit.
Valeurs par défaut = l'installation d'origine (Jeux_WII). Pour une autre machine, au choix :
  - config.local.json à côté de ce fichier (non versionné) : {"JEUX": "D:\\\\mes_jeux", "BLUR_TEST": "..."}
  - variables d'environnement BLURRE_<NOM> (ex. BLURRE_JEUX), prioritaires sur le json.
Changer JEUX suffit si l'arborescence est la même ; les autres clés se règlent une par une."""
import json
import os

_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.local.json")
_over = json.load(open(_local, encoding="utf-8")) if os.path.exists(_local) else {}


def _get(name, default):
    return os.environ.get("BLURRE_" + name, _over.get(name, default))


JEUX = _get("JEUX", r"C:\Users\sanqu\Jeux_WII")
BMB_GAME = _get("BMB_GAME", os.path.join(JEUX, "bmb_game"))                      # copie du jeu pour Map Builder
MAP_BUILDER_DIR = _get("MAP_BUILDER_DIR", os.path.join(BMB_GAME, "map_builder"))  # zip 1.0.0 + nfs_studio.patch
MAP_BUILDER_ZIP = _get("MAP_BUILDER_ZIP", os.path.join(os.path.expanduser("~"), "Downloads", "blur-map-builder-1.0.0.zip"))
BLUR_TEST = _get("BLUR_TEST", os.path.join(JEUX, "Blur_test"))                    # seule copie où l'on installe
NFS_EXTRACTED = _get("NFS_EXTRACTED", os.path.join(JEUX, "nfs_extracted"))        # extraction Hot Pursuit Wii
ENV_DIR = _get("ENV_DIR", os.path.join(NFS_EXTRACTED, "files", "Data", "Environments"))
STM_WORK = _get("STM_WORK", os.path.join(NFS_EXTRACTED, "stm_work"))             # world*.json, web_cache
BLUR_EXTRACTED = _get("BLUR_EXTRACTED", os.path.join(JEUX, "blur_extracted"))
NFS_OUT = _get("NFS_OUT", os.path.join(BLUR_EXTRACTED, "mods", "nfs_dubai", "files"))  # sortie de construction
