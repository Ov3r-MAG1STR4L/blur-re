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
`extra_blindfire4`, `UI.HUD.PerksOnlyOneForAI` sont tous dans `Blur.exe` : **Confirmé**. Le seuil « 100 »,
`GetPerkInfo` et le calcul des V sont **confirmés dans l'exe** (§8).

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

1. ~~Seuil « 100 » et calcul V dans `Blur.exe`~~ : **confirmés** (§8). Reste l'essai en jeu : mettre
   `shield.texture_index` à 104 dans la copie et voir l'étoile.
2. ~~Adresse de `GetPerkInfo`~~ : `0xC55320` (§8).
3. Le moteur accepte-t-il une planche agrandie (128 × 1024) sans souci de budget mémoire ? Essai en jeu.
4. Qui lit `colour_glow`, `loc_id_name`, `past_loc_id_name` ? Chercher dans les `.luac` (`InGameScoring`) et les
   messages de score.
5. Les formes `_x2` étaient-elles destinées au DoubleTap ? Il n'y a pas de document : seulement les indices du §5.
6. Format exact attendu pour la planche inversée (DXT5, alpha prémultiplié ou non) : comparer une case réencodée à
   l'original avant tout essai.
7. Le choix caméra extérieure → carrousel derrière la voiture / pare-chocs → carrousel du HUD est-il le même dans
   l'exe ? Un essai en jeu suffit (changer de caméra).

---

## 8. Vérification dans `Blur.exe` (2026-11-17, désassemblage capstone, lecture seule)

Tout ce qui suit est **Confirmé** dans l'exécutable vendu (`Blur.exe`, 13,7 Mo, base 0x400000, `.text` fichier 0x400
→ VA 0x401000). Script reproductible, sans rustine : **`hud_exe_probe.py`**. Il retrouve et vérifie chaque
instruction citée, et échoue si l'exe diffère.

### 8.1 Disposition en mémoire (tables XT de l'exe)

Les fiches de champs XT sont dans `.data` : 20 o par champ = (pointeur du nom, type, 0, **décalage**, drapeaux).

| Fiche | VA | Taille en mémoire |
|---|---|---|
| `UIPerkInfo` | `0x1105CF8` | **0x48** (24 o sur le disque) |
| `UiPerkDisplayParameters` | `0x1105EE8` | **0x480** = 16 × 0x48 |
| `UIPerks2` | `0x1105E30` | 0x2C0 |
| `UIPerks` | `0x1105DB0` | 0x194 |

Champs de `UIPerkInfo` : `texture_index` +0, `colour_fill` +4, `colour_glow` +8, `colour_text` +0xC (pointeurs vers
les noms), `loc_id_name` +0x10, `past_loc_id_name` +0x14. Le constructeur `0xC5BBB0` ajoute trois
`C_UISpriteColours` résolues à **+0x18 (fill), +0x28 (glow), +0x38 (text)**.

Entrées de `UiPerkDisplayParameters` (lues à `0x1106068`) :

| Entrée | Décalage | Entrée | Décalage |
|---|---|---|---|
| `nitrous` | 0 | `repair` | 0x240 |
| `shock` | 0x48 | `shield` | 0x288 |
| `shunt` | 0x90 | `superShield` | 0x2D0 |
| `barge` | 0xD8 | `empty` | 0x318 |
| `bomb` | 0x120 | `extra_blindfire4` | 0x360 |
| `blindfire3` | 0x168 | `extra_blindfire3` | 0x3A8 |
| `blindfire2` | 0x1B0 | `extra_blindfire2` | 0x3F0 |
| `blindfire1` | 0x1F8 | `extra_blindfire1` | 0x438 |

La structure vit dans `C_UiXtConfig` à **+0x70**. L'instance est le pointeur global **`[0x124291C]`**.

### 8.2 `C_PerkDisplayParameters::GetPerkInfo` = `0xC55320` (fonction propre, non inlinée)

