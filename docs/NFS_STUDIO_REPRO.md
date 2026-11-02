# NFS Studio : reproduire la construction (étape 0)

But : reconstruire une carte Hot Pursuit Wii (référence : Dubaï, `Location1\location11.stm`) à partir du dépôt et
de prérequis listés ici, sans rien deviner. Rien du jeu n'est dans le dépôt (règle du projet).

## 1. Dépendances

| Élément | Version testée | Rôle | Où |
|---|---|---|---|
| Python | 3.13.7 | toute la chaîne | python.org |
| numpy | 2.2.6 | géométrie, hauteurs | pip |
| scipy | 1.16.2 | `cKDTree` (set_heights) | pip |
| Pillow | 11.3.0 | textures, vignette | pip |
| git | 2.55 | `git apply` du correctif Map Builder | git-scm.com |
| three.js | 0.160.0 | vue 3D de `web/index.html` | **CDN unpkg** (connexion requise) |
| Blur Map Builder | 1.0.0 (MIT, MdPro64) | construit le niveau `flat_earth` | zip `blur-map-builder-1.0.0.zip`, sha256 `cc7425bd…d171` |
| `cpmodel` (BlurImportExport) | fourni dans Map Builder | lecture des `.model` (blurmodel_write) | dans le zip |

Hors chaîne NFS (sondes, mémoire) : pymem, matplotlib, capstone.

Données locales (jamais versionnées), chemins réglés dans `config.py` :

