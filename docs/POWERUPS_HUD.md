# Icônes des bonus dans le HUD : planches, index, affichage

Étude du 2026-11-17, faite en lecture seule (aucun fichier du jeu modifié). Elle suit `POWERUPS.md` §6. Planche
contact : `perk_icons.py` → `C:\Users\sanqu\Jeux_WII\blur_extracted\hud_icons\perk_icons_sheet.png`. L'image reste
hors du dépôt, car c'est du contenu du jeu.

Confiance :

- **Confirmé** : lu dans les fichiers du jeu vendu (`ui_common.bpr`, `ui.bin`, chaînes de `Blur.exe`) ;
- **Fort** : lu dans le code source fuité (`blur_source\BlurRebuilt\code`, juin 2010, retouches `[Blur2PC]`
  d'uKER possibles) ;
- **Hypothèse** : déduit, non vérifié.

Rien n'a été essayé en jeu pour cette étude.

## 1. Où sont les icônes

### 1.1 Les planches (`root.pak` → `ui\data\ui_common.bpr`, **Confirmé**)

Extraites avec `blurbpr.py`. Chemin extrait :
`C:\Users\sanqu\Jeux_WII\blur_extracted\root\ui\data\ui_common.bpr`.

| Image | Format | Mips | Taille | Contenu |
|---|---|---|---|---|
| `perk_sheet` | DXT1, opaque (alpha 255 partout) | 3 | 128 × 1024 | 10 icônes, cases 0-9 |
| `perk_sheet_inverted` | DXT5 (alpha réel) | 3 | 128 × 1024 | les mêmes 10, couleurs inversées |
| `perk_sheet_support` | DXT1, opaque | 3 | 128 × 512 | 5 icônes, cases 100-104 |
| `perk_sheet_support_inverted` | DXT5 | 3 | 128 × 512 | les mêmes 5, inversées |
| `mod_gift` | DXT1, opaque | 2 | 128 × 512 | 5 symboles de mods (cadeaux de bonus) |
| `hud_main` | DXT5 | 3 | 512 × 256 | entre autres, la **case vide** et les flèches de visée |
| `blob` | — | — | — | halo sous la case sélectionnée |

- **Les icônes sont groupées en planches verticales**, pas en fichiers séparés.
- Une case fait **128 × 96 px**. Les bandes d'icônes mesurées tombent tous les 96 px :

| Planche | Bandes mesurées (px) |
|---|---|
| `perk_sheet` | 14-85, 110-181, … 876-948 |
| `perk_sheet_support` | 12-84 … 396-468 |

- Place libre :
  - `perk_sheet` : 1024 − 10 × 96 = **64 px vides** en bas ;
  - `perk_sheet_support` : 512 − 5 × 96 = **32 px vides**.

  **Aucune place pour une case de plus** sans agrandir l'image.
- Les icônes normales sont **grises sur fond noir, sans alpha**. Le gadget dessine avec
  `effect_index = IntensityAsAlpha` : la luminosité sert de transparence. La couleur vient ensuite de `colour_fill`
  (§2).

### 1.2 Qui découpe les planches : les gadgets de `ui.bin` (**Confirmé**)

`gamedata\xt\ui.bin` contient les écrans d'interface (`UIScreen`, 129). L'écran `hud_objects` contient les gadgets
du HUD. Chaque gadget a une liste `textures` de `UITextureParam` :

| Champ | Type |
|---|---|
| `filename` | nom d'une image `.bpr` |
| `pos` | `{u, v}` |
| `size` | `{u, v}` |
| `name` | i32 |

Les gadgets qui affichent des bonus :

| Gadget (`hud_objects`) | Classe | n° de texture → image, `pos`, `size` |
|---|---|---|
| `Perks_MainHUD` (élément 61) | `UIPerks2` | 0 `perk_sheet` (0,0) (1 ; **0,09375**) · 1 `perk_sheet_inverted` idem · 2-3 `xbox360_buttons` · 4 `options_slider` · **5 `hud_main` (0,75 ; 0) (0,1875 ; 0,25) = case vide** · 6 `perk_sheet_support` (0,0) (1 ; **0,1875**) · 7 `perk_sheet_support_inverted` idem · 8 `mod_gift` (0,0) (1 ; 0,1875) · 9 `blob` |
| `Perks_MainAttached` (22), enfant de `Perks_Dummy` (59) | `UIPerks2`, `attached_to_car = true` | les mêmes 10 textures |
| `ai_perks` (26), enfant de `ai_damage` | `UIPerks` | 0 `perk_sheet` (0,0) (1 ; 0,09375) · 1 `hud_main` (case vide) · 2 `perk_sheet_support` (0,0) (1 ; 0,1875) |

- `size.v` = 0,09375 = 96 / 1024 et 0,1875 = 96 / 512 : c'est la **hauteur d'une case**.
- Aucune coordonnée par icône n'est stockée : le code multiplie (§3).
- Seuls autres utilisateurs de `perk_sheet` : les 24 éléments `Gfx_PowerupsImgIcon*` de l'écran d'aide
  `Shared\Help_Powerups.lua`. Ils ont des `pos.v` fixes : Mine 0, Barge 0,09375, Shunt 0,1875, Shock 0,28125,
  Nitro 0,375, Bolt 0,5625 (case 6), Shield 0,65625, Repair 0,75. Elles correspondent aux mêmes cases.
- **Les noms des planches ne sont ni dans `Blur.exe` ni dans les scripts Lua** : seulement dans `ui.bin`
  (**Confirmé** : chaîne absente de l'exe et des 144 scripts BZUI).

### 1.3 Icônes des menus : une autre source (vectorielle)

- L'écran des options LAN (`MpCustomRacePowerups.lua`), l'aide (`Help.lua`, `Help_Powerups.lua`, `Help_Video.lua`)
  et le menu de jeu utilisent des **formes vectorielles**. Elles sont dans
  `root.pak` → `ui\data\ipf\perk_icons.ipf`, sous le nom de la forme : `perk_bolt`, `perk_mine`, `perk_barge`,
  `perk_shunt`, `perk_shock`, `perk_nitro`, `perk_shield`, `perk_repair`, `perk_option`, `perk_question`.
- On les demande ainsi : `CustomRace_SetupToggle(…, "perk_shield", "perk_icons")`. **Confirmé** (chaînes des
  `.luac` ; source Lua dans `code\amax\library\Ui\game\lua_scripts`).
- Le même fichier contient **`perk_mine_x2`, `perk_barge_x2`, `perk_shunt_x2`, `perk_shock_x2`,
  `perk_nitro_x2`**. Voir §5.

---

## 2. Correspondance complète bonus → icône

L'**index n'est pas le numéro du bonus**. Le jeu passe par une entrée nommée de
`ui.bin` → `UiXtConfig.PerkDisplayParameters`. Sa structure : `UiPerkDisplayParameters`, 384 o, 16 champs
`UIPerkInfo` de 24 o, dans l'ordre :

| + | Champ | + | Champ |
|---|---|---|---|
| 0 | `nitrous` | 192 | `repair` |
| 24 | `shock` | 216 | `shield` |
| 48 | `shunt` | 240 | `superShield` |
| 72 | `barge` | 264 | `empty` |
| 96 | `bomb` | 288 | `extra_blindfire4` |
| 120 | `blindfire3` | 312 | `extra_blindfire3` |
| 144 | `blindfire2` | 336 | `extra_blindfire2` |
| 168 | `blindfire1` | 360 | `extra_blindfire1` |

Chaque `UIPerkInfo` contient `texture_index`, `colour_fill`, `colour_glow`, `colour_text`, `loc_id_name`,
`past_loc_id_name`.

**Choix de l'entrée** (`C_PerkDisplayParameters::GetPerkInfo(type, nbTirs, modBoltEnPlus)`, `UIPerks2.cpp:80`,
**Fort**) :

| Type (`E_PICKUP_TYPE`) | Sous-type / état | Entrée `ui.bin` | `texture_index` | Planche [case], pixels V | Dessin | `colour_fill` (r, g, b) |
|---|---|---|---|---|---|---|
| 0 Nitrous | tous | `nitrous` | 4 | `perk_sheet`[4], 384-480 | double chevron | `Nitro_Icon` (0,4 ; 1 ; 0,5) vert |
| 1 Shock | tous | `shock` | 3 | `perk_sheet`[3], 288-384 | éclair | `Shock_Icon` (0,5 ; 0,83 ; 1) bleu |
| 2 Shunt | tous | `shunt` | 2 | `perk_sheet`[2], 192-288 | chevron + losange | `Shunt_Icon` (1 ; 0,44 ; 0,4) rouge |
| 3 Blindfire (Bolt) | 3 tirs restants (ou autre nombre) | `blindfire3` | **6** | `perk_sheet`[6], 576-672 | 3 chevrons | `Blindfire_Icon` (0,98 ; 0,57 ; 0,84) rose |
| 3 Blindfire | 2 tirs | `blindfire2` | **9** | `perk_sheet`[9], 864-960 | 2 chevrons | `Blindfire_Icon` |
| 3 Blindfire | 1 tir | `blindfire1` | **5** | `perk_sheet`[5], 480-576 | 1 chevron | `Blindfire_Icon` |
| 3 Blindfire, mod « tirs en plus » (`Boss_AdditionalBlindfireShots`) | 4 / 3 / 2 / 1 tirs (autre → 4) | `extra_blindfire4/3/2/1` | **100 / 101 / 102 / 103** | `perk_sheet_support`[0-3] | 4 / 3 / 2 / 1 chevrons | `Blindfire_Icon` |
| 4 Barge | tous | `barge` | 1 | `perk_sheet`[1], 96-192 | ⟨◆⟩ | `Barge_Icon` (0,62 ; 0,5 ; 1) violet |
| 5 Bomb (Mine) | tous | `bomb` | 0 | `perk_sheet`[0], 0-96 | **éclat (soleil levant)** | **`Flash_Icon`** (1 ; 0,55 ; 0,32) orange |
| 6 Repair | tous | `repair` | 8 | `perk_sheet`[8], 768-864 | clé | `Repair_Icon` (0,9 ; 0,94 ; 0,5) jaune |
| 7 Shield | tous | `shield` | 7 | `perk_sheet`[7], 672-768 | hexagone | `Shield_Icon` (0,65 ; 0,65 ; 0,72) gris |
| 8 Fan | — | **aucune** (`GetPerkInfo` rend `NULL`) | — | — | — | — |
| 9 Stopwatch | — | **aucune** (`NULL`) | — | — | — | — |
| 10 SuperShield | tous | `superShield` | **104** | `perk_sheet_support`[4], 384-480 | **étoile** | `!255 153 153 255` rose |
| case vide | réserve vide | `empty` | 5 (**ignoré**) | `hud_main` (texture 5 / 1) | case vide | `Main_Black` |

Remarques :

- Valeurs (index, couleurs, images) : **Confirmées** dans `ui.bin` et `ui_common.bpr`. Choix de l'entrée selon le
  type et le nombre de tirs : **Fort** (source).
- **Le sous-type ne change pas l'icône** : Normal, Reversed, DoubleTap, Mod… utilisent la même entrée. Le HUD
  regarde le **type** et le **nombre de tirs** de la réserve (`PickupStore.mType`, `mNumShots`), jamais le
  sous-type. **Fort.**
- **Seul le Bolt change d'icône selon son état** : le nombre de tirs restants (3, 2, 1, ou 4 à 1 avec le mod).
- Un Bolt à 3 tirs utilise la case 6 et un Bolt à 2 tirs la case 9 : l'ordre des cases ne suit ni les types ni le
  nombre de tirs. **La case 9 a sans doute été ajoutée après coup** (**Hypothèse**).
- La Mine porte l'icône et les couleurs d'un « Flash ». Le prototype `PickupFlash.cpp` (non compilé, voir
  `POWERUPS.md` §1.3) et ces noms de couleurs montrent que **la Mine est l'ancien « Flash »**, dont elle a gardé
  l'icône. **Fort** (deux indices concordants).
- **L'étoile de la case 104 est l'icône du SuperShield**, donnée par `ui.bin`. Elle était encore rose dans l'export
  d'origine. Le Railgun l'a passée en blanc titane dans `Blur_test` : ce n'est pas l'icône d'un bonus de Blur 2.

---

## 3. Chaîne d'affichage

```
réserve du véhicule : VehiclePickupInfo.mPickupStore[i] = {mType, mNumShots}, mPickupStoreIndex = case choisie
  → C_PerkDisplayParameters::GetPerkInfo(mType, mNumShots, modBoltEnPlus)   → C_UIPerkInfo (ui.bin)
  → m_sTextureIndex : < 100 → texture 0 (sélectionnée) / 1 (non sélectionnée) du gadget
                      ≥ 100 → index − 100, texture 6 / 7   (UIPerks : 0, ou 2 pour ≥ 100)
  → UITextureParam {filename, pos, size} du gadget (ui.bin hud_objects)
  → V = pos.v + size.v × index ; U = pos.u, largeur size.u           (gSimple2D.AddTexUVs)
  → image du .bpr (ui_common.bpr) teintée par colour_fill, effet IntensityAsAlpha
```

Code (**Fort**) :

- `UIPerks2::Render`, `src…\Ui\game\Gadgets\Hud\UIPerks2.cpp:640-860` ;
- `UIPerks::Render`, `UIPerks.cpp:100-179` ;
- liaison des champs : `XT_TYPE(UI::C_UIPerkInfo, "UIPerkInfo")` et `XT_TYPE(UI::C_PerkDisplayParameters,
  "UiPerkDisplayParameters")` ;
- couleurs résolues au chargement : `UiLayer.cpp:957-972` (`Resolve` → `SetByName`, palette `UISpriteColours` de
  `ui.bin`).

Les noms `texture_index`, `UiPerkDisplayParameters`, `UIPerkInfo`, `UIPerks2`, `attached_to_car`, `slot_effect`,
`extra_blindfire4`, `UI.HUD.PerksOnlyOneForAI` sont tous dans `Blur.exe` : **Confirmé**. Le seuil « 100 » n'a pas été
retrouvé dans le désassemblage (§7).

**Le Lua ne choisit pas l'icône.** `HUD.lua` :

- clone les gadgets (`UIButtons.CloneXtGadgetByName("hud_objects", "Perks_Dummy")`) ;
- les aplatit en écran partagé (`SetXtVar(id, "bender", 0.0)`) ;
- gère l'alerte du Shunt (`HUD_ActivateECMWarning` colore `targeting_bottom` en `Slot3`, seulement en multijoueur
  sans écran partagé).

