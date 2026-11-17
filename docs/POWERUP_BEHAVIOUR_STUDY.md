# Étude du comportement des bonus d'origine de Blur

- **v1** (2026-11-17) : première étude, lecture seule.
- **v2** (2026-11-17) : consolidation après les essais en jeu T1 à T8, les modifications de carrière et multijoueur, et
  les sources communautaires.

Tout est en **lecture seule** : aucun fichier du jeu, aucune copie, aucun exécutable modifiés. Ce document complète
**`POWERUPS.md`** (référence technique) et **`POWERUPS_DONNEES.md`** (toutes les valeurs) sans les recopier.

## 0. Nouveautés de la v2 (résumé)

1. **Les 8 modifications de carrière sont tracées dans la source et les données.** Ce sont des capacités
   `Boss_*`. Chaque boss la porte via sa voiture (`AmaxVehicle.BossAbilitySlot`, `amax.bin`), et le joueur via une
   seule capacité équipée (`mSpEquippedAbility`). Valeurs exactes en §4.
2. **« Armor Plating » (Talon) s'appelle `BossRepairBonus` dans le code.** Elle réduit de 50 les dégâts de la Barge, du
   Shunt et de la Mine. Elle ne répare rien.
3. **`Shielding Efficiency` explique l'exception du bouclier en multijoueur** :
   - la durée est multipliée par 1,8 et la santé passe de 50 à 150 (`multiplayer.bin`) ;
   - un dôme de Shock fait 100 de dégâts : avec le mod, le bouclier survit à un dôme et casse au deuxième.

   **Mais AMAX annonce avoir réduit ce mod** (§5.2) : la valeur jouée en ligne aujourd'hui est inconnue.
4. **Le Scatter Shot répond à une question ouverte de la v1** : c'est le seul créateur des sous-types `MOD` et
   `SUB_MOD` du Bolt. Il tire 3 Bolts à −2°, 0° et +2° et vide toute la pile de Bolts d'un coup.
5. **Le Nitro Rift est un Nitro de type NITROUS.** Il traverse donc les boucliers, comme le Nitro arrière (T1).
6. **L'explosion d'une Mine n'est qu'un effet visuel** (`Explode()`) : aucune zone de dégâts. Cela explique pourquoi
   elle ne détruit pas une Mine voisine (observé en jeu).
7. **Contradiction ouverte** : le Shock détruit une Mine en jeu, mais aucun code de la source ne le fait (§7).
8. **Correction de `POWERUPS.md` §11** : la masse de 10 000 de `C_PickupDoubleShield` ne s'applique jamais, parce que
   `CreatePickup` ne crée pas cette classe. La poussée du Titanium Shield vient d'ailleurs (§4.2).
9. **Pas de nettoyage par joueur** : une Mine dont le poseur part vit ses 60 s (cohérent avec T8).

## 1. Niveaux de preuve

| Étiquette | Sens |
|---|---|
| **CONFIRMÉ — GAME** | observé en jeu par le joueur |
| **CONFIRMÉ — SOURCE** | démontré par le code source fuité (juin 2010). Ce **n'est pas une preuve absolue du binaire final** : des retouches `[Blur2PC]` sont possibles |
| **CONFIRMÉ — DATA** | lu dans les fichiers de données du jeu (`pickups.bin`, `multiplayer.bin`, `amax.bin`, `rldatabase.bin`) |
| **CONFIRMÉ — COMMUNITY** | décrit par une source communautaire (§11). Ce n'est pas une preuve du fonctionnement |
| **PROBABLE** | explication cohérente, non démontrée |
| **À VÉRIFIER** | contradiction ou documentation insuffisante |

Quelques points ont aussi été vérifiés dans `Blur.exe` (v1 et `POWERUPS_HUD.md`). Ils sont notés **EXE**.

