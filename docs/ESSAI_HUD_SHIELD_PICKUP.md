# Essai : apparence du Bouclier posé sur la piste (hexagone → triangle « 6 »)

2026-11-17. Préparé, **pas encore joué**. But : changer l'apparence du Bouclier posé sur la piste sans changer son
comportement. `Blur.exe`, le jeu installé et les copies `Blur_test`, `Blur_test_hud`, `Blur_test_hud_atlas` ne sont
pas touchés.

## 1. Ressources (**Confirmé**, lecture des fichiers)

**Chaîne d'affichage** :

1. `pickups.bin` → `PickupType` #399 (Shield) → `PickupSpecialFX` ;
2. l'effet a deux composants :
   - `AnimatedMeshSpecialFX` : modèle `models\Perks\Pickups\ShieldPickup.model`, animation
     `animations\Perks\ShieldPickup.cycle`, `FarDistance` 350 ;
   - `LightSpecialFX` : une lumière.

   Voir `POWERUPS_DONNEES.md`. Le leurre (`PickupSpecialFXDecoy`) est un autre modèle, `ShieldPickupDecoy.model`.
3. Rien de tout cela ne touche au comportement : la collision et le ramassage sont ceux de l'emplacement
   (`PickupPositionActor`, rayon `PickupRadius` 2 m), pas du modèle.

**`shieldpickup.model`** :

- 791 814 o, SHA-1 `d56a40d70ea3e78b6fc44d936999f80022dbe12e` ;
- présent dans `root.pak` **et** dans `boot.pak`, identique ;
- shaders `MeshEffect.fx` et `MeshEffectUVDistort.fx` (`g_tTexture`, `g_tUVDistortTexture`, `g_vColour`,
  `g_vColourFresnel`, défilement d'UV), paramètre animé `hlslShader3.ScrollDistortOffsetY`.

**Textures** : il n'y en a **que deux**, et elles sont **intégrées au fichier `.model`** (enregistrements
« inline », il n'existe pas de fichier de texture séparé) :

| Texture | Données dans le `.model` | Format | Contenu |
|---|---|---|---|
| `icon_shield_01` | `0x0003D7`-`0x00AE8F` (43 704 o) | DXT1 256 × 256, 9 mips, opaque, gris | cadre lumineux + hexagone sombre |
| `icon_shield_01_inverse` | `0x0B5A51`-`0x0C0509` (43 704 o) | idem | hexagone blanc sur fond noir |

- **La couleur ne vient pas des textures**, qui sont en niveaux de gris. Elle vient du shader (`g_vColour`, sans doute
  animé par le `.cycle`) et de la lumière de l'effet. Même principe que les effets des bonus (`CONNAISSANCES`,
  « Couleurs des effets »).
- **Partage** : aucun autre modèle de `root` ne contient `icon_shield_01` (recherche sur tous les `.model` extraits).
  Le changement reste donc limité au Bouclier posé sur la piste. Les autres bonus ont leurs propres modèles, et le
  leurre `shieldpickupdecoy.model` ne contient pas ces textures.

**Contrainte de chargement.** `boot.pak` contient 718 fichiers, **tous identiques** à ceux de `root.pak`, dont ce
modèle et les 171 `.cycle` des bonus. D'après le constat Process Monitor (CONNAISSANCES §3.1 bis), un fichier présent
dans un pak passe avant le fichier en clair. Or le script de copie met `root.pak` de côté, **pas `boot.pak`** : la
version d'origine du modèle pourrait encore être lue depuis `boot.pak`. Pour l'essai, `boot.pak` est donc **aussi mis
de côté**. C'est sans perte, puisque son contenu est déjà posé en clair, depuis `root`.

## 2. Modification (vérifiée hors jeu)

Script : **`shield_pickup_icon.py`**.

- Il retire l'hexagone de `icon_shield_01`, en remplissant la zone par diffusion de la lueur voisine, puis dessine
  un **triangle + « 6 »** sombres dans le même style.