Tout le reste se fait en C++ dans les gadgets. **Fort** (source Lua) ; noms **Confirmés** dans `HUD.luac`.

---

## 4. Comportement du HUD

### 4.1 Les trois affichages de la réserve

| Gadget | Où | Quand (`UIPerks2::Render`, l. 520-527) |
|---|---|---|
| `Perks_MainAttached` | carrousel de 3 cases **en 3D derrière la voiture** (`attached_to_car`), avec une lumière ponctuelle de la couleur `colour_text` de la case choisie | un seul écran **et** caméra extérieure |
| `Perks_MainHUD` | carrousel dans le calque 3D du HUD | un seul écran **et** caméra pare-chocs (`E_VFCamera_Bumper`) ; toujours en écran partagé (aplati) |
| `ai_perks` (`UIPerks`) | **une** icône au-dessus de chaque voiture adverse : son bonus choisi (`UI.HUD.PerksOnlyOneForAI`) | sous les étiquettes des IA / joueurs (`ai_damage`) |

- La **barre de course** (`UIRaceLine.cpp:131, 414, 543, 673`) colore aussi le point de chaque voiture avec le
  `colour_fill` de son bonus choisi. Pour le point du joueur : hors ligne, ou avec la capacité « radar ».
- Ce que voient les **adversaires** : `ai_perks` et la barre de course, avec la même table. Pas de vue spectateur
  propre aux bonus : le gadget suit `m_sVehicleIndexOverride` s'il est réglé. **Fort.**

