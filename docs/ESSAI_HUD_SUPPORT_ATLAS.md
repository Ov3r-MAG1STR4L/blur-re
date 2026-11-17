# Essai HUD : planche support agrandie (cases 100-109)

2026-11-17. Ce rapport couvre la faisabilité, puis la préparation du prototype. **Pas encore joué** : rien n'est
validé en jeu. Les copies de référence `Blur_test_hud` et `Blur_test` (Railgun), le jeu installé et `Blur.exe` ne
sont pas touchés.

## 1. Textures actuelles (**Confirmé**, `ui_common.bpr` de `root.pak`)

`blur_extracted\root\ui\data\ui_common.bpr` : 63 images, SHA-1 `6b18c436…`. Fiche `.bpr` (28 o) =
`[pas, nom, début, 1, taille, 0, format, mips, largeur, hauteur]`.

| Image | Format | Mips | Taille (px) | Octets (mip 0 / 1 / 2) | Alpha |
|---|---|---|---|---|---|
| `perk_sheet_support` | DXT1 | 3 | 128 × 512 | 43 008 (32 768 / 8 192 / 2 048) | aucun (255 partout) : luminosité = transparence (`IntensityAsAlpha`) |
| `perk_sheet_support_inverted` | DXT5 | 3 | 128 × 512 | 86 016 (65 536 / 16 384 / 4 096) | réel |
| `perk_sheet` (modèle de forme) | DXT1 | 3 | 128 × 1024 | 86 016 | — |
| `perk_sheet_inverted` | DXT5 | 3 | 128 × 1024 | 172 032 | — |

- Une case = **128 × 96 px**, mesuré sur les bandes non vides (12-84, 108-180 … 396-468).
- 5 cases utilisées (100-104 = lignes 0-480).
- Les lignes 480-512 sont vides.
- La planche normale et la planche inversée ont la même disposition.

## 2. Calcul des UV et limites dans l'exe (**Confirmé**, `POWERUPS_HUD.md` §8)

- **Seuil** : `cmp …, 0x64` dans `UIPerks2::Render` (`0xC592B8`) et `UIPerks::Render` (`0xC57FD1`). Au-delà, on
  calcule `index − 100` et on prend les textures 6 / 7 (`UIPerks2`) ou 2 (`UIPerks`).
- **V** = `(index − 100) × size.v + pos.v`, avec `size.v` / `pos.v` lus dans le `UITextureParam` du gadget
  (`[param+0x10]` / `[param+8]`). U = `pos.u` ; largeur = `size.u`.
- **Aucune borne sur l'index** : rien ne compare l'index à un maximum.
- `GetTextureParam` (`0x74B270`) ne borne que le **numéro de texture du gadget** (0 ≤ n < `[gadget+0x64]`), pas la
  case ni les UV. Elle ne regarde pas les dimensions de l'image.
- La taille de l'image n'est jamais lue par ce code. Les gadgets sont en `texture_address = Wrap`.
- La limite de **16 entrées** (`PerkDisplayParameters`, 0x480 o) ne concerne que les bonus. Elle ne limite pas le
  nombre de cases d'une planche.
- **Les deux planches doivent changer ensemble.** La case choisie lit la texture 6, les autres la texture 7, chacune
  avec son propre `size.v`. Une seule planche agrandie, ou des `size.v` différents, décaleraient les cases non
  choisies.

Avec `size.v` = 96 / 1024 = **0,09375**, la case k (100 + k) occupe les pixels 96k à 96k + 96 :

- les cases 100-104 restent **aux mêmes pixels** qu'aujourd'hui ;
- les cases 105-109 arrivent aux lignes 480-960.

## 3. Format `.bpr` et outils

- `blurbpr.Bpr.rebuild` recalcule la table, les noms et les débuts de données, et termine bien la liste chaînée.
  **Prouvé en jeu sur ce même fichier** par `artatlas.py` (ajout d'une image, 2026-11-16).
- Il réaligne aussi les images sur 16 octets : certaines ne le sont pas dans le fichier d'origine (exemple : début
  147 029). La reconstruction n'est donc pas identique à l'octet, mais **chaque image et chaque champ de fiche est
  conservé**. C'est vérifié, et c'est le même comportement qu'`artatlas.py`.
- Ajout du 2026-11-17 : `rebuild(resize={nom: (w, h, données)})` remplace une image par une autre de taille
  différente, au même format et avec le même nombre de mips. Les appels existants ne changent pas.