| Clé `config.py` | Contenu | Comment l'obtenir |
|---|---|---|
| `BMB_GAME` | copie du jeu pour Map Builder : `Blur.exe`, `cache\*.pak`, `levels\showroom`, `Blur Map Builder\base` (`unpacked`, `orig_xt`, `catalog.json`, `model_cache`, `level_template`), `map_builder\` | premier lancement de Map Builder sur une copie du jeu, puis fusion manuelle des xt de Blur_test (voir §5, problème 1) |
| `MAP_BUILDER_DIR` | Map Builder corrigé | `python vendor/map_builder/setup_map_builder.py install` |
| `ENV_DIR` | `.stm` HP Wii | extraction du disque HP Wii (`nfs_extracted\files\Data\Environments`) |
| `STM_WORK` | `world*.json`, `web_cache\<lieu>\index.json` | produits par NFS Studio (« Charger » un lieu) |
| `BLUR_EXTRACTED` | `nfs_models\sign_wetfloor.model` (gabarit) | extraction Blur |
| `BLUR_TEST` | copie de test du jeu ; seul endroit où l'on installe | `make_test_copy.ps1` |
| `NFS_OUT` | sortie de construction | créée par la construction |

## 2. Configuration

`config.py` porte les chemins de la chaîne NFS (make_nfs_map, nfs_web, nfs_studio, blurmodel_write, addramp).
Valeurs par défaut = cette machine, donc aucun changement de comportement. Ailleurs : `config.local.json`
(non versionné, `{"JEUX": "D:\\jeux"}`) ou variables `BLURRE_<CLÉ>`. Les arguments en ligne de commande
de `make_nfs_map.py [BMB_GAME] [SORTIE]` restent prioritaires.

## 3. Correctifs Map Builder (`vendor/map_builder/`)

`nfs_studio.patch` = seule différence entre le zip 1.0.0 et la copie utilisée (3 fichiers de `flat_earth/`).
Tout est conditionné à des variables d'environnement : sans elles, Map Builder se comporte comme l'original.

| Fichier | Variable | Effet |
|---|---|---|
| build.py | `NFS_COUNT` | ajoute `tower_nfs000…` (modèles `nfs_%03d.model`, uid `0xF1E40000 + 2k`) |
| build.py | `NFS_DRAW` | distance d'affichage de ces modèles |
| build.py | `NFS_NO_WALLS` | aucun mur / pièce / tablier de Map Builder dans la physique |
| build.py | `NFS_FLOOR_Y` | hauteur du sol physique |
| gen_actorpack.py | `NFS_GRID_GAP` | écart de la grille de départ (8 m par défaut) |
| road_layout.py | `NFS_SPOTS` | un acteur par modèle NFS au centre de sa zone ; limite 144 acteurs |

Vérifier une copie : `python vendor/map_builder/setup_map_builder.py check` (fins de ligne ignorées :
la copie actuelle est en CRLF, le zip en LF). Résultat au 2026-11-02 : OK.
Installer sur une machine neuve : `... install [ZIP] [DOSSIER]` (refuse d'écraser un dossier existant).

## 4. Reconstruire Dubaï

Blur fermé. Rien n'est écrit dans le jeu installé ni dans Blur_test pendant la construction.

1. `python vendor/map_builder/setup_map_builder.py check` → OK.
2. Interface : `Jeux_WII\NFS Studio.bat` → choisir `Location1/location11.stm` → « Construire ».
   Sans interface (même chemin de code) :
   ```
   python -c "import sys,nfs_web as W,os;W.load_location(os.path.join(W.ENV_DIR,'Location1','location11.stm'));W.M.OUT=sys.argv[1];W.A.rebuild(auto_pickups=False)" SORTIE
   ```
   Attention : `load_location`/`set_heights` réécrit `STM_WORK\world.json` et la construction écrase
   `BMB_GAME\levels\flat_earth`, `Blur Map Builder\maps` et `work`. Sauvegarder avant si l'état compte.
3. Durée ≈ 30 min, ~139 fichiers. Installation éventuelle : bouton « Installer dans Blur_test » uniquement.

## 5. Problèmes restants (non corrigés : chacun changerait la sortie ou demande une décision)

1. **Base xt de Map Builder désynchronisée** : `BMB_GAME\Blur Map Builder\base\unpacked\gamedata\xt\amax.bin`
   et `multiplayer.bin` diffèrent de ceux de Blur_test. La « fusion par-dessus nos mods » est manuelle et
   périmée depuis les dernières installations Reverse. Installer une construction peut donc écraser des
   ajouts Reverse dans ces fichiers.
2. **Dépendance à l'état de Blur_test** : la vignette est ajoutée au `ui_frontend.bpr` *de Blur_test*,
   dont le contenu dépend des installations précédentes : la sortie n'est pas fonction du seul dépôt.
3. **Sortie non nettoyée** : `rebuild` écrit dans `NFS_OUT` sans le vider ; des fichiers d'une carte
   précédente peuvent rester.
4. **État global mutable** : `make_nfs_map` lit `sys.argv` à l'import ; `M.OUT`, `M.STM`, `M.WORLD` sont
   modifiés par `nfs_web`. Un script qui importe la chaîne doit vider `sys.argv` d'abord.
5. **`MAP_BUILDER_DIR` n'est lu que par blurmodel_write** : la construction utilise toujours
   `BMB_GAME\map_builder` (nfs_atlas, make_nfs_map). Les deux doivent rester cohérents.
6. **three.js via CDN** : NFS Studio web ne s'affiche pas hors ligne.
7. **Chemins en dur hors chaîne NFS** (non touchés) : `.bat` / `make_test_copy.ps1`, sondes
   (findtexhash, hashmember, hashprobe, hashscan, listcartex, modelprobe*, xtprobe*).
8. **Mémoire** : une construction a échoué une fois sur `MemoryError` dans `pak.add_aliases` (Map Builder
   reconstruit le pak par concaténations de `bytes`). Relancée telle quelle, voir §6.
9. **`BMB_GAME` lui-même n'est pas reproductible** : son contenu vient d'un premier lancement de Map Builder
   et d'étapes manuelles non scriptées.

## 6. Comparaison

Sorties conservées dans `blur_extracted\etape0_ref\` (logs `ref*.log`, empreintes `sha256_ref.txt`).

| Construction | Code | Durée | Fichiers | Résultat |
|---|---|---|---|---|
| ref1 (1er essai) | d'origine | 29 min | 0 | `MemoryError` dans Map Builder (`pak.add_aliases`), RAM libre 3,8 Go |
| ref2 | d'origine | 33 min | 139 | référence |
| ref1 (relancée) | d'origine | 31 min | 139 | **identique à ref2, octet par octet** |
| ref3 | avec `config.py` | 21 min | 139 | **identique à ref2, octet par octet** |

Les 139 fichiers sont identiques dans les trois sorties : aucun fichier ne diffère.

Pas de comparaison avec l'installation actuelle (`mods\nfs_dubai\files`) : elle ne vient pas du `world.json`
de Dubaï (construite depuis un autre lieu, probablement location21).

Après les tests, `bmb_game` (9 fichiers écrits par la construction) a été remis à l'état sauvegardé avant les
tests (`blur_extracted\etape0_sauvegarde`, 2026-11-02 21:05). Les dates montrent qu'aucun autre fichier n'y a changé.

Machine propre (après §1) :
```
python vendor/map_builder/setup_map_builder.py install ZIP DOSSIER\bmb_game\map_builder
python vendor/map_builder/setup_map_builder.py check
```
puis §4.