### 4.2 États et effets (**Fort** pour le code, **Confirmé** pour les données)

- **Case choisie** : image `perk_sheet` (icône blanche sur fond sombre). **Autres cases** : `perk_sheet_inverted`
  (icône sombre sur fond clair), avec l'état de rendu `m_SelectedRS`. Le nom est inversé dans le code
  (l. 806-809), mais c'est bien la case choisie qui reçoit la planche normale.
- **Case vide** : `hud_main` (texture 5), quel que soit `empty.texture_index`.
- **Taille des cases** : chacune grossit vers `scale_amount` quand elle est choisie (`m_Items[i].FrameUpdate`).
  `slot_effect` donne pour chaque case : échelle, alpha, mod (taille et alpha), halo `blob`. Dans les données
  d'origine, mod et halo sont à 0 : **jamais affichés**.
- **Symbole de mod sur une case** : `mod_gift`, ligne choisie par la capacité qui a offert le bonus :

| Ligne | Capacité |
|---|---|
| 0 | Front Runner (couleur `m_ColourMod1`) |
| 1 | Bribe (`ColourMod3`) |
| 2 | Safety Net (`ColourMod2`) |
| 3 | Drifter (`ColourMod1`) |
| 4 | Boss FansNitroGift (`ColourModSp`) |

  Dessin seulement si `mod_scale` et `mod_alpha` > 0 : avec les données d'origine, **jamais**.
