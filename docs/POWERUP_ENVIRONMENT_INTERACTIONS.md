# Bonus et décor : cartographie des interactions

2026-11-18, **lecture seule**. Complète `POWERUP_EXTENSION_ARCHITECTURE.md` (étape « 3 bis ») et `POWERUPS.md` §12.

Niveaux de preuve :

| Étiquette | Sens |
|---|---|
| **CONFIRMÉ — CODE** | lu dans l'exe utilisé (`Blur.exe` `dcbd312a…`, désassemblage capstone) |
| **CONFIRMÉ — DONNÉES** | lu dans les fichiers du jeu |
| **CONFIRMÉ — GAME** | vu en jeu |
| **INDICE** | lu dans la source fuitée, pas vérifié dans l'exe |
| **HYPOTHÈSE** | interprétation à vérifier |
| **INCONNU** | non déterminé |

`src/` = `blur_source\BlurRebuilt\code\amax\game\`.

## 1. Les deux familles d'objets du décor

| Famille | Classe | Ce que fait une poussée de bonus | Dégâts | Niveau |
|---|---|---|---|---|
| **Objet dynamique** (cônes, barrières, caisses…) | `DynamicObjectActor` (`src/GameLogic/ActorStudioActors/DynamicObjectActor.cpp:905`) | `m_pBody->ApplyImpulse(Min(F, F × masse), position)`, puis **effet électrique** facultatif (sous-technique de rendu « électrique », couleur) | **aucun** : `m_DamageScale` n'est pas lu | INDICE |
| **Objet physique** (objets à éléments cassables) | `C_PhysicalObject` (`PhysicalObjectActor.cpp:1590`) | `ApplyImpulse(F × masse)`, effet électrique, puis **dégâts électriques** à tous ses éléments : `|F| × DamageScale` (`DamageAllElements`, `E_Damage_Electric`) | oui, si `DamageScale` > 0 | INDICE |
| Décor fixe (murs, sol, bâtiments) | maillage statique | aucune réaction ; c'est un obstacle pour les projectiles (§3) | — | INDICE + CODE (test de mur `0xBE4D10`) |

Champs de données d'un objet dynamique (`DynamicObjActor` / `DynamicObjType`, chaînes présentes dans l'exe : CODE) :

- `m_Weight`, `RespawnTimer`, `LifespanAfterDamage`, `SwapElementsOnCollision` (modèle abîmé),
  `VehicleDamage` ;
- animations `OnCollision` ;
- événements `OnCollision`, `OnPlayerCollision`, `OnDestroyed`.

Ce qui fait passer un objet dynamique à l'état « touché » (animation `ONCOLLISION`, minuterie de réapparition,
durée de vie après dégâts) : **le choc d'une voiture**, dans `RegisterCollision` (`:1461`). La poussée d'un bonus ne
le fait pas directement. Elle met l'objet en mouvement, et l'objet peut ensuite heurter quelque chose (INDICE).
**Réapparition** : un objet touché reprend sa place quand il est hors de vue depuis `RespawnTimer` secondes
(`UpdateLifeTime`, `Respawn` : `:1180-1213`) (INDICE).

## 2. Réglages des forces : `PerkForceEffects` (`pickups.bin` #868, CONFIRMÉ — DONNÉES)

Structure `RLPickupForceEffects`, 9 entrées `ForceEffect`. Champs :

- `ForceType` : Area, Forward ou Side ;
- `MaxForce`, `Radius`, `Time`, `ConeAngle`, `UpwardForce` ;
- `DamageScale` ;
- `ElectricalEffect`, `ElectricalEffectColour`.

| Entrée | ForceType | MaxForce | Radius | Time | UpwardForce | DamageScale | Électrique (couleur) | Lue par du code vivant ? |
|---|---|---|---|---|---|---|---|---|
| LargeExplosion | Area | 300 | 20 | 0,5 | 0,2 | 0,1 | non | **non trouvé** |
| SmallExplosion | Area | 150 | 10 | 0,2 | 0,2 | 0,1 | non | **non trouvé** |
| Shock | Area | 5 | 0 | 0 | 0,1 | **0** | oui (bleu) | oui (§3) |
| ShuntFire | Area | 10 | 2 | 0 | 0,1 | **0** | oui (rouge) | oui (§3) |
| ShuntExplode | Area | 100 | 10 | 0,1 | 0,2 | 0,1 | oui (rouge) | **non trouvé** |
| Barge | Area | 8 | 0 | 0,2 | 0 | **0** | oui (violet) | oui (§3) |
| Mine | Area | 100 | 10 | 0,1 | 0,2 | 0,1 | oui (jaune) | **non trouvé** |
| MineProjectile | Area | 10 | 2 | 0 | 0,1 | **0** | oui (jaune) | oui (§3) |
| Blindfire | Area | 10 | 2 | 0 | 0,1 | **0** | oui (rose) | oui (§3) |

**Conséquence** : toutes les entrées lues par le jeu ont `DamageScale` 0. **Aucun bonus n'abîme ni ne casse un
objet** ; il le pousse et l'électrise (DONNÉES + INDICE). Les entrées qui auraient fait des dégâts (explosions de
Mine et de Shunt, grandes et petites explosions) ne sont lues que par le système générique du §4, sans appelant
vivant connu.

`Radius`, `Time`, `ForceType`, `UpwardForce` et `ConeAngle` ne servent **que** dans ce système générique. Les bonus
vivants n'utilisent que `MaxForce`, `DamageScale` et l'effet électrique, et prennent leur propre rayon (§3).

## 3. Les chemins vivants

| Chemin | Bonus | Où | Comment | Limites | Niveau |
|---|---|---|---|---|---|
| **A. Couche « transparente » du rayon des projectiles** | Shunt, Bolt (et Railgun), Mine lancée vers l'avant | `C_PickupProjectile::CheckCollisions` (`0xBE6200`, CODE pour l'adresse) ; code `PickupProjectileBase.cpp:597-660` | le rayon de déplacement a deux filtres : **solide** (voitures, bonus, monde) et **transparent** (`kbDynamicObject`). Chaque objet dynamique ou physique traversé reçoit `C_DynamicObjectApplyImpulseMsg` (direction × `MaxForce` du type, électrique, `DamageScale`) ; le projectile **ne s'arrête pas** | aucune limite de nombre | INDICE (adresse de la fonction : CODE) |
| **B. Sphère de la Barge** | Barge | `C_PickupBarge::CheckDynamicObjects`, **`0xBE6970`** (CODE : prologue, et lecture de `Perks.Barge.MaxObjectsToDamage` en `0xBE6DD3`) ; appelée à chaque `Update` (`PickupBarge.cpp:162`) | sphère de rayon `BargeBalancingData.Radius` (7 m), filtre `kPerkCollisionFilter` → objets dynamiques et physiques poussés depuis le centre (`MaxForce` 8), électriques violets | **3 objets** au plus par appel (`Perks.Barge.MaxObjectsToDamage`, valeur `0x123BE94`, défaut 3 : CODE) | INDICE + CODE |
| **C. Sphère de la Shock** | Shock (chaque dôme) | `C_PickupShock::CheckDynamicObjects`, **`0xBE75D0`** (CODE : prologue, et lecture de `Perks.Shock.MaxObjectsToDamage` en `0xBE7A72`) ; appelée pendant la croissance du dôme | sphère du dôme (rayon qui grandit jusqu'à 14 m), filtre limité à `kbDynamicObject`, poussée `MaxForce` 5, électrique bleu | **3 objets** par appel (`0x123C038`, défaut 3 : CODE) | INDICE + CODE |

**Particularité des chemins B et C** (INDICE, `PickupBarge.cpp:254`, `PickupShock.cpp:320`) : la poussée n'est
envoyée que si l'objet est **déjà** dans l'ensemble `mDynamicsHit` (`if(!insResult.inserted)`, et `inserted` vaut vrai
pour une clé nouvelle). Lecture :

- la 1re image où l'objet est dans la sphère, il est seulement enregistré ;
- les images suivantes, il est **poussé à chaque image**, tant qu'il reste dans la sphère.

C'est probablement une inversion de test ; l'effet serait une poussée continue au lieu d'une poussée unique. Non
vérifié dans l'exe (HYPOTHÈSE).

**Effet électrique** : sous-technique de rendu « électrique », coupée par un message retardé de 1 à 2 s
(`DelayMessageToActorBySeconds(1 + aléa)`). Uniquement visuel (INDICE).

## 4. Le système générique (apparemment mort)

`C_ActorUtils::RegisterForceEffectWithActors(matrice, type)` (`ActorUtils.cpp:472-620`, INDICE) :

- sphère de rayon `Radius` ;
- poids de l'objet : `m_Weight` (objet dynamique), 50 (objet physique), sinon 99 999 ;
- trois formes :
  - **Area** : force décroissante avec la distance, + `UpwardForce` ;
  - **Forward** : cône à l'avant, z > 2|x| ;
  - **Side** : de côté, |x| > |z| ;
- message **retardé** selon la distance (`Time`) : l'onde « se propage » ;
- puis dégâts (`DamageScale`) et électricité.

Appelants dans la source :

- `PerkControllerActor` (Shock, ShuntFire) : classe **référencée nulle part ailleurs** ;
- `PickupMagnet` : prototype **non compilé** (`POWERUP_EXTENSION_ARCHITECTURE.md` §8).

Les entrées LargeExplosion, SmallExplosion, ShuntExplode et Mine (les seules avec `DamageScale` > 0) ne sont donc
lues par aucun code vivant connu. Présence de la fonction dans l'exe : **INCONNU** (pas de chaîne propre).

**Intérêt** : c'est un modèle complet d'onde de choc sur le décor (cône, propagation, soulèvement, casse). S'il est
compilé, un nouveau bonus pourrait l'appeler directement ; sinon, à réécrire dans la DLL sur le modèle des chemins
B et C.

## 5. Bonus par bonus

Cases : « Non identifié » = rien trouvé ; « Non applicable » = le bonus n'a pas d'objet ou pas d'effet de ce genre.

| Bonus | Force | Destruction | Collision décor | Animation / état | Effet indirect |
|---|---|---|---|---|---|
| **Shock** | oui : chemin C, `MaxForce` 5, au plus 3 objets à la fois (INDICE + CODE) | non (`DamageScale` 0, DONNÉES) | aucune collision : sphère de recherche seulement ; aucune interaction avec les Mines (source + GAME) | électrique bleu (INDICE) | objet poussé qui peut gêner une voiture (HYPOTHÈSE) |
| **Shunt** (en vol) | oui : chemin A, `MaxForce` 10 (INDICE) | non (`DamageScale` 0) | objets dynamiques : traversés et poussés ; murs : rebond rasant ou explosion (`CheckRebound`, `CollideWithEnvironment`) | électrique rouge | explosion sur un mur : **aucune** poussée du décor trouvée (l'entrée `ShuntExplode` n'est pas lue) |
| **Bolt** | oui : chemin A, `MaxForce` 10 | non | idem Shunt | électrique rose | Non identifié |
| **Railgun** (Bolt modifié) | oui : chemin A, force du Bolt | non | objets traversés ; murs traversés aussi (`0xBE654B`, CODE + GAME) | électrique rose | Non identifié |
| **Barge** | oui : chemin B, `MaxForce` 8, 3 objets à la fois ; pousse aussi les Mines (`MinMinePushForce` 50 000, DONNÉES) | non pour le décor ; détruit les bonus (Shunt, Bolt, Mine) | sphère de recherche seulement | électrique violet | Mines déplacées par la poussée (INDICE) |
| **Mine posée** | **Non identifié** : l'explosion (`Explode()`) n'est qu'un effet visuel ; l'entrée `Mine` n'est pas lue | non | corps de collision intérieur et extérieur : réagit aux **voitures** (déclenche, amorce) ; contact Mine contre Mine sans effet ; contact avec le décor non identifié | Non identifié | Non identifié |
| **Mine lancée** (vers l'avant) | oui : chemin A en vol, `MaxForce` 10 | non | traverse et pousse le décor mobile ; meurt contre un mur | électrique jaune | Non identifié |
| **Fan** | Non applicable (pastille de mode, aucun objet de bonus) | Non applicable | Non applicable | Non applicable | Non applicable |
| **Nitro** (avant) | Non identifié | Non identifié | Non applicable : c'est la **voiture** qui heurte le décor, par la physique normale (`DynamicObjectActor::RegisterCollision`) | Non identifié | plus de vitesse = chocs plus forts contre le décor (HYPOTHÈSE) |
| **Nitro arrière** et **Nitro Rift** (Carver) | Non identifié : `PickupNitrousReverse` et `PickupDoubleNitrous` ne touchent que des voitures | Non identifié | Non applicable | Non identifié | Non identifié |
| **Shield** | Non identifié | Non identifié | Non applicable (bulle sur la voiture) | Non identifié | Non identifié |
| **Titanium Shield** (Khan) | Non identifié | Non identifié | poids « Ultra » **entre voitures seulement** (`RaceLogicLayer.cpp:1805`, INDICE) | Non identifié | Non identifié |
| **SuperShield d'origine** (coupé) | change la **masse** de la voiture et lui applique des impulsions (`PickupSuperShield.cpp:142-310`, INDICE) | — | la masse changerait aussi les chocs contre le décor (HYPOTHÈSE) | — | non actif (type 10 repris par le Railgun) |
| **Repair**, **Stopwatch** | Non applicable | Non applicable | Non applicable | Non applicable | Non applicable |
| **Mods de carrière** | Scatter Shot : 3 Bolts → 3 rayons, chemin A (INDICE) ; Quad Shock : 4 dômes, chemin C ; Super Shunt, Armor Plating, Fan Nitro : Non identifié | — | — | — | — |
| **Mods multijoueur** | Splash Damage : sphère de la Barge × 1,2, donc aussi pour le décor (même rayon, INDICE) ; Last Gasp : Barge `MOD`, chemin B | — | — | — | — |
| **Prototypes coupés** (non compilés) | BlackHole, Bombard, Trap, Magnet : impulsions sur les **voitures** ; Magnet appelle le système générique | — | Magnet : `CheckObstacles` | — | modèles seulement |

## 6. Comparaison des architectures

- **Système commun** : un seul message, `C_DynamicObjectApplyImpulseMsg`, traité par les deux familles d'objets
  (INDICE), et un seul bloc de réglages, `PerkForceEffects`. Trois façons de trouver les objets :
  - rayon transparent des projectiles (A) ;
  - sphère de la Barge (B) ;
  - sphère de la Shock (C).

  B et C sont presque le même code : deux fonctions jumelles dans l'exe, même schéma autour de la lecture du
  maximum (CODE).
- **Logique propre** : aucun bonus n'a de logique de décor à lui en dehors de ces trois chemins. La Mine et le Nitro
  n'en ont pas.
- **Décor et projectiles** : **pas le même système**.
  - Les projectiles sont des objets du gestionnaire de bonus (`C_PickupsManager`).
  - Le décor est fait d'acteurs du monde (`DynamicObjectActor`, `C_PhysicalObject`), adressés par messages
    (`SendMessageToActor`, `DelayMessageToActorBySeconds`).
  - Les corps physiques se distinguent par leur `UserData` : `Actor`, `MineInner` / `MineOuter`, `Projectile`
    (INDICE).
- **Réseau** : aucune mention d'objets dynamiques ou physiques dans les événements réseau lus (`NetEvent*`,
  `RaceModeMultiplayer`, `GameModeNetwork`). Les poussées sont envoyées **localement**, sur chaque machine, par sa
  propre copie du projectile, de la Barge ou du dôme. **Le décor n'est pas synchronisé** : chaque joueur voit ses
  cônes voler à sa façon (INDICE : absence dans le code lu).
- **Réutilisable pour un nouveau bonus** :

| Besoin | Moyen existant | Nouveau crochet ? |
|---|---|---|
| Pousser le décor le long d'une trajectoire | hériter d'un projectile (chemin A, déjà actif) | non |
| Pousser le décor autour d'un point | hériter de la Barge (B) ou de la Shock (C) ; ou envoyer soi-même `C_DynamicObjectApplyImpulseMsg` | oui, pour l'envoyer depuis la DLL : adresses de `SendMessageToActor` et de la recherche de corps à relever (les appels dans `0xBE6970` et `0xBE75D0` y mènent) |
| Changer la force ou la couleur électrique | `PerkForceEffects` dans `pickups.bin` (données seules, entrée du parent) | non |
| Dégâts au décor (casse) | `DamageScale` > 0 dans l'entrée du parent → `C_PhysicalObject` reçoit des dégâts électriques | non (données). Effet réel : INCONNU, à tester |
| Plus de 3 objets par Barge ou Shock | valeurs `0x123BE94` / `0x123C038` (variables `Perks.*`) | écriture mémoire par la DLL |
| Onde qui se propage, cône, soulèvement | système générique (§4) | oui (s'il est compilé), sinon réécriture |
| Activer un mécanisme du circuit, une animation | événements `OnCollision` et animations des objets dynamiques, déclenchés par les **chocs de voiture** | oui : rien ne relie un bonus à ces événements |

## 7. Pistes de test (proposées, non lancées)

| # | Question | Protocole | Résultats possibles |
|---|---|---|---|
| E1 | La Barge pousse-t-elle les objets **en continu** (`!inserted`) ou une seule fois ? | Barge près d'une rangée de cônes, en vidéo | poussée qui dure 0,4 s → continue ; à-coup unique → l'exe diffère de la source |
| E2 | Bolt, Shunt : le décor est-il poussé sans arrêter le tir ? | tir à travers des cônes | cônes électrisés et poussés, tir qui continue → chemin A confirmé |
| E3 | `DamageScale` > 0 casse-t-il des objets ? | copie de test seulement : `PerkForceEffects.Barge.DamageScale` 0 → 0,1 (une valeur), Barge contre un objet cassable | éléments cassés → casse possible par les données |
| E4 | Le décor est-il synchronisé ? | LAN, deux écrans, une Barge dans des cônes | positions différentes → calcul local confirmé |

## 8. Sources

- Source : `PickupProjectileBase.cpp:597-660`, `PickupBarge.cpp:150-275`, `PickupShock.cpp:220-345`,
  `ActorUtils.cpp:472-620`, `DynamicObjectActor.cpp:80-120, 895-925, 1180-1215, 1440-1470`,
  `PhysicalObjectActor.cpp:1590-1620, 1860-1880`, `RLDatabase.h:715-750`, `PerkControllerActor.cpp`.
- Exe :
  - chaînes `Perks.Barge.MaxObjectsToDamage` (`0xEE1194`, variable `0x123BE70`, valeur `0x123BE94`) et
    `Perks.Shock.MaxObjectsToDamage` (`0xEE12D8`, `0x123C014`, `0x123C038`) ;
  - lectures en `0xBE6DD3` / `0xBE7A72` ; fonctions `0xBE6970` / `0xBE75D0` ;
  - chaînes `PerkForceEffects`, `ForceEffectType`, `DamageScale`, `RespawnTimer`, `LifespanAfterDamage`,
    `SwapElementsOnCollision`, `DynamicObjType` présentes.
- Données : `pickups.bin` #868 `PerkForceEffects`.