Convention : `thiscall`. `ecx` = `&PerkDisplayParameters`, puis `(E_PICKUP_TYPE type, S32 amount, bool
extraBoltMod)`, `ret 0xC`. Elle rend un `C_UIPerkInfo*` ou `NULL`.

```
0xC55320  mov eax, ecx
0xC55322  mov ecx, dword ptr [esp + 4]      ; type
0xC55326  inc ecx                           ; -1 (NONE) -> 0
0xC55327  cmp ecx, 0xb
0xC5532A  ja  0xC553DB                      ; -> NULL
0xC55330  jmp dword ptr [ecx*4 + 0xC553E0]  ; table de 12 entrées
```

| `type` | Cible | Résultat |
|---|---|---|
| −1 NONE | `0xC553D3` | `add eax, 0x318` → `empty` |
| 0 Nitrous | `0xC553DD` | `ret 0xc`, eax = this → `nitrous` |
| 1 Shock | `0xC55337` | +0x48 `shock` |
| 2 Shunt | `0xC5533D` | +0x90 `shunt` |
| 3 Blindfire | `0xC55355` | branche du nombre de tirs (ci-dessous) |
| 4 Barge | `0xC55345` | +0xD8 |
| 5 Bomb | `0xC5534D` | +0x120 |
| 6 Repair | `0xC553BB` | +0x240 |
| 7 Shield | `0xC553C3` | +0x288 |
| **8 Fan** | `0xC553DB` | **`xor eax, eax` → NULL** |
| **9 Stopwatch** | `0xC553DB` | **NULL** |
| 10 SuperShield | `0xC553CB` | **+0x2D0 `superShield`** |

Branche du Bolt (`0xC55355`) :

```
cmp byte ptr [esp+0xc], 0 ; mov ecx, [esp+8]      ; extraBoltMod ? amount
je 0xC55394
  amount 4 -> +0x360, 3 -> +0x3A8, 2 -> +0x3F0, 1 -> +0x438, autre -> +0x360   (extra_blindfire4..1)
0xC55394:
  amount 3 -> +0x168, 2 -> +0x1B0, 1 -> +0x1F8, autre -> +0x168                (blindfire3..1)
```

Identique à la source, valeur par défaut comprise.

**Appelants** :

| Adresse | Fonction | Arguments |
|---|---|---|
| `0xC554CF` | `UIPerks2::GetPerkInfo` (`0xC554C0`) : `mov eax,[0x124291C]` ; NULL si pas de config ; `lea ecx,[eax+0x70]` ; `jmp 0xC55320`. Appelée en `0xC59293` (case pleine) et `0xC592A2` (case vide : `push 0, 0, -1`) | — |
| `0xC57F9B` | `UIPerks::Render` | `(type, mNumShots, extraBoltMod)` lus dans `mPickupStore[mPickupStoreIndex]` (éléments de 24 o, `+0` type, `+8` tirs) |
| `0xC60971` | `UITargeting::ProcessHitByPerk` | `(type, 0, 0)`. **Le résultat est jeté aussitôt** (`ret 4`) : c'est le `return;` de la source, le texte « touché par… » est bien coupé dans l'exe |

Une **copie inlinée et simplifiée** existe aussi dans `UIRaceLine` (`0xC56350`, appelée en `0xC5A9EE` et `0xC5BA0C`).
Elle a sa propre table (`0xC56490`, type + 1), **sans le nombre de tirs** : le Bolt donne toujours `blindfire3`, et
Fan / Stopwatch donnent NULL. Elle ne sert qu'à la couleur des points de la barre de course.

### 8.3 Seuil 100 et choix de la planche

**`UIPerks::Render`** = `0xC57E90` (entrée 10 de la vtable `0xEE99F0`, fiche en `0xEE9A18`) :