- **Animations** (timelines des deux gadgets `UIPerks2`) :

| Timeline | Effet |
|---|---|
| `Unfold_Pickup` | dépliage au départ de la course : `foldout_scale`, `slot_step`, `scale_amount`, `angle_step` |
| `Show_Pickup` | apparition par l'alpha |
| `Pulse_Pickup` | pulsation : échelle et intensité |
| `ability_active_pickup_slot1/2/3` | une case par capacité |

  Compte à rebours sonore avant l'activation des bonus : `E_UiSoundEffect_PerksCountdownActionIn` puis
  `PerksGoActionIn` (pendant 3 s, `GetPerksActivatedIn`).
- **Ramassage** : `E_UiGameMsg_PickedupAPerk` → `UIPerks2::AddPerk`, **vide** dans la source (aucun effet propre au
  ramassage dans ce gadget).
- **Changer de case** : `ShufflePerks` → son `E_UiSoundEffect_PerkSwitchActionIn`.
- **Bonus consommé** : `RemovePerk` fait glisser les cases.
- **HUD caché** :
  - pendant le mod Last Gasp ou si la voiture est brouillée (Scrambler) : `m_LastGaspActive || m_ScramblerActive` ;
  - avant l'activation des bonus.
- **Rien ne montre** un bonus refusé ou impossible à tirer : le son d'erreur `PickupsFireErrorActionIn` est en
  commentaire (`VLC_Pickups.cpp:856`). Ni le DoubleTap ni les autres sous-types n'ont d'affichage propre.