Chemins : `src/` = `blur_source\BlurRebuilt\code\amax\game\`.

## 2. Observations en jeu T1 à T8 (CONFIRMÉ — GAME)

| Test | Observation du joueur | Explication trouvée | Accord |
|---|---|---|---|
| T1 | Un Nitro tiré vers l'arrière traverse un Shield | `AttemptHitByPickup` : `if (mShieldTime > 0 && type != NITROUS)` → le Nitro n'est jamais bloqué (SOURCE) | oui |
| T2 | Un seul Shock détruit un Shield | dôme : 100 de dégâts contre 50 de santé du bouclier (DATA) ; seule la Shock entame le bouclier (SOURCE) | oui |
| T3 | Deux Bolts pour détruire une Mine | dégâts croisés : Bolt 50 contre Mine santé 100 (DATA + SOURCE, `PickupProjectileBase.cpp:503`) | oui |
| T4 | Un Shield activé après le tir d'un Bolt bloque quand même ce Bolt | le bouclier est testé **au moment de l'impact** (`mShieldTime`) | oui |
| T5 | La Barge détruit Mines, Shunts et Bolts dans sa portée | boucle de l'ellipse : Shunt → `CollideWithPickup`, Bolt et Mine → `KillPickup` (`PickupBarge.cpp:170-206`) | oui |
| T6 | Un Shunt ou une Mine interrompent un Nitro actif | `DisableActiveNitrous` sur coup de Shunt et de Mine (`VLC_Pickups.cpp` ~1690, ~1935) | oui |
| T7 | Repair utilisable à tout moment, même avec d'autres effets actifs | la réparation passe par `RegisterHitByPickup` direct, sans test de bouclier ni de réaction (SOURCE) | oui |
| T8 | Une Mine reste 60 s, même si son poseur est détruit, éliminé ou déconnecté | `Lifespan` 60 (DATA) décompté par la Mine elle-même (`PickupBomb.cpp:181`) ; aucun nettoyage par joueur trouvé (§8) | oui |

Autres observations du joueur, intégrées telles quelles :

| Sujet | Observation (CONFIRMÉ — GAME) | Lecture technique |
|---|---|---|
| Shield | protège de la Barge, de la Mine et du Shunt | cohérent (bloqué par `AttemptHitByPickup`) |
| Shield | « Fan » pousse un véhicule protégé | **À VÉRIFIER** : aucun bonus Fan ne pousse dans le code (§3). Piste : effet de type NITROUS (Nitro arrière ou Nitro Rift), qui traverse le bouclier |
| Shield | exception en multijoueur face au Shock | **PROBABLE** : `Shielding Efficiency` (§5.2) |
| Repair | utilisable pendant d'autres effets | cohérent |
| Repair | Repair juste avant un Shock : souvent un mauvais choix, sauf si la santé est presque vide | aucun lien de code trouvé entre Repair et Shock → **INCONNU**. Lecture probable : la réparation est perdue si le Shock arrive juste après. Ce n'est pas une interaction de code |
| Barge contre Nitro | la Barge l'emporte en général ; le résultat dépend du moment ; on observe une perte de vitesse plutôt qu'une annulation | la Barge n'appelle pas `DisableActiveNitrous`. Sa réaction `ROLL` / `JINK` freine la voiture, mais le Nitro continue (SOURCE) → cohérent |
| Mine | une explosion de Mine ne détruit pas une autre Mine | `Explode()` = effet visuel seulement (SOURCE) → cohérent |
| Mine | le Shock détruit une Mine dans sa portée | **CONTRADICTION** avec la source (§7) |
| Mine | le Shunt peut détruire une Mine | dégâts croisés 100 contre 100 → les deux meurent (SOURCE) |
| Bolt | ne touche pas plusieurs véhicules | le projectile meurt sur la première voiture touchée (SOURCE) |
| Bolt | ne change pas de cible | trajectoire droite, pas de guidage (SOURCE) |
| Bolt | détruit par un mur | `CollideWithEnvironment`, sauf rebond sur un angle rasant (`CheckRebound`, §6.4) |
| Bolt | aucune collision Bolt contre Bolt observée | voir §6.4 (rare, **PROBABLE**) |
| Shunt | suit une trajectoire vers sa cible, peut toucher un mur, perdre sa cible à une bifurcation, détruire une Mine | guidage par les tracés `.aid` (§6.5) |

## 3. Rappel : Fan et Stopwatch ne sont pas des armes (v1, inchangé)

Le **Fan** (type 8) et le **Stopwatch** (type 9) sont des **pastilles de mode de jeu** : fans des défis, temps des
points de contrôle. Preuves :

- `HitPickUp` les refuse (SOURCE) ;
- `GetPerkInfo` rend NULL (EXE) ;
- ils sont exclus du tirage (EXE) ;
- seul le joueur 0 peut les ramasser.

Aucun code ne les fait pousser, bloquer ou toucher quoi que ce soit.

L'observation « Fan pousse un véhicule protégé » (§2) désigne donc probablement autre chose. À préciser par le joueur
(test N9).

## 4. Les huit modifications de carrière (boss)

### 4.1 Mécanisme commun (CONFIRMÉ — SOURCE + DATA)

- **Ce sont des capacités multijoueur `Boss_*`.** Elles utilisent le même système que les mods multijoueur
  (`C_MultiplayerAbilities`, `UI::E_MultiplayerVehicleAbilities_Boss_*`, `library/Ui/game/Multiplayer/MultiplayerDefines.h:386-393`).
  Valeurs : `MultiplayerAbility` dans `multiplayer.bin`, emplacement `Slot4`.
- **Boss IA** : chaque mod est une propriété de la **voiture** du boss (`AmaxVehicle.BossAbilitySlot`, `amax.bin`).
  Il est activé pour toute voiture IA qui conduit ce modèle (`LevelState.cpp:864-867`), donc **en permanence**, quel
  que soit son usage des bonus.
- **Joueur** :
  - **une seule** capacité équipée (`GameProfile.mSpEquippedAbility`, un seul champ) ;
  - active seulement dans les épreuves solo de type **course** ou **boss** (`kSP_RaceEvent`, `kSP_BossEvent`), pas
    dans les épreuves Fan, Checkpoint ou Destruction (`LevelState.cpp:838-852`) ;
  - aussi dans un « Friend Demand » (défi d'ami) qui impose un mod de boss.
- **Débloqué en battant le boss** : CONFIRMÉ — COMMUNITY (wiki Career). La récompense est gérée dans `SP_Rewards.cpp`
  (non lu en détail).
- **Icône HUD** : l'icône d'activation d'un mod de boss n'apparaît que pour une voiture qui a une vue à l'écran
  (`canUseBossMod`, `LevelStateMultiplayerAbilities.cpp:118`). L'effet de jeu, lui, ne dépend pas de cette condition.

| Boss | Voiture (`amax.bin`) | Nom affiché | Nom interne |
|---|---|---|---|
| Shannon | `Renault_MeganeSportR26_Stock_Shannon` | Overbolt | `BossAdditionalBlindfireShots` |
| Khan | `Foose_Stallion_Stock_Khan` | Titanium Shield | `BossDoubleShield` |
| Rhymer | `Chevrolet_CamaroSS_Stock_Rymer` | Fan Nitro | `BossFansNitroGift` |
| Drayke | `Hummer_H2_OffRoad_Drayke` | Super Shunt | `BossShuntDamage` |
| Natalya | `BMW_1SeriesTii_Race_Natalya` | Quad Shock | `BossAdditionalShockDomes` |
| Talon | `Corvette_ZR1_Stock_Talon` | Armor Plating | **`BossRepairBonus`** |
| Ayumi et Harumi | `Nissan_SkylineR34ZTune_Stock_Ayumi` / `_Harumi` | Scatter Shot | `BossShotgunBlindfire` |
| Carver | `Dodge_ViperGTSR_Stock_Carver` | Nitro Rift | `BossNitroRift` |

Correspondance boss ↔ capacité : **DATA**. Noms affichés : **COMMUNITY**, cohérents avec la DATA pour les 8 boss.

Unité des dégâts : `GetAFractionOfAHealthPipInDamagePoints(v)` = `v × HealthIncrement`. `HealthIncrement` vaut 100
(`DamageParameters`, `rldatabase.bin`). Donc **0,5 = 50 points de dégâts** (DATA + SOURCE).

### 4.2 Fiches

| Mod | Ce que fait le code | Valeur (DATA) | Type |
|---|---|---|---|
| **Overbolt** | `GetNumShotsAwarded(BLINDFIRE)` = 3 + valeur → **4 Bolts** par bonus ramassé | `AbilityValue` 1 | change le nombre de tirs |
| **Scatter Shot** | voir ci-dessous | angle 2°, 1 tir de chaque côté (`Perks.BlindfireShotgun.*`, valeurs de débogage par défaut) | change la forme du tir |
| **Quad Shock** | `numShocksToFire += valeur` (`ShockManager.cpp:175-184`) → **4 dômes** | 1 | ajoute un objet |
| **Super Shunt** | dégâts du Shunt **+50** (100 → 150) ; son de Shunt propre | 0,5 pip | change les dégâts |
| **Armor Plating** | dégâts subis **−50** contre Barge, Shunt et Mine (`VLC_Damage.cpp:1328-1336`) ; pas contre Bolt ni Shock | 0,5 pip | défense du véhicule |
| **Titanium Shield** | voir ci-dessous | niveau DoubleTap : 12 s, santé 50 | change le bouclier |
| **Fan Nitro** | voir ci-dessous | 500 | donne un bonus |
| **Nitro Rift** | voir ci-dessous | `RiftTime` 2,5 s, `RiftRadius` 30 m, `RiftAngleRange` 0,1 | ajoute un effet |

**Scatter Shot** :

- le Bolt passe en sous-type `MOD`, ou `MOD_REVERSED` vers l'arrière (`VLC_Pickups.cpp:1501-1514`) ;
- `C_PickupBlindfireShotgun` crée **3 Bolts `SUB_MOD` en même temps**, à −2°, 0° et +2° (`Mods/PickupBlindfireShotgun.cpp`) ;
- la pile de Bolts est **entièrement consommée** en un tir (`hasShotgun`, `VLC_Pickups.cpp:1076-1081`) ;
- les Bolts créés sont des Bolts normaux : mêmes dégâts, même santé.

**Titanium Shield** :

- le Bouclier passe en sous-type DoubleTap (`VLC_Pickups.cpp:1422-1426`) et lit les réglages DoubleTap : **12 s au
  lieu de 6**, **santé 50, inchangée**. Un Shock le casse donc toujours (PROBABLE, dérivé du code) ;
- pendant sa durée, la voiture compte comme **classe de poids « Ultra »** dans les chocs entre voitures
  (`RaceLogicLayer.cpp:1805-1809`) ;
- une voiture **sans** bouclier renforcé qu'elle percute reçoit un écart scripté `JINK_SHIELD_LEFT/RIGHT`, avec un
  délai de rechargement (`VLC_Pickups.cpp:2281-2330`). Pas de dégâts : seul le SuperShield en inflige ;
- correction de `POWERUPS.md` §11 : la masse de 10 000 appartient à `C_PickupDoubleShield`, que `CreatePickup` ne crée
  jamais. Le Bouclier crée toujours `C_PickupShield` (`PickupsManager.cpp:502-507`).

**Fan Nitro** : un Nitro est offert chaque fois que le score de fans affiché (`mFinalScoreForUI`) dépasse
500 × (nombre déjà offerts + 1). Le Nitro est donné par `C_GrantPickupMsg` (`VLC_Abilities.cpp:309-323`). Ce qui se
passe si la réserve est pleine n'est pas connu → **INCONNU**.

**Nitro Rift** :

- le Nitro normal **plus** un objet `C_PickupDoubleNitrous` (`VLC_Pickups.cpp:1443-1450`) ;
- pendant 2,5 s, chaque voiture à moins de 30 m dont l'angle relatif dépasse 0,1 (devant, **PROBABLE**) reçoit un coup
  **mineur de type NITROUS** (`Double/PickupDoubleNitrous.cpp`) ;
- ce coup **traverse un bouclier**, comme le Nitro arrière ;
- les forces `RiftMinForce` / `RiftMaxForce` (500 à 1 500) existent dans les données, mais ne sont pas lues par cette
  classe : **INCONNU**.

Effets visuels et sonores : chaque mod déclenche un état « actif » (`SetAbilityFiring`) lu par le HUD et le son. Le
Super Shunt et le Nitro Rift choisissent un son de sous-type à part (`PickupSubSystem.cpp:580`, `862-870`). L'Armor
Plating réutilise le son du Titanium Armour multijoueur (`PickupSubSystem.cpp:762-763`). Les modèles du Nitro Rift
sont `Nitro_Carver.model` et `Rift2.model` (DATA).

### 4.3 Show Down (finale à plusieurs boss)

| Point | Statut |
|---|---|
| Les boss y conduisent d'autres voitures, de classe A | CONFIRMÉ — GAME (observation) |
| Ils n'ont plus leur mod | PROBABLE : le mod est lié au **modèle de voiture**. Seuls les 9 modèles `*_Stock_<boss>` / `*_Race_Natalya` / `*_OffRoad_Drayke` ont un `BossAbilitySlot` (DATA) ; `Opel_AstraExtreme_Stock_Shannon` n'en a pas. Les voitures exactes de la finale ne sont pas vérifiées |
| Leurs préférences de bonus restent identiques | **INCONNU** : les préférences viennent soit de l'épreuve (`PerkAI` du CSV de difficulté), soit du personnage (`rbChar->preferredPickups`) (`LevelState.cpp:870-897`). Les fichiers de personnages n'ont pas été trouvés dans les `.bin` extraits |

## 5. Modifications multijoueur (système à part)

### 5.1 Ce qui les sépare des mods de carrière (CONFIRMÉ — SOURCE)

- Les mods de carrière et les mods multijoueur passent par le **même** système d'exécution (`C_MultiplayerAbilities`).
- **Multijoueur** :
  - 3 emplacements (`Slot1` à `Slot3`) remplis par le loadout du joueur (`FillOutLevelStateCar`) ;
  - en LAN (System Link), des loadouts par défaut séparés (`m_SystemLinkLoadOuts`).
- **Carrière** : `Slot4`, un seul mod (§4.1).

### 5.2 Shielding Efficiency et le bouclier

| Point | Valeur | Statut |
|---|---|---|
| Durée du bouclier × `AbilityValue` | × **1,8** (6 s → 10,8 s) | DATA + SOURCE (`PickupShield.cpp:181-185`) |
| Santé du bouclier + `shielding_efficiency_extra_health` | +100 → **150** | DATA + SOURCE |
| Dégâts d'un dôme de Shock | 100 | DATA |
| Résultat calculé | 1er dôme : bloqué, santé 50 ; 2e dôme : bloqué, santé −50, le bouclier se coupe à l'image suivante ; 3e dôme : touche | PROBABLE (calcul) |
| Description communautaire | « actif plus longtemps et peut encaisser un coup de Shock en plus » | COMMUNITY (wiki Multiplayer, PSNProfiles) |
| **AMAX** (serveur utilisé par le joueur) | annonce du 2025-01-04 : bonus de durée **réduit de moitié**, santé en plus **réduite** | COMMUNITY (amax-emu.com/news) ; nouvelles valeurs inconnues |

Conclusion : **PROBABLE**. `Shielding Efficiency` est la meilleure explication de l'exception en multijoueur.
Restent à vérifier (**À VÉRIFIER**) :

- si l'adversaire avait ce mod lors de l'observation ;
- les valeurs AMAX actuelles : si le bonus de santé est inférieur à 50, le bouclier ne survit plus à un dôme.

Les 3 dômes sont des coups **séparés**. Chacun passe par `AttemptHitByPickup` et teste le bouclier à son tour
(SOURCE).

### 5.3 Autres mods qui touchent aux bonus (valeurs d'origine, DATA + SOURCE)

| Mod (nom interne) | Effet sur les bonus | Valeurs d'origine |
|---|---|---|
| `TitaniumArmour` (Titanium Armor) | −50 dégâts contre Barge, Mine et Shunt (pas Bolt ni Shock) ; atténue l'éclat des effets (`g_debugTitaniumArmourIntensity`) | 0,5 pip |
| `IronFist` | dégâts en plus par type | Shunt +50 ; autres types +0 |
| `SplashDamage` | ellipse de la Barge agrandie | × 1,2 |
| `SafetyNet` | coups absorbés par le bouclier → réparation | Mine, Shunt, Barge : oui ; Shock, Bolt : non |
| `ShieldedBoosters` | dégâts absorbés par type | Barge 100, Bolt 50, Mine 100, Shock 150, Shunt 100 |
| `Mastermine` | une Mine amorcée par un porteur se change en mini-mines (`MOD`) | amorce 0,3 s |
| `Scrambler` | bloque la réserve de la victime touchée par un Bolt, une Mine ou un Shunt **arrière**, ou par un Nitro Rift | 5 s |
| `LastGasp` | une fois détruit, tire un bonus (`MOD`) | type 4 = Barge |

Correspondance avec les noms affichés (Adaptive Shielding, Magnetic Field) : **INCONNU**. Le wiki les cite, mais il n'y
a pas de lien sûr avec les noms internes. AMAX dit avoir changé « Adaptive Shielding », qui absorbe désormais Shock et
Bolt : c'est peut-être `ShieldedBoosters` ou `SafetyNet` (**PROBABLE**, non démontré).

## 6. Interactions entre projectiles et objets

### 6.1 Règle générale (SOURCE)

Quand un projectile rencontre une Mine ou un autre projectile (`PickupProjectileBase.cpp:503-560`) :

- chacun inflige à l'autre ses dégâts du niveau Normal et perd de la santé ;
- un objet dont la santé tombe à 0 meurt ;
- le plus récent des deux est crédité de la destruction.

Santé / dégâts (DATA) :

| Objet | Santé | Dégâts |
|---|---|---|
| Bolt | 50 | 50 |
| Shunt | 100 | 100 |
| Mine posée | 100 | 100 |
| Mine lancée vers l'avant | 100 | 100 |
| Mini-mine | 25 | 50 |

### 6.2 Mine et Mine : trois situations

| Situation | Mécanisme | Résultat | Statut |
|---|---|---|---|
| 1. Une Mine **explose** près d'une autre | `Explode()` = effet visuel seulement, pas de zone de dégâts ; deux mines au contact : `RaceLogicLayer.cpp:2653` traite le contact sans effet | aucune | SOURCE + GAME |
| 2. Une Mine **lancée vers l'avant** touche une Mine | classe projectile (`PickupBombReverse`) → règle §6.1 : 100 contre 100 | les deux meurent | SOURCE ; **non testé en jeu** |
| 3. Mine détruite par un autre bonus | Bolt, Shunt : §6.1 ; Barge : `KillPickup` direct ; Shock : voir §7 | Bolt : 2 tirs ; Shunt : 1 ; Barge : 1 | SOURCE + GAME (Shock : **CONTRADICTION**) |

Les situations 1 et 2 utilisent des mécanismes **différents** : le contact entre deux corps de mines ne fait rien, alors
qu'un projectile applique des dégâts. La Barge n'utilise pas la santé : elle tue directement les objets.

### 6.3 Barge

| Objet dans l'ellipse (7 m, `IsInsideEllipse`) | Effet | Statut |
|---|---|---|
| Shunt | détruit (`CollideWithPickup`) | SOURCE + GAME |
| Bolt | détruit (`KillPickup`) | SOURCE + GAME |
| Mine | détruite (`KillPickup`) et poussée (`MinMinePushForce` 50 000) | SOURCE + GAME |
| Shock (dôme) | ignoré : les dômes ne sont pas dans la boucle | SOURCE |
| autre Barge | ignorée : une Barge n'est pas un objet de la liste ; chacune frappe la voiture d'en face | PROBABLE |
| voiture adverse | coup (réaction `ROLL` / `JINK`, dégâts 100) ; bloqué par un bouclier | SOURCE + GAME |
| décor mobile | vraie force (`PerkForceEffects`) | SOURCE |

**Barge et Titanium Shield sont différents** :

- la Barge est un **coup de bonus** : dégâts 100, réaction scriptée, bloqué par un bouclier ;
- le Titanium Shield est une **règle de collision** : contact physique, poids « Ultra », écart `JINK_SHIELD`, sans
  dégâts.

### 6.4 Bolt

- Trajectoire droite à 300, sans guidage. Il meurt au premier contact avec une voiture, une Mine, un projectile ou un
  mur (SOURCE).
- **Murs** : `CheckRebound` laisse le Bolt rebondir sur un angle rasant : rebond si |cos(normale du mur, direction)| < 0,1
  (`Perks.Projectile.ReboundAngle`, valeur par défaut). Sinon il meurt (`CollideWithEnvironment`).
- **Objets destructibles** (décor mobile) : ils sont dans la couche « transparente » du rayon. Le Bolt les **pousse**
  (`m_Blindfire.m_MaxForce`) **sans s'arrêter** (`PickupProjectileBase.cpp:597-645`) (SOURCE ; à voir en jeu, N5).
- **Bolt contre Bolt** : le code le permet (règle §6.1 → 50 contre 50, les deux meurent). Le filtre des rayons porte
  l'identifiant de groupe du tireur, ce qui **écarte probablement les Bolts d'un même tireur** (PROBABLE). Deux Bolts
  adverses de face (rayon 0,2) se croisent rarement, ce qui explique qu'on ne l'ait jamais observé.
- **Cible détruite avant l'impact** : le Bolt n'a pas de cible, il continue tout droit (SOURCE).
- **Overbolt** : un tir de plus en réserve, mêmes Bolts.
- **Scatter Shot** : 3 Bolts en éventail de ±2° tirés en même temps (§4.2).

### 6.5 Shunt

D'après la source :

- la cible est choisie au tir : la voiture devant (`mTargetIdx`). Pas de changement de cible trouvé ;
- le Shunt suit les **tracés `.aid`** : il cherche la route de sa cible (`UpdateTargetRoute`, `UpdateCurrentRoute`).
  À une **bifurcation**, il peut prendre une autre branche que sa cible, ce qui est cohérent avec l'observation ;
- il abandonne le guidage à moins de 10 m (`Perks.Shunt.LoseHomingDist`). La portée de visée est de 75 m
  (`TargettingCutOffRange`) ;
- l'ECM fait dévier le Shunt de sa cible (distances 13, 20 et 25 m, DATA) ;
- **murs** : même règle que le Bolt (rebond rasant ou mort) ;
- **objets** : il détruit les Mines (100 contre 100). Contre un autre Shunt, les deux meurent ;
- **décor mobile** : il le pousse ;
- **Super Shunt** : dégâts seulement, le guidage ne change pas (aucun autre code ne lit ce mod).

### 6.6 Shock

- Ne touche que les **voitures** : 3 dômes, 4 avec Quad Shock, placés par l'hôte.
- Pousse le **décor mobile** (`CheckDynamicObjects`, filtre `kbDynamicObject`, `PickupShock.cpp:290-340`).
- **Aucune** référence aux Mines (voir §7).

## 7. Contradictions

| # | Sujet | Source / données | Jeu / communauté | Pistes |
|---|---|---|---|---|
| C1 | Le Shock détruit une Mine | rien dans `C_PickupShock` / `C_ShockManager` : la recherche de corps ne garde que le décor mobile ; les Mines sont d'un autre type (`MineInner` / `MineOuter`) | GAME : la Mine disparaît | a) une voiture ralentie par le Shock a déclenché la Mine ; b) Mastermine ; c) la Mine était à la fin de ses 60 s ; d) changement du binaire final ou d'AMAX. **Test N2** |
| C2 | Bouclier et Shock en multijoueur | code d'origine : `Shielding Efficiency` donne 150 de santé → survit à 1 dôme | GAME : exception ; AMAX : mod réduit | §5.2, **test N1** |
| C3 | Fan pousse un véhicule protégé | aucun Fan qui pousse | GAME | §3, **test N9** |
| C4 | Masse 10 000 du bouclier DoubleTap (`POWERUPS.md` §11) | classe jamais créée | — | corrigé ici (§4.2) |
| C5 | « Modifications do not work in the pc DVD version » | — | wiki Career (note du 28/12/2014) | **À VÉRIFIER** : contredit l'usage rapporté par le joueur ; peut dépendre du patch ou de la version |

## 8. Durée de vie et propriété des objets après déconnexion

D'après la source :

- **Durée** : la Mine décompte elle-même ses 60 s (`mTimer`, `PickupBomb.cpp:181`). Rien ne dépend de l'état de son
  poseur.
- **Nettoyage** : aucune fonction de nettoyage des bonus d'un joueur n'a été trouvée. Seul `KillAllPickups` existe, en
  fin de course. Cela explique T8, mais l'absence de code n'est pas une preuve complète : le code réseau n'a pas été lu
  en entier.
- **Propriétaire** : la Mine garde l'indice de voiture du poseur (`mFiringIdx`) jusqu'à sa mort.
- **Qui décide d'un déclenchement** : la machine de la **victime** (`CheckMineCollision` → `Trigger`). Le mécanisme
  ne dépend donc pas de la présence du poseur : une Mine dont le poseur est parti peut encore toucher, et a priori
  provoquer un wreck (PROBABLE).

Reste **INCONNU** :

- l'attribution des points ou du wreck quand le poseur n'est plus là ;
- la réutilisation de son indice de voiture par un nouveau joueur ;
- d'éventuelles différences entre modes de jeu.

## 9. IA et boss

D'après la source et les données :

- **Deux couches**, à ne pas confondre :
  1. les **règles générales** d'usage : `cPerkSkillUsage`, profils `air.bin` (`AIPerkSkillz`, `AIPerkPrefs`) choisis
     par le CSV de difficulté (`POWERUPS.md` §8) ;
  2. la **personnalisation par adversaire** dans l'épreuve (`PerkAI`, `GameEventData.cpp:91-99`, `LevelState.cpp:870-897`).
- **Champs de `PerkAI`** :
  - `PreferredPickups` : bonus préférés. À défaut, ceux du personnage (`rbChar->preferredPickups`) ;
  - `CharactersNeverTargetted` : personnages jamais visés ;
  - `MaxPerkLevel` ;
  - `PerkToGrant`, `GrantTimeMin`, `GrantTimeMax` : un bonus **offert** à cet adversaire sur minuterie.
- **Mod du boss** : lié à la voiture (§4.1), indépendant des préférences.
- **Valeurs par boss** (préférences, bonus offerts) : **INCONNU**. Les données d'épreuves et de personnages ne sont pas
  dans les `.bin` lus (`gamedata\xt`). Prochaine recherche : les données solo (`SP_*`, épreuves de boss).
- **Show Down** : voir §4.3.

## 10. Matrice d'interactions (v2)

Ligne = ce qui agit ; colonne = la cible ou la situation. Légende :

| Code | Sens |
|---|---|
| **D** | détruit |
| **B** | bloque |
| **T** | traverse |
| **R** | repousse |
| **I** | annule ou interrompt |
| **Dg** | inflige des dégâts |
| **0** | sans effet observé ou lu |
| **NT** | non testé |

Source de chaque case : G = GAME, S = SOURCE, D = DATA, P = PROBABLE, C = contradiction.

| Agit sur → | Voiture avec bouclier | Nitro actif | Mine posée | Shunt en vol | Bolt en vol | Décor mobile |
|---|---|---|---|---|---|---|
| **Shunt** | B (G, S) | I (G, S) | D, et meurt (G, S) | D mutuel (S) | D le Bolt, survit à 50 (S) | R (S) |
| **Bolt** | B (G, S) | 0 (S) | Dg 50, 2 tirs pour D (G, S) | Dg 50 (S) | D mutuel si adverse (S), NT | R sans s'arrêter (S), NT |
| **Mine** (déclenchée) | B (G, S) | I (G, S) | 0 (G, S) | — | — | — |
| **Mine lancée** | B (S) | I (S, P) | D mutuel (S), NT | D mutuel (S) | — | R (S) |
| **Shock** | B puis casse le bouclier (G, S) ; avec Shielding Efficiency : survit à 1 dôme (D, P) | 0 (S) | 0 (S) contre D (G) → C1 | 0 (S) | 0 (S) | R (S) |
| **Barge** | B (G, S) | Dg + réaction, perte de vitesse, sans I (G, S) | D + R (G, S) | D (G, S) | D (G, S) | R (S) |
| **Nitro arrière** | **T** (G, S) | ralentit (S) | 0 (S) | 0 (S) | 0 (S) | NT |
| **Nitro Rift** | **T** (S, P) | NT | 0 (S) | 0 (S) | 0 (S) | NT |
| **Titanium Shield** (contact) | 0 contre un autre bouclier renforcé (S) | NT | 0 (S) | NT | NT | collision normale |
| **Repair** | soigne même sous bouclier (G, S) | 0 (S) | — | — | — | — |
| **Fan / Stopwatch** | sans objet (S) ; observation « pousse » : C3 | — | — | — | — | — |

## 11. Sources communautaires consultées

| Source | URL | Ce qu'elle confirme | Date | Désaccord |
|---|---|---|---|---|
| Blur Wiki : Modifications (Career) | https://blur.fandom.com/wiki/Modifications_(Career) | noms, boss et descriptions des 8 mods ; un seul mod par épreuve solo | non affichée ; note du 28/12/2014 | « ne marche pas sur la version PC DVD » (C5) ; écrit « Drake » pour Drayke |
| Blur Wiki : Modifications (Multiplayer) | https://blur.fandom.com/wiki/Modifications_(Multiplayer) | Shielding Efficiency : durée plus longue et un Shock de plus ; Titanium Armor : demi-dégâts des attaques standard ; Iron Fist : dégâts du Shunt | non affichée | noms affichés ≠ noms internes (Adaptive Shielding, Magnetic Field) |
| Blur Wiki : Shock | https://blur.fandom.com/wiki/Shock | un bouclier est coupé par un seul dôme ; Quad Shock = un dôme de plus ; le tireur peut être touché | non affichée (ébauche) | — |
| Giant Bomb : Blur | https://giantbomb.com/wiki/Games/Blur | Scatter Shot (3 Bolts à la fois) ; Titanium Shield ; Shielding Efficiency « résiste à deux dômes » | non affichée | « deux dômes » : le calcul §5.2 donne 1 dôme encaissé puis cassé au 2e. La formulation est ambiguë |
| GameFAQs : guide de 91sportsfan | https://gamefaqs.gamespot.com/ps3/959892-blur/faqs/60150 | Khan → Titanium Shield | non affichée | — |
| PSNProfiles : trophée Modder | https://psnprofiles.com/trophy/321-blur/46-modder | texte de Shielding Efficiency | — | — |
| PCGamingWiki : Blur | https://www.pcgamingwiki.com/wiki/Blur | patch 1.2 : Titanium Armour peut atténuer les effets visuels | — | cohérent avec `g_debugTitaniumArmourIntensity` |
| AMAX Emu : news | https://amax-emu.com/news | Shielding Efficiency réduit (durée de bonus divisée par 2, santé en plus réduite) ; Adaptive Shielding absorbe Shock et Bolt | 2025-01-04 | change les valeurs d'origine → C2 |

Non consultés dans cette passe : SuperCheats, Neoseeker, les pages Bolt, Shield et One-on-One du wiki. Les points
qu'ils couvriraient sont déjà tranchés par la source et les données.

## 12. Questions ouvertes

1. **C1** : pourquoi la Mine disparaît-elle avec un Shock ?
2. **AMAX** : valeurs actuelles de Shielding Efficiency. Le serveur peut-il changer `multiplayer.bin` ou les
   paramètres en ligne (`PickupParametersStoredOnline`) ?
3. Ce que le joueur appelle « Fan » qui pousse un véhicule protégé (C3).
4. Show Down : quelles voitures, et quelles préférences (`PerkAI`) pour les boss ?
5. Fichiers de personnages et d'épreuves solo (préférences des boss, `PerkToGrant`).
6. Nitro Rift : qui applique la force (500 à 1 500) ? Le seuil `RiftAngleRange` 0,1 désigne-t-il bien l'avant ?
7. Fan Nitro avec une réserve pleine.
8. Mine dont le poseur est parti : attribution du wreck et des points.
9. Mods de carrière en écran partagé : la source ne les active que dans les épreuves solo (course ou boss). Le
    joueur rapporte un usage en écran partagé : **À VÉRIFIER**.
10. v1, toujours ouvert : `do_charging` forcé à `false` dans l'exe ? Formules de chaque `cPerk*`.

Question v1 **résolue** : qui crée `SUB_MOD` → le Scatter Shot (§4.2).

## 13. Tests en jeu proposés (à ne lancer qu'après accord)

Priorité aux tests qui départagent deux explications.

| # | Prio | 1er bonus → 2e bonus ou cible | Mode | Mod nécessaire | Attendu selon les hypothèses | Ce que chaque résultat permet de conclure |
|---|---|---|---|---|---|---|
| N1 | 1 | Shield → Shock (3 dômes) | LAN ou en ligne sur AMAX, 2 joueurs | un essai sans mod, un essai avec Shielding Efficiency | sans mod : cassé au 1er dôme ; avec le mod (valeurs d'origine) : survit au 1er, cassé au 2e | survit au 1er → C2 expliqué ; cassé au 1er malgré le mod → AMAX a baissé la santé sous +50 ; survit à tout → autre règle |
| N2 | 1 | Mine posée → Shock dont le dôme couvre la Mine, **sans voiture à proximité** | course perso, IA lointaine | aucun | la Mine reste (source) | la Mine disparaît sans voiture → C1 confirmé (le binaire diffère de la source) ; elle reste → la disparition observée venait d'une voiture |
| N3 | 2 | Mine lancée vers l'avant → Mine posée | course perso | aucun | les deux explosent | aucune n'explose → le cas 2 (§6.2) diffère de la source |
| N4 | 2 | Barge → Nitro de l'adversaire, à 3 moments (avant, pendant, juste après le Nitro) | LAN | aucun | perte de vitesse, Nitro jamais coupé net | Nitro coupé → il existe un `DisableActiveNitrous` non lu |
| N5 | 3 | Bolt → objet destructible (barrière, cône) | course perso | aucun | l'objet est poussé, le Bolt continue | le Bolt s'arrête → couche « transparente » mal comprise |
| N6 | 3 | Bolt contre Bolt de face (un tireur devant, un derrière, Bolts croisés) | LAN | aucun | les deux disparaissent | ils se croisent → filtre de groupe entre joueurs aussi |
| N7 | 3 | Boss en course normale puis en Show Down | carrière | aucun | mod visible en course (4 dômes chez Natalya, Scatter chez Ayumi), absent en Show Down | mod présent en Show Down → le slot ne dépend pas que de la voiture |
| N8 | 3 | Mine posée → poseur qui quitte (LAN), puis une 3e voiture passe dessus | LAN, 3 machines | aucun | explosion, wreck possible | noter qui reçoit les points |
| N9 | 3 | Clarifier « Fan pousse un véhicule protégé » | — | — | — | le joueur précise le bonus en cause ; si c'est un Nitro (arrière ou Rift) → déjà expliqué (T1) |
| N10 | 4 | Titanium Shield → percuter une IA | carrière (Khan battu) | Titanium Shield | IA écartée (`JINK_SHIELD`), pas de dégâts, 12 s | dégâts → confusion avec le SuperShield |
| N11 | 4 | Armor Plating : encaisser un Bolt, puis un Shunt | carrière | Armor Plating | Bolt : dégâts pleins ; Shunt : 50 au lieu de 100 | réduit aussi le Bolt → la liste des types diffère |

## 14. Statut des informations de la v1

Les conclusions de la v1 sont conservées et confirmées en jeu par T1 à T8 :

- le bouclier bloque tout sauf le Nitro ;
- seul le Shock casse le bouclier ;
- 2 Bolts par Mine ;
- la Barge détruit les projectiles et les mines ;
- le Shunt et la Mine coupent le Nitro ;
- la Réparation passe sous le bouclier.

Corrections :

- v1 §11 Q6 (`SUB_MOD`) : résolue (§4.2) ;
- v1 §5.2 « Shock et Mines : aucune interaction, **DÉDUCTION** forte » : devient **CONTRADICTION** C1 après
  l'observation en jeu.

Anomalies de la v1 (§10 v1) inchangées :

- `FansToGain` et `TimeToGain` jamais lus ;
- IA de `pickups.bin` coupée ;
- aiguillage DoubleTap de la Shock ;
- `case BOMB` sans `break` dans la Barge ;
- texte « touché par… » coupé.
