# Étude du comportement des bonus d'origine de Blur

2026-11-17, **lecture seule** : aucun fichier du jeu, aucune copie, aucune DLL modifiés. Ce document est la suite de
**`POWERUPS.md`** (référence complète : données, classes, réseau, HUD, effets) et de **`POWERUPS_DONNEES.md`** (toutes
les valeurs). Il ne recopie pas ces documents : il ajoute ce qui manquait (interactions, nature réelle du Fan et du
Stopwatch, bouclier, anomalies) et propose un plan de tests.

## 1. Périmètre et niveaux de certitude

Types 0 à 9 : Nitrous, Shock, Shunt, Blindfire (Bolt), Barge, Bomb (Mine), Repair, Shield, Fan, Stopwatch. Le type 10
(SuperShield) est un cas à part, aujourd'hui réutilisé par le mod Railgun dans `Blur_test` : son rôle d'origine est
décrit dans `POWERUPS.md` §1.3 et §3.2. Pas de nouveau bonus ici.

| Étiquette | Sens |
|---|---|
| **CONFIRMÉ — CODE** | lu dans le **code compilé** (`Blur.exe`, désassemblage) ; si seule la source fuitée le montre, on écrit **SOURCE** |
| **CONFIRMÉ — DONNÉES** | lu dans les fichiers du jeu |
| **CONFIRMÉ — JEU** | vu en jeu |
| **SOURCE** | lu dans le code source fuité (juin 2010, retouches `[Blur2PC]` possibles), pas vérifié dans l'exe |
| **DÉDUCTION** | soutenu par plusieurs éléments |
| **INCONNU** | pas encore déterminé |
| **CONTRADICTION** | sources, exe, données ou jeu en désaccord |