- **Alertes d'attaque** :
  - Shunt qui arrive → `targeting_bottom` change de couleur (`HUD.lua:2015`) ;
  - flèches `targeting_left/right/top/bottom` et `ai_targeting_left/right` : image `hud_main`, (0,9375 ; 0,0625),
    taille (0,0625 ; 0,75) ;
  - `UITargeting::ProcessHitByPerk` prévoyait un texte « touché par… » mais fait `return;` avant (« Put back in when
    PK has done us a 'negative' message »).
- **Champs sans lecteur trouvé** dans le C++ : `colour_glow`, `loc_id_name`, `past_loc_id_name`. Seul `colour_text`
  sert, pour la lumière derrière la voiture. **Inconnu** : peut-être lus par le Lua (`InGameScoring.GetPerkName`).

---

## 5. Contenu inutilisé ou prototype

| Élément | Preuve | Conclusion |
|---|---|---|
| `perk_icons.ipf` : `perk_mine_x2`, `perk_barge_x2`, `perk_shunt_x2`, `perk_shock_x2`, `perk_nitro_x2` | noms dans le fichier ; **aucune** référence dans les 144 `.luac`, les scripts Lua de la source ou `Blur.exe` | inutilisées (**Confirmé**). Probablement les icônes du **DoubleTap** (**Hypothèse** forte) : « ×2 », les 5 types ont un `mUpgrades.Double*` dans `CanUseDouble` (`DoubleBarge` compris), et elles n'ont aucun usage ailleurs. Pas de `perk_shield_x2`, alors que `DoubleShield` existe |
| `mod_gift` (5 lignes) et halo `blob` | lus par le code, mais `mod_scale`, `mod_alpha`, `blob_*` valent 0 dans `ui.bin` | effets prévus, **jamais visibles** avec les données d'origine (**Confirmé** pour les données) |
| case 9 (`blindfire2`) après le Repair (8) | ordre des cases | ajout tardif (**Hypothèse**) |
| icône « Flash » de la Mine | `Flash_Icon/Glow/Text`, prototype `PickupFlash.cpp` | ancien nom de la Mine (**Fort**) |
| bas des planches (64 et 32 px) | noirs dans `perk_sheet` / `perk_sheet_support` | pas d'icône cachée (**Confirmé**) |
| icônes des prototypes non compilés (Magnet, BlackHole, Teleport…) | rien dans les planches ni dans `perk_icons.ipf` | **aucune icône** pour eux |
| texte « touché par… » | `UITargeting.cpp:207` (`return;`) | fonction coupée (**Fort**) |

