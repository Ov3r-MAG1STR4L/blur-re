# Étude du comportement des bonus d'origine de Blur

Versions :

- **v1** (2026-11-17) : première étude.
- **v2** (commit `f30d2e3`) : essais en jeu T1 à T8, modifications de carrière et multijoueur.
- **v3** (2026-11-17) : recherche communautaire, AMAX, mods, mécaniques cachées, correction Shock contre Mine.

Tout est en **lecture seule** : aucun fichier du jeu, aucune copie de test, aucun exécutable modifiés, aucun mod
installé. Ce document complète **`POWERUPS.md`** (référence technique) et **`POWERUPS_DONNEES.md`** (toutes les
valeurs).

## 0. Nouveautés de la v3

1. **Correction : le Shock et la Mine n'interagissent pas** (confirmé par le joueur). La source le disait déjà : le
   Shock ne cherche que le décor mobile. La « contradiction C1 » et le test N2 de la v2 sont supprimés (§14).
2. **Le « balance patch » d'AMAX était un poisson d'avril.** Il a duré du 1er au 4 avril 2025, puis a été annulé. AMAX
   écrit : « now we are back to the good old Blur from 2010 ». La v2 se trompait en disant que `Shielding Efficiency` est
   réduit aujourd'hui (§6).
3. **Le bouclier qui survit à un Shock en ligne est expliqué.** `Shielding Efficiency` donne 150 de santé, et un dôme
   fait 100 de dégâts. Il y a aussi des témoignages indépendants de 2010 sur Xbox 360 (« going through 2 shocks ») et
   le texte du jeu (« sustain an extra hit from Shock blasts »). La question est close, sans test (§5.2).
4. **Les noms affichés des mods multijoueur sont reliés aux noms internes** (§5.1). Les noms trompent :
   - **Adaptive Shielding** = `SafetyNet` dans le code ;
   - **Safety Net** = `ShieldedBoosters` ;
   - **Magnetic Field** = `RoadSweeper`.
5. **Les défis multijoueur officiels prouvent des interactions voulues par les développeurs** (§7.1) :
   - « Explode a Mine with another Mine » ;
   - « Block attacks using another Power-up » : une Mine, un Bolt ou un Shunt arrière, ou une Barge qui arrête un
     projectile.
6. **Le joueur appelle aussi « Nitro Rift » le Nitro arrière** (frein aérien) : c'est le nom de ses défis. Il ne faut
   pas le confondre avec le mod de Carver (§7.3).
7. **Mécaniques cachées** (§9) :
   - une réserve pleine refuse les bonus ;
   - un bonus n'est déposé sur la piste que s'il a toutes ses munitions ;
   - un dôme de Shock ne touche qu'une voiture ;
   - la sphère intérieure du Shock est désactivée ;
   - Adaptive Shielding a un plafond ;
   - restes d'un ancien système d'améliorations (`CollectAnyPerkType`, emplacements de bouclier, `FanPower`).
8. **Une partie du comportement des bonus dépend de la fréquence d'images sur PC** (`FakePhysics`, rotation des bonus,
   Nitro arrière), d'après le travail de l'auteur d'AMAX (§7.4).
9. **Show Down** : le duel final contre Shannon se joue en `Opel_AstraExtreme_Stock_Shannon`. Ce modèle n'a pas de mod
   (DATA), et le guide dit « no Mod to earn » (§4.3).

## 1. Niveaux de preuve et environnements