- Pas de conversion PNG ou DDS : on écrit la **chaîne de mips brute** attendue par le jeu (DXT1 sans en-tête, DXT5
  sans en-tête), aux mêmes tailles que `perk_sheet` / `perk_sheet_inverted`.

## 4. Conditions pour ajouter les cases 105-109

1. Deux planches agrandies à 128 × 1024, **mêmes formats** (DXT1 / DXT5) et **3 mips**, comme `perk_sheet`.
2. Cases 100-104 inchangées.
3. Dans `ui.bin`, `size.v` 0,1875 → 0,09375 pour les 5 textures de planche support des 3 gadgets.
4. Un `texture_index` de 105-109 sur une entrée existante, pour voir la case.
5. Rien dans `Blur.exe`.

## 5. Risques

- **Budget mémoire des textures d'interface.** +129 134 o pour `ui_common.bpr` (2 408 946 → 2 538 080). Le fichier a
  déjà accepté +1 Mo (planche de pochettes) en jeu : risque faible.
- **Coutures entre niveaux de mip** à la ligne 480 (240, 120) : la partie basse est encodée par nos outils, la partie
  haute est d'origine. C'est sans effet sur les cases 100-104, à voir en jeu pour 105.
- **Teinte** : l'icône est multipliée par `colour_fill` de l'entrée (le Bouclier est gris bleuté). Les couleurs des
  icônes d'essai seront donc assombries.
- La version inversée (DXT5) est encodée par Pillow 11.3 : à surveiller (artefacts).

**Conclusion de faisabilité : faisable par les données seules**, sous réserve de l'essai en jeu. Le prototype a donc
été préparé.

## 6. Prototype (préparé, **pas joué**)

