# Blur : cahier des charges

Les projets envisagés, ce qu'il faut pour chacun, et comment savoir qu'ils sont réussis.
Les faits techniques sont dans [CONNAISSANCES.md](CONNAISSANCES.md) ; ce document n'en recopie que ce
qui sert à décider.

Dernière mise à jour : 2026-10-19.

## Règles communes à tous les projets

1. **Le jeu installé n'est jamais modifié.** Toute modification se teste dans une copie du dossier du jeu,
   lancée hors ligne.
2. **Rien de ce qui change le gameplay ne va en ligne** (AMAX) sans accord explicite : risque d'écarts
   entre joueurs.
3. **Lecture avant écriture** : un format n'est réécrit qu'une fois qu'on le relit à l'identique
   (aller-retour octet pour octet, ou relecture par notre propre parseur sans erreur).
4. **Une hypothèse reste une hypothèse** tant qu'elle n'a pas son test de validation (voir chaque projet).
5. Chaque découverte met à jour `CONNAISSANCES.md` dans le même commit que le code.
6. **Copie de test coupée du réseau** : la copie garde le chargeur Lua d'AMAX (`d3d9.dll`, `lua_hooks.asi`,
   plugins dont `solo`), mais **jamais** `amax_auth.asi`, `amax_pfp.dll`, `blur_rpc.dll` ni `amax\config`
   (redirection des serveurs). Un fichier modifié ne peut donc pas atteindre une partie en ligne. Le script le
   vérifie à chaque `-Run` (accord de l'utilisateur le 2026-10-19 ; sans le plugin `solo`, impossible de
   lancer une course perso seul).

### Fichiers à risque

| Catégorie | Fichiers | Risque |
|---|---|---|
| Démarrage | `Blur.exe`, `d3d9.dll`, `amax/`, `cache/*.pak` (signés : `.sig`) | jeu ou AMAX qui ne démarre plus |
| Solo **et** en ligne | `racingphysics.bin`, `amax.bin`, `pickups.bin`, `multiplayer.bin` (`pack_version`, `matching_version`), `levels/*`, `actorpack.xt`, `finalracebook.bin`, `air.bin`, `events/*.csv` | triche, désynchronisation entre joueurs |
| Surtout solo | `singleplayer.bin`, `events/*_easy\|medium\|hard.csv`, `splitscreen.bin` | faible hors ligne |
| Cosmétique, local | textures, skins, `.loc`, interface | faible (mais dans des `.pak` signés) |
| Progression | sauvegarde, fans, rang | à ne pas toucher (synchronisée par AMAX ?) |

Classement établi à partir des données ; l'effet réel en ligne n'est **pas vérifié**.

## État des capacités

