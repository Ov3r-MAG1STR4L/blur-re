# Essai en jeu : icône du Bouclier 7 → 104 (planche support)

Préparé le 2026-11-17. **Pas encore joué** : les colonnes « Résultat » sont à remplir après l'essai. Rien ne doit
être déclaré réussi sans capture d'écran ou vidéo. Contexte : `POWERUPS_HUD.md` §8 (mécanisme vérifié dans
`Blur.exe`).

## 1. But

Vérifier en jeu que :

1. un `texture_index` ≥ 100 fait bien passer le HUD sur la planche `perk_sheet_support` (seuil `cmp …, 0x64`,
   `0xC57FD1` / `0xC592B8`) ;
2. la case est bien choisie par V = (index − 100) × `size.v` + `pos.v` ;

le tout sans changer le comportement du Bouclier. Si ça marche, le Bouclier normal doit afficher l'**étoile** du
SuperShield, mais avec **ses propres couleurs** (`Shield_Icon`, gris bleuté).

## 2. Copie de test et fichiers

| Élément | Valeur |
|---|---|
| Copie de test | `C:\Users\sanqu\Jeux_WII\Blur_test_hud` (créée par `make_test_copy.ps1 -Dest … -Mod … -Run`) : hors ligne, paks `gamedata` / `root` / `root_streaming` posés en clair, **sans Railgun** |
| Copie du Railgun | `C:\Users\sanqu\Jeux_WII\Blur_test` : **pas touchée** |
| Jeu installé | pas touché (seulement lu) |
| Dossier du mod | `C:\Users\sanqu\Jeux_WII\blur_extracted\mods\hud_shield104\` |
| `ui.bin` d'origine (sauvegarde) | `…\hud_shield104\original\ui.bin`, 1 004 480 o, SHA-1 `3f235b34411ba1879d43469f8daa61b7290cd132` = celui de `cache\gamedata.pak` du jeu installé (extrait à nouveau avec `blurpak.py` et comparé) |
| `ui.bin` modifié | `…\hud_shield104\files\gamedata\xt\ui.bin`, copié par le script dans `Blur_test_hud\gamedata\xt\ui.bin` |
| Outil | `blurxt.py --set original\ui.bin files\gamedata\xt\ui.bin "#187" "PerkDisplayParameters.shield.texture_index" 104` |

### Modification (**Confirmée** hors jeu)

- Enregistrement `UiXtConfig` `#187` → `PerkDisplayParameters.shield.texture_index` : **7 → 104**.
- **Seul octet changé : décalage fichier `0x61D00`**, u32 little-endian `07 00 00 00` → `68 00 00 00`. Même taille.
- Contexte : ce u32 est suivi des références de couleur `Shield_Icon` / `Shield_Glow` / `Shield_Text`, puis des deux
  textes. C'est bien le premier champ du `UIPerkInfo` `shield`.
- Relecture complète des deux fichiers par le lecteur KSLF (`blurxt.XT.records()`) :
  - 201 enregistrements de chaque côté ;
  - **un seul différent**, `UiXtConfig #187` ;
  - dans celui-ci, un seul champ : `shield.texture_index` (7 → 104).

  Couleurs, textes et les 15 autres entrées sont identiques.

### Copie créée et vérifiée (2026-11-17 20:17, **Confirmé**)

`make_test_copy.ps1` a fini avec « Prêt » : 1 378 fichiers, 9,4 Go, aucun échec. Le « code 3 » affiché à la sortie
est celui de robocopy : 3 = des fichiers copiés, ce n'est pas une erreur. Sauvegarde Blur :
`blur_save_backups\2026-11-17_20-16-14`.

| Contrôle | Résultat |
|---|---|
| `Blur_test_hud\gamedata\xt\ui.bin` | SHA-1 `106400dada69f0d4aa3a74f1da0a8c1eb71abfc6` = fichier modifié |
| `cache\gamedata.pak`, `root.pak`, `root_streaming.pak` (+ `.sig`) | renommés en `.off` : les fichiers en clair sont lus |
| `ui\data\ui_common.bpr` | SHA-1 `6b18c436…` = l'original extrait ; `perk_sheet_support` 128 × 512 DXT1 et son inversée présents |
| Modules en ligne | `amax\dlls` = seulement `lua_hooks.asi` ; pas de `amax\config` : la copie ne peut pas aller en ligne |
| Railgun | absent de la copie (ni `railgun.dll`, ni plugin) |
| `Blur_test` (Railgun) | `ui.bin` toujours `c17ba829…` : pas touché |

## 3. Ce que le code prévoit (pour lire les résultats)

| Affichage | Code (exe) | Effet attendu de l'essai |
|---|---|---|
| Carrousel de la réserve, case choisie | `UIPerks2::Render`, index ≥ 100 → texture 6 `perk_sheet_support` | étoile (planche normale), teinte grise du Bouclier |
| Carrousel, cases non choisies | idem → texture 7 `perk_sheet_support_inverted` | étoile **inversée** (sombre sur cadre clair) |
| Caméra extérieure | `Perks_MainAttached` (3D derrière la voiture) | étoile |
| Caméra pare-chocs | `Perks_MainHUD` | étoile |
| Icône au-dessus d'un adversaire | `UIPerks::Render` (`ai_perks`), index ≥ 100 → texture 2 `perk_sheet_support` | étoile au-dessus d'une IA qui tient un Bouclier |
| Barre de course (points des voitures) | **copie simplifiée inlinée** `0xC56350` : n'utilise que `colour_fill`, **jamais d'icône** | **aucun changement** : point gris du Bouclier comme avant |
| Bulle du Bouclier activé | effets `pickups.bin`, pas le HUD | **aucun changement** |
| Railgun | autre copie (`Blur_test`), son `ui.bin` n'est pas modifié | étoile blanc titane comme avant (pas dans cette copie : voir cas 9) |