```
0xC57FA4  mov ebp, [0x124291C] ; add ebp, 0x388 ; mov byte [esp+0x13], 1   ; réserve vide -> empty (0x70+0x318)
0xC57FCE  mov ebx, dword ptr [ebp]          ; texture_index
0xC57FD1  cmp ebx, 0x64
0xC57FD6  jge 0xC57FDC
0xC57FD8  push 0 ; jmp 0xC57FE1            ; < 100 -> GetTextureParam(0) = perk_sheet
0xC57FDC  sub ebx, 0x64 ; push 2            ; >= 100 -> index-100, GetTextureParam(2) = perk_sheet_support
0xC57FE1  call 0x74B270                     ; GetTextureParam
...
0xC5809D  push 1 ; call 0x74B270            ; case vide -> GetTextureParam(1) = hud_main
0xC580C4  movss xmm0,[edi+0x10] ; cvtsi2ss xmm1, ebx ; mulss xmm1, xmm0 ; addss xmm1,[edi+8]
                                            ; V = index * size.v + pos.v ; U = [edi+4], largeur [edi+0xC], texture [edi+0x14]
```

**`UIPerks2::Render`** = `0xC58130` (entrée 10 de la vtable `0xEEAFF0`) :

```
0xC592B6  mov eax, dword ptr [edi]          ; texture_index
0xC592B8  cmp eax, 0x64
0xC592C1  jge 0xC592CE
0xC592C3  push 0 ; call 0x74B270 ; push 1   ; perk_sheet (case choisie) / perk_sheet_inverted (autres)
0xC592CE  sub dword ptr [esp+0x3c], 0x64
0xC592D3  push 6 ; call 0x74B270 ; push 7   ; perk_sheet_support / perk_sheet_support_inverted
0xC592DC  call 0x74B270
0xC59896  movss xmm0,[edi+0x10] ; cvtsi2ss xmm1,[esp+0x3c] ; ... ; addss xmm1,[edi+8]   ; même calcul de V
```

**`GetTextureParam`** = `0x74B270` (thiscall, `ret 4`) :

- tableau du gadget `[this+0x60]`, nombre d'éléments `[this+0x64]`, éléments de 24 o :

| + | Champ |
|---|---|
| 0 | nom |
| 4 | pos.u |
| 8 | pos.v |
| 0xC | size.u |
| 0x10 | size.v |
| 0x14 | texture |

- **bornes vérifiées** : `test eax,eax ; jl` / `cmp eax,[esi+0x64] ; jge`. Hors bornes, la fonction rend un paramètre
  statique par défaut : texture `"null"`, pos 0, size 1. Pas de plantage.

### 8.4 Source contre exécutable

