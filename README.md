# blur-re

Rétro-ingénierie de **Blur** (Bizarre Creations, PC, 2010) : formats de fichiers, données de jeu,
mémoire en course.

- [docs/CONNAISSANCES.md](docs/CONNAISSANCES.md) : tout ce qui a été découvert, avec le niveau de confiance
- [docs/CAHIER_DES_CHARGES.md](docs/CAHIER_DES_CHARGES.md) : les projets, leurs étapes et leurs critères de validation

Aucun fichier du jeu n'est inclus. Les outils lisent une installation existante et les données extraites
(`..\blur_extracted`).

## Outils

| Script | Rôle |
|---|---|
| `blurpak.py` | lister / extraire les `.pak` (« 2KAP ») |
| `blurxt.py` | lire les `.bin` / `.xt` (KSLF) : schéma, JSON, export complet avec références résolues |
| `kslfwrite.py` | écrire du KSLF : reconstruction identique, clonage d'enregistrement, ajout à une liste de références |
| `blurloc.py` | textes `.loc` → JSON |
| `blurmodel.py`, `blurtex.py` | textures des `.model` : extraction et réinjection |
| `carsummary.py` | tableau récapitulatif des voitures (CSV) |
| `cpdump.py` | arborescence des fichiers « CP » (`.level`, `.levelphysics`, `.levelrender`, `.model`) |
| `blurroute.py` | données de piste de l'IA (`.aid`) → JSON + image |
| `aidreverse.py` | inverser une route d'un point à un autre (`.aid`) : nœuds, 11 lignes, portes, table logique |
| `gridreverse.py`, `make_haruna_reverse.py` | grille de départ pour une route inversée ; construction complète du mod « Haruna montée » |
| `blur_live.py` | lecture **seule** de la mémoire en course (véhicules, positions, vitesses, profils IA) |
| `deeprec.py` | enregistrement mémoire profond (objets pointés) pour l'analyse hors ligne |
| `memscan.py`, `ptrwalk.py`, `aiwalk.py` | recherches en mémoire (lecture seule) |
| `*probe*.py`, `hash*.py`, autres | essais ponctuels gardés pour l'historique |

Python 3.13, avec `pymem`, `numpy`, `matplotlib`, `Pillow`, `capstone`.