- `icon_shield_01_inverse` reçoit le même triangle + « 6 », en blanc sur noir, à la même place.
- Injection par `blurtex.inject` : même format DXT1, mêmes 9 mips, même taille.

Fichiers (dossier `blur_extracted\mods\hud_shield_pickup\`) :

| Fichier | Rôle |
|---|---|
| `original\shieldpickup.model` | sauvegarde de l'original, SHA-1 `d56a40d7…` |
| `textures_orig\*.png` | textures d'origine extraites |
| `textures_new\*.png` | textures d'essai |
| `files\models\perks\pickups\shieldpickup.model` | modèle modifié, SHA-1 `a0bfca90ee28af84626d97bcbe40c8d11ec802cb`, même taille (791 814 o) |
| `preview\avant_apres.png` | textures relues **depuis le nouveau modèle**, à côté des originales |

**Différences exactes** :

- 24 647 octets changés, **tous** dans les deux plages de données de texture (17 786 + 6 861), vérifié par le
  script ;
- géométrie, matériaux, chaînes et en-têtes sont identiques à l'octet ;
- `pickups.bin`, la collision et les autres bonus ne sont pas touchés.

Note : la consigne disait de ne pas modifier `shieldpickup.model`. C'est impossible ici, parce que les textures sont
**à l'intérieur** de ce fichier. Seuls leurs octets changent : le reste du modèle est identique, ce que le script
vérifie.

Défaut visuel connu : il reste un léger fantôme de l'hexagone dans la lueur de `icon_shield_01`. Le remplissage
n'est pas parfait, mais cela ne gêne pas l'essai.

## 3. Copie de test

`C:\Users\sanqu\Jeux_WII\Blur_test_hud_pickup` (`make_test_copy.ps1 -Dest … -Mod …\hud_shield_pickup\files -Run`),
puis `cache\boot.pak` → `boot.pak.off`. Contrôles : §5.

## 4. Procédure en jeu

Course perso seul (F1) avec des IA, **seulement Shield** coché, plus un essai avec Shield + Nitro. Captures dans
`hud_shield_pickup\captures\`.

| # | Vérifier | Attendu |
|---|---|---|
| 1 | Bouclier posé sur la piste | cadre lumineux avec **triangle + « 6 »** (couleur habituelle du Bouclier) |
| 2 | Lisibilité de face et de côté | symbole lisible ; proportions et rotation du modèle inchangées |
| 3 | Animation | rotation / pulsation comme avant |
| 4 | Ramassage | passer dessus donne un Bouclier (carrousel) |
| 5 | Bouclier activé | bulle de 6 s |
| 6 | Réapparition | le bonus revient au même endroit |
| 7 | Autres bonus (Nitro) et leurres | apparence inchangée |
| 8 | Comparaison | capture d'un Bouclier sur la piste dans `Blur_test_hud` (hexagone) |
| 9 | Démarrage | le jeu démarre sans `boot.pak` (sinon §6) |

Captures demandées : de face, de côté, en course, pendant le ramassage si possible, et comparaison avec l'original.

## 5. Contrôles de la copie (2026-11-17 21:57, **Confirmé**)

Le script a fini avec « Prêt ». Le « code 3 » est celui de robocopy : des fichiers copiés, pas une erreur.

| Contrôle | Résultat |
|---|---|
| `models\perks\pickups\shieldpickup.model` | SHA-1 `a0bfca90…` = modèle modifié |
| `cache` | `boot.pak`, `gamedata.pak`, `root.pak`, `root_streaming.pak` (+ `.sig`) en `.off` ; `gamedata_boot.pak` actif, comme dans les autres copies (il ne contient pas de modèles) |
| `ui.bin` / `ui_common.bpr` | originaux (`3f235b34…` / `6b18c436…`) : HUD d'origine |
| Modules | `lua_hooks.asi` seul ; pas de `amax\config` (hors ligne) ; pas de Railgun |
| Copies de référence | `Blur_test`, `Blur_test_hud`, `Blur_test_hud_atlas` : modèle d'origine `d56a40d7…`, `boot.pak` actif, non touchées |

## 6. Si ça ne marche pas : diagnostic d'abord

| Symptôme | Piste |
|---|---|
| Le jeu ne démarre pas | `boot.pak` nécessaire au démarrage : le remettre (`boot.pak.off` → `boot.pak`) et noter si l'hexagone revient (cela prouverait la priorité du pak) |
| Toujours l'hexagone | le modèle d'origine est lu ailleurs (vérifier avec Process Monitor quel fichier est ouvert) |
| Symbole invisible ou délavé | rôle exact de chaque texture dans les deux shaders (`g_tTexture` / `g_tUVDistortTexture`) : l'une peut seulement déformer l'autre |
| Fantôme de l'hexagone gênant | améliorer le remplissage, pas le modèle |

Ne pas remplacer le modèle par `ShieldSuperPickup.model` dans cette première expérience.

## 7. Réutilisation pour un futur bonus

Si l'essai réussit, chaque bonus posé sur la piste a son propre modèle, avec ses propres textures intégrées
(`<type>pickup.model`). On peut changer l'apparence d'un type de bonus sur la piste en réinjectant ses textures, sans
toucher à `pickups.bin` ni au comportement.

Pour un bonus maison qui emprunte un type (comme le Railgun avec le SuperShield), c'est le modèle du type emprunté
qu'on redessine : par exemple `shieldsuperpickup.model` pour le Railgun.

## 8. Résultats (2026-11-17, capture `captures\01_piste_triangle6.webp`, **Confirmé en jeu**)

| # | Vérifié | Résultat |
|---|---|---|
| 1 | Bouclier posé sur la piste | **triangle + « 6 »** dans le cadre lumineux, avec la teinte habituelle (blanc rosé) : le modèle modifié est bien lu |
| 2 | Proportions, lisibilité | cadre et taille inchangés, symbole lisible en course (vue de 3/4 avant) |
| 7 | Autres bonus | Nitro posé sur la piste inchangé (double chevron vert) |
| 9 | Démarrage sans `boot.pak` | le jeu démarre et la course se lance |
| — | HUD | le carrousel montre toujours l'**hexagone**, ce qui est attendu (`ui.bin` d'origine dans cette copie) : le HUD et le bonus sur la piste sont bien indépendants |
| 3-6 | Animation, ramassage, Bouclier de 6 s, réapparition | **OK**, d'après l'utilisateur (sans capture) |
| — | Vue de côté | OK (rapporté) : le cadre est plat, presque invisible de profil, comme l'original |
| — | Vue de dos | OK (rapporté) : symbole vu inversé, comme l'original |
| — | Rétroviseur | OK (rapporté) |
| — | Fantôme de l'hexagone | **présent** (rapporté) : léger hexagone dans la lueur de `icon_shield_01` (défaut du remplissage, connu) |

Retour de l'utilisateur, 2026-11-17 : côté, dos, rétroviseur, Bouclier de 6 s et réapparition sont OK. Le
comportement du bonus n'a pas changé.

**Conclusion** :

- on peut changer l'apparence d'un bonus posé sur la piste en remplaçant **seulement les textures intégrées** à son
  modèle ;
- il ne faut rien toucher d'autre : `pickups.bin`, l'exe et la géométrie restent tels quels ;
- dans une copie de test, il faut aussi mettre `boot.pak` de côté (contenu identique à `root`, déjà en clair). Le
  jeu démarre sans lui. Ce n'est pas une preuve de la priorité de `boot.pak` : aucun essai n'a été fait avec
  `boot.pak` actif.

**Reste à faire** : seulement le léger fantôme de l'hexagone, s'il gêne. Il faut améliorer le remplissage de
`icon_shield_01` dans `shield_pickup_icon.py`, ou dessiner le cadre en entier, sans partir de l'original.