| Étiquette | Sens |
|---|---|
| **CONFIRMÉ — SOURCE OFFICIELLE** | texte du jeu lui-même (description d'un mod, d'un défi) ou annonce de l'éditeur ou d'AMAX sur son propre serveur |
| **CONFIRMÉ — CODE SOURCE** | code source fuité (juin 2010, `src/` = `blur_source\BlurRebuilt\code\amax\game\`). **Ce n'est pas une preuve absolue du binaire final** |
| **CONFIRMÉ — FICHIERS DU JEU** | `pickups.bin`, `multiplayer.bin`, `amax.bin`, `rldatabase.bin` lus avec `blurxt.py` |
| **CONFIRMÉ — GAMEPLAY OBSERVÉ** | vu en jeu par le joueur |
| **CONFIRMÉ — COMMUNITY** | source communautaire (§16). Plusieurs sites qui recopient le même texte comptent pour **une seule** source |
| **PROBABLE** | cohérent, non démontré |
| **NON VÉRIFIÉ** | trop peu documenté |
| **CONTRADICTOIRE** | sources en désaccord |

Abréviations utilisées dans les tableaux :

| Abréviation | Niveau |
|---|---|
| OFF | SOURCE OFFICIELLE |
| CODE | CODE SOURCE |
| DATA | FICHIERS DU JEU |
| GAME | GAMEPLAY OBSERVÉ |
| COMM | COMMUNITY |

**Environnements**, à ne jamais mélanger :

| Environnement | Ce que c'est | Valeurs des bonus |
|---|---|---|
| **Blur PC d'origine** (2010, patch 1.2) | le jeu installé, solo, écran partagé, LAN | celles des fichiers (`POWERUPS_DONNEES.md`) |
| **AMAX** | serveur en ligne de remplacement, utilisé par le joueur | **celles de 2010** (OFF, AMAX 2025-04-04), sauf du 1er au 4 avril 2025 (§6) |
| **Mods communautaires** | BlurRebuilt, déblocage d'images, etc. (§12) | aucun mod public connu ne change les bonus |

## 2. Observations en jeu T1 à T8 (GAMEPLAY OBSERVÉ, v2 conservée)

| Test | Observation du joueur | Explication | Autres sources |
|---|---|---|---|
| T1 | Un Nitro arrière traverse un Shield | `AttemptHitByPickup` : `type != NITROUS` → jamais bloqué (CODE) | — |
| T2 | Un seul Shock détruit un Shield | dôme 100 contre bouclier 50 (DATA) | OFF : wiki Shield ; COMM : guide GameFAQs « will only protect you from one dome » |
| T3 | 2 Bolts pour une Mine | Bolt 50 contre Mine 100 (DATA + CODE) | COMM : guide GameFAQs « firing 2 Bolt rounds at it » |
| T4 | Un Shield activé après le tir d'un Bolt bloque ce Bolt | bouclier testé à l'impact (CODE) | — |
| T5 | La Barge détruit Mines, Shunts et Bolts | ellipse de la Barge (CODE) | COMM : guide ; OFF : défi « Rear Guard » (Barge contre projectile) |
| T6 | Shunt et Mine interrompent un Nitro | `DisableActiveNitrous` (CODE) | — |
| T7 | Repair utilisable à tout moment | `RegisterHitByPickup` direct (CODE) | — |
| T8 | Mine active 60 s, même après le départ de son poseur | `Lifespan` 60, minuterie propre à la Mine (DATA + CODE) | aucune trouvée |

Autres observations du joueur :

| Sujet | Observation | Lecture |
|---|---|---|
| Shield contre Barge, Mine, Shunt | protège | cohérent (CODE, COMM) |
| **Shock contre Mine** | **aucune collision ni interaction** (correction v3) | cohérent avec le CODE : le Shock ne cherche que le décor mobile (§8.6) |
| Mine contre Mine | une explosion ne détruit pas une Mine voisine | `Explode()` = effet visuel seulement (CODE) |
| Barge contre Nitro | perte de vitesse, sans annulation nette, selon le moment | la Barge n'appelle pas `DisableActiveNitrous` (CODE) |
| Repair juste avant un Shock | souvent un mauvais choix | aucun lien de code → choix tactique, pas une règle (PROBABLE) |
| Bolt | une seule voiture touchée, pas de nouvelle cible, détruit par un mur | cohérent (CODE, COMM « no homing capabilities ») |
| Shunt | suit sa cible, peut toucher un mur, perdre sa cible à une bifurcation, détruire une Mine | cohérent (CODE, COMM) |
| **« Fan » pousse un véhicule protégé** | — | **NON VÉRIFIÉ**, voir §3 |

## 3. Fan, Stopwatch et l'observation « Fan pousse un véhicule protégé »

Rappel v1 : le **Fan** (type 8) et le **Stopwatch** (type 9) sont des pastilles de mode de jeu, pas des bonus
utilisables :

- `HitPickUp` les refuse (CODE) ;
- `GetPerkInfo` rend NULL (exe) ;
- seul le joueur 0 les ramasse.

Recherches faites :

- wiki Power-Ups et Nitro ;
- guide GameFAQs ;
- défis multijoueur ;
- liste des mods ;
- recherche de « fan » dans la source.

**Aucune** source ne décrit un Fan qui pousse ou un projectile Fan. Les seuls effets du jeu qui **poussent une voiture
protégée** sont du type NITROUS, que le bouclier ne bloque pas (CODE) :

- le **Nitro arrière** (frein aérien et sillage « Nitro Rift ») : « If another vehicle slams into yours (or touches
  the Rift) … they receive damage and are stopped » (COMM, wiki Nitro) ;
- le **Nitro Rift de Carver** (faille devant soi).

Mods dont le nom contient « Fan » : **Fan Nitro** (Rhymer, donne un Nitro), **Fan Favourite** (fans en plus en fin de
course). Aucun ne pousse.

Statut : **NON VÉRIFIÉ**. L'observation n'est pas déclarée fausse, mais aucune source ne permet de l'expliquer telle
quelle. **Question au joueur** (pas un test) : de quel bonus ou effet s'agissait-il (couleur, icône, tiré par qui) ?
Si c'est un Nitro, l'observation est expliquée.

## 4. Les huit modifications de carrière (boss)

### 4.1 Mécanisme (CODE + DATA, v2) et confirmations externes

- Ce sont des capacités `Boss_*` du système des mods multijoueur, emplacement `Slot4`.
- **Boss IA** : le mod est porté par la voiture (`AmaxVehicle.BossAbilitySlot`, `amax.bin`).
- **Joueur** : **un seul** mod (`mSpEquippedAbility`), actif seulement en épreuve solo de **course** ou de **boss**
  (`LevelState.cpp:838-852`).
- Confirmations externes :
  - « Only a single modification can be used in a Single Player event » (COMM, wiki) ;
  - « MODS do not work in Destruction Mode - Single player » (COMM, 3 joueurs GameFAQs 2010, Xbox 360) ;
  - la source n'active pas non plus les mods dans les épreuves Fan et Checkpoint (pas de témoignage trouvé sur ces
    deux-là).
- Unité : 0,5 pip = 50 points (`HealthIncrement` 100, DATA).

### 4.2 Fiches (code, données et confirmations)

| Mod (boss) | Code et données | Texte officiel (OFF) | Témoignages (COMM) | Statut |
|---|---|---|---|---|
| **Overbolt** (Shannon) | 3 + 1 = **4 Bolts** (`GetNumShotsAwarded`) | « Gain an extra Bolt round for every Bolt Power-up » | « Bolt gives 4 bolts » (GameFAQs 2010) ; guide « fire 4 shots » | confirmé |
| **Titanium Shield** (Khan) | bouclier DoubleTap : **12 s**, santé 50 ; poids « Ultra » au contact ; écart `JINK_SHIELD`, sans dégâts | « Increase your Shield Power-up strength and use it to smash opposition out of your way » | guide : « increases the strength » | durée et contact : CODE ; « strength » = durée et poussée, **pas** la santé (CODE) |
| **Fan Nitro** (Rhymer) | un Nitro tous les 500 de score ; **perdu si la réserve est pleine** (`HitPickUp` sans place libre) | « Gain a Nitro Power-up for every 500 Fans earned » | guide : « As long as you have an empty Power-up slot » | confirmé (CODE + COMM) |
| **Super Shunt** (Drayke) | Shunt **+50** (100 → 150) ; son à part | « Increase the power of your Shunt Power-ups » | guide : « increases the amount of damage » | confirmé ; aucun changement de guidage (CODE) |
| **Quad Shock** (Natalya) | **4 dômes** (`numShocksToFire += 1`) | « Gain an extra Shock dome » | wiki Shock | confirmé |
| **Armor Plating** (Talon), `BossRepairBonus` | **−50** contre Barge, Shunt et Mine ; pas contre Bolt ni Shock | « Reduce the damage sustained from heavy Power-ups » | — | confirmé. Le nom interne est trompeur : rien n'est réparé |
| **Scatter Shot** (Ayumi et Harumi) | sous-type `MOD` → 3 Bolts `SUB_MOD` en même temps à −2°, 0° et +2° ; pile vidée ; vers l'arrière : `SUB_MOD_REVERSED` | « Fire off all three Bolt Power-up rounds at once » | guide | confirmé |
| **Nitro Rift** (Carver) | Nitro + faille 2,5 s, 30 m, coup NITROUS qui traverse les boucliers | « Clear a path ahead by firing a rift of energy forward every time you use a Nitro » | — | CODE + OFF ; traverse le bouclier : CODE seulement |

Plateformes : aucune différence trouvée entre PC et consoles. Bugs connus :

- patch PC 1.2 : « Equipping Titanium Armour can make Power-up special effects fade out » (COMM, PCGamingWiki). Il
  s'agit du mod **multijoueur** Titanium Armor, cohérent avec `g_debugTitaniumArmourIntensity` (CODE) ;
- wiki Career, note de 2014 : « Modifications do not work in the pc DVD version ». **NON VÉRIFIÉ**, aucune autre
  source (§14).

### 4.3 Show Down

| Point | Statut |
|---|---|
| 6 courses en classe A contre tous les boss, puis un duel contre Shannon en **Opel Astra Extreme** | COMM (guide GameFAQs, juin 2010) |
| Shannon n'y a pas de mod | **confirmé** : `Opel_AstraExtreme_Stock_Shannon` n'a pas de `BossAbilitySlot` (DATA), et le guide dit « there is no Mod to earn » (COMM) |
| Les autres boss n'ont pas de mod dans les 6 courses | PROBABLE : seuls les 9 modèles de boss portent un mod (DATA). Les voitures exactes des boss dans ces courses ne sont pas documentées |
| Préférences de bonus inchangées | NON VÉRIFIÉ (§11) |

## 5. Modifications multijoueur (Blur d'origine)

### 5.1 Liste complète : nom affiché, nom interne, valeurs

Sources :

- textes et rangs : wiki Multiplayer et page du wiki communautaire (COMM, recopie du texte du jeu) ;
- noms internes et valeurs : `multiplayer.bin` (DATA) et code (CODE) ;
- 3 groupes de couleur, un mod par groupe ; jusqu'à 4 jeux de mods enregistrés (COMM).

Rangs de déblocage : ils viennent du wiki, et les deux pages communautaires ne sont pas d'accord pour Front Runner
(26 ou 28). Les mods de carrière ne sont pas dans ce système de rangs.

**Groupe 1 (jaune)**

| Nom affiché (rang) | Nom interne | Effet réel (CODE + DATA) |
|---|---|---|
| Stable Frame (3) | `StableFrame` | moins de dégâts des chocs (valeur 0,5) ; immunité au Battering Ram |
| Battering Ram (3) | `BatteringRam` | chocs plus forts (valeur 1) |
| Showy Flourish (6) | `ShowyFlourish` | fans en plus par coup de bonus (10) |
| Titanium Armor (13) | `TitaniumArmour` | **−50** contre Barge, Mine et Shunt (`titanium_armour_blocks_*`) ; Bolt et Shock non concernés ; effets atténués |
| Iron Fist (20) | `IronFist` | **Shunt +50** ; autres types +0 (`iron_fist_*_damage`) |
| Front Runner (26 ou 28) | `FrontRunner` | Nitro à chaque tour (et au dernier tour), pas au départ ; perdu si la réserve est pleine (COMM) |
| Drifter (32) | `Drifter` | Nitro par super-dérapage (`drifter_lengths` 100) |
| Jump The Gun (45) | `JumpTheGun` | réapparition plus rapide (× 0,66), élan 45 ou 60 |

**Groupe 2 (orange)**

| Nom affiché (rang) | Nom interne | Effet réel (CODE + DATA) |
|---|---|---|
| Safety Net (3) | **`ShieldedBoosters`** | un coup arrêté par le bouclier **répare** la voiture des dégâts Normal du bonus (`CheckShieldedBoostersAbsorbDamage`) |
| Adaptive Shielding (3) | **`SafetyNet`** | Shunt, Barge ou Mine arrêtés par le bouclier → **le même bonus est ajouté à la réserve** (`HandleSafetyNetPickupAward`). Bolt et Shock désactivés par les données (`safety_net_absorb_enabled_*`). Plafond : `Multiplayer.Upgrades.SafetyNet.MaxPickupsAbsorbable` = 2, test `>` |
| Shielding Efficiency (9) | `ShieldingEfficiency` | durée × 1,8 ; santé +100 (§5.2) |
| Splash Damage (17) | `SplashDamage` | ellipse de la Barge × 1,2 |
| Scrambler (22) | `Scrambler` | bonus **arrière** (Mine, Bolt, Shunt) et Nitro arrière qui touchent → réserve de la victime bloquée 5 s |
| Shielded Bay (22) | `ShieldedBay` | immunité au Scrambler et aux leurres |
| Magnetic Field (35) | **`RoadSweeper`** | rayon de ramassage × 1,3 (`CheckRoadSweeperMultiplier`) |
| Decoy Drop (40) | `DecoyDrop` | le bonus lâché devient un leurre (sous-type `DECOY`) ; 1 par joueur |

**Groupe 3 (vert)**

| Nom affiché (rang) | Nom interne | Effet réel (CODE + DATA) |
|---|---|---|
| Laser Sight (3) | `LaserSight` | visée du Bolt |
| Fan Favorite (3) | `FanFavourite` | bonus de fans de fin × 1,25 |
| ECM (10) | `ECM` | Shunts plus faciles à semer (13 / 20 / 25 m) |
| Bribe (15) | `Bribe` | bonus au départ et après un wreck (probabilités `bribe_mod_settings`) |
| Vampiric Wreck (25) | `VampiricWreck` | réparation (5) à chaque adversaire détruit |
| Mastermine (30) | `Mastermine` | passer près d'une Mine l'amorce (0,3 s), qui se change en mini-mines `MOD` et `MINI` |
| Last Gasp (38) | `LastGasp` | une fois détruit, tire un bonus `MOD` de type 4 (**Barge**) |
| Silent Running (47) | `SilentRunning` | invisibilité |

**Hors groupes** :

- `AdvancedRadar` : présent dans le code et les données, « not currently used » (CODE) ;
- `Boss_*` : `Slot4`, carrière (§4).

**Combinaisons et compatibilités** (CODE) :

- un mod par groupe ;
- `ShieldedBoosters` passe **avant** `SafetyNet` dans le chemin du coup arrêté (`VLC_Pickups.cpp:1571`) : avec les
  deux, la conversion d'Adaptive Shielding ne se déclenche que si `ShieldedBoosters` n'a pas agi (PROBABLE, lecture du
  `if`) ;
- Stable Frame annule Battering Ram ;
- Shielded Bay annule Scrambler et Decoy Drop.

### 5.2 Shielding Efficiency contre Shock : question close

| Élément | Contenu | Niveau |
|---|---|---|
| Valeurs | durée × 1,8 (6 → 10,8 s) ; santé 50 + 100 = 150 | DATA + CODE |
| Un dôme | 100 de dégâts, **un seul coup** (le dôme meurt sur la première voiture touchée, la sphère intérieure est désactivée, §9.3) | CODE |
| Calcul | 1er dôme : bloqué, il reste 50 ; 2e dôme : bloqué, le bouclier tombe à −50 et se coupe ; 3e dôme : touche | CODE |
| Texte du jeu | « can sustain an extra hit from Shock blasts » | OFF |
| Joueurs en 2010 | « the extra shielding one (for going through 2 shocks) » ; « blocks 2 shocks » | COMM, 2 joueurs GameFAQs (Xbox 360) |
| Giant Bomb | « withstand two shock domes » | COMM (même lecture : deux dômes bloqués) |
| AMAX aujourd'hui | valeurs de 2010 | OFF (AMAX) |
| Observation du joueur | exception en multijoueur | GAME |

**Conclusion : CONFIRMÉ.** Avec Shielding Efficiency, le bouclier **bloque deux dômes** et casse au deuxième. Sans le
mod, il casse au premier. Le test N1 de la v2 n'est plus nécessaire.

Modes : `ApplyShieldModMultipliers` lit le mod de la voiture, quel que soit le mode. Les mods multijoueur ne sont
remplis qu'en multijoueur ou en LAN (`FillOutLevelStateCar`), donc il n'y a pas de Shielding Efficiency en solo (CODE).
PC et consoles : aucune différence signalée.

## 6. AMAX (serveur en ligne de remplacement)

| Point | Contenu | Niveau |
|---|---|---|
| Projet | serveur de remplacement de Blur en ligne, par « aibot » et des contributeurs | OFF (amax-emu.com, GitHub `Amax-Emu`) |
| **« BLUR AMAZING BALANCE PATCH »** | annoncé le 1er avril 2025, « patch is already on the server », annulation prévue le 3 avril, oubliée un jour | OFF (news du 2025-04-01 et du 2025-04-04) |
| Retour aux valeurs d'origine | « now we are back to the good old Blur from 2010 » ; « messing with its balance is a bad, **bad** idea. So I won't » | OFF (2025-04-04) |
| Contenu du patch (seulement du 1er au 4 avril 2025) | Titanium Armor : bloque aussi Shock et Bolt, −70 % ; Iron Fist : Barge, Bolt, Shunt et Shock ; Front Runner : plus de Nitro au dernier tour ; Drifter : distance × 4 ; Jump the Gun : −60 % ; Adaptive Shielding : absorbe Shock et Bolt ; Shielding Efficiency : bonus de durée / 2, santé en plus réduite ; Splash Damage plus grand ; Scrambler : Shock et Bolt avant, plus long ; Magnetic Field × 5 ; 2 leurres ; Bribe : plus de Nitro, moins de bouclier ; Vampiric Wreck : soin complet ; Last Gasp : dégâts et rayon × 2 ; Silent Running : caché du radar | OFF |
| **Comment** | changé sur le serveur, sans téléchargement. Chaque ligne correspond à un réglage de `misc_mod_settings` ou à une `AbilityValue` de `multiplayer.bin` (ex. `safety_net_absorb_enabled_shock/bolt` = « absorbs shocks and bolts » ; `iron_fist_*_damage`). AMAX peut donc envoyer la configuration des mods depuis le serveur | correspondance : DATA ; méthode exacte d'envoi : PROBABLE (`TitleManagedStorageSettings`, `PickupParametersStoredOnline` existent dans `multiplayer.bin`) |
| Valeurs exactes du patch | non publiées (« reduced ») | NON VÉRIFIÉ, sans importance aujourd'hui |
| Autres changements AMAX | correctif de fréquence d'images en préparation (physique, rotation des bonus) ; statistiques serveur des bonus utilisés ; week-ends double fans ; projet « Blur community patch » (contenu coupé, équilibrage), sans date | OFF |

Conséquence pour l'étude : **toute observation faite sur AMAX en dehors du 1er au 4 avril 2025 utilise les valeurs de
2010.**

## 7. Découvertes communautaires

### 7.1 Les défis multijoueur montrent les intentions des développeurs (OFF + CODE)

Le texte des défis est celui du jeu, et leur code est dans `VLC_MultiplayerChallenges.cpp:712-840`.

| Défi | Texte | Code | Ce que cela prouve |
|---|---|---|---|
| Master Exploder | « Explode a Mine with another Mine » | victime Mine, tueur Mine (pas les siennes) | **une Mine peut en détruire une autre**. C'est forcément une Mine lancée vers l'avant (projectile), puisqu'une explosion n'a pas de zone de dégâts |
| Minesweeper | « Destroy Mines without taking damage » | tueur Bolt, Shunt ou Barge | les trois détruisent une Mine |
| Rear Guard | « Block attacks using another Power-up » | 1) **ma Mine** arrête un Shunt ou un Bolt adverse ; 2) **mon Bolt ou Shunt arrière** arrête un Shunt ou un Bolt ; 3) ma **Barge** neutralise un Shunt ou un Bolt (pas celle de Last Gasp) | **Bolt contre Bolt de face** est un cas voulu, comme la Mine qui sert de bouclier arrière |
| Fully Bolt | « Fully Bolt 10 cars » | 3 Bolts sur la même voiture | — |
| Hit 3, 4 ou 5 cars with a single Barge | — | — | **une Barge touche plusieurs voitures** |
| Shock Evader | « Be targeted by Shock and avoid being hit » | `AvoidedAllDomes` | — |
| Nitro Rift | « Hit opponents with a reverse Nitro Rift » | — | le Nitro **arrière** s'appelle « Nitro Rift » en jeu |
| Adaptive Shielding / Road Sweeper | « Absorb … Power-ups » / « Collect … with the Magnetic Field Mod » | `SafetyNet` / `RoadSweeper` | confirme les correspondances de noms du §5.1 |

### 7.2 Guide GameFAQs de 91sportsfan (PS3, v1.0, 2010-06-08)

- **Interactions** :
  - le Shield bloque tout, mais un seul dôme de Shock ;
  - la Barge détruit un Shunt qui arrive ;
  - **2 Bolts détruisent un Shunt** ou une Mine ;
  - une Mine posée détruit un Shunt ;
  - un Shunt tiré sur une Mine peut tourner vers une voiture au lieu de la toucher.

  Tout cela est cohérent avec le CODE.
- **Shunt arrière** : « will only travel in a straight path » ; **Bolt** : « no homing capabilities ».
- **Shock** : « pass through the edges of the domes with no effect ». Lecture CODE : le rayon du dôme **grandit** avec
  le temps jusqu'à 14 m (`g_debugShockInitialGrowthRate`), et une différence de hauteur minimale est exigée
  (`HeightDiff` −1,5 m). PROBABLE.
- **Repair** : « may not restore you to full Health » sur les voitures lourdes. Lecture : `AmaxVehicle` a une santé
  par voiture, et la réparation fait 400 points. PROBABLE.
- **Comportement des boss** (COMM, une seule source) :
  - Khan repousse les Shunts avec la Barge ;
  - Natalya est défensive et détruit les bonus qui arrivent avec la Barge ;
  - Talon préfère la course ;
  - Ayumi et Harumi prennent Repair et Shield.

### 7.3 Deux sens de « Nitro Rift »

1. **Nitro arrière** (tous les joueurs) : frein aérien, sillage qui touche et arrête les voitures qui le percutent.
   C'est le niveau `Nitrous · Reversed` (`RiftRangeSquared` 100, `ForwardDot` 0,2, dégâts 50, DATA). Défis « reverse
   Nitro Rift » (OFF), wiki Nitro (COMM).
2. **Mod de Carver « Nitro Rift »** : faille **devant** soi en plus du Nitro normal (`Nitrous · DoubleTap`,
   `PickupDoubleNitrous`).

Les deux sont de type NITROUS : **aucun n'est bloqué par un bouclier** (CODE ; GAME pour le Nitro arrière).
`scrambler_enabled_nitro_rift` désigne le Nitro arrière, puisque le Scrambler ne vise que les tirs arrière.

### 7.4 Fréquence d'images et bonus (COMM, auteur d'AMAX, ébauche du 2025-08-23)

- Le jeu calcule une partie de sa physique **à chaque image**. Les réactions `FakePhysics` (vrille de Mine, salto du
  Shunt, redressement après un Nitro) sont mises à jour image par image.
- Au-delà de 30 images par seconde :
  - la voiture se redresse plus vite après un Nitro (`Perks.FakePhysics.Speed.AccelerateStabilise`, `…Rate`) ;
  - les bonus posés sur la piste tournent trop vite (`Perks.PickupActor.RotationSpeed`) ;
  - on peut faire **plus de 360°** pendant un Nitro arrière.
- Les joueurs compétitifs bloquent le PC à 30 images par seconde pour retrouver la physique PS3.
- **CONTRADICTOIRE** : le README de BlurRebuilt dit au contraire que le jeu original était « designed around 60 fps ».
  Conséquence pour l'étude : les durées de réaction et les enchaînements Nitro et dérapage peuvent dépendre de la
  fréquence d'images. Toute mesure de durée en jeu doit noter le FPS.

## 8. Interactions entre projectiles et objets

### 8.1 Règle générale (CODE)

Quand un projectile rencontre une Mine ou un autre projectile, il y a des dégâts croisés selon santé et dégâts
(`PickupProjectileBase.cpp:503-560`), et le plus récent est crédité :

| Objet | Santé | Dégâts |
|---|---|---|
| Bolt | 50 | 50 |
| Shunt | 100 | 100 |
| Mine posée | 100 | 100 |
| Mine lancée | 100 | 100 |
| Mini-mine | 25 | 50 |

### 8.2 Mine et Mine

| Situation | Mécanisme | Résultat | Niveau |
|---|---|---|---|
| 1. Explosion près d'une autre Mine | `Explode()` = effet visuel ; contact entre deux corps de Mine sans effet (`RaceLogicLayer.cpp:2653`) | rien | CODE + GAME |
| 2. Mine lancée qui touche une Mine | projectile (`C_PickupBombReverse : C_PickupProjectile`) → 100 contre 100 | les deux détruites | CODE + **OFF (Master Exploder)** |
| 3. Mine détruite par un autre bonus | Bolt (2 tirs), Shunt (1), Barge (1) | détruite | CODE + GAME + OFF (Minesweeper) + COMM |
| 3 bis. Shock | aucune interaction | rien | CODE + GAME |
| 4. Voiture | la sphère intérieure déclenche, la sphère extérieure amorce (Mastermine) (`CheckMineCollision`) | explosion | CODE |
| 4 bis. Décor | les Mines physiques sont poussées par la Barge ; leur collision avec le décor n'a pas été lue | — | NON VÉRIFIÉ |

### 8.3 Barge

- **Détruit** : Shunt, Bolt et Mine dans son ellipse de 7 m (× 1,2 avec Splash Damage).
- **Pousse** : les Mines (`MinMinePushForce` 50 000) et le décor mobile.
- **Ignore** : les dômes de Shock et les autres Barges.
- **Voitures** : touche **plusieurs voitures** à la fois (OFF : défis « Hit 5 cars with a single Barge »), avec 100 de
  dégâts et une réaction `ROLL` / `JINK`. Bloquée par un bouclier. Contre un Nitro, elle fait perdre de la vitesse
  sans l'annuler (GAME + CODE).
- **Différence avec le Titanium Shield** : la Barge est un coup de bonus ; le Titanium Shield est une règle de
  collision (poids « Ultra », écart, sans dégâts) (§4.2).

### 8.4 Bolt

- Trajectoire droite à 300, sans guidage (CODE + COMM). Il meurt sur la première voiture, Mine, projectile ou mur
  touché.
- Rebond sur un mur seulement à angle rasant (|cos| < 0,1). Sinon il meurt (CODE).
- **Bolt contre Bolt** : prévu par le défi Rear Guard (OFF + CODE), 50 contre 50 → les deux meurent. Le cas classique
  est un Bolt **arrière** contre un Bolt qui arrive. Les Bolts d'un même tireur s'ignorent probablement (filtre de
  groupe, PROBABLE).
- **Bolt contre Shunt** : 2 Bolts (COMM + CODE). **Bolt contre Mine** : 2 Bolts (GAME + COMM + CODE).
- **Décor mobile** : poussé, et le Bolt continue (CODE). Aucune source externe.
- **Overbolt** : 4 tirs séparés. **Scatter Shot** : 3 Bolts en éventail de ±2° en un tir. Avec Overbolt, la pile
  ferait 4, mais un seul mod est équipé à la fois : pas de combinaison possible.

### 8.5 Shunt

- Cible : la voiture devant, au moment du tir. Il suit les tracés `.aid` de sa cible et peut prendre une autre branche
  à une bifurcation. Le guidage s'arrête à moins de 10 m (CODE).
- COMM : un Shunt tiré vers une Mine peut changer de direction (guidage).
- Shunt arrière : en ligne droite (COMM + CODE).
- Murs : rebond rasant ou mort (CODE).
- Objets : Mine (les deux détruites), Shunt (les deux détruits), Bolt (survit à 50) (CODE + COMM).
- **Super Shunt** : seulement les dégâts.

### 8.6 Shock

- Ne touche que les **voitures**. Il pousse le décor mobile (`CheckDynamicObjects`).
- **Aucune interaction avec les Mines** (CODE + GAME, correction v3).
- Chaque dôme ne touche qu'**une** voiture, puis disparaît (`KillPickup` après le premier coup). Il ignore une voiture
  qu'il a déjà vue protégée (`mVehiclesShielded`) (CODE).

## 9. Variantes peu documentées et mécaniques cachées

### 9.1 Qui crée chaque sous-type (CODE)

| Sous-type | Créé par | Rencontré en jeu ? |
|---|---|---|
| `NORMAL` | tir normal | oui |
| `REVERSED` | tir arrière | oui |
| `DOUBLE_TAP` | Titanium Shield, Nitro Rift (Carver), Shock (aiguillage interne) ; DoubleTap du joueur coupé | oui, par les mods et la Shock |
| `REVERSED_DOUBLE_TAP` | DoubleTap arrière (coupé) | non |
| `DECOY` | Decoy Drop (bonus lâché transformé en leurre) | multijoueur |
| `MOD` | Scatter Shot (Bolt) ; Mastermine (Mine convertie) ; Last Gasp (Barge) | carrière et multijoueur |
| `MOD_REVERSED` | Scatter Shot arrière | carrière |
| `SUB_MOD` | les 3 Bolts du Scatter Shot | carrière |
| `SUB_MOD_REVERSED` | les 3 Bolts du Scatter Shot arrière (`PickupBlindfireShotgunReverse.cpp:59`) | carrière |
| `MINI` | fragments de Mastermine | multijoueur |

### 9.2 Réserve de bonus (CODE, sauf mention)

| Mécanique | Détail |
|---|---|
| Capacité | `NumPickupSlots`, venu du profil (3 hors ligne, `OfflineValues`) et envoyé en réseau (`m_PickupSlots`). 3 : COMM (wiki) |
| **Réserve pleine** | `HitPickUp` refuse le bonus : rien n'est remplacé. Fan Nitro, Front Runner et Drifter sont **perdus** si la réserve est pleine (CODE + COMM, guide et wiki Nitro) |
| Restes d'un système coupé | `CollectAnyPerkType` : si faux, on ne pouvait ramasser **que le même type** que le premier emplacement (toujours vrai en jeu). `mShieldsTiedToPickups` / `mFanPower` : ancien bouclier lié aux ramassages (« Craig's new shield system »). Champs d'améliorations jamais remplis (`mFansViral`, `mRepairBoostLevel2/3`, `mShuntUpgrade`…) |
| Dépôt sur la piste | un bonus n'est déposé que s'il lui reste **toutes** ses munitions (`HandleDropPickupOnTrack`) : un Bolt entamé n'est jamais déposé |
| Pile de Bolts | 3 tirs (4 avec Overbolt). Le Scatter Shot vide la pile d'un coup |
| Après un wreck | aucun vidage de la réserve dans `ResetAfterWrecked` (seulement le Bribe). Vidage trouvé au départ (`InitialiseImpl`) → **NON VÉRIFIÉ** |
| Pause entre deux tirs | 0,75 s (0,05 s entre deux Bolts) (v1) |

### 9.3 Shock (CODE)

- La sphère intérieure (`InnerRadius` 7) est **désactivée** : il n'y a qu'un coup mineur, dans la sphère extérieure
  qui grandit.
- Les dégâts du Shock sont lus au niveau Normal (v1).

### 9.4 Adaptive Shielding (`SafetyNet`)

- Plafond de conversions par vie (`MaxPickupsAbsorbable` 2, test `>`) ;
- les Bolts comptent par 3 ;
- un Shock n'active la conversion qu'une fois (« hit by both spheres of a shock only activates once », commentaire du
  code).

## 10. Mines : durée de vie et propriété après déconnexion

- **CODE** : la Mine décompte elle-même ses 60 s. Aucun nettoyage par joueur n'a été trouvé (seulement
  `KillAllPickups`). Elle garde `mFiringIdx`. C'est la machine de la **victime** qui la déclenche.
- **GAME** : elle reste après le wreck, l'élimination ou la déconnexion de son poseur (T8).
- **COMM** : **rien trouvé** sur ce sujet (forums, wiki, AMAX). Pas de différence connue entre LAN et AMAX : AMAX ne
  sert que de serveur de mise en relation, et les parties restent entre joueurs (OFF, architecture « master server »).
  PROBABLE pour la partie réseau.
- **NON VÉRIFIÉ** : à qui sont crédités le wreck et les points quand le poseur est parti, et si son indice de voiture
  peut être réutilisé.

## 11. IA et boss

- **Règles générales** : `cPerkSkillUsage` et profils `air.bin` (`POWERUPS.md` §8) (CODE).
- **Par adversaire** : `PerkAI` dans l'épreuve (`PreferredPickups`, `CharactersNeverTargetted`, `MaxPerkLevel`,
  `PerkToGrant` avec `GrantTimeMin/Max`). À défaut, les valeurs du personnage (CODE). Fichiers non trouvés dans
  `gamedata\xt` → NON VÉRIFIÉ.
- **Comportement des boss observé par la communauté** : §7.2 (une seule source).
- **Mod du boss** : lié à la voiture, permanent ; absent en Show Down pour Shannon (§4.3).

## 12. Modifications communautaires

| Nom | Auteur | Version et date | Plateforme | URL | Effet sur les bonus | AMAX |
|---|---|---|---|---|---|---|
| Amax Emu | aibot et contributeurs | en cours (news 2023-2025) | PC | https://amax-emu.com | aucun en temps normal ; patch du 1er avril 2025, temporaire (§6) | — |
| Blur fps unlocker | Amax-Emu (aibot) | ébauche du 2025-08-23, dépôt mis à jour le 2025-04-15 | PC | https://github.com/Amax-Emu/blur-fps-unlocker | corrige `FakePhysics` et la rotation des bonus au-delà de 30 FPS | prévu pour AMAX |
| BlurRebuilt | uKER | v1.6 (2026-11-02) | PC (DX11) | https://github.com/uKER/BlurRebuilt | aucun changement de gameplay annoncé (rendu, FPS, audio) | non précisé |
| NO-HUD-NO-EFFECTS | — | — | PC | https://www.nexusmods.com/blur/videos/1 | masque le HUD et les effets (visuel) | non précisé |
| Xenia game patches | communauté Xenia | — | Xbox 360 (émulateur) | https://github.com/xenia-canary/game-patches | rendu | sans objet |
| Sahin | 7tg | — | PS5 (jailbreak) | https://github.com/7tg/sahin | portage de la version PC | non précisé |
| Blur community patch | AMAX | annoncé, sans date | — | news AMAX | contenu coupé, nouveautés, équilibrage | — |
| Greffons AMI | Tobii et aibot | — | PC | news AMAX | points d'accroche C pour les mods | — |

**Aucun mod public modifiant les bonus** (dégâts, vitesses, projectiles, IA) n'a été trouvé. Les travaux de ce dépôt
(Railgun, HUD, bonus posé sur la piste) semblent être les premiers à le faire. Le seul précédent est le patch serveur
d'AMAX d'avril 2025, fait par « Timber » (timberstalker), dont les outils ne sont pas publics.

## 13. Matrice d'interactions (v3)

Ligne = ce qui agit ; colonne = la cible ou la situation. Légende :

| Code | Sens |
|---|---|
| **D** | détruit |
| **B** | bloque |
| **T** | traverse |
| **R** | repousse |
| **I** | interrompt |
| **Dg** | inflige des dégâts |
| **0** | aucun effet |
| **NT** | non testé |

Niveaux : C = CODE, G = GAME, O = OFF, M = COMM, P = PROBABLE.

| Agit sur → | Bouclier | Nitro actif | Mine posée | Shunt en vol | Bolt en vol | Décor mobile |
|---|---|---|---|---|---|---|
| **Shunt** | B (G, C, M) | I (G, C) | D, et meurt (G, C, M) | D mutuel (C) | D le Bolt, survit (C) | R (C) |
| **Bolt** | B (G, C) | 0 (C) | Dg ; 2 tirs = D (G, C, M) | Dg ; 2 tirs = D (C, M) | D mutuel (C, O) | R sans s'arrêter (C) |
| **Mine** (déclenchée) | B (G, C) | I (G, C) | 0 (G, C) | D le Shunt (C, M, O) | D le Bolt, survit (C, O) | — |
| **Mine lancée** | B (C) | I (C, P) | D mutuel (C, O) | D mutuel (C) | — | R (C) |
| **Shock** | B puis casse ; avec Shielding Efficiency : 2 dômes bloqués (G, C, D, O, M) | 0 (C) | **0 (C, G)** | 0 (C) | 0 (C) | R (C) |
| **Barge** | B (G, C, M) | Dg, perte de vitesse, pas I (G, C) | D + R (G, C, M) | D (G, C, M, O) | D (G, C, O) | R (C) |
| **Nitro arrière** (« Nitro Rift ») | **T** (G, C) | — | 0 (C) | 0 (C) | 0 (C) | NT |
| **Nitro Rift de Carver** | **T** (C) | NT | 0 (C) | 0 (C) | 0 (C) | NT |
| **Titanium Shield** (contact) | 0 contre un autre bouclier renforcé (C) | NT | 0 (C) | NT | NT | collision |
| **Repair** | soigne même sous bouclier (G, C) | 0 (C) | — | — | — | — |
| **Fan / Stopwatch** | aucun effet connu ; « pousse » : NON VÉRIFIÉ (§3) | — | — | — | — | — |

## 14. Contradictions

### 14.1 Résolues

| # | Sujet | Résolution | Sources |
|---|---|---|---|
| C1 (v2) | « Le Shock détruit une Mine » | **interprétation erronée, retirée.** Il n'y a aucune interaction, ce qui est cohérent avec le code | GAME (correction du joueur) + CODE |
| C2 (v2) | Bouclier qui survit à un Shock en ligne | Shielding Efficiency, valeurs de 2010 ; AMAX est revenu aux valeurs d'origine | DATA, CODE, OFF, COMM ×2 |
| C4 (v2) | Masse 10 000 du bouclier DoubleTap | classe jamais créée (correction de `POWERUPS.md` §11) | CODE |
| v2 §5.2 | « AMAX a réduit Shielding Efficiency » | vrai seulement du 1er au 4 avril 2025 (poisson d'avril) | OFF |
| v2 §5.3 | Noms d'Adaptive Shielding et de Magnetic Field | `SafetyNet` et `RoadSweeper` ; Safety Net = `ShieldedBoosters` | CODE + DATA + OFF (défis) |
| v2 Q4 | Show Down | Shannon en Opel Astra, sans mod | DATA + COMM |
| v2 Q7 | Fan Nitro avec une réserve pleine | Nitro perdu | CODE + COMM |
| v2 Q10 | Mods de carrière par type d'épreuve | course et boss seulement ; pas en Destruction | CODE + COMM |

### 14.2 Encore ouvertes

| # | Sujet | Sources en désaccord | Statut |
|---|---|---|---|
| C3 | « Fan pousse un véhicule protégé » | GAME contre CODE et COMM, qui ne connaissent pas de Fan qui pousse | NON VÉRIFIÉ ; question au joueur (§3) |
| C5 | « Modifications do not work in the pc DVD version » | wiki (2014) contre l'usage rapporté par le joueur et le CODE | NON VÉRIFIÉ, source unique, non datée |
| C6 | 30 ou 60 FPS, fréquence de référence du jeu PC | fps-unlocker (aibot) contre README BlurRebuilt (uKER) | CONTRADICTOIRE (§7.4) |
| C7 | Rang de Front Runner (26 ou 28) | deux pages communautaires | CONTRADICTOIRE, sans enjeu |

## 15. Tableau de suivi des recherches

| Question | Résultat | Sources | Code | Statut |
|---|---|---|---|---|
| A. Shield contre Shock | 1 dôme sans mod, 2 avec Shielding Efficiency ; AMAX = 2010 | wiki Shield, wiki Multiplayer, GameFAQs ×2, Giant Bomb, AMAX news | `PickupShield.cpp:173-205`, `PickupShock.cpp:246-272` | **résolu** |
| B. Fan contre Shield | aucun Fan qui pousse dans aucune source ; seuls les Nitro traversent | wiki Nitro, Power-Ups, guide, défis | `HitPickUp`, `AttemptHitByPickup` | ouvert (question au joueur) |
| C. Mine contre Mine | explosion : rien ; Mine lancée : D mutuel ; autres bonus : D ; Shock : rien | défis Master Exploder et Minesweeper, guide | `PickupBomb::Explode`, `PickupProjectileBase`, `RaceLogicLayer:2653` | **résolu** (sauf Mine contre décor) |
| D. Mine après déconnexion | aucune source externe | — | §10 | partiel (attribution inconnue) |
| E. Bolt | collisions et Overbolt / Scatter détaillés | défis Rear Guard et Fully Bolt, guide | §8.4 | **résolu** |
| F. Shunt | guidage `.aid`, arrière en ligne droite, 2 Bolts pour le détruire | guide, GameFAQs | §8.5 | **résolu** |
| G. Barge | détruit, pousse, ignore ; plusieurs voitures | défis, guide | §8.3 | **résolu** |
| Mods de carrière | 8 confirmés, Show Down, épreuves | wiki Career, guide, GameFAQs | §4 | **résolu** |
| Mods multijoueur | liste complète avec noms internes | wikis, défis, `multiplayer.bin` | §5 | **résolu** |
| AMAX | valeurs de 2010 ; patch du 1er avril 2025 | amax-emu.com/news | — | **résolu** |
| Mods communautaires | aucun mod public sur les bonus | Nexus, GitHub | — | **résolu** |

## 16. Sources

| Source | URL | Date | Ce qu'elle apporte | Fiabilité |
|---|---|---|---|---|
| AMAX Emu : news | https://amax-emu.com/news | 2025-04-01, 2025-04-04, 2025-12-31 | patch d'avril, annulation, projets | **officielle pour AMAX** |
| GitHub Amax-Emu | https://github.com/Amax-Emu | 2023-2026 | dépôts (fps-unlocker, binlog…) | officielle AMAX |
| Ébauche « Blur fps unlocker » (aibot) | https://github.com/Aib0t/write-ups/blob/main/blur-fps-unlock/readme.md | 2025-08-23 | FPS et `FakePhysics`, rotation des bonus, Nitro arrière | bonne (rétro-ingénierie avec code) |
| Wiki communautaire (sauvegarde Git de wiki.blurthegame.net) | https://github.com/Aib0t/blur-community-wiki (`mechanics/mods.html`) | ~2021 | textes, rangs et notes des mods multijoueur | bonne (texte du jeu recopié) |
| Blur Wiki : Modifications (Career), (Multiplayer), Shield, Shock, Nitro, Challenges, Power-Ups | https://blur.fandom.com/wiki/ | non datées | textes du jeu ; notes de joueurs | moyenne (recopies du jeu = fiables ; notes = à vérifier) |
| GameFAQs : guide de 91sportsfan (PS3) | https://gamefaqs.gamespot.com/ps3/959892-blur/faqs/60150 | v1.0, 2010-06-08 | interactions, boss, Show Down | bonne (une seule personne) |
| GameFAQs : « What mod do you use? » | https://gamefaqs.gamespot.com/boards/959893-blur/55173979 | 2010 | Overbolt 4 Bolts ; 2 dômes avec Shielding Efficiency | témoignages (Xbox 360) |
| GameFAQs : « mods not working in career mode ?? » | https://gamefaqs.gamespot.com/boards/959893-blur/55288264 | 2010 | pas de mods en Destruction | témoignages ×3 |
| Giant Bomb : Blur | https://giantbomb.com/wiki/Games/Blur | non datée | descriptions des mods | moyenne |
| PCGamingWiki : Blur | https://www.pcgamingwiki.com/wiki/Blur | — | patch 1.2 : Titanium Armour, Motormash et Nitros | bonne |
| BlurRebuilt (README) | https://github.com/uKER/BlurRebuilt | v1.6, 2026-11-02 | rendu et FPS ; « designed around 60 fps » | bonne pour son projet |
| PSNProfiles : trophée Modder | https://psnprofiles.com/trophy/321-blur/46-modder | — | texte de Shielding Efficiency | recopie |

Non consultés, ou sans résultat utile :

- Reddit : les recherches ne renvoyaient que d'autres jeux nommés « Blur » ;
- SuperCheats, Neoseeker : pas lus ;
- vidéos YouTube (vitrine des mods solo `C_rcvb0Dbs0`, tutoriel `e80jPSXb65s`) : repérées, pas regardées ;
- Steam Community : rien trouvé sur les bonus.

## 17. Questions ouvertes et tests vraiment nécessaires

### 17.1 Questions ouvertes

1. **C3** : de quel effet s'agit-il quand « Fan pousse un véhicule protégé » ? **Question au joueur**, pas un test.
2. La réserve est-elle conservée après un wreck ? La source ne la vide pas, aucune source externe n'en parle.
3. Mods de carrière en écran partagé : la source ne les active qu'en épreuve solo de course ou de boss.
4. Attribution d'un wreck par une Mine dont le poseur est parti.
5. Préférences de bonus des boss (`PerkAI`) : fichiers non trouvés.
6. Collision des Mines avec le décor.
7. Hérités de la v1 :
   - `do_charging` forcé à `false` dans l'exe ;
   - formules de chaque `cPerk*` ;
   - force de la faille de Carver (`RiftMin/MaxForce`, non lus par la classe).

### 17.2 Tests en jeu encore utiles (à ne lancer qu'après accord)

Tests de la v2 retirés :

| Test v2 | Raison |
|---|---|
| N1 | résolu par plusieurs sources (§5.2) |
| N2 | Shock contre Mine : l'interaction n'existe pas |
| N3 | Mine contre Mine : défi Master Exploder |
| N4 | Barge contre Nitro : déjà observé, cohérent avec le code |
| N5, N6 | Bolt : défi Rear Guard et code |
| N9 | devient une question au joueur |
| N10, N11 | code, données et descriptions concordent |

| # | Question | Hypothèses | Pourquoi les sources ne suffisent pas | Protocole | Résultats possibles |
|---|---|---|---|---|---|
| R1 | La réserve survit-elle à un wreck ? | a) conservée (aucun vidage dans le code) ; b) vidée par un chemin non lu | aucune source externe ; code incomplet | course perso, ramasser 3 bonus, se faire détruire (mur à pleine vitesse ou bonus adverses), regarder le carrousel à la réapparition | conservée → a) ; vide → chercher le chemin de vidage |
| R2 | Mods de carrière en écran partagé ? | a) inactifs (code : épreuve solo seulement) ; b) actifs (rapport du joueur) | contradiction entre le code et le rapport | écran partagé, Overbolt équipé en carrière, ramasser un Bolt | 3 tirs → a) ; 4 → b), il existe un autre chemin d'activation |
| R3 | Les autres boss ont-ils leur mod dans les 6 courses du Show Down ? | a) non (mod lié à la voiture) ; b) oui | voitures des boss non documentées | Show Down, observer Natalya (3 ou 4 dômes) et Ayumi / Harumi (Bolts en éventail ou non) | 3 dômes et Bolts séparés → a) |
| R4 | (facultatif) Mine dont le poseur est parti : qui marque ? | a) le poseur, même absent ; b) personne | aucune source | LAN à 3, poser une Mine, quitter, une 3e voiture passe dessus, lire le tableau de fin | — |

Toute mesure de durée (réactions, Nitro) doit noter le **FPS** (§7.4).

## 18. Statut des versions précédentes

- **v1** : conclusions conservées, confirmées par T1 à T8 et par les sources externes (§2).
- **v2** : conclusions conservées, avec ces corrections :
  - Shock contre Mine (retiré) ;
  - AMAX et Shielding Efficiency (le patch était temporaire) ;
  - noms des mods multijoueur ;
  - Show Down.
- **Anomalies v1** inchangées :
  - `FansToGain` et `TimeToGain` jamais lus ;
  - IA de `pickups.bin` coupée ;
  - aiguillage DoubleTap de la Shock ;
  - `case BOMB` sans `break` dans la Barge ;
  - texte « touché par… » coupé.