---

## 6. Modifier ou ajouter une icône

### 6.1 Remplacer une icône existante (données seules, **Fort**, pas encore essayé)

1. Dessiner la case : 128 × 96 px, au même rang dans :
   - **la planche normale** : icône claire sur fond **noir**, sans alpha (la luminosité fait la transparence, DXT1) ;
   - **la planche inversée** : icône sombre sur cadre clair, avec alpha (DXT5).
2. Réencoder l'image **à la même taille, au même format, avec le même nombre de mips** (DXT1 / DXT5, 3 mips).
   Réécrire seulement ses octets dans `ui_common.bpr` : `blurbpr.Bpr.reuse` / remplacement en place, sans changer
   la table ni les noms (règle du `.bpr`, CONNAISSANCES §3.6 bis). `encode()` de `blurbpr.py` sait faire le DXT1 ;
   le DXT5 de la planche inversée reste à vérifier.
3. `ui_common.bpr` est dans `root.pak`. Comme pour les pochettes d'album : copie de test seulement, `root.pak` mis
   de côté et son contenu posé en clair. **Méthode prouvée en jeu** pour ce même fichier (`artatlas.py`).
4. Couleurs et nom : `ui.bin` (`colour_*`, chaîne de même longueur réécrite sur place, comme pour le Railgun) et le
   `.loc`.

**Pour le Railgun** : remplacer la case **104** (rang 4 de `perk_sheet_support` et de
`perk_sheet_support_inverted`, pixels V 384-480). Elle ne sert qu'au SuperShield, donc rien d'autre ne change.

### 6.2 Ajouter une icône (nouvelle case)