Script : **`hud_support_atlas.py`**. Il lit les originaux, écrit dans `blur_extracted\mods\hud_support_atlas\`, et
vérifie chaque modification.

**Planches.** Dessin des nouvelles cases :

| Case | Planche normale | Planche inversée |
|---|---|---|
| 105 | rond rouge + « 5 » | même forme, noire sur cadre clair |
| 106 | triangle vert + « 6 » | idem |
| 107 | carré bleu + « 7 » | idem |
| 108 | croix jaune + « 8 » | idem |
| 109 | losange magenta + « 9 » | idem |

Ce ne sont pas des icônes du jeu. Construction de chaque niveau de mip :

- **blocs compressés d'origine recopiés** pour les cases 100-104 (lignes 0-480, 0-240, 0-120 : des rangées de blocs
  4 × 4 entières) ;
- nouvel encodage seulement en dessous.

| Image | Avant | Après | SHA-1 des données |
|---|---|---|---|
| `perk_sheet_support` | 128 × 512, 43 008 o | 128 × 1024, 86 016 o | `3ca6a9e4a4b0…` |
| `perk_sheet_support_inverted` | 128 × 512, 86 016 o | 128 × 1024, 172 032 o | `bee028ac2f6f…` |
| `ui_common.bpr` | SHA-1 `6b18c436…`, 2 408 946 o | SHA-1 `144164cba7d5…`, 2 538 080 o | — |

Contrôles du script (tous passés) :

- les 61 autres images sont identiques à l'octet, avec les mêmes formats ;
- les blocs des cases 100-104 sont identiques à chaque mip ;
- les lignes 0-480 décodées sont identiques au pixel près ;
- les fiches portent bien `[format, 3, 128, 1024]`.

Aperçu : `hud_support_atlas\preview\decoded_from_bpr.png` (décodé depuis le nouveau `.bpr`).

**`ui.bin`** (original SHA-1 `3f235b34…` = celui du pak). Modifications sur place :

| Décalage | Avant → après | Champ |
|---|---|---|
| `0x0DA1F4` | `0000403e` → `0000c03d` | `Perks_MainHUD.textures[6].size.v` 0,1875 → 0,09375 |
| `0x0DA20C` | idem | `Perks_MainHUD.textures[7].size.v` |
| `0x0D9DA4` | idem | `Perks_MainAttached.textures[6].size.v` |
| `0x0D9DBC` | idem | `Perks_MainAttached.textures[7].size.v` |
| `0x0D9E4C` | idem | `ai_perks.textures[2].size.v` |
| `0x061D00` | `07000000` → `69000000` | `shield.texture_index` 7 → **105** |

- **Fichier installé** (`files\gamedata\xt\ui.bin`, SHA-1 `38d57bea…`) : 6 u32 changés. Le script vérifie qu'aucun
  autre ne change, et que les 5 `size.v` sont bien ceux des textures `perk_sheet_support*` des 3 gadgets.
- **Variante pour la 2e étape** (`variants\ui_106_109.bin`, SHA-1 `e3202f9a…`, **non installée**) : les mêmes 6
  changements, plus :

| Décalage | Champ |
|---|---|
| `0x061C28` | `nitrous` 4 → 106 |
| `0x061C70` | `barge` 1 → 107 |
| `0x061CE8` | `repair` 8 → 108 |
| `0x061C88` | `bomb` 0 → 109 |

Originaux sauvegardés : `hud_support_atlas\original\ui_common.bpr` et `ui.bin`.

## 7. Copie de test

`C:\Users\sanqu\Jeux_WII\Blur_test_hud_atlas` (`make_test_copy.ps1 -Dest … -Mod …\hud_support_atlas\files -Run`).
Créée le 2026-11-17 à 21:17 : 1 378 fichiers, 9,4 Go, aucun échec. Le « code 3 » est celui de robocopy : des
fichiers copiés, pas une erreur. Contrôles (**Confirmé**) :

| Contrôle | Résultat |
|---|---|
| `gamedata\xt\ui.bin` | SHA-1 `38d57bea…` = fichier préparé |
| `ui\data\ui_common.bpr` | SHA-1 `144164cb…` = fichier préparé |
| `cache` | `gamedata.pak`, `root.pak`, `root_streaming.pak` (+ `.sig`) en `.off` |
| Modules | `amax\dlls` = `lua_hooks.asi` seul ; pas de `amax\config` (hors ligne) ; aucun Railgun (ni DLL, ni plugin) |
| Copies de référence | `Blur_test_hud\…\ui.bin` toujours `106400da…`, `Blur_test\…\ui.bin` toujours `c17ba829…` : pas touchées |

## 8. Procédure en jeu

Course perso seul (F1) avec des IA. Options de bonus : **Shield et Nitro**. Captures dans
`hud_support_atlas\captures\`.

| # | Cas | Attendu |
|---|---|---|
| 1 | Bouclier ramassé, caméra extérieure | **rond + « 5 »** dans le carrousel derrière la voiture (teinte grise) |
| 2 | Idem, caméra pare-chocs | rond + « 5 » dans le carrousel du HUD |
| 3 | Bouclier non sélectionné (Nitro choisi) | **version inversée** : rond noir sur cadre clair |
| 4 | IA qui porte un Bouclier | rond + « 5 » au-dessus d'elle |
| 5 | Nitro (case 4, planche normale) | double chevron inchangé : `perk_sheet` n'est pas touchée |
| 6 | Activer le Bouclier | bulle de 6 s, normal |
| 7 | Toute la course | pas de texture manquante, pas de mélange d'icônes, pas de plantage ; menus et autres images du HUD normaux |
| 8 | Cases 100-104 | pas visibles en course normale (le mod « tirs de Bolt en plus » et le SuperShield n'apparaissent pas). Leur conservation est **prouvée hors jeu** (octets identiques), pas en jeu |

**2e étape (106-109)**, seulement si la 1re réussit :

1. copier `variants\ui_106_109.bin` sur `Blur_test_hud_atlas\gamedata\xt\ui.bin` ;
2. course avec Nitro, Barge, Repair, Mine et Shield ;
3. attendu : triangle « 6 » pour le Nitro, carré « 7 » pour la Barge, croix « 8 » pour la Réparation, losange « 9 »
   pour la Mine.

Pour revenir à la 1re étape : recopier `files\gamedata\xt\ui.bin`.

**Si ça échoue** :

| Symptôme | Cause probable |
|---|---|
| Case blanche ou vide | image refusée (format, taille, budget) : vérifier `Blur_test_hud_atlas\ui\data\ui_common.bpr` (SHA-1 `144164cb…`) et `root.pak` en `.off` |
| Moitié d'icône ou icônes mélangées | un `size.v` oublié |
| Planche entière écrasée | `size.v` non appliqué : `ui.bin` d'origine lu |

Aucune correction dans l'exe.

## 9. Résultats

### 1re étape : case 105 (2026-11-17, **Confirmé en jeu**, captures)

Captures : `blur_extracted\mods\hud_support_atlas\captures\`, hors dépôt. Copie `Blur_test_hud_atlas`, Shield + Nitro.

| # | Cas | Capture | Résultat |
|---|---|---|---|
| 1 | Bouclier choisi, caméra extérieure | `02_exterieur_105_selectionne` | **rond + « 5 »** (planche normale), gros, dans le carrousel derrière la voiture |
| 2 | Caméra pare-chocs | `03_parechocs_105_inverse` | **rond + « 5 »** dans le carrousel du HUD (Bouclier non choisi : version inversée) |
| 3 | Bouclier non choisi (Nitro choisi) | `01_exterieur_105_inverse`, `03_…` | **version inversée** : rond noir et « 5 » sur cadre clair |
| 4 | IA qui porte un Bouclier (Rhymer) | `04_ia_105` | **rond + « 5 »** au-dessus de son nom |
| 5 | Nitro (`perk_sheet`, case 4) | toutes | double chevron vert inchangé |
| 6 | Bouclier activé | — | pas de capture (non vérifié dans cette étape) |
| 7 | Corruption / plantage | toutes | aucune texture manquante, aucun mélange d'icônes, pas de plantage pendant la course |
| 8 | Cases 100-104 | — | pas visibles en course normale ; conservation prouvée **hors jeu** seulement |

**Conclusion** :

- le jeu **accepte une planche support agrandie** (128 × 1024, DXT1 et DXT5, 3 mips) ;
- il **affiche une case qui n'existait pas** (105), dans les deux carrousels et au-dessus des IA, en version normale et
  inversée ;
- on peut donc **ajouter des icônes au HUD par les seules données** : `ui_common.bpr` + 5 `size.v` dans `ui.bin`,
  sans toucher à `Blur.exe`.

Seule la case 105 est validée en jeu : les cases 106-109 ne le sont pas encore.

Observation : sur la planche normale, le rond rouge s'affiche **gris clair**, avec la teinte du Bouclier. Le gadget
utilise l'intensité de la texture et la couleur `colour_fill`, pas la couleur du dessin (`effect_index =
IntensityAsAlpha`). C'est pour ça que les icônes d'origine sont grises. **Fort** (constat sur capture). **Une icône
du HUD doit donc être dessinée en niveaux de gris, et sa couleur se règle dans `ui.bin`.**

### 2e étape : cases 106-109, une par une (préparée le 2026-11-17, **pas encore jouée**)

**Sauvegarde de l'état validé de l'étape 1**, avant toute modification, dans
`hud_support_atlas\etape1_valide\` :

- `gamedata\xt\ui.bin` : SHA-1 `38d57bea…` ;
- `ui\data\ui_common.bpr` : SHA-1 `144164cb…`.

Pour revenir à l'étape 1, recopier ces deux fichiers dans la copie.

**Planches** (`hud_support_atlas.py`, liste `NEW`). Les dessins demandés :

| Case | Dessin |
|---|---|
| 106 | triangle « 6 » |
| 107 | carré « 7 » |
| 108 | **losange « 8 »** |
| 109 | **croix « 9 »** |

106 et 107 étaient déjà ainsi ; 108 et 109 ont été échangés. Contrôles hors jeu, par rapport au `ui_common.bpr` de
l'étape 1 :

- dans les deux planches et à chaque niveau de mip, **seules les cases 108 et 109 diffèrent** ;
- les cases 100-107 (105 comprise, validée en jeu) sont identiques à l'octet ;
- les 61 autres images sont inchangées.

Nouveau `ui_common.bpr` : SHA-1 `38b34bbe…` (2 538 080 o). Données :

| Image | SHA-1 |
|---|---|
| `perk_sheet_support` | `6d00aa2a…` |
| `perk_sheet_support_inverted` | `4f666204…` |

Aperçu : `preview\etape2_cases_105_109.png`. Les formes se distinguent sans la couleur : le HUD ne garde que
l'intensité.

**`ui.bin` d'essai** (`variants\`). Chacun = le `ui.bin` de l'étape 1 avec **un seul** u32 changé :
`shield.texture_index`, décalage `0x061D00`. Les 5 `size.v` sont les mêmes partout, et le Nitro n'est pas touché.

| Test | Fichier | Avant → après | SHA-1 |
|---|---|---|---|
| 106 | `ui_shield_106.bin` | 105 → 106 (`69000000` → `6a000000`) | `c5cc94df…` |
| 107 | `ui_shield_107.bin` | 105 → 107 (`6b000000`) | `85ff9ab1…` |
| 108 | `ui_shield_108.bin` | 105 → 108 (`6c000000`) | `6ca6f78d…` |
| 109 | `ui_shield_109.bin` | 105 → 109 (`6d000000`) | `3c65b140…` |

L'ancienne variante `ui_106_109.bin`, qui changeait 4 bonus d'un coup, a été retirée : elle n'a jamais été installée.

**Installé dans `Blur_test_hud_atlas`** (2026-11-17) :

- `ui\data\ui_common.bpr` = `38b34bbe…` ;
- `gamedata\xt\ui.bin` = `ui_shield_106.bin` (`c5cc94df…`) → **test 106 prêt**.

`Blur_test_hud` et `Blur_test` sont inchangées (vérifié par SHA-1).

**Passer au test suivant**, Blur fermé, une fois le test courant fait et capturé :

```
copy /Y "C:\Users\sanqu\Jeux_WII\blur_extracted\mods\hud_support_atlas\variants\ui_shield_107.bin" "C:\Users\sanqu\Jeux_WII\Blur_test_hud_atlas\gamedata\xt\ui.bin"
```

Pour les tests 108 et 109, remplacer `107` par `108`, puis `109`. La planche ne change plus.

**Pour chaque index** : course perso, **Shield et Nitro**. Captures dans
`captures\<index>_exterieur_bouclier.*`, `<index>_exterieur_nitro.*`, `<index>_parechocs.*`, `<index>_ia.*`.

1. Caméra extérieure, Bouclier choisi : la forme et le chiffre de l'index sur la planche normale.
2. Caméra extérieure, Nitro choisi : la même forme, **inversée**, et le Nitro inchangé.
3. Caméra pare-chocs.
4. IA qui porte un Bouclier.
5. Activer le Bouclier (bulle de 6 s).
6. Vérifier : aucun plantage, aucune texture manquante, aucune moitié de case, aucune forme voisine visible.

Si un index échoue : arrêter, garder les captures, et ne pas passer au suivant avant le diagnostic.

### Tableau des résultats

| Index | Caméra extérieure | Caméra pare-chocs | IA | Inversée | Stabilité |
|---|---|---|---|---|---|
| 105 | Validé (captures 01-02) | Validé (03) | Validé (04) | Validé (01, 03) | Validé (pas de plantage ni de texture cassée vus ; Bouclier activé non capturé) |
| 106 | Validé : triangle « 6 » inversé (capture `106_exterieur_inverse`) | rapporté OK | rapporté OK | Validé (même capture) | rapporté OK |
| 107 | Validé : carré « 7 », case choisie (`107_exterieur_selectionne`) | rapporté OK | rapporté OK | rapporté OK | rapporté OK |
| 108 | rapporté OK | rapporté OK | Validé : losange « 8 » au-dessus de Carver (`108_ia`) | rapporté OK | rapporté OK |
| 109 | rapporté OK | Validé : croix « 9 », case choisie (`109_parechocs_selectionne`) | rapporté OK | rapporté OK | rapporté OK |

« rapporté OK » : l'utilisateur a joué les quatre tests et indique que tout fonctionne (2026-11-17). Une capture par
index a été fournie (`captures\106…109_*`). Sur ces captures :

- chaque case montre sa propre forme et son propre chiffre ;
- aucune moitié de case, aucune forme voisine qui déborde, aucune texture manquante ;
- les icônes d'origine affichées à côté (Mine, Repair, Shunt, Bolt) sont normales.

Les deux planches (normale : 107, 108, 109 ; inversée : 106) et les deux gadgets (`UIPerks2` : carrousels ;
`UIPerks` : IA) sont couverts par des captures. La copie est restée sur le test 109 : `ui.bin` `3c65b140…`, planche
`38b34bbe…`.

Retour de l'utilisateur : « l'affichage extérieur c'est toujours un hexagone, partout ». Les captures 106 / 107
montrent pourtant la nouvelle forme dans le carrousel derrière la voiture. L'hexagone est donc, selon toute
vraisemblance, le **Bouclier posé sur la piste**. Il est **attendu** : ce modèle (`models\perks\pickups\shieldpickup.model`)
a ses propres textures (`icon_shield_01`, `icon_shield_01_inverse`) et ne lit pas `ui.bin`
(`ESSAI_HUD_SHIELD104_DIAGNOSTIC.md` §5). Pour le changer, il faut réinjecter ces textures (`blurtex.py inject`) ou
changer `PickupType.PickupSpecialFX` du Bouclier dans `pickups.bin`. C'est indépendant du HUD.

**Conclusion** : la planche support agrandie à **10 cases** fonctionne en jeu, et les cases 105 à 109 sont chacune
utilisables et indépendantes. **Ajouter des icônes au HUD par les seules données (`ui_common.bpr` + `ui.bin`, sans
toucher à `Blur.exe`) est démontré.**

La validation de 105 ne vaut pas pour 106-109 : chaque index doit avoir ses propres captures.