| Mécanisme | Source fuitée | `Blur.exe` | Conclusion |
|---|---|---|---|
| Seuil 100 | `if (sTexIndex < 100)` dans les deux `Render` | `cmp ebx, 0x64` (`0xC57FD1`), `cmp eax, 0x64` (`0xC592B8`) | **Confirmé**, identique |
| Planche normale | `GetTextureParam(0)` (+ `(1)` inversée dans `UIPerks2`) | `push 0` / `push 1` | **Confirmé** |
| Planche support | `index -= 100` ; `GetTextureParam(2)` / `(6)` + `(7)` | `sub ebx, 0x64 ; push 2` / `sub [esp+0x3c], 0x64 ; push 6 ; push 7` | **Confirmé** |
| Calcul de V | `pos.v + size.v * index` | `cvtsi2ss` / `mulss [+0x10]` / `addss [+8]` | **Confirmé** |
| `GetPerkInfo` | `C_PerkDisplayParameters::GetPerkInfo`, `switch` | `0xC55320`, table `0xC553E0`, `ret 0xC` ; + wrapper `0xC554C0` ; + copie simplifiée inlinée dans `UIRaceLine` (`0xC56350`) | **Confirmé** (la copie inlinée n'est pas dans la source sous cette forme : c'est l'optimiseur qui a intégré la fonction statique de `UIRaceLine`) |
| Icône du Bolt | 3 / 2 / 1 tirs, mod 4-1, défaut 3 (ou 4) | mêmes comparaisons, mêmes défauts | **Confirmé** |
| SuperShield | `m_PerkInfoSuperShield` | type 10 → +0x2D0 | **Confirmé** |
| Fan / Stopwatch | `default: return NULL` | table → `0xC553DB` `xor eax, eax` | **Confirmé** |
| Texte « touché par… » | `return;` avant l'affichage | résultat de `GetPerkInfo` jeté (`0xC60976 ret 4`) | **Confirmé** |
| Choix caméra extérieure / pare-chocs | `UIPerks2.cpp:520-527` | non désassemblé | **à vérifier** (essai en jeu) |

Aucune différence trouvée entre la source et l'exe pour ces mécanismes.

### 8.5 Jusqu'où le HUD peut s'étendre (d'après l'exe)

| Question | Réponse | Preuve |
|---|---|---|
| Changer le seuil ? | Seulement par rustine : deux immédiats `0x64` (`0xC57FD1` + `0xC57FDC`, `0xC592B8` + `0xC592CE`). **Inutile** : le seuil ne limite rien, il choisit juste la planche | §8.3 |
| Plus d'index ? | **Oui, par les données.** Rien ne borne l'index : V = index × `size.v` + `pos.v`, et `texture_address = Wrap` dans `ui.bin`. Avec une planche support de 128 × 1024 et `size.v` = 0,09375 (3 gadgets), les cases 100 à 109 existent | §8.3, §6.2 |
| Taille des planches codée en dur ? | **Non.** Ni dimension ni nom de texture dans le code : tout vient de `UITextureParam` (`ui.bin`) | §8.3 |
| Une 3e planche ? | **Pas par les données.** Le code ne connaît que les paramètres 0/1 et 6/7 (`UIPerks2`), 0/2 (`UIPerks`), et seulement deux branches (< 100, ≥ 100). Ajouter des paramètres à un gadget est possible (`GetTextureParam` vérifie ses bornes), mais rien ne les lirait sans rustine des deux `Render` | §8.3 |
| Étendre `GetPerkInfo` par une DLL ? | **Oui, c'est le bon point d'accroche.** Fonction unique, `thiscall`, 3 arguments, `ret 0xC`, 3 appelants (§8.2), rend un pointeur. Une enveloppe peut rendre son propre bloc de **0x48 o** (index à +0 ; `C_UISpriteColours` déjà résolues à +0x18 / +0x28 / +0x38). Attention : la copie inlinée de `UIRaceLine` (`0xC56350`) n'y passe pas (seulement la couleur de la barre de course) | §8.2 |
| Plus de 16 entrées ? | Pas dans `ui.bin` : la structure est fixe (0x480, 16 champs nommés). Une DLL peut garder ses propres blocs de 0x48 et les rendre depuis l'enveloppe de `GetPerkInfo`, sans limite | §8.1 |
| Remplacer une icône est-il plus sûr ? | **Oui.** Aucun code touché, mêmes chemins qu'en jeu normal | — |
| Le Railgun peut-il garder l'entrée SuperShield ? | **Oui, sans rien de plus.** Le joueur garde un type 10 en réserve : `GetPerkInfo` → +0x2D0 → index 104 → case 4 de `perk_sheet_support`. Les IA reçoivent un Bolt : leur icône `ai_perks` est celle du Bolt | §8.2 + `POWERUPS.md` §14 |

### 8.6 Recommandations

- **A. Remplacer une icône existante** : redessiner la case dans les deux planches de `ui_common.bpr`, à la même
  taille, au même format et avec les mêmes mips, remplacement en place (§6.1). Aucune rustine. C'est le plus sûr.
- **B. Réutiliser un index pour un bonus maison** : laisser le bonus porter un type existant (méthode du Railgun) et
  changer seulement le `texture_index` / les couleurs de cette entrée dans `ui.bin`. Données seules.
- **C. Une vraie nouvelle entrée** : une DLL qui enveloppe `GetPerkInfo` (`0xC55320`), en vérifiant les octets
  d'origine comme `railgun.dll`. Elle rend un bloc de 0x48 o à elle quand le contexte l'exige : par exemple le bonus
  maison repéré dans `mPickupStore`, ou un sous-type. L'index de ce bloc pointe vers une case ≥ 100 d'une planche
  support agrandie.
- **D. Une planche de plus / plus de 16 entrées** :
  - plus de 16 entrées = blocs de la DLL (C), sans toucher à `ui.bin` ;
  - plus de cases = agrandir `perk_sheet_support` (données) ;
  - une 3e planche n'est utile que si 100 + n cases ne suffisent pas. Elle demanderait une rustine des deux `Render`
    (troisième branche, nouveaux numéros de paramètre) : à éviter.

**Prochain essai conseillé, sur une copie séparée** (`make_test_copy.ps1`, jamais le jeu installé) :

1. dans `ui.bin` de la copie, passer `shield.texture_index` de 7 à **104** (modification d'un nombre, `blurxt.py
   --set`), sans toucher à `ui_common.bpr` ;
2. course perso, ramasser un Bouclier ;
3. on doit voir l'étoile dans le carrousel, en caméra extérieure **et** en caméra pare-chocs, ainsi qu'au-dessus d'une
   IA qui tient un Bouclier ;
4. cela valide en jeu le seuil, le calcul de V et la planche support.

Pour vérifier aussi les planches agrandies : refaire l'essai avec `perk_sheet_support` en 128 × 1024 et `size.v` à
0,09375, et l'index **105** sur une case dessinée exprès.

Essai préparé (copie `Blur_test_hud`, `shield.texture_index` → 104) : voir **`ESSAI_HUD_SHIELD104.md`**. Pas encore joué.

Résultat partiel de l'essai : étoile en caméra pare-chocs et au-dessus des IA, hexagone signalé en caméra extérieure. Diagnostic (même code et même configuration pour les deux carrousels ; l'hexagone viendrait des Boucliers posés sur la piste, `shieldpickup.model` / `icon_shield_01`) : **`ESSAI_HUD_SHIELD104_DIAGNOSTIC.md`**.

**Essai en jeu réussi (2026-11-17, captures)** : `shield.texture_index` = 104 affiche l'étoile dans le carrousel extérieur, dans le carrousel pare-chocs et au-dessus des IA. Le seuil 100, la planche `perk_sheet_support` (normale et inversée) et le calcul de V sont **confirmés en jeu**. Les bonus posés sur la piste gardent leur propre icône (textures intégrées à `models\perks\pickups\<type>pickup.model`, indépendantes de `ui.bin`).

**Planche support agrandie (cases 100-109)** : faisabilité démontrée (données seules : planches en 128 × 1024 + `size.v` 0,09375 dans 3 gadgets) et prototype préparé dans `Blur_test_hud_atlas` (Bouclier → 105). Voir **`ESSAI_HUD_SUPPORT_ATLAS.md`**. Pas encore joué.

**Essai en jeu réussi (2026-11-17, captures)** : la case **105** de la planche support agrandie s'affiche dans le carrousel extérieur, le carrousel pare-chocs et au-dessus des IA, en version normale et inversée. **Ajouter des icônes au HUD est possible par les données seules.** Les cases 106-109 restent à essayer. Une icône du HUD se dessine en niveaux de gris : sa couleur vient de `colour_fill`. Voir `ESSAI_HUD_SUPPORT_ATLAS.md` §9.

Étape 2 (cases 106-109, une par une, Bouclier → 106 / 107 / 108 / 109) préparée dans `Blur_test_hud_atlas`, test 106 installé ; pas encore jouée. Voir `ESSAI_HUD_SUPPORT_ATLAS.md` §9.

**Étape 2 réussie (2026-11-17)** : les cases 106 à 109 s'affichent chacune avec leur forme (une capture par index, le reste rapporté OK par l'utilisateur). La planche support à 10 cases (100-109) fonctionne : **on peut ajouter des icônes au HUD sans toucher à `Blur.exe`**.

**Bouclier posé sur la piste** : modèle 3D `shieldpickup.model` avec 2 textures intégrées (`icon_shield_01`, `_inverse`), indépendantes de `ui.bin`. Essai « triangle 6 » préparé dans `Blur_test_hud_pickup` : voir **`ESSAI_HUD_SHIELD_PICKUP.md`**. Pas encore joué.