- **Pas de place libre** dans les planches (§1.1).
- Option données seules (**Hypothèse**, à essayer) :
  1. agrandir `perk_sheet_support` (et son inversée) à 128 × 1024 ;
  2. passer `size.v` de 0,1875 à 0,09375 dans les textures 6 et 7 de `Perks_MainHUD` et de `Perks_MainAttached`,
     et dans la texture 2 de `ai_perks` ;
  3. les cases 100 à 109 existent alors.

  Car le calcul V = `pos.v + size.v × (index − 100)` vient des données. `rebuild()` sait agrandir un `.bpr`, avec le
  risque connu du budget de textures d'interface.
- **Une nouvelle case ne suffit pas.** Il faut qu'une **entrée** de `PerkDisplayParameters` la désigne :
  - la structure a **16 champs fixes** ;
  - `GetPerkInfo` est un `switch` sur le type, codé en dur.

  Donc :
  - **réutiliser une entrée** : changer son `texture_index` dans `ui.bin` (données seules). Exemple : `superShield`
    → 104 ;
  - **une entrée de plus** (vrai 12e bonus, ou icône propre à un sous-type) : il faut le code. Une DLL doit
    envelopper `GetPerkInfo` et rendre son propre `C_UIPerkInfo` (24 o : index, 3 couleurs résolues, 2 textes).
    L'adresse de `GetPerkInfo` dans `Blur.exe` reste à trouver (§7). Les fonctions `Render` lisent `m_sTextureIndex`
    et `m_ColourFill` dans la structure rendue, donc une structure à nous suffit (**Hypothèse**).
- **Icône du menu LAN** : vectorielle (`perk_icons.ipf`). Le plugin du Railgun utilise `"perk_bolt"`. Pour une forme
  à nous, il faut écrire dans `perk_icons.ipf`. `bluripf.py` ne lit pas encore ce fichier : arrêt sur un type de
  forme ≠ 1 à 0x581. Plus simple : réutiliser une forme existante (`perk_shunt_x2` est libre).

### 6.3 Ce qu'il faut toucher

| Besoin | Fichiers | Exe / DLL |
|---|---|---|
| changer le dessin d'un bonus | `ui_common.bpr` (2 planches) | non |
| changer sa couleur / son nom | `ui.bin`, `.loc` | non |
| donner à un bonus une autre case existante | `ui.bin` (`texture_index`) | non |
| plus de cases | `ui_common.bpr` (planche agrandie) + `ui.bin` (`size.v` de 3 gadgets) | non (**Hypothèse**) |
| une icône pour un type ou un sous-type qui n'a pas d'entrée | — | **oui** (`GetPerkInfo`) |
| icône dans les menus | `perk_icons.ipf` (ou une forme existante) + plugin Lua | non |

---

## 7. Questions ouvertes

1. Le seuil « index ≥ 100 → planche support » et le calcul V sont-ils **identiques dans `Blur.exe`** ?
   - Preuve à chercher : les fonctions `UIPerks2::Render` / `UIPerks::Render` (une comparaison à `0x64`, puis
     `GetTextureParam(6)` / `(2)`), à repérer par la vtable de `UIPerks2` (son nom est dans l'exe).
   - Essai en jeu : mettre `shield.texture_index` à 104 dans la copie et voir l'étoile.
2. Adresse de `C_PerkDisplayParameters::GetPerkInfo` dans l'exe (pour une entrée de plus).
3. Le moteur accepte-t-il une planche agrandie (128 × 1024) sans souci de budget mémoire ? Essai en jeu.
4. Qui lit `colour_glow`, `loc_id_name`, `past_loc_id_name` ? Chercher dans les `.luac` (`InGameScoring`) et les
   messages de score.
5. Les formes `_x2` étaient-elles destinées au DoubleTap ? Il n'y a pas de document : seulement les indices du §5.
6. Format exact attendu pour la planche inversée (DXT5, alpha prémultiplié ou non) : comparer une case réencodée à
   l'original avant tout essai.
7. Le choix caméra extérieure → carrousel derrière la voiture / pare-chocs → carrousel du HUD est-il le même dans
   l'exe ? Un essai en jeu suffit (changer de caméra).