Chemins : `src/` = `blur_source\BlurRebuilt\code\amax\game\`.

## 2. Ce qui est déjà établi (renvois)

| Sujet | Où | Statut |
|---|---|---|
| Types, sous-types, 7 poignées de niveau par type, classes et pools | `POWERUPS.md` §1-2 | DONNÉES + CODE (`CreatePickup` `0xBAAD50`) |
| Réglages par niveau | `POWERUPS_DONNEES.md`, `POWERUPS.md` §3 | DONNÉES |
| Dégâts lus au niveau Normal ; réactions `FakePhysics` | `POWERUPS.md` §3.1, §12 | SOURCE |
| Shock = aiguillage DoubleTap → 3 dômes Normal placés par l'hôte | `POWERUPS.md` §3.2, §13 | SOURCE |
| DoubleTap coupé (`do_charging = false`) | `POWERUPS.md` §11 | SOURCE + JEU (jamais déclenchable) |
| IA : `pickups.bin` mort, `air.bin` actif | `POWERUPS.md` §8 | SOURCE |
| Réseau : victime ou tireur décide, hôte pour la Shock | `POWERUPS.md` §13 | SOURCE |
| Rétroviseur sans particules ni lumières | `POWERUPS.md` §7 | SOURCE + DONNÉES |
| HUD : `GetPerkInfo` `0xC55320`, seuil 100, planches | `POWERUPS_HUD.md` §8 | CODE + JEU |
| Bonus posé sur la piste : modèle avec textures intégrées | `ESSAI_HUD_SHIELD_PICKUP.md` | JEU |

## 3. Correction importante : Fan et Stopwatch ne sont pas des armes

La demande les traite comme des bonus à effet (forces, ralentissement du temps). **Ce n'est pas le cas dans Blur.**

- **Fan** (type 8) = la **pastille de fans** des défis de fans (« Fan Demand ») du mode carrière.
- **Stopwatch** (type 9) = la **pastille de temps** des épreuves à points de contrôle.

Preuves (**SOURCE**, et **CONFIRMÉ — CODE** pour le HUD) :

- `VLC_Pickups::HitPickUp` (`VLC_Pickups.cpp:1209`) : `if(type == FAN || type == STOPWATCH) return false;` — ils
  n'entrent **jamais** dans la réserve et ne peuvent donc pas être tirés.
- `GetPerkInfo` rend `NULL` pour 8 et 9 (`0xC553DB`, **CONFIRMÉ — CODE**). C'est logique : ils n'ont pas de case dans
  le carrousel, puisqu'ils n'y entrent jamais. Ce n'est pas un oubli.
- Ramassage (`PickupPositionActor::CheckPickup` / `AwardPickup`, `PickupPositionActor.cpp:1304-1412`) : **joueur 0
  seulement** (`vehicleIndex != 0 → false`), les IA ne les prennent pas.
  - Stopwatch : envoie `E_PickupMessage_CollectStopwatch` à la voiture puis à tous. Le mode de course ajoute le temps
    au compteur de point de contrôle. `VLC_NewScoring.cpp:4163` donne aussi un « close call » si le temps restant
    était < 0,5 s.
  - Fan : logique « Fan Demand » (`VLC_FanDemands.cpp:1214`). Variantes visuelles `Golden`, `Aggressive`, `Faded`.
- Ils sont **exclus en dur** du tirage aléatoire des emplacements (`0xB5B492`, **CONFIRMÉ — CODE**).

Les questions « Stopwatch contre un Bolt », « Fan pousse les mines », etc. sont donc **sans objet** : aucun code ne
relie ces pastilles aux autres bonus ou à la physique.

**Anomalie** : les champs de données `FanBalancingData.FansToGain` (1) et `StopwatchBalancingData.TimeToGain` (0)
n'ont **aucun lecteur** dans la source, en dehors de la liaison `XT_FIELD`. Les montants viennent du mode de course et
des défis, pas de `pickups.bin`. Statut : **SOURCE** (vestige, non vérifié dans l'exe).

## 4. Fiches des huit bonus utilisables (compléments)

Activation commune (**SOURCE**) : `VLC_Pickups::Update` lit les touches, puis `ActivatePerk` → `StartPerk` choisit le
sous-type puis `CreatePickup`. Pause entre deux tirs : 0,75 s (0,05 s de Bolt à Bolt). Bouclier et Réparation partent
toujours. Détails : `POWERUPS.md` §3.

| Bonus | Nature | Cible / direction | Délai → durée | Ce qui l'arrête | Touché pendant l'activation |
|---|---|---|---|---|---|
| Nitro | effet sur soi (`C_PickupEffectsNitrous`, mis à jour à chaque image) ; arrière = onde | soi ; arrière : cône arrière 10 m (`RiftRangeSquared` 100, `ForwardDot` 0,2) | 0 → 1,3 s (courbe) | fin de courbe ; **un Shunt ou une Mine qui touche coupe le Nitro en cours** (`DisableActiveNitrous`, VLC_Pickups.cpp ~1690 / ~1935) | coupé (Shunt, Mine) ; ralenti seulement par un Nitro arrière (`DisableActiveNitrous(true)`) |
| Shock | 3 dômes posés devant la cible | la cible (`mCurrentTargetIdx`) ; dômes sur l'`.aid` | 1 s de charge → dômes de 1,5 s | durée de vie ; plafond de 12 | — |
| Shunt | projectile à tête chercheuse | voiture devant (`0x44DB20`) ; arrière : derrière | 0,5 s → 40 s au plus | touche ; mur ; autre bonus (santé) ; Barge (§5) | — |
| Bolt | 3 projectiles droits | ligne de tir | 0,1 s → 10 s | voiture, mur, sortie du monde, autre bonus | — |
| Barge | onde autour de soi | ellipse de 7 m autour du tireur | 0,2 s → 0,4 s | durée | — |
| Mine | objet posé 5 m derrière ; avant = lancée | qui passe dessus | 0,2 s → 60 s | déclenchée, détruite, durée, plafond de 30 | — |
| Repair | effet direct sur soi | soi | 0 → instantané | — | marche **même sous bouclier** : `RegisterHitByPickup` direct, pas `AttemptHitByPickup` |
| Shield | bulle | soi | 0 → 6 s | durée ; santé ≤ 0 (seule la Shock l'entame, §5) ; relancer = redémarrer | — |

**Ce que répare la Réparation** (**SOURCE**) : `C_VehicleLogicRepairMsg(AmountToRepair = 400)` à la voiture. Elle ne
coupe ni une réaction `FakePhysics` en cours, ni un ralentissement de Shock, ni un blocage de bonus : aucun code de
réparation ne les touche. **DÉDUCTION** à vérifier en jeu (T5).

## 5. Interactions (mécanismes trouvés)

### 5.1 Bouclier (`VLC_Pickups::AttemptHitByPickup` / `RegisterShieldedPickup`, **SOURCE**)

```
if (mShieldTime > 0 && type != NITROUS)  -> RegisterShieldedPickup   (bloqué)
else                                      -> RegisterHitByPickup      (touché)
```

- **Bloque tout ce qui passe par `AttemptHitByPickup`** : Shunt, Bolt, Mine, Shock, Barge, Mini-mines. Il bloque
  dégâts **et** réactions (aucun `FakePhysics` dans la branche bloquée), et donne un effet `ShieldedSpecialFX`.
- **Ne bloque pas le Nitro arrière d'un adversaire** (exception `!= NITROUS`) : son onde passe à travers le bouclier.
  **SOURCE**, à vérifier en jeu (T1).
- **Usure** : « Shield no longer takes damage ». Seule la **Shock** retire `DamageInflicted` (100) à `mShieldHealth`
  (50). Elle **casse donc le bouclier**, après avoir été bloquée elle-même. Les autres coups ne l'usent pas.
- **Projectile déjà en vol** : seul compte l'état du bouclier **au moment du coup** (test sur `mShieldTime` à
  l'impact). Un bouclier activé juste avant l'impact protège.
- Le projectile bloqué meurt quand même (Bolt : `KillPickup(-1, HIT_VEHICLE)` après `RegisterHit`, `0xBECB2A`,
  **CONFIRMÉ — CODE**).

### 5.2 Bonus contre bonus (santé et dégâts, `PickupProjectileBase.cpp:490-560`, **SOURCE**)

Chaque projectile et chaque mine a une santé (`BalancingData.Health`) et inflige `GetDamageToApply()` (son
`DamageInflicted` Normal). Au contact, chacun prend les dégâts de l'autre. Le plus récent est crédité de la
destruction (`iKilledThem`).

| Contact | Valeurs (santé / dégâts) | Résultat calculé |
|---|---|---|
| Bolt → Mine | 50 / 50 contre 100 / 100 | le Bolt meurt ; la Mine survit à 50 → **il faut 2 Bolts** |
| Bolt → Shunt | 50 / 50 contre 100 / 100 | le Bolt meurt ; le Shunt survit à 50 → **2 Bolts** |
| Shunt → Mine | 100 / 100 contre 100 / 100 | les deux meurent |
| Shunt → Shunt | 100 / 100 | règle spéciale : pas de `CollideWithPickup` entre deux Shunts (`!(SHUNT && SHUNT)`), les deux meurent |
| Mine avant (lancée) → Mine | 100 / 100 | les deux meurent |

**Barge** (`PickupBarge.cpp:170-206`, **SOURCE**) : elle **détruit** tous les Shunts (`CollideWithPickup`), Bolts et
Mines dans son ellipse (`IsInsideEllipse`, marge 3). Elle **pousse** aussi les mines physiques (`MinMinePushForce`
50 000). Une Barge **ne touche pas une autre Barge** : une Barge n'est pas un objet dans la liste des bonus actifs. Les
deux Barges frappent chacune la voiture d'en face (**DÉDUCTION**). Petit défaut : le `case E_PICKUP_TYPE_BOMB` n'a pas
de `break` avant un bloc en commentaire, sans conséquence (vestige).

**Shock et Mines** : aucune référence aux mines dans `C_PickupShock` / `C_ShockManager`. La Shock ne touche que les
voitures (**DÉDUCTION** forte).

### 5.3 Matrice (attaquant en ligne → situation de la victime)

| | Bouclier actif | Nitro en cours | Réaction en cours | Projectile / mine adverse |
|---|---|---|---|---|
| Shunt | bloqué | **coupe le Nitro** | nouveau `FLIP_FORWARD` (un coup par projectile) | dégâts mutuels (§5.2) |
| Bolt | bloqué | — (pas de `DisableActiveNitrous`) | `SPIN_45` | dégâts mutuels |
| Mine | bloquée | **coupe le Nitro** | `SPIN_360` | dégâts mutuels |
| Shock | **casse le bouclier** (bloquée la 1re fois) | — | freinage (cumul par coups consécutifs, `RecoveryTimeSpeedMod`) | aucun |
| Barge | bloquée | — | `ROLL` / `JINK` | **détruit** Shunt, Bolt, Mine |
| Nitro arrière | **non bloqué** | ralentit seulement | `JINK_NITROUS` | — |
| Repair | — | — | rien d'annulé (DÉDUCTION) | — |
| Fan / Stopwatch | sans objet (§3) | | | |

**Cumuls** :

- deux bonus **différents** se cumulent ;
- un même projectile ne touche qu'une fois chaque voiture (`mVehiclesHitMajor/Minor`) ;
- les blocages de bonus prennent le plus long (`if(mDisablePickups < …)`).

## 6. IA (compléments)

- **Ramasser** (`cPerkLogic`) : bonus devant, à moins de 25 nœuds `.aid`, hauteur −0,5 à +2 m, réserve < 3. Les IA ne
  ramassent **ni Fan ni Stopwatch** (§3).
- **Tirer** (`cPerkSkillUsage`) : profils `air.bin` (`AIPerkSkillz` Offensive / Defensive / Avoidance, `AIPerkPrefs`)
  choisis par le CSV de difficulté de l'épreuve. Délais selon `Offensive` (Shunt : 8 / 6 / 4 / 2 s). Bolt par 3, puis
  4 s de pause.
- **Informations en plus** : les évaluateurs lisent directement les positions, l'avancement et la réserve des autres
  véhicules (`PickupInfo`), et les tracés `.aid`. Un joueur ne voit pas tout cela (**SOURCE**).
- **Difficulté** : par les profils `air.bin` du CSV de l'épreuve. Pas de règle cachée de plus trouvée (**DÉDUCTION**).
- **Non étudié en détail** : les formules exactes de chaque `cPerk*` (Bolt, Mine, Shield…) → **INCONNU**, prochaine
  lecture.

## 7. Réseau (compléments)

- **Joueur qui quitte pendant un effet** : les tirs portent l'identifiant de connexion (`JoinId`). Le comportement
  d'un projectile dont la cible part n'a pas été lu → **INCONNU**.
- **Deux coups en même temps** : chaque coup est un événement séparé (`HitByPickup`), appliqué dans l'ordre d'arrivée.
  Le bouclier est testé à chaque coup (**SOURCE**).
- **Coup vu par deux machines** : le premier qui annonce le coup fait taire les autres copies (`NinjaKill`). Une
  victime « décidante » et un tireur « décidant » ne se mélangent pas sur un même type (`IsDefenderCentric`).

## 8. Physique

Rien de neuf par rapport à `POWERUPS.md` §12. Les voitures reçoivent :

- des **animations scriptées** (`FakeVehiclePhysics`) ;
- un **freinage forcé** (Shock, `FakeSpeed`) ;
- des **poussées réelles** seulement pour le Nitro (courbe de poussée) et le SuperShield (masse, poussées).

Le décor reçoit de **vraies forces** (`PerkForceEffects`). Distinction : **SOURCE**.

## 9. HUD, effets, son

Voir `POWERUPS.md` §4-7 et `POWERUPS_HUD.md`. Ajouts :

- **Fan et Stopwatch** n'ont pas de case HUD (§3). Le Stopwatch a sa propre image `stopwatch` dans `ui_common.bpr` et
  son propre son (`BaseMessageHandler.cpp:5321`).
- **Bonus posés sur la piste** : chaque type a son modèle `<type>pickup.model`, avec ses propres textures intégrées,
  indépendantes du HUD (**CONFIRMÉ — JEU**, essai du Bouclier).
- **Rétroviseur** : bonus posés sur la piste visibles, d'après l'utilisateur (**CONFIRMÉ — JEU**). Les traînées et
  particules des projectiles au rétroviseur ne sont pas encore observées.

## 10. Anomalies

| Anomalie | Nature | Statut |
|---|---|---|
| `FansToGain`, `TimeToGain` jamais lus | vestige (montants ailleurs) | SOURCE |
| `AIPickupController` (`pickups.bin`) jamais utilisé (`Update` → `return`) | fonction désactivée | SOURCE |
| Shock toujours tirée en sous-type DoubleTap, dômes en Normal | choix de conception (aiguillage) | SOURCE ; JEU (aucune différence visible) |
| `DamageInflicted` des niveaux DoubleTap / Reversed ignorés | choix de conception | SOURCE |
| Bouclier : « no longer takes damage » sauf Shock | choix de conception (changé en cours de développement) | SOURCE |
| Nitro arrière traverse le bouclier | volontaire ou oubli : **à vérifier** | SOURCE |
| `do_charging = false` (DoubleTap) | fonction désactivée | SOURCE ; exe **INCONNU** (non désassemblé) |
| Icônes vectorielles `perk_*_x2` jamais référencées | vestige probable du DoubleTap | DONNÉES |
| `case BOMB` sans `break` dans la Barge | vestige sans effet | SOURCE |
| Texte « touché par… » coupé | fonction désactivée | CODE (`0xC60971`) |

## 11. Questions ouvertes

1. Le **Nitro arrière** traverse-t-il vraiment un bouclier en jeu ?
2. `do_charging` est-il bien forcé à `false` dans l'exe ? Il faut désassembler la lecture des touches de
   `VLC_Pickups::Update` (autour de `0x47BE80`).
3. Formules d'évaluation de chaque `cPerk*` de l'IA.
4. Projectile dont la cible quitte la partie ; mine dont le poseur est éliminé.
5. Réparation pendant une réaction : rien n'est annulé (DÉDUCTION) ?
6. Les sous-types `SUB_MOD` / `SUB_MOD_REVERSED` : créés par `CreatePickup` comme des Bolts normaux. Qui les
   choisit ? Non trouvé → **INCONNU**.

## 12. Plan de tests en jeu (à ne lancer qu'après accord)

Copie : `Blur_test_hud` (données d'origine pour les bonus), course perso, IA.

| # | Question | Conditions et actions | Attendu (code) | Autres résultats possibles | À observer |
|---|---|---|---|---|---|
| T1 | Le Nitro arrière traverse-t-il le bouclier ? | 2 joueurs en LAN (ou une IA derrière soi avec un Nitro) ; activer le Bouclier, l'autre tire un Nitro vers l'arrière | **touché** : petit écart, ralentissement | bloqué | réaction `JINK` malgré la bulle |
| T2 | La Shock casse-t-elle le bouclier ? | être 1er avec un Bouclier actif ; une IA tire une Shock | 1er dôme bloqué, bulle cassée, dômes suivants subis | bulle intacte | disparition de la bulle avant 6 s |
| T3 | 2 Bolts pour une Mine | Mine posée par une IA devant ; tirer 1 Bolt, puis 2 | 1 Bolt : la Mine reste ; 2 Bolts : elle explose | 1 suffit | la mine après chaque tir |
| T4 | La Barge détruit les projectiles | Shunt d'une IA qui arrive ; Barge au dernier moment | Shunt détruit, pas de coup | coup quand même | explosion du Shunt sans réaction de la voiture |
| T5 | La Réparation annule-t-elle une réaction ? | touché par un Shunt, Réparation pendant le saut | santé remontée, saut continué | réaction coupée | animation complète |
| T6 | Le Shunt coupe le Nitro | Nitro en cours, Shunt reçu | poussée coupée | Nitro continue | vitesse juste après le coup |
| T7 | Le Bouclier activé au dernier moment | Shunt d'une IA à moins de 25 m (alerte) ; Bouclier | bloqué | touché | `ShieldedSpecialFX` |

## 13. Conclusion

1. **Comprend-on les dix bonus ?** Oui pour l'essentiel. Huit sont des armes ou des effets (fiches `POWERUPS.md`
   + §4). Le Fan et le Stopwatch sont des **pastilles de mode de jeu**, pas des bonus utilisables (§3) : c'est la
   correction principale de cette étude.
2. **Confirmé dans l'exe** : création des bonus, tirage, HUD, Bolt (dans l'exe) ; la plupart du comportement reste
   **SOURCE**.
3. **Interactions connues** (§5) :
   - le bouclier bloque tout sauf le Nitro arrière ;
   - seule la Shock casse le bouclier ;
   - destruction mutuelle par la santé : 2 Bolts par Mine ou Shunt ;
   - la Barge détruit les projectiles et les mines ;
   - le Shunt et la Mine coupent un Nitro en cours ;
   - la Réparation passe même sous bouclier.
4. **IA** : ramassage sur l'`.aid`, choix par `air.bin`, accès à l'état complet des autres.
5. **Réseau** : inchangé (victime / tireur / hôte selon le type).
6. **Physique** : animations scriptées pour les voitures, forces réelles pour le décor.
7. **Désactivé** : DoubleTap, IA de `pickups.bin`, texte « touché par… », montants de Fan / Stopwatch dans les données.
8. **Tests prioritaires** : T1 (Nitro arrière et bouclier), T2 (Shock et bouclier), T3 (2 Bolts par Mine).
9. **Contradictions** : aucune trouvée entre source et exe sur les points vérifiés (HUD, tirage, création, Bolt).