## 4. Procédure

Lancer `C:\Users\sanqu\Jeux_WII\Blur_test_hud\Blur.exe`. Le menu passe par Online → Local Network → Custom Game.
Faire une course perso, seul avec F1 (plugin `solo`), avec des IA. Dans Power-up Options, **seulement Shield** coché :
il n'y aura que des Boucliers sur la piste. Les captures vont dans `…\hud_shield104\captures\`, hors dépôt :
`Impr. écran`, ou l'enregistrement de la Xbox Game Bar (Win + Alt + R).

Rappel : Blur se met en pause quand sa fenêtre perd le focus.

| # | Situation | Attendu | Résultat | Preuve |
|---|---|---|---|---|
| 0 | Avant la course : course normale dans le **jeu installé**, un Bouclier ramassé | hexagone (case 7) : capture de référence « avant » | | |
| 1 | Ramasser un Bouclier | étoile grise dans le carrousel | | |
| 2 | 2-3 Boucliers en réserve (en ramasser plusieurs ; la réserve n'accepte que le type de la 1re case) | étoile normale sur la case choisie, étoiles **inversées** sur les autres | | |
| 3 | Activer le Bouclier | la case se vide (case vide `hud_main`) ; bulle du Bouclier normale, 6 s | | |
| 4 | Caméra extérieure | étoile sur le carrousel 3D derrière la voiture | | |
| 5 | Caméra pare-chocs | étoile sur le carrousel du HUD | | |
| 6 | Une IA porte un Bouclier (se mettre derrière une IA qui vient d'en ramasser un) | — | | |
| 7 | Icône au-dessus de cette IA | étoile au-dessus de son nom | | |
| 8 | Barre de course | point de la couleur du Bouclier, **inchangé** (pas d'icône) | | |
| 9 | Railgun | non testable dans cette copie (pas de Railgun). À vérifier dans `Blur_test`, inchangé : étoile blanc titane quand on tient le Railgun | | |

À noter pour chaque cas :

- différence entre la caméra extérieure et la caméra pare-chocs ;
- différence entre le carrousel et l'icône au-dessus des IA ;
- une case mal découpée (moitié d'icône, bord d'une autre icône) indiquerait un mauvais `size.v`.

## 5. Si ça ne marche pas : diagnostic, sans toucher à l'exe

| Symptôme | Piste | Vérification |
|---|---|---|
| Toujours l'hexagone | `ui.bin` d'origine encore chargé | `Blur_test_hud\cache\gamedata.pak` doit être renommé en `.off`, et `Blur_test_hud\gamedata\xt\ui.bin` doit avoir le SHA-1 du fichier modifié. Process Monitor : chemin de `ui.bin` réellement ouvert |
| Case blanche ou vide | planche support absente | `Blur_test_hud\ui\data\ui_common.bpr` présent (posé depuis `root`), `root.pak` en `.off` ; `perk_sheet_support` présent (`blurbpr.py`) |
| Autre icône (Bolt 4 chevrons…) | mauvais rang | V attendu : rang 4 = 384-480 px sur 512 ; comparer à la planche contact `perk_icons_sheet.png` |
| Étoile au HUD mais pas sur les IA (ou l'inverse) | l'affichage concerné passe par une autre entrée | `ai_perks` utilise le même `GetPerkInfo` (`0xC57F9B`) : différence inattendue, à noter avec une capture |
| Barre de course sans changement | **attendu** | elle n'affiche pas d'icône |

## 6. Après l'essai

- La copie `Blur_test_hud` reste en place pour la suite.
- La sauvegarde Blur faite avant la copie est dans `blur_save_backups\<date>`. Pour la remettre :
  `.\make_test_copy.ps1 -Restore -Run`. La sauvegarde est partagée entre toutes les installations.
- Remplir les colonnes « Résultat » et « Preuve », puis noter la conclusion dans `POWERUPS_HUD.md` et
  `CONNAISSANCES.md`.

## 7. Essai suivant conseillé

Si l'étoile apparaît, le seuil et la planche support sont validés en jeu. Essai suivant : **une planche support
agrandie**. Toujours dans `Blur_test_hud` :

1. `perk_sheet_support` et son inversée en 128 × 1024 (cases 100-109), via `blurbpr.Bpr.rebuild` ;
2. `size.v` 0,1875 → 0,09375 dans les textures 6 / 7 de `Perks_MainHUD` et de `Perks_MainAttached`, et dans la
   texture 2 de `ai_perks` ;
3. `shield.texture_index` → **105**, sur une case dessinée exprès.

Cela validerait l'ajout de cases sans toucher à l'exe.

## 8. Résultats

*(à remplir après l'essai)*