| Capacité | Lire | Écrire |
|---|---|---|
| `.pak` | oui | pas besoin pour l'instant : sans `gamedata.pak`, le jeu lit tout en clair (testé en jeu). Le pak passe AVANT un fichier en clair |
| `.bin` / `.xt` (KSLF) | oui, à 100 % | oui : reconstruction, valeurs, clonage, ajout à une liste. **Testé en jeu** (route + listes ajoutées, chargées et jouées) |
| `.loc` (textes) | oui | oui : ajout de textes par clé (`blurloc.add_text`, utilisé par le bandeau de musique, testé en jeu) |
| Textures de `.model` | oui | oui (réinjection, jamais testée en jeu) |
| `.aid` (IA / logique de piste) | oui, à 100 % de la structure | oui : réécriture identique (33/33) et **inversion testée en jeu** (Haruna) |
| `.level*` (géométrie, collision) | structure ; collision lue (`bmb_levelphysics`, format Gravity d'après la source) | oui : rampes et murs ajoutés à la collision (`addramp`, testé en jeu), niveaux complets via le Map Builder (projet J) |
| `.bpr` (images d'interface) | oui | oui : remplacement et ajout d'images (`blurbpr.rebuild`, testé en jeu : pochettes) |
| `.baf` (sons) | oui | oui : ajout et remplacement de morceaux ADPCM (`blurbaf`, testé en jeu : playlists) |
| Mémoire en course | position, vitesse, rotation, voiture, profils IA | (lecture seule, par règle) |

---

## Projet A : cartographie des données de course (en cours)

**Objectif** : lire en direct tout l'état d'une course, de façon fiable.

**Déjà fait** : liste des véhicules, voiture de chacun, position, vitesse, orientation, profils IA (paliers).

**Reste à trouver**, par priorité :

1. Classement en course (1er, 2e…)
2. Palier IA actif (lequel des 10)
3. Bonus détenus par chaque voiture (et leur utilisation)
4. Tour en cours, progression sur la piste, état de course (départ, course, arrivée, épave)
5. Accélérateur et frein du joueur

**Méthode** : `deeprec.py 40` (enregistre les objets véhicule, pilote, physique et tout ce qu'ils pointent)
pendant une séquence jouée et notée par l'utilisateur : 0-10 s gaz à fond ; ~10 s freinage fort 2 s puis
roue libre 2 s ; ramasser un bonus, le garder, l'utiliser ; un dépassement ; position du HUD notée au début
et à la fin. Puis analyse hors ligne.

**Validation** : chaque donnée doit coller à ce que montre le HUD, ou à une grandeur mesurée, sur au moins
2 courses différentes. Piste pour le classement : la ligne logique des `.aid` (projet B) donne une progression
de référence, à comparer aux champs candidats.

**Livrable** : `blur_live.py list` affiche les nouvelles données ; tableau à jour dans `CONNAISSANCES.md` §5.

---

## Projet B : données de piste (`.aid`), validation en course

**Objectif** : confirmer en jeu ce que le décodage des `.aid` laisse penser.

**Étapes** :

1. Enregistrer une course sur Amboy (`blur_live.py recall` ou `deeprec.py`).
2. Superposer les positions des voitures au tracé (attention : Z inversé dans les `.aid`).
3. Vérifier que les IA suivent les tronçons, et lesquelles prennent les jonctions.
4. Relier le passage des portes (Start, InterOne, InterTwo) aux changements de tour ou de chrono (`+0x638`).

**Validation** : écart moyen voitures ↔ tracé inférieur à la largeur de route ; passage de la porte Start
au même moment que le changement de tour au HUD.

**Inconnues à lever en chemin** : le rôle de `+0` des lignes et de `+36`/`+40` des nœuds, les valeurs des
règles de jonction, le bit 0x400.

---

## Projet C : Haruna en sens inverse : **fonctionne en jeu** (2026-10-19)

**Objectif** : une course qui monte Haruna (la route d'origine descend), jouable avec des IA.

**Ce qu'il faut** :

| Élément | Travail | Bloquant actuel |
|---|---|---|
| `.aid` inversé | inverser l'ordre des nœuds de chaque section, échanger Start et Finish, inverser la ligne logique et sa table | écrire un `.aid` ; comprendre et retourner les champs orientés des nœuds (directions, décalages gauche/droite) |
| Grille de départ | 20 positions en bas, orientées vers le haut | écrire un `actorpack.xt` (KSLF) |
| Route et épreuve | nouvelle route dans `amax.bin` (un emplacement libre existe : `JPN_MHaruna_0`), texte `.loc`, vignette ; pour l'afficher : ajout à `MultiplayerConfig.routes` (course perso) et/ou une épreuve dans un palier de `SP_TierData` | écrire du KSLF |
| `Routes` de `.levelphysics` | sans doute pour les remises en piste | format non décodé |
| Décor | flèches, barrières, bonus et déclencheurs pensés pour la descente | à évaluer en jeu |
| Chargement | fichiers en clair prioritaires sur les paks (lu dans le code) | à confirmer sur une copie |

**Avant tout** : repérer les circuits inversables (sauts et rampes à sens unique) hors jeu, via les noms de
tronçons (`*Ramp*`) et les ruptures de hauteur le long des 11 lignes des `.aid`.

**Tri des routes (2026-10-19, hors jeu, sur indices)** — détail dans `blur_extracted/routes/reversibility.json` :

| Verdict | Routes |
|---|---|
| Saut sur la boucle principale : non inversable tel quel | `uk_brighton_2` (déclencheurs de saut + remise en piste en cas d'échec) |
| Doute | `usa_la_downtown_1`, `usa_la_downtown_6` (`Building_TopofJump` à 40 m du tracé) |
| Rampe ou saut seulement sur un raccourci : inversable sans ce raccourci | `usa_amboy_1`, `usa_la_longbeachdocks_3`, `usa_la_river_3`, `usa_la_river_6` |
| Aucun indice de saut | les 26 autres, dont **`jpn_mharuna_1`** |

Limites : « aucun indice » ne veut pas dire inversable. Une bosse, une marche, une barrière ou un raccourci à
sens unique sans objet nommé passent inaperçus, et les hauteurs des `.aid` sont parfois aplaties. Montées les
plus raides à l'envers (pente de la descente d'origine, sur les hauteurs des `.aid`) : Sausalito 1 (34 %),
Russian Hill (33 %), Gracia 1 (31 %), **Haruna (29 %)**. Seul un essai en jeu (copie hors ligne) tranche.

**Fait (2026-10-19, hors jeu)** : `aidreverse.py` génère `jpn_mharuna_7.aid` (dans
`blur_extracted/mods/haruna_reverse/`, avec `comparaison.png`). Vérifications :
relu intégralement ; points des 11 lignes au même endroit (écart max 1e-6 m) ; même convention d'axe latéral que
le jeu ; longueurs conformes au nouveau trajet (écart médian 4 mm) ; départ en bas (~500 m), arrivée en haut
(~1050 m), portes et intermédiaires échangés ; table logique valide ; inverser deux fois redonne l'original
(à des arrondis près). Incertitude restante : le champ « virage » (+0) des lignes, changé de signe par hypothèse.

**Fait aussi (hors jeu)** : `make_haruna_reverse.py SORTIE` produit les 4 fichiers du mod, rangés comme dans le
dossier du jeu (`blur_extracted/mods/haruna_reverse/files/`) :
`gamedata/levels/jpn_mharuna/jpn_mharuna_7.aid`, `gamedata/levels/jpn_mharuna/actorpack.xt` (+ listes #67 solo et
#68 multi : 20 voitures en bas, tournées vers le haut, textes Start/Finish échangés), `gamedata/xt/amax.bin`
(+ route `JPN_MHaruna_7`, copie de `_1` avec ces deux listes), `gamedata/xt/multiplayer.bin` (route ajoutée à la
course perso). Relecture complète : seuls ces ajouts changent, toutes les références se résolvent (`grille.png`).
Choix et limites : hauteur des voitures = sol estimé (cônes et lampadaires proches) + 1 m ; écartement latéral
réduit de moitié car la route fait 20 m en bas contre 40 m en haut (aucun chevauchement) ; zones « Hand of God »
laissées en haut ; nom affiché « Ascent » / « Montée » (texte `CRN_MOUNT_HARUNA_2` laissé par les devs) ; vignette identique.

**Copie de test** : `make_test_copy.ps1` (simulation par défaut ; `-Run` pour agir ; `-Restore -Run` après le test).
Il sauvegarde d'abord `%APPDATA%\bizarre creations\blur\save` + `settings.xml` (**sauvegarde partagée entre toutes
les installations** : la copie de test écrit dans la même), copie le jeu dans `Jeux_WII\Blur_test` avec **AMAX hors ligne**
(voir règle 6) et pose les fichiers du mod. `-Update -Run` met à jour une copie existante (AMAX + mod) sans
refaire la sauvegarde. Simulation vérifiée : 125 fichiers / 7,28 Go, rien d'écrit.

**Reste pour le projet C** : vérifier le texte d'arrivée replacé ; bonus et HUD (ci-dessous) ; puis d'autres routes.

**Déroulé du test en jeu** (dans la copie) :
1. le jeu démarre-t-il (AMAX hors ligne : choisir « Skip » à la connexion) ?
2. Online → Local Network → Custom Game (F1 pour lancer seul) → Game Settings : lieu « Mount Haruna »,
   circuit « Ascent » / « Montée » (= notre route) ?
3. départ en bas, voitures tournées vers le haut, IA qui montent ?
4. passage des points intermédiaires puis arrivée en haut ?
5. noter tout comportement bizarre (remise en piste, voitures qui tombent, IA qui braquent à contresens).

**Première étape proposée** (faite) : écrire `Haruna_reverse.aid`, puis le relire avec `blurroute.py` (aucune erreur,
jusqu'au dernier octet) et le tracer. Cette étape ne touche pas au jeu.

**Validation finale** : la course se lance depuis la copie du jeu, les IA montent sans se bloquer, l'arrivée
est détectée en haut.

---

**À faire plus tard (demandé le 2026-10-19)** :
- déplacer les **bonus** (power-ups) pour le sens montant (listes de l'actorpack de la route) ;
- corriger le **HUD** (mini-carte, textes de départ/arrivée…) pour le sens inversé.
- idée : **vignette animée** (flèche qui bouge). Pas de GIF possible dans un `.bpr` (textures fixes) : il faudrait
  plusieurs images + un plugin Lua AMAX qui les alterne dans l'écran du menu (scripts des menus pas encore trouvés).

## Projet D : DoubleTap (combiner deux bonus)

**Objectif** : savoir si le DoubleTap coupé peut être réactivé.

**Étapes** :

1. Lire les réglages DoubleTap de `pickups.bin` (`pickups/PickupLevel/...`) et les comparer aux versions normales.
2. Dans Ghidra, trouver le code qui lit le champ `DoubleTap` des `PickupType`, et voir s'il est encore appelé.
3. Selon le résultat : modification des données seulement, ou du code (bien plus lourd).

**Validation** : en jeu (copie), deux bonus identiques donnent l'effet DoubleTap défini dans les données.

**État (2026-10-19)** : données complètes ; effets vivants via les capacités de boss ; déclencheur « deux bonus »
inaccessible sans modifier l'exe (chargeur de `debug_values.xml` orphelin). Essais possibles par les données :
(1) « tout en DoubleTap » (`PickupType.Normal` → niveau DoubleTap) ; (2) capacité de boss sur n'importe quelle voiture.

---

## Projet E : skins de voitures

**Objectif** : modifier la livrée d'une voiture.

**État** : extraction et réinjection des textures faites (`blurtex.py`), **jamais testées en jeu**.
La Focus RS voulue au départ n'a pas de texture de livrée (peinture par shader).

Voitures avec une texture de livrée, donc modifiables tout de suite : bmw_1seriestii_race_natalya,
chevrolet_camaross_stock_rymer, corvette_zr1, foose_stallion, nissan_skyliner34ztune,
opel_astraextreme_shannon, renault_meganesportr26, lotus_exigecup260, nissan_350znismo, ford_gt,
ford_supervan, hhr, bmw_1seriestii_stock.

**Validation** : la texture modifiée apparaît en jeu (copie, fichiers non empaquetés).

---

## Projet F : partage avec la communauté (plus tard)

**Objectif** : publier le décodeur KSLF (`blurxt.py`) et la doc des formats, qui manquent à la commu.

**Avant de publier** : nettoyer le code, retirer nos notes de travail personnelles, choisir une licence.
Ne publier aucun fichier du jeu. Le dépôt reste privé tant que ce n'est pas décidé.

---

## Projet G : choix des chemins par les IA (embranchements) — à faire

Constat (2026-10-22, Concrete Basin = LA River 3) : au premier pont après la grille (~370 m du départ), le raccourci à
gauche (`bank`, jonction `JunctionSidebank`) n'est pris que par 7 à 12 IA sur 19 au premier tour (13 à 16 sur une course
de 3 tours) ; celles de tête passent à droite, le joueur les double toutes en coupant. Chaque jonction a une règle :
type 5 (3 valeurs) ou 9 (2 valeurs), ou aucune (drapeaux 0x40). LA River 3 : `JunctionSidebank` 5 [3, 0, 3],
`JunctionsSwerve` 5 [4, 0, 3], `Junctionside` 9 [3, 5], `Junctionjump` 5 [2, 0, 2], `Junctionbridge` 5 [4, 0, 4],
`JunctionLeftBank` / `JunctionSide` sans règle.

Étapes :
1. Lire dans l'exe (lecture seule) le code qui applique ces règles : sens de « type 5 / 6 / 9 / 2 » et des valeurs
   (probabilité ? condition de place, de vitesse, de nombre de voitures ?).
2. Mesurer la vitesse réelle de chaque branche (enregistrements du joueur et des IA).
3. Régler les règles pour que les IA prennent le chemin le plus rapide (données du circuit seulement), un essai mesuré.
4. Plus tard : inverser aussi les jonctions pour les routes à raccourcis (Russian Hill : parking retiré pour l'instant).

## Projet H : corrections des routes inversées — avant les prochains circuits

**Test en jeu du premier lot (2026-10-24)** : Bayshore Route, Urban Belt, Central Sprint et Highrise Ring ont été
testées dans `Blur_test`. Défauts observés : vignettes blanches pour toutes les routes inversées ; sur Tokyo
Bayshore Reverse, la voiture traverse le sol et tombe dans le vide ; texte de grille à l'envers ; bonus orientés
dans le mauvais sens. Le comportement des IA n'a pas encore été évalué.

**Tokyo corrigé (2026-10-24, confirmé par l'utilisateur en jeu)** : le placement vertical des 40 véhicules a été
recalé sur les hauteurs interpolées des lignes du `MainLoop` en conservant l'écart de la grille originale. Le
contrôle hors jeu donne +0,34 à +0,97 m au-dessus des lignes ; `RouteNumber=2` est conservé et les UID clonés sont
distincts du pack source.

**Lot suivant installé, test en attente** : Sausalito 1 Reverse et Sausalito 2 Reverse. Le build contient aussi les
neuf routes déjà installées afin de préserver les références de menu, les actorpacks partagés et les vignettes.

**Retour de test Sausalito (2026-10-24)** : Sausalito 1 Reverse fonctionne ; en Sausalito 2 Reverse, tous les véhicules tombent
dans le vide avant le lancement de la course. `RouteNumber=2` est conservé et le bloc Route 2 de la collision existe ; les UID des deux listes clonées sont uniques et absents du pack source. Comparaison au `MainLoop` : la grille multi reverse reste proche (1,5 à 1,8 m horizontalement, hauteur relative -1,5 à +1,2 m) ; les places solo 13 et 15 sont à environ 28 m et 21 m des lignes (la grille solo source est à environ 12 m et 6 m). Le bloc Route 2 est lisible comme un petit mesh type 0, mais aucune surface de ce mesh ne se trouve sous les grilles ; il ne donne donc pas la vraie hauteur du sol. Cause non confirmée : vérifier quelle liste de départ le Custom Game sélectionne et mesurer le sol réel au spawn avec `trackrec.py` si nécessaire.

Ordre de travail :
1. Corriger et tester les vignettes de toutes les routes inversées (rebuild BPR à entrées ajoutées déjà validé hors jeu).
2. Tokyo est confirmé corrigé par l'utilisateur; si la chute réapparaît, mesurer la vraie hauteur en roulant avec
   `trackrec.py` (le bloc collision Route 2 reste de type 2 et non décodé).
3. Remettre les textes de grille dans le bon sens.
4. Orienter les bonus selon le sens inverse.
5. Vérifier le comportement des IA sur les quatre routes ; si elles roulent correctement, mesurer puis améliorer
   leurs trajectoires. Ne pas faire cette amélioration avant discussion avec Claude.

**Validation attendue** : Sausalito 1/2 se sélectionnent et roulent sans défaut; toutes les vignettes sont visibles,
textes et bonus sont orientés dans le sens de course, puis les IA suivent les circuits. Pas de nouveau lot et pas de
commit avant ces corrections et la validation en jeu.

## Projet I : passer à la musique suivante avec un bouton — fait (validé en jeu le 2026-10-26)

**Demande** : pendant une course, permettre au joueur de passer au morceau suivant sans attendre la fin du morceau.

**Point de départ confirmé dans `music_controller.dat`** : le graphe possède `InGameLicensedMusicNextTrackScript`,
qui sélectionne l'index suivant et appelle `InGameLicensedMusicPlayScript`. `RaceStartScript` démarre la lecture au
départ. Aucun lien entre une entrée clavier/manette et le script suivant n'est encore établi dans les plugins Lua du
projet.

Étapes :
1. Trouver, sans modifier `Blur.exe`, une API ou un événement AMAX/Lua pour détecter un bouton pendant une course.
2. Relier cet événement au mécanisme suivant de la playlist, en arrêtant proprement le morceau en cours et sans
   déclencher plusieurs morceaux simultanément.
3. Tester clavier et manette dans la copie hors ligne, avec les playlists originale et personnalisée.

**Contraintes** : ne rien modifier dans le jeu installé ni dans `Blur.exe`; conserver le comportement normal en
ligne et ne tester que dans `Blur_test`. Solution et faisabilité à discuter avec Claude avant implémentation.

**Précisions de l'utilisateur (2026-10-26)** : une touche clavier ou manette pour **passer** le morceau et une pour
**pause / reprise** ; **délai de 2 s** entre deux appuis (anti-spam) ; **un son court comme indicateur**. Candidats
parmi les sons jamais utilisés par le jeu (78 sur 2 732, voir CONNAISSANCES) : `FE_Left` / `FE_Right` / `FE_Move`
(bips de menu, `frontendui.baf`), `HUD_PerksCountdown` (`ingameui.baf`).

## Projet L : popup « morceau en cours » — fait (bandeau publié, v1.1 du pack musique, 2026-11-13)

**Demande (communauté, 2026-11-13)** : afficher le titre du morceau quand la musique change en course.
**Étude (voir CONNAISSANCES, « Étude : popup »)** : l'affichage est probable (cloner un élément texte du HUD,
`ChangeText` avec une clé `.loc` écrite par le pack) ; le Lua ne peut pas savoir quel morceau joue. Piste : le Lua
choisit le morceau via l'option `music_type` si le moteur transmet n'importe quelle valeur au graphe.
Étapes : 1. sonde en jeu (`music_type` 2/3, texte `.loc` et clé absente) ; 2. selon le résultat, conception
(qui enchaîne les morceaux, gestion des pauses) ; 3. intégration au pack. Rien à promettre avant l'étape 1.

## Projet J : circuits d'autres jeux dans Blur — à étudier (session à part)

**Idée de l'utilisateur (2026-10-26)** : importer des circuits d'autres jeux de course à structure proche (NFS Hot
Pursuit Wii, Split/Second) comme nouvelles cartes de Blur, en usage personnel uniquement (rien de ces jeux dans le
dépôt ni partagé).

Chaîne envisagée :
1. Extraire la géométrie du circuit (modèle + textures) de l'autre jeu : le plus difficile, propre à chaque jeu
   (Hot Pursuit Wii : `Jeux_WII\NFS_HP_WII_TOOLS`, `nfs_extracted`).
2. Convertir et nettoyer (Blender : échelle, route séparée du décor).
3. Construire la carte avec Blur Map Builder (MDPRO) : rendu, collision, `.aid` ; ne garder que ses fichiers produits
   (pas son exe modifié).
4. Poser la carte dans `Blur_test` comme les routes inversées (ville, route, menu, vignette, nom, tracé lumineux).

Limites attendues : géométrie Wii basse définition, tracé IA à retoucher, pas d'objets dynamiques ni d'effets.
**Première étape** : un circuit simple de Hot Pursuit Wii, voir ce qui s'extrait et ce que Map Builder accepte.

**Rendre les cartes NFS plus belles (shaders de Blur, plan du 2026-10-27)** : nos objets partent tous du gabarit
`sign_wetfloor.model` (`default_NB_NL_NV.fx`, le shader de 643 objets de Blur). Les beaux shaders des circuits
(`Road_*`, `RoadTwoSpec*`, `SpeedTree*`, `Puddle_*`, `default_LN_*`…) ne sont que dans `levels/*/level.levelrender`
(non décodé). Étapes : (1) essayer, dans Blur_test, des gabarits d'objets à autre shader : `AnimatedNeon_NL_NV`
(néons, ex. `trafficlighttypef`), `Water_NL_NV` (rivières, `dynamicwaterlevel`), `default_NL_NV` (avec relief,
`sunlounger`) ; (2) plusieurs matériaux par modèle ; (3) éclairage d'ombre précalculé dans les couleurs de sommets ;
(4) à plus long terme : décoder `.levelrender` pour la route et les bâtiments éclairés.

## Projet K : feuille de route reverse et IA (2026-11-09)

Ordre décidé par l'utilisateur :
1. **Murs et rampes pour toutes les maps reverse** : généraliser ce qui a été fait sur Route 66 (murs invisibles,
   rampes ajoutées à la collision comme East River Run), map par map.
2. **Tracés des IA** : l'utilisateur roule des tours sur chaque reverse (`trackrec.py`) ; ces tours servent de
   ligne de course IA (`.aid`) à la place de l'inversion automatique.
3. **IA entraînée** : essayer d'entraîner notre propre pilote (lecture seule de la mémoire pour l'état ; entrées
   clavier/manette simulées ; Blur se met en pause sans focus, donc fenêtre au premier plan ou copie dédiée).
4. **Buff des IA via les paramètres de Blur** : profils IA (`rldatabase.bin`, profils déjà repérés en mémoire),
   sans patch d'exe, testé dans `Blur_test` uniquement.

   **Idée de l'utilisateur (2026-11-09)** : un agent qui observe la façon de jouer des joueurs sur une longue période
   (trajectoires, mouvements, esquives, usage des bonus) puis « fusionne » ces données avec l'IA du jeu.
   Faisabilité : l'IA de Blur est pilotée par des données (lignes `.aid`, profils et paramètres), pas par un modèle
   qu'on peut remplacer sans patch d'exe. La fusion passe donc par la traduction des données observées :
   - trajectoires → lignes de course `.aid` (moyenne des meilleurs tours par segment) ;
   - mouvements / esquives → paramètres d'agressivité, de dépassement, d'évitement des profils IA ;
   - bonus → fréquence et contexte d'usage (quel bonus, à quelle distance, cible devant/derrière) → paramètres d'armes des profils.
   À faire : (a) identifier en mémoire l'état des bonus et les événements de tir ; (b) enregistreur long
   (`trackrec.py` étendu) ; (c) cartographier quels paramètres de profil IA influencent quoi (un essai mesuré par paramètre).
   **Fusion, pas copie (2026-11-09)** : pour éviter 19 clones, chaque IA garde son profil d'origine et on le
   mélange avec le style du joueur selon un poids propre à chaque IA (ex. 20 % à 80 %) ; lignes `.aid` variées
   (plusieurs tours du joueur, décalages latéraux) ; usage des bonus mélangé de la même façon.
   **Décision (2026-11-09)** : le joueur roule toujours en physique d'origine (pas de modif de `racingphysics.bin`).
   Les IA reprennent son style « simplifié » : géométrie, freinages, bonus, esquives ; dans les grands virages serrés
   où leur adhérence les avantage, elles gardent leur propre passage.
   Collecte : uniquement en LAN / `Blur_test` ou sur ses propres courses, jamais via lecture mémoire pendant les
   parties en ligne AMAX (risque anti-triche, données d'autres joueurs).

## Projet M : bonus « Railgun » (idée de l'utilisateur, 2026-11-16) — prototype installé, à essayer en jeu

**Objectif** : un tir unique, très rapide, longue portée, qui traverse murs et véhicules (touche toutes les voitures
sur sa ligne). Détails techniques : CONNAISSANCES, « Bonus Railgun ».

**Faisabilité** : un 12e type de bonus demande de réécrire le jeu (énumération `E_PICKUP_TYPE` partout). Prototype :
**le Bolt devient le Railgun** dans Blur_test (`railgun_install.py`, `natif/railgun`), réversible (`--remove`).

**Validation en jeu (copie)** :
1. un Bolt ramassé = **1** tir ; `railgun.log` dit « patched » 6 fois ;
2. tir sur deux voitures alignées : les deux sont touchées (compteur « vehicle hit(s) passed through ») ;
3. tir contre un mur / dans un virage : le tir continue derrière (compteur « wall hit(s) ignored ») ;
4. pas de plantage sur 3 courses avec IA ; noter ce qui gêne (tir qui meurt derrière les bâtiments, IA trop fortes).

**v1 validée en jeu par l'utilisateur (2026-11-16)**. **v2 (construite)** : bonus à part à la place du SuperShield
(Bolt rendu normal), délai 1,5 s, hitbox 0,8, dégâts 50 × 1,5 / 1,0 / 0,5, bouclier cassé, mines / Shunts / orbes
détruits, HUD blanc titane, nom RAILGUN, son de charge et de tir. Validation v2 : le Railgun apparaît sur la piste et
au HUD ; tir 1,5 s après l'appui ; journal « railgun(s) fired / vehicle hit(s) / wall(s) / shield(s) downed » ;
moins de dégâts sur la 3e voiture traversée ; les IA ne gardent jamais de Railgun.

**À faire (demandes de l'utilisateur, 2026-11-17)** :
- **Visuel** : charge = mélange de la charge du Shunt (`ShuntBuild2.model`, effet d'écran, secousse caméra) et des
  anneaux du Nitro arrière (`NitroReverseBlastRings.model`) ; projectile = spirale comme l'orbe mais plus grosse,
  blanc titane, avec une traînée bien visible qui s'efface lentement en particules le long de la trajectoire ;
  impact = perte de contrôle comme l'orbe (déjà le cas : le Railgun est un projectile Bolt), effet d'impact aussi
  sur les murs et objets traversés ; nouveau symbole (HUD case 104, bonus sur la piste `ShieldSuperPickup.model`).
- **Options LAN** (écran « Power-up Options » de la partie perso : Nitro, Barge, Shunt, Bolt, Repair, Shield, Mine,
  Shock) : ajouter une ligne « Railgun » On / Off qui pilote son apparition.
- **Son d'impact** sur voitures et objets : l'utilisateur cherche un son (un seul pour les deux, ou deux).

**Suite possible** : visuel propre (SpecialFX du niveau Normal) ; Railgun rare (une partie des Bolts seulement :
crochet sur l'attribution du bonus) ; jamais en ligne (gameplay différent entre joueurs).

## Journal

| Date | Avancée |
|---|---|
| 2026-09 | Format `.pak` résolu, `.loc` décodé, textures extraites et réinjectées |
| 2026-10-18 | KSLF résolu (noms, valeurs, références) ; chaîne mémoire des véhicules ; position, vitesse, voiture ; profils IA en mémoire |
| 2026-10-19 | Orientation ; formats « CP » des niveaux ; `.aid` décodés en entier (33/33) ; restes du DoubleTap ; dépôt GitHub créé |
| 2026-10-19 | Nœuds `.aid` compris : en-tête (position, largeur, axe latéral avec dévers) + 11 lignes parallèles (fraction, hauteur, longueur) |
| 2026-10-19 | Menus : listes explicites (`MultiplayerConfig.routes` = 30 routes jouables, paliers de carrière) ; 70 routes déclarées pour 33 `.aid` |
| 2026-10-19 | KSLF : encodeur des noms (aller-retour identique, 49 fichiers) ; modification de valeurs sur place (`blurxt.py --set`), non testée en jeu |
| 2026-10-19 | Écrivain KSLF complet : reconstruction identique (49/49), clonage, ajout à une liste ; test « JPN_MHaruna_7 » ajoutée au menu de course perso (hors jeu) |
| 2026-10-19 | Tri des 33 routes pour l'inversion : 1 saut sur boucle (Brighton 2), 2 doutes, 4 rampes sur raccourci, 26 sans indice (dont Haruna) ; hauteurs `.aid` parfois aplaties |
| 2026-10-19 | Système de fichiers : le dossier du jeu (couche 0) est consulté avant les paks (couche 1) ; chemins où poser nos fichiers |
| 2026-10-19 | Écriture des `.aid` : réécriture identique des 33 fichiers (`blurroute.build`) |
| 2026-10-19 | Haruna inversé généré (`aidreverse.py` → `jpn_mharuna_7.aid`) et vérifié hors jeu |
| 2026-10-19 | Mod Haruna inversé complet hors jeu : grilles en bas (actorpack), route `JPN_MHaruna_7`, menu course perso (`make_haruna_reverse.py`) |
| 2026-10-19 | Script de copie de test hors ligne (`make_test_copy.ps1`), sauvegarde Blur protégée ; simulation OK |
| 2026-10-19 | 1er essai en jeu : la montée n'est pas sélectionnable. La copie sans AMAX n'a plus le plugin `solo` (partie perso seul, F1). Menu course perso lu dans le code. Route renommée « Ascent » (texte inutilisé des devs), Index 3 |
| 2026-10-19 | Copie de test : AMAX hors ligne (chargeur Lua + plugin `solo`, sans module en ligne), `-Update` |
| 2026-10-19 | 2e essai : le menu affiche seulement « Descent ». Lu en mémoire : 30 routes, pas de `JPN_MHaruna_7` → fichiers en clair ignorés. Essai suivant : chemin `gamedata/gamedata/...`, puis Process Monitor |
| 2026-10-19 | Process Monitor : le pak passe avant le dossier (en clair = secours pour fichiers absents). Copie de test : les 588 fichiers de `gamedata.pak` posés en clair, pak à mettre de côté |
| 2026-10-19 | Sans `gamedata.pak` (tout en clair) : le jeu démarre, 31 routes au menu, « Ascent » (`JPN_MHaruna_7`) chargée. `make_test_copy.ps1` le fait seul |
| 2026-10-19 | 1re course « Ascent » : départ sur la grille d'origine (en haut), chute dans le lac. Uids des acteurs clonés renouvelés (`make_haruna_reverse.py`) |
| 2026-10-19 | 2e course : départ sur notre grille du bas, mais chute à travers la route (`RouteNumber` 7 = pas de physique de route). Passé à 1 |
| 2026-10-19 | 3e course : route solide, mais une colonne hors route et le fond de grille au-delà de la collision. Grille centrée et resserrée |
| 2026-10-19 | Descent enregistrée en roulant : le nœud `.aid` est un bord de la route. Inversion `.aid` corrigée (lignes IA exactes), grille replacée sur le sol mesuré |
| 2026-10-19 | **Ascent fonctionne en jeu** (départ, IA, bonus). Textes Start/Finish replacés selon la règle de l'original (Finish était ~90 m trop loin) |
| 2026-10-19 | `Tester le mod.bat` / `Jouer en ligne.bat` : sauvegarde et restauration automatiques autour des tests (essais à blanc OK) |
| 2026-10-19 | Format `.bpr` (images d'interface) décodé et réécrit ; image de présentation « Ascent » ajoutée (`JPN_MHaruna_7`) ; copie de test : `root.pak` aussi en clair |
| 2026-10-19 | Image Ascent noire (ajoutée en fin de fichier) → emplacement d'un doublon réutilisé. Grilles avancées à la porte, textes Start/Finish replacés, mesures sur l'axe central |
| 2026-10-19 | `.bpr` : changer la taille des noms décale toutes les images (corruption). Correctif : remplacement en place d'un doublon. Relevé des lignes Start/Finish en Descent en cours |
| 2026-10-19 | `.bpr` : les données commencent juste après les noms (décalage de 1 392 o corrigé, vu grâce à l'image en jeu). Image Ascent régénérée, logo en bas à gauche |
| 2026-10-19 | Image Ascent vue en jeu. Lignes peintes mesurées en Descent : textes et grille calés dessus. Encodeur DXT1 maison (flèche plus lisse) |
| 2026-10-19 | Images OK en jeu, textes OK. Arrivée trop tôt / grille dans la porte : portes Start/Finish déplacées sur les lignes peintes (`move_gate`) |
| 2026-10-19 | Portes déplacées : départ et arrivée « mieux mais pas parfait » (petit écart restant, jugé acceptable). Ascent utilisable |
| 2026-10-19 | Générateur commun `make_reverse.py` (toutes les routes en une passe ; Haruna identique à l'octet). 2e route : **Brighton 1 inversée** (`UK_Brighton_1R`, « Route 1 Reverse »), 1re boucle, vérifiée hors jeu |
| 2026-10-19 | Brighton 1R en jeu : ligne/porte OK, mais grille multi dans l'ancien sens (places `NewStartPosition*` ignorées). Places reconnues par leur type ; corrigé |
| 2026-10-19 | **Brighton « Route 1 Reverse » fonctionne en jeu** : bon sens, bien placés. 1re boucle inversée. Suite : routes à une jonction (support des jonctions dans `aidreverse`) |
| 2026-10-19 | Limite d'IA en LAN : `max_ai_per_console` 4 → 19 (seul : jusqu'aux 18 IA du menu). Plus de 20 voitures : limite moteur, non |
| 2026-10-19 | **18 IA seul en LAN : confirmé en jeu** (`max_ai_per_console` = 19). Au-delà de 20 voitures : limite du moteur |
| 2026-10-19 | Scripts Lua des menus trouvés dans `Blur.exe` (archive BZUI, 144 scripts) et extraits. Plafond Max AI 18 = constante ; plugin AMAX `ai19` livré avec le mod de test |
| 2026-10-19 | **19 IA en course perso seul (20 voitures) : confirmé en jeu** (plugin `ai19` + `max_ai_per_console`) |
| 2026-10-19 | Essai 49 IA : le jeu coupe à 20 voitures (plafond moteur). Retour à 19 |
| 2026-10-19 | IA, essai 1 : référence Hard mesurée (Brighton 1, 3 tours). Profils Difficulty 1-10 identiques. CSV « élite » (Tier 10 Skills partout) prêt |
| 2026-10-19 | IA, essai 1 : profil élite = mêmes temps que la référence (< 1 s). Rythme imposé par le Race Director. Suite : essai 2 (rattrapage / plafond de vitesse) |
| 2026-10-19 | IA, essai 2 prêt : ligne des facteurs à 1,2 pour toutes les IA (Hard), profils d'origine |
| 2026-10-19 | **IA, essai 2 : facteurs 1,2 → IA nettement plus rapides** (médiane −13 s sur 3 tours). La ligne des facteurs = plafond de vitesse |
| 2026-10-19 | IA, essai 3 : facteurs 1,5 ≈ 1,2 (gain saturé, limite physique des IA). Plafond utile ~1,2 |
| 2026-10-19 | IA : essais clos, jugés **échec** par le joueur (testé sur une autre carte : le rattrapage n'est pas vraiment corrigé, un autre paramètre est en jeu). Copie remise au Hard d'origine. Suite : DoubleTap |
| 2026-10-19 | DoubleTap : données complètes, effets recyclés en capacités de boss, déclencheur d'origine orphelin. 2 essais par les données proposés |
| 2026-10-19 | DoubleTap, essai 1 : `pickups.bin` Normal → niveau DoubleTap pour Mine, Shunt, Shock, Bouclier, Nitro (10 octets) ; dans la copie |
| 2026-10-19 | DoubleTap essai 1 : les IA utilisent les bonus DoubleTap sans souci, mais **plantage dès que le joueur utilise un bonus**. Recherche bonus par bonus (Bouclier seul d'abord) |
| 2026-10-19 | DoubleTap : Bouclier seul OK pour le joueur. Test suivant : Bouclier + Nitro |
| 2026-10-19 | DoubleTap : Nitro en DoubleTap = pas de plantage mais aucun effet (réglages d'un autre type ; la faille passe par la capacité BossNitroRift). Test suivant : Bouclier + Mine |
| 2026-10-19 | DoubleTap : Mine OK pour le joueur (dure ~3 s, mêmes dégâts que la normale). Test suivant : Bouclier + Shunt |
| 2026-10-19 | DoubleTap : **Shunt = plantage** quand le joueur l'utilise (réglages incomplets). Test suivant : Bouclier + Shock |
| 2026-10-19 | DoubleTap, bilan : Bouclier 12 s OK ; Mine OK mais éphémère ; Shock sans différence ; Nitro sans effet ; Shunt plante. Faille du nitro : voie BossNitroRift |
| 2026-10-19 | Restes de développement : menu de débogage complet (verrou `UIGlobals.DevMode`), triche chrome inachevée, mode « Motor Mash » coupé, notes de devs ; pistes IA « coupées » = doublons |
| 2026-10-20 | Hard « sans bridage » (facteurs 1,2 + profil 900 pour toutes les IA) et « Evil Shannon » (avatar + profil ultime) dans la copie, à tester |
| 2026-10-20 | Vitesse des IA : sujet clos. Freinage après nitro expliqué (vitesse cible calculée au chargement depuis la physique de chaque voiture, frein forcé au-dessus) ; aucun levier « IA seulement » en course perso sans toucher à l'exe ; en carrière, `OverrideAISurfaceValue` 1,5 testé sans effet sur le freinage (retiré). Gardé : direction amortie, Hard sans bridage, meute de rivales. Outils `racegaps.py`, `aispeedrec.py` |
| 2026-10-20 | Musique : banques `.baf` décodées / encodées (`blurbaf.py`), contrôleur JBOA compris en partie ; 24e morceau de course ajouté et entendu en jeu (`make_music.py`). Suite : musique qui réagit aux actions (nitro, épave, place) |
| 2026-10-21 | Musique : sélecteur limité à 32 (coupé en deux), départ de course corrigé, 8 morceaux retirés (36 au total). Lecture du code de Blur Map Builder (MDPRO) : signature des paks, `.aid` complet, insertion triée dans les `.bin` |
| 2026-10-22 | Russian Hill Route 1 Reverse OK en jeu ; projet G (choix des chemins par les IA) ajouté |
| 2026-10-23 | New York à l'envers OK en jeu : Route 2 Reverse et East River Run (rampe invisible ajoutée à la collision) |
| 2026-10-23 | Passation : docs/PASSATION.md (règles, méthode, tâches en cours dont l'option musique « non » à 3 niveaux) |
| 2026-10-23 | Musique : modes oui / partiel / non implémentés ; variables type 20 référencées depuis les objets type 42, reconstruction et relecture JBOA réussies |
| 2026-10-23 | Essai en course, mode « non » : effets sonores persistants lors de l'activation des bonus sauf nitro et bouclier ; son également modifié à très faible niveau de vie. Identifier puis neutraliser ces deux sources dans `finalsubmix.dat` |
| 2026-10-24 | BPR agrandi : ajout de vignettes avec offsets relatifs alignés sur 16, aller-retour sans ajout byte-identique et 226 images originales préservées avec un ajout. Premier lot de quatre routes inversées installé hors ligne |
| 2026-10-24 | Tokyo Bayshore Reverse corrigé par recalage des grilles sur les hauteurs des lignes MainLoop ; correction confirmée en jeu par l'utilisateur |
| 2026-10-24 | Sausalito 1 Reverse et Sausalito 2 Reverse générées et installées avec le lot précédent ; test en jeu en attente |
| 2026-10-26 | Vignettes blanches expliquées (liste chaînée du `.bpr` terminée par 0 sur l'ancienne dernière entrée) et corrigées : **vignettes OK en jeu** |
| 2026-10-26 | Toutes les routes inversées générées (30, dont Seafront Strip, The Money Run, Harbor Freeway) : 60 routes au menu, **toutes se lancent** |
| 2026-10-26 | Chutes au départ : la course perso utilise la grille **multi**. Sol mesuré en roulant les routes d'origine (`trackrec.py --all`) ; grilles recalées dessus (`gridreverse`, clé `ground`) pour City Breach, Speedway, Highland Charge, Stormdrain Surge, Bay Area Tour (à vérifier en jeu) |
| 2026-10-26 | Projet I : plugin `musicctl` (suivant / pause par l'option « Musique », via `MusicTypeResetScript`) ; L3/R3 à remplacer par des touches libres. Liste des 78 sons inutilisés (`docs/SONS_INUTILISES.md`) |
| 2026-10-26 | Projet J : `.stm` de Hot Pursuit Wii décodés (route séparée du décor, `stm2obj.py`, Dubaï exporté) ; Map Builder n'importe pas de maillage (ligne centrale `map.json`) ; prochaine étape : tracé HP → `.blurmap` |
| 2026-10-26 | Projet J : route 1 de Dubaï (Hot Pursuit) → Map Builder (dossier séparé) → fusion par-dessus nos mods (`make_nfs_map.py`), installée dans Blur_test, à tester en jeu |
| 2026-10-27 | Projet J : textures HP décodées (CMPR, C8), matériaux des maillages, générateur de `.model` de taille libre (`blurmodel_write.py`) ; 1er immeuble HP installé dans Dubai Loop, à tester |
| 2026-10-27 | Projet J : **route de Dubaï (Hot Pursuit Wii) visible et roulable dans Blur** (collision HP, 11 modèles générés de même taille, identifiants uniques ; crash 0x6DB2EB résolu) |
| 2026-10-27 | Projet J : décor HP de Dubaï chargé en jeu (122 modèles) ; restent la liaison des textures du décor et les performances (découpage par zone, distance d'affichage, LOD) - en pause |
| 2026-10-27 | Projet J : NFS Studio, réglage par rangée de bonus (nombre 1-9 et type, champs `n` / `type` de Map Builder), affiché sur le cube ; à vérifier en jeu |
| 2026-10-27 | Projet J : UV HP = s16 / 2048 (prouvé par le VAT des captures FIFO), corrige les textures répétées 2×2 |
| 2026-10-27 | Projet J : shaders de Blur recensés (objets vs `.levelrender`) ; plan pour embellir les cartes NFS (gabarits néon / eau / relief, multi-matériaux, ombre précalculée) |
| 2026-10-27 | Projet J : transparence des textures HP gardée en jeu (DXT1 1 bit) ; plantes sans collision ; à vérifier en jeu |
| 2026-10-28 | Projet J : arbres sur le shader des plantes de Blur (transparent noir en jeu) ; tracé sous le sol de référence accepté (voiture en vol corrigée) ; à vérifier en jeu |
| 2026-10-28 | Projet J : carte noire et lenteurs : shader des plantes annulé, nature retirée du décor, modèles à la taille réelle, collision à 40 m, réglages avancés repliés dans NFS Studio. **EN PAUSE, à reprendre** : reconstruire Location45 (NFS Studio relancé), tester en jeu (noir, fluidité, décor) ; si encore lent : atlas 512x512 (CELL 64), VERTS plus bas ; ensuite gabarit néon, lumières / animations (lampadaires) |
| 2026-10-28 | Voitures : jantes dans `wheels/<voiture>.model`, phares = éléments `e_*Light*` (shaders `veh_Light`, textures on/off), transparence via `veh_Alpha` / `veh_Glass` ; demandé par Splat (LBPU, Vehicle Maker) |
| 2026-11-02 | Projet J, étape 0 (reproductibilité) : correctif Map Builder versionné (`vendor/map_builder/`, s'applique sur un zip 1.0.0 propre), chemins centralisés dans `config.py`, Dubaï reconstruit 3 fois (2 avant, 1 après) : 139 fichiers identiques octet par octet. Problèmes restants dans `docs/NFS_STUDIO_REPRO.md` §5. **En attente de validation** |
| 2026-11-02 | Projet J, étape 1 (diagnostic P1, Dubaï) : grillage = alphaTest sur les vitres à envmap (studio) et vitres retirées par see_through (export, 163 295 triangles) ; 8 pâtés présents seulement en LOD (absents des deux) ; faces, profondeur et décodage hors de cause. **En attente de validation**, rendu en jeu à vérifier |
| 2026-11-02 | Projet J, P1 phase A : vitres à reflet sans alphaTest dans NFS Studio (affichage seul, export inchangé), vérifié sur Dubaï et Rio dans le studio |
| 2026-11-03 | Projet J, P1 phase B (diagnostic) : see_through décide par texture sans voir le reflet ; vitres gardées = +6 modèles à Dubaï, limites tenues ; une vitre gardée doit avoir une case d'atlas opaque. Visibilité Blur : PVS + portails pour le décor statique, nos modèles sont des acteurs (distance). **Proposition en attente de validation** |
| 2026-11-03 | Raccourcis IA inversés validés en jeu (Tokyo) puis appliqués à toutes les routes ; Urban Belt Reverse mis de côté |
| 2026-11-03 | Projet J, P1 phase B (correction) : vitres à reflet (envmap.tex) gardées avec case d'atlas opaque, par matériau ; collision et Location45 inchangés ; Dubaï +6 modèles (91, 65 000 sommets), Rio 61. Point ouvert : LSData/LSTree dépendent de l'ordre des constructions. **À essayer dans Blur_test** |
| 2026-11-03 | Chat vocal : gadget HUD `UIMultiplayerSpeaking` (calque `MP_SPEAKING`) présent dans Blur.exe PC, sans VoIP trouvée |
| 2026-11-03 | Projet J : essai en jeu de Dubaï phase B (vitres OK) ; diagnostic lignes blanches (sommets en T de tile_split + atlas sans marge), collision (murs à normale dos au tracé, maillage visuel, vitres non solides), performances, visibilité (décor > 300 m non exporté). Rien de corrigé |
| 2026-11-05 | Reverse : raccourcis IA ramenés à Tokyo (chutes ailleurs), 5 routes retirées, minimap de course des reverse (copie des formes `_game.ipf`, validée en jeu), flèches Tokyo : chevrons non identifiés (décor), respawn non réglable sans patch d'exe |
| 2026-11-07 | Respawn bloqué / sens inverse : réglages `HandOfGodParameters` dans `rldatabase.bin` (pas d'exe) ; `edits/norespawn.py` installé dans Blur_test, à tester en jeu |
| 2026-11-05 | Pack LAN réversible (`lan_pack/`) : installateur / désinstallateur testés hors jeu (retour à l'identique). Ensuite : Hardcore, onglet Reverse |
| 2026-11-05 | Hardcore construit (studio12, installé dans Blur_test, pack LAN rafraîchi). Ensuite : test en jeu, embranchements reverse map par map |
| 2026-11-05 | Route 66 reverse : murs invisibles (dont un tracé enregistré qui ferme un chemin), puis premiers objets ajoutés à une carte existante (néons bleus, `neon.py`) |
| 2026-11-09 | Projet K : feuille de route (murs/rampes de toutes les reverse → tracés IA roulés → IA entraînée → buff des IA par paramètres) |
| 2026-11-09 | Projet K : idée d'IA buff par observation des joueurs (trajectoires, esquives, bonus) traduite en `.aid` + paramètres de profils |
| 2026-11-09 | Projet K : IA buff = fusion profil d'origine × style joueur, poids différent par IA (pas de clones) |
| 2026-11-09 | Boost d'adhérence IA : effet réel dans les grands virages serrés (observation joueur), invisible dans la moyenne du tour |
| 2026-11-09 | Projet K : joueur enregistré en physique d'origine seulement ; IA = style joueur simplifié, virages serrés gardés à l'IA |
| 2026-11-09 | Prototype Blur 2 (X360) inspecté : sain, même moteur en gros-boutiste, 32 cartes inédites (conversion à écrire) |
| 2026-11-09 | Blur 2 : level.level et physics = PC inversé, voitures = 2 véhicules de trafic seulement ; Map Builder récent intègre des véhicules (à récupérer) |
| 2026-11-09 | Blur 2 du 10/11/2010 : sain, maps plus avancées (Dubaï, Hong Kong, Miami, Ski Resort, LA Freeway), IA de Liverpool, table voitures refaite ; pak X360 en LZX |
| 2026-11-09 | Décodeur LZX X360 (`lzx.py`) ; Blur 2 novembre : 45 voitures refaites (Veyron, FXX, GT-R…), 10 modèles dont la BMW M3 Concept Race complète |
| 2026-11-09 | Blur 2 : root.pak X360 lu (morceaux LZX/stockés), BMW M3 Concept Race extraite = M3 Drift de Blur 1 retravaillée, textures manquantes |
| 2026-11-09 | Découverte de BlurRebuilt (uKER) : Blur recompilé depuis la source fuitée, branche blurx orientée Blur 2 (Kanzen, Dubaï) |
| 2026-11-09 | Décor de Dubaï (Blur2DubaiTest) dans la map Marina : 119 modèles à atlas (`b2decor.py`, `make_b2_map.py --decor`), installé dans Blur_test, à essayer en jeu |
| 2026-11-09 | Marina avec décor essayée en jeu : charge et roule ; vitres noires corrigées (alpha opaque des matériaux à reflet), reste éclairage, ciel, chemins secondaires |
| 2026-11-09 | Marina : objets inutiles retirés (autres routes, effets, icônes de bonus), 4 chemins secondaires officiels, ciel Amboy ; restent vrai ciel, éclairage, transparence |
| 2026-11-10 | Marina : bords calés sur les murs de collision, éclairage approché (lightmap A + soleil, atlas 1 024), LA River ; à essayer en jeu |
| 2026-11-10 | Marina : départ sous la map = trou de la collision Unity ; ligne déplacée au vrai portique Start/Finish de Blur 2 (start_m 131) |
| 2026-11-10 | Marina : bords issus de la conduite le long des murs (--drive), éclairage approché retiré, collision à 150 m ; à essayer en jeu |
| 2026-11-10 | Éditeur des tracés Blur 2 (`b2track.py`, « Tracés Blur 2.bat ») + `make_b2_map --track` : l'utilisateur corrige route et embranchements à la main |
| 2026-11-10 | Éditeur des tracés : toutes les villes Blur 2, journaux de conduite par route (et en direct), construction + installation depuis la page, vue 3D |
| 2026-11-10 | Éditeur des tracés, surfaces praticables étape 1 : polygones libres (dessin, sommets, propriétés, simplification), enregistrés sous `areas`, rien d'exporté |
| 2026-11-10 | Studios web : priorité 1 sécurité et protection des travaux (studio_safe.py, 37 tests), voir docs/SECURITE_STUDIOS.md |
| 2026-11-10 | Marina en mode mixte : façades cuites avec la formule du shader Blur 2, sols en atlas nets ; à essayer en jeu |
| 2026-11-10 | Comparaison des builds Blur 2 du 4 et du 10 novembre : Dubaï plus avancé le 10 (lightmaps, IA) ; le 4 apporte bonus et métadonnées IA (wallride, tunnel) + audio X360 |
| 2026-11-10 | Compléments du 4 novembre (b2nov04.py) : 83 bonus hors Marina, wallride et tunnel situés sur Marina (virage sud-ouest) |
| 2026-11-10 | Fusion 10/4 nov : 100 bonus du 10 gardés, 83 du 4 écartés (ancienne version d un groupe), wallride/tunnel compatibles avec l IA du 10 ; effet en jeu à tester |
| 2026-11-10 | Audit rendu Blur 2 + prototype hors jeu (b2proto) : lightmap aux sommets + textures d origine ≈ rendu Blur 2 ; looping = surfaces GravityBend |
| 2026-11-10 | Couleurs de sommet Blur 1 : ordre R,G,B,A confirmé (normales 60/60, Shunt rouge, alpha), lecteur multi-flux blurmesh.py (1 759/1 763 modèles) ; espace sRGB/linéaire à tester en jeu |
| 2026-11-11 | Couleur de sommet ajoutée au gabarit (add_colour, stride 24, default_NB_NL) ; panneau de gris installé dans la copie Blur_vcolor (pas Blur_test) ; capture en jeu à faire |
| 2026-11-11 | Crash Blur_vcolor analysé (crashdump.py sur le minidump WER) : remplissage de 0 octet avant les sommets de nos modèles (moteur : 5 à 20) ; correctif proposé, non appliqué |
| 2026-11-11 | Remplissage des flux corrigé (5 à 20, aligné sur Scene, règle empirique) ; 148 modèles réinstallés et vérifiés dans Blur_vcolor ; capture en jeu attendue |
| 2026-11-11 | Panneau couleur de sommet en jeu : charge, couleur lue (ordre R,G,B confirmé), mais effet partiel (pas un produit) et image saturée ; sRGB/linéaire non tranché |
| 2026-11-11 | 2e essai couleur de sommet installé dans Blur_vcolor : 3 panneaux à 15 m (lumière du matériau 0 / 30 / 110) + référence à 40 m ; captures attendues |
| 2026-11-11 | 2e essai en jeu : couleur de sommet × texture quand la lumière du matériau est 0 ; cette lumière s'ajoute sans passer par la couleur ; même espace que la texture, gain ≈ 2 |
| 2026-11-11 | Preuve de concept lightmap → couleurs de sommet : nervures de la tour (draws_d0154) dans Blur_vcolor, lumière du matériau 0 ; captures attendues, pas de généralisation |
| 2026-11-11 | 2e preuve de concept : mur de béton de la tour (draws_d0088) subdivisé niveau 2, écart hors jeu 2,9 contre 16 sans subdivision ; installé dans Blur_vcolor, captures attendues |
| 2026-11-11 | Limites du conteneur (essais G1 à G3b, Blur_vcolor) : 65 504 sommets et index 16 bits non signés confirmés en jeu ; tailles de modèles différentes acceptées dans cet ensemble de 148 acteurs (G3b préliminaire, 263,8 → 10,87 Mo sur disque, aucun benchmark) ; limite de 144 acteurs = Map Builder ; matériaux multiples et nombre d'acteurs pas encore essayés |
| 2026-11-12 | G4, matériaux multiples et plages de distance (Blur_vcolor, captures) : 2 puis 4 matériaux dans un modèle natif réécrit (S1, S2) ; plages de distance par maillage indépendantes (T1, T2) ; texture 256 × 512 confirmée (ordre de l'en-tête) ; le champ de matériau d'un maillage est lu, et appliqué selon l'ordre des sommets (T3, probable, 2 gabarits) |
| 2026-11-12 | G5 : première façade réelle de Dubai Marina (Blur 2, `i0046`, 4 matériaux) convertie et validée en jeu (G5b à G5d) ; géométrie et matériaux affichés correctement (textures matériau mates (41, 0, 49), `u5` de chaque enregistrement) ; la règle « ordre des sommets » de G4 est contredite : la règle générale d'affectation des matériaux reste non résolue |
| 2026-11-12 | Fouille des prototypes Blur 2 (lecture seule) : `.xex` devkit déchiffrés (clé AES nulle), assertions signées par les développeurs, `.loc` X360 lus ; route 4 de Dubaï nommée officiellement « Route 04 - Marina » ; aucun message d'adieu ; rapport `blur2_aid\easter_eggs\rapport.md` |
| 2026-11-12 | G7, témoin `fence01` sur `road_21_34` (Blur_vcolor, captures) : crash au chargement causé par mon script (table d'instances de matériaux prise pour une boîte, `Blur.exe+0x2F0140`, 4 dumps), corrigé dans R3c qui charge (cadre visible) ; R3 + R5 : bâche affichée mais avec de grandes zones manquantes ; R3 + R5 + R6 : surface complète, des deux côtés, couleur correcte ; `default_NB_NL_NM_NV` = test d'alpha confirmé ; instance 1 = tubes, instance 2 = bâche ; éclairage ambiant absent (hypothèse ouverte : variante `LN` seule déclarée par le niveau) ; P1 retiré, fichiers et empreintes dans `blur2_aid/G7/` |
| 2026-11-12 | Musique, mode « non » : les deux restes trouvés et neutralisés hors jeu : baisse de volume du décor, des IA et de la réverb sur chaque bonus (`finalsubmix`) et second étage d'effets `finalperksubmix.dat` (bit crusher, ring mod, flanger, passe-bas, passe-haut des bonus et de la santé faible) ; à tester en course |
| 2026-11-13 | Musique, mode « non » : plus de baisse sur les bonus (confirmé en jeu) ; son aigu en état critique = passe-haut santé de `finalperksubmix`, coupé sur l'entrée du filtre (la constante dans `HighPassFinal` ne prenait pas) ; à tester |
| 2026-11-13 | Musique, mode « non » validé en jeu : plus de baisse sur les bonus ni de son aigu en état critique (le battement de cœur a aussi disparu, accepté) ; chantier musique terminé |
| 2026-11-13 | Pack musique pour la communauté (`music_pack/`, `Blur_Music.zip`, en anglais) : playlists perso, touche suivant, effets on/partial/off, désinstallation à l'identique ; testé hors jeu sur un faux dossier ; à essayer sur une vraie installation et en ligne avant publication |
| 2026-11-13 | Pack musique : `Launch Blur.bat` retiré (les joueurs lancent par TextMod…) ; départ aléatoire du mélange à chaque session, dans le contrôleur (`random_start`), installé dans Blur_test, à confirmer en jeu |
| 2026-11-13 | Pack musique, retours d'un testeur : numba manquant (installé et vérifié avant de toucher au jeu) ; sauvegarde déplacée dans `Blur_Music_backup` (survit à une mise à jour du pack), README : mise à jour et récupération ; cycle installation / remplacement du pack / désinstallation retesté hors jeu |
| 2026-11-13 | Pack musique : reprise automatique d'une ancienne installation interrompue (question Y/N, paks remis, fichiers en clair identiques au pak repris comme ajoutés) ; état du testeur reproduit hors jeu : reprise, installation, désinstallation = identique à l'origine |
| 2026-11-13 | Pack musique, alerte antivirus chez un testeur : version douce (plus d'auto-élévation ni de winget dans les .bat) ; vrais .bat testés hors jeu, retour identique ; Defender : aucune menace ; à revérifier chez le testeur |
| 2026-11-13 | Pack musique : un fichier en clair déjà présent n'est repris (et supprimé à la désinstallation) qu'en reprise d'installation interrompue (réponse Y), plus jamais en installation normale (anciennes extractions du joueur) ; testé hors jeu : fichiers extraits autrefois et .bat perso conservés |
| 2026-11-13 | Pack musique : empreinte sha1 de chaque fichier extrait (`added.txt` = chemin, tabulation, sha1) ; la désinstallation laisse en place et signale un fichier modifié depuis (autre mod) ; testé hors jeu |
| 2026-11-13 | Audit A, environnements et éclairage de Blur 2 (lecture seule, pas d'essai en jeu) : réglages déplacés dans `environmentalsettings.bin` (lien `tracks.bin`), `LightingSettings` de même structure que Blur 1 (188 o) ; ciel, cubemap et échantillons séparés ; 31 août = format Blur 1 (`CubePt2`, `LSData` 24 o), novembre = `CubePt3` + 16 o ; seule ambiance propre à Dubaï en août (`HFD_HemiClouds16`, `Dubai_Sunny_LUT_01`, 73 357 échantillons) ; 3 pistes de portage ; rapport `docs/blur2/audit_environnements/` |
| 2026-11-13 | Pack musique, alerte antivirus identifiée : `Trojan:Script/Wacatac.B!ml` (verdict cloud de Defender) au téléchargement depuis Discord, même sur la version douce ; non reproductible en scan local : faux positif de réputation. À faire : déclarer à Microsoft, choisir un autre hébergement |
| 2026-11-13 | Pack musique publié : dépôt public GitHub `Ov3r-MAG1STR4L/blur-music-pack`, release `v1.0` (zip identique au local, aucune menace au scan Defender après téléchargement) ; reste à vérifier un téléchargement par navigateur chez un testeur |
| 2026-11-13 | Projet L (popup du morceau en cours) : étude sur les 144 scripts BZUI ; affichage probable via clé `.loc`, morceau en cours illisible par le Lua ; tout dépend d'un essai `music_type` en jeu |
| 2026-11-13 | Projet L : sonde installée dans Blur_test (`music_probe.py` : graphe MusicType 2/3, clé `hud.loc` 0x0B1E0001, plugin `musicprobe` sur R3 / touche 8 ; `Tester le mod.bat` ne remélange plus tant qu'elle est là) ; essai en jeu à faire |
| 2026-11-13 | Projet L, sonde 1 en jeu (LAN) : **le plugin peut choisir le morceau** (`music_type` 2 / 3 → morceaux A / B entendus) ; `UIText.X` = hash `.loc` confirmé ; popup de rang absente hors ligne : sonde 2 d'affichage à faire |
| 2026-11-13 | Projet L : texte `.loc` par hash **affiché en jeu** ; popup de montée de rang (centrée, animée) retenue pour « morceau en cours » ; reste : titre et icône de la popup, détection de fin de morceau, conception |
| 2026-11-13 | Projet L intégré (musicctl 0.3) : bandeau bas gauche placé par le joueur, titres depuis les tags, le plugin choisit et suit les morceaux (début de course, fin de morceau, double L3 / ç / à) ; installé dans Blur_test, à tester en jeu ; pack adapté (gamedata.pak) |
| 2026-11-13 | Bandeau finalisé (fond en 3 morceaux, traînée bleue shp_FanSwirlWin placée par le joueur, suivi entre courses, correctif pause) ; pack testé hors jeu avec gamedata.pak (blurloc et modèle du plugin manquaient, corrigés) ; **release GitHub v1.1** publiée |
| 2026-11-13 | Correctif pause du bandeau confirmé en jeu ; crédit à Gongas (idée du bandeau) sur GitHub (README, notes v1.1) et dans le README du pack |
| 2026-11-14 | **Release v1.1.1** : traînées en alternance, titres des morceaux d'origine, pack tolérant (Blur_Music à côté du jeu, ffmpeg dans tools\ffmpeg ou winget, Python hors PATH) après les retours de joueurs |
| 2026-11-14 | **Avis de mise à jour** : `pack.py` interroge GitHub (releases/latest, 3 s max) au lancement de « Choose music.bat » et affiche le lien si une version plus récente existe ; rien n'est téléchargé, silencieux hors ligne. Penser à monter `VERSION` à chaque release |
| 2026-11-14 | **Release v1.2.0** (avis de mise à jour) publiée sur blur-music-pack ; README public complété |
| 2026-11-14 | **Release v1.2.1** (publiée) : un joueur ayant installé avec une ancienne version (sans `gamedata.pak`) plantait sur `Blur_Music_backup\data\gamedata\...\hud.loc` introuvable : `prepare()` s'arrêtait dès `installed.txt`. Ajout de `upgrade()` : déballe seulement les archives de `PAKS` dont les originaux manquent dans `data` (sauvegarde du seul `hud.loc` du joueur, noté dans added/renamed pour la désinstallation). Testé sur un faux dossier de jeu : mise à niveau, deuxième lancement sans effet, désinstallation complète |
| 2026-11-16 | Lecture des dépôts publics d'Aib0t / Amax-Emu (pubs, avatars, FPS, journaux de course) : notre `Blur.exe` = celui d'AMAX (même SHA-1), 10 adresses vérifiées ; code source de Blur public depuis mai 2026 selon Aib0t, et build PS3 avec symboles : à chercher ; section « Sources AMAX » de CONNAISSANCES |
| 2026-11-16 | Recherche : le code source cité par Aib0t = la fuite publiée dans `uKER/BlurRebuilt` (`code/amax/game/Game/GameWorld/GameWorld.cpp`, `AdvertManager.cpp`, `GamerPictureManager_Pc.cpp` présents, moteur « Mercury ») ; build PS3 avec symboles non trouvée en ligne (TCRF ne décrit qu'une « PS3 Final Debug » de 2019) ; rien téléchargé |
| 2026-11-16 | Code source de Blur cloné pour lecture dans `Jeux_WII/blur_source/BlurRebuilt` (commit 87aa6861, 20 206 fichiers, hors dépôt) ; `C_GameWorld::CalcNumberOfSteps` trouvée (GameWorld.cpp l. 2488) |
| 2026-11-16 | Scan de Blur Map Builder 2.5.0 (C#) : `.aid` = 11 drapeaux de route et 9 règles d'embranchement dynamique dans le code source (Md n'en écrit que 5) ; REBORN = 7 changements, empreinte = notre Blur.exe ; pistes pour aider Md dans CONNAISSANCES |
| 2026-11-16 | Lecture des outils de Bizarre Creations (fuite) : `.levelphysics` = format Gravity (type 2 = boîte, 6 = cylindre, 7 = composite, fin 0x0FFFFFFF) ; seul `gamedata.pak` est signé (RSA), root/models/shaders/root_streaming non ; `.level` exporté = Header + MdlDat ; acteurs max 512 |
| 2026-11-16 | Correction globale du dépôt : 14 sondes dans `archive/`, imports morts retirés, arrêt propre des serveurs de test (21 + 59 tests au vert), trois studios ouverts sans erreur ; docs : sections pochette / message de fans remises sous le projet L, README (studios, musique, tests), état des capacités, passation marquée datée |
| 2026-11-16 | Shaders d'objets lus dans la fuite : suffixe `_NL` = sans lightmap ; couleur de sommet = couleur² × albédo (gamma 2, codage Marina à corriger : `255 × sqrt(lumière / exposition)`) ; `_ipr0` R = spéculaire, G = émissif, B = Fresnel ; objets `_NL_NV` éclairés par le nœud SH du niveau (explique fence01) ; découpe alpha 0,5 ; aucune gravité collée dans le code de Bizarre (outil d'uKER) |
| 2026-11-16 | Marina lot 1 installé dans Blur_test, à essayer en jeu : `b2lit` (textures tuilées nettes, lumière Blur 2 en couleurs de sommet, codage gamma 2), 193 modèles dont 51 acteurs ajoutés au-delà des 144 de Map Builder (`extra_actors`, `insert_uid`) ; limite du jeu = 10 000 acteurs (`MAX_NUM_ACTORS`), pas 512 |
| 2026-11-16 | Marina lot 1 essayé en jeu : fluide, décor complet (acteurs au-delà de 144 confirmés), éclairage visible ; à corriger : reflets, transparences, décor manquant par endroits, bonus (centre de route, types en rotation), téléportation en boucle = passages sur murs du virage sud-ouest (gravité collée d'Unity absente de Blur 1) |
| 2026-11-16 | Gravité collée aux murs : DLL `natif/b2gravity` (crochet à 0x453BEF dans `C_VehicleActor::Update`, gravité propre à chaque voiture d'après le code source), 23 zones tirées des conduites Unity, seuil « retournée » 0,45 → 0 dans Blur_test ; installée, à essayer en jeu |
| 2026-11-16 | Railgun (Projet M) : un 12e bonus est infaisable (énumération `E_PICKUP_TYPE` partout, `GetPickupType` = premier du type) ; prototype = le Bolt modifié : DLL `natif/railgun` (1 tir : `GetNumShotsAwarded` 0x4699F0 + 3 copies ; traverse les voitures : `KillPickup` sauté en 0xBECB2A ; traverse les murs : test de mur en 0xBE654B) + `pickups.bin` #796 (600 m/s, rayon 0,4, 150 dégâts) ; installé dans Blur_test, à essayer en jeu |
| 2026-11-16 | Marina lot 2 installé (faces doubles, transparences DXT5, cartes matériau, 263 modèles) + DLL de gravité v2 (compensation au sol) ; Blur 2 : Blindfire = Bolt, Bomb = Mine, Javelin et Icewall = vrais nouveaux bonus ; conduite au plafond de Blur 2 identifiée (`CeilingRidingControl`, 40-70 mph) ; à essayer en jeu |
| 2026-11-16 | Railgun v2 : à la place du SuperShield (bonus coupé mais câblé : énumération, HUD, nom), Bolt rendu normal ; DLL 11 sites (tirage 0xB5B497, ramassage IA 0x47CC60, `CreatePickup` 0xBAB600, constructeur du Bolt, `Trigger` par vtable, `GetDamageToApply` 0xBA8CC0) ; dégâts dégressifs, bouclier cassé, pièces détruites ; délai 1,5 s, HUD blanc titane, nom RAILGUN, son maison ; construit, à installer (jeu ouvert) puis essayer |
| 2026-11-16 | Railgun : délai 1,0 s, son = charge de l'utilisateur + tir plasma + boom et descente du vrai `ShuntFire` (pickups.baf) ; installé dans Blur_test |
| 2026-11-16 | Railgun : son A (titane) pour le tir avant, B (lourd) pour le tir arrière ; tir arrière plus rapide (0,5 s contre 1,0 s), délais posés par la DLL dans la structure de création (+0x10) ; pickups.bin d'origine ; installé |
| 2026-11-17 | Railgun : effets propres (niveau à lui accroché au SuperShield.Modified, `railgun_fx.py`) : charge Shunt + anneaux du Nitro arrière, traînée lumineuse 2,5 s + fumée blanche, impact orbe + coque de la Shock, lumières blanc titane ; DLL 13 sites ; installé, à essayer en jeu (modèles pas encore recolorés) |
| 2026-11-17 | Railgun v3 après le 1er essai : tir arrière réparé (réglages reposés après le constructeur du Bolt arrière), IA armées (Bolt 1 tir tiré en Railgun), mixeur de sons waveOut (plus de coupures ni de retard), sons plus forts, dégâts 1,5 partout, néon à la place de la fumée, charges à demi-vitesse ; reste : couleurs des modèles, étoile sur la piste, options LAN |
| 2026-11-17 | Railgun v4 : ligne « RAILGUN » On/Off dans les options de bonus de la course perso (plugin AMAX + package.loadlib vers la DLL), tir arrière = tir avant tourné (visuel), mixeur logiciel (fin du volume global), orbes et Railgun séparés (mode test coupé) ; installé, à essayer |
| 2026-11-17 | Railgun v5 : Railgun seul possible (le jeu coupait tous les bonus sans bonus d'origine coché), sons d'orbe du jeu retirés pour le Railgun (0x535770), volume 0,7, secousse de charge pour le tireur seulement (Local / External comme le Shunt), charge arrière du Shunt à 0,5 s, tir arrière à 300 m/s ; installé, à essayer ; reste les couleurs |
| 2026-11-17 | Étude complète des bonus (lecture seule) : `docs/POWERUPS.md` (inventaire, fichiers, réglages, audio, effets, HUD, rétroviseur, IA, emplacements, LAN, DoubleTap, réseau, création, gabarits, Blur 2, système modulaire) et `POWERUPS_DONNEES.md` (`powerups_dump.py`) ; prototypes non compilés, Shock = aiguillage DoubleTap vers dômes Normal placés par l'hôte, IA pickups.bin morte, rétroviseur sans particules |
| 2026-11-17 | Icônes des bonus du HUD : planches `perk_sheet` / `perk_sheet_support` (+ inversées) de `ui_common.bpr`, découpe par les gadgets `hud_objects` de `ui.bin`, table bonus → case (SuperShield = étoile 104), formes `_x2` inutilisées, carrousel derrière la voiture / HUD selon la caméra ; `docs/POWERUPS_HUD.md`, `perk_icons.py` (planche contact hors dépôt) |
| 2026-11-17 | Icônes du HUD vérifiées dans `Blur.exe` (`hud_exe_probe.py`) : `GetPerkInfo` 0xC55320, seuil 100 dans les deux `Render`, calcul des V, disposition mémoire 0x48 / 0x480 ; identique à la source ; essai conseillé : `shield.texture_index` → 104 dans une copie |
| 2026-11-17 | Essai HUD préparé : copie isolée `Blur_test_hud` (sans Railgun), `ui.bin` avec `shield.texture_index` 7 → 104 (un seul octet, fichier 0x61D00) ; procédure et résultats attendus dans `docs/ESSAI_HUD_SHIELD104.md` ; pas encore joué |
| 2026-11-17 | Essai HUD Shield 104 : étoile en pare-chocs et sur les IA, hexagone en extérieur ; désassemblage : même `UIPerks2::Render` (0xC58130), même `GetPerkInfo`, une seule configuration (chargée une fois, 0xC3BD15) ; cause probable : Boucliers posés sur la piste (`shieldpickup.model`, textures `icon_shield_01` propres) ; `docs/ESSAI_HUD_SHIELD104_DIAGNOSTIC.md`, captures à faire |
| 2026-11-17 | Essai HUD Shield 104 **réussi** (captures) : étoile dans le carrousel extérieur, le carrousel pare-chocs et au-dessus des IA ; l'hexagone vu au 1er essai = Bouclier posé sur la piste (textures propres au modèle) ; seuil 100 et planche support confirmés en jeu |
| 2026-11-17 | Planche support agrandie : faisable par les données seules ; `hud_support_atlas.py` (planches 128 × 1024, cases 100-104 recopiées bloc par bloc, 105-109 d'essai ; `ui.bin` : 5 `size.v` + Bouclier → 105) ; `blurbpr.rebuild(resize=…)` ; copie `Blur_test_hud_atlas` prête ; `docs/ESSAI_HUD_SUPPORT_ATLAS.md` ; pas encore joué |
| 2026-11-17 | Planche support agrandie **validée en jeu** pour la case 105 (captures : carrousels extérieur et pare-chocs, IA, versions normale et inversée) ; 106-109 à essayer avec `variants/ui_106_109.bin` |
| 2026-11-17 | Planche support, étape 2 préparée : 108 = losange, 109 = croix (seules ces cases changent, 100-107 identiques à l'octet), 4 `ui.bin` à un seul changement (Bouclier 106-109), état de l'étape 1 sauvegardé, test 106 installé ; pas encore joué |
| 2026-11-17 | Planche support, étape 2 **réussie** : cases 106-109 affichées chacune (captures + retour « tout fonctionne ») ; ajouter des icônes au HUD par les données seules est démontré |
| 2026-11-17 | Bouclier posé sur la piste : 2 textures intégrées à `shieldpickup.model` (non partagées) ; `shield_pickup_icon.py` les remplace par un triangle « 6 » (seuls leurs octets changent) ; copie `Blur_test_hud_pickup` (avec `boot.pak` mis de côté) ; `docs/ESSAI_HUD_SHIELD_PICKUP.md` ; pas encore joué |
| 2026-11-17 | Bouclier posé sur la piste **réussi en jeu** (capture : triangle « 6 » sur la piste, HUD inchangé, jeu démarré sans `boot.pak`) ; ramassage, Bouclier de 6 s et réapparition à capturer |
| 2026-11-17 | Bouclier posé sur la piste : vues de côté, de dos et au rétroviseur, Bouclier de 6 s et réapparition OK (rapportés) ; seul défaut : léger fantôme de l'hexagone dans la lueur |
| 2026-11-17 | Étude du comportement des bonus (lecture seule) : `docs/POWERUP_BEHAVIOUR_STUDY.md` ; Fan et Stopwatch = pastilles de mode (jamais en réserve) ; bouclier : bloque tout sauf le Nitro arrière, seule la Shock le casse ; dégâts mutuels par la santé (2 Bolts par Mine ou Shunt) ; la Barge détruit Shunt, Bolt et Mine ; Shunt et Mine coupent un Nitro en cours ; plan de tests T1-T7 non lancé |
| 2026-11-17 | Étude des bonus v2 (lecture seule) : T1 à T8 intégrés (tous cohérents avec la source) ; 8 mods de carrière tracés (`Boss_*`, `amax.bin` `BossAbilitySlot`, valeurs de `multiplayer.bin`) ; Armor Plating = `BossRepairBonus` ; `Shielding Efficiency` explique probablement le bouclier qui survit à un Shock en ligne (AMAX l'a réduit) ; contradiction Shock contre Mine ; plan de tests N1 à N11 non lancé |
| 2026-11-18 | Gravité v4 essayée : toujours deux roues + accroche au mur. Cause (source) : anti-roulage sur les murs de Blur 1 (roues : sol pris selon la verticale du monde, pente > 75° exclue, mode `m_bEnableWallRiding` jamais branché ; caisse : « WallRiding Fix2 » = mur + freinage 450). Piste v5 notée, rien codé |
| 2026-11-18 | Gravité v5 installée dans Blur_test : `m_bEnableWallRiding` (Car + 0x12D5) mis à vrai pendant le wall-ride (roues cherchent le sol sous la voiture) + Fix2 (`0x1212A84`) coupé ; à essayer en jeu |
| 2026-11-18 | Gravité v5 essayée : contrôle nettement meilleur sur le mur, toujours deux roues (voiture penchée ~30°, rien ne la tourne vers le mur). v6 installée : couple d'alignement vers la normale (externalTorque, `align` / `damp` dans `b2gravity.txt`) ; à essayer |
| 2026-11-18 | Gravité v6 essayée : quatre roues sur le mur à basse vitesse, remise à plat au-dessus (appui aérodynamique de Blur 1 selon −haut, croît avec la vitesse). v7 installée : appui redirigé vers le mur (`0x7C2F00`, réglage `press`) ; à essayer |
| 2026-11-18 | Gravité v7 essayée : pas d'évolution, rupture à ~20 mph (la DLL n'agissait qu'au-dessus de 40). v8 installée : anti-mur levé à toute vitesse dans les zones, gravité collée entre 15 et 35 mph (`mph_min` / `mph_max`) ; à essayer |
| 2026-11-18 | Gravité v8 essayée : collé au mur à 150-170 km/h après un Nitro pris sur le mur → la tenue marche ; l'entrée échoue car le raccord banquette (35°) → paroi (80°) de la collision se fait sur 2-5 m (64 g à 180 km/h). Pistes : congé dans la collision ou réorientation par la DLL |
| 2026-11-18 | Gravité v9 « rail » installée : normale lue devant la voiture, corps tourné vers elle et vitesse couchée le long de la surface (Car + 0xC8 axes, + 0x138 vitesse, + 0x118 quantité de mouvement, vérifiés en jeu avant écriture) ; réglages `turn` / `ahead` ; à essayer |
