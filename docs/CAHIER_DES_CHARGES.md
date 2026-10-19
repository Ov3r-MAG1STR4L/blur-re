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
6. **Copie de test coupée du réseau** : dans la copie du jeu, retirer `d3d9.dll` et `amax/` (au minimum la
   redirection), pour qu'un fichier modifié ne puisse jamais atteindre une partie en ligne.

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
| `.pak` | oui | inutile : un fichier en clair dans le dossier du jeu passe avant le pak (lu dans le code, à confirmer en jeu) |
| `.bin` / `.xt` (KSLF) | oui, à 100 % | oui : reconstruction identique (49/49), modification de valeurs, clonage d'enregistrement, ajout à une liste de références ; non testé en jeu |
| `.loc` (textes) | oui | non |
| Textures de `.model` | oui | oui (réinjection, jamais testée en jeu) |
| `.aid` (IA / logique de piste) | oui, à 100 % de la structure | oui : réécriture identique (33/33) ; pas encore de route modifiée |
| `.level*` (géométrie, collision) | structure seulement | non |
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

## Projet C : Haruna en sens inverse (mis de côté, à garder en tête)

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
laissées en haut ; le nom affiché reste « Mount Haruna » (texte `.loc` non modifié) ; vignette identique.

**Copie de test** : `make_test_copy.ps1` (simulation par défaut ; `-Run` pour agir ; `-Restore -Run` après le test).
Il sauvegarde d'abord `%APPDATA%\bizarre creations\blur\save` + `settings.xml` (**sauvegarde partagée entre toutes
les installations** : la copie de test écrit dans la même), copie le jeu dans `Jeux_WII\Blur_test` **sans AMAX**
(ni `d3d9.dll` ni `amax\`) et pose les fichiers du mod. Simulation vérifiée : 125 fichiers / 7,28 Go, rien d'écrit.

**Reste pour le projet C** : lancer la copie (`-Run`), essai en jeu, puis `-Restore -Run`.

**Déroulé du test en jeu** (dans la copie) :
1. le jeu démarre-t-il sans AMAX ?
2. course perso / réseau local : « Mount Haruna » apparaît-il deux fois (le 2e = notre route) ?
3. départ en bas, voitures tournées vers le haut, IA qui montent ?
4. passage des points intermédiaires puis arrivée en haut ?
5. noter tout comportement bizarre (remise en piste, voitures qui tombent, IA qui braquent à contresens).

**Première étape proposée** (faite) : écrire `Haruna_reverse.aid`, puis le relire avec `blurroute.py` (aucune erreur,
jusqu'au dernier octet) et le tracer. Cette étape ne touche pas au jeu.

**Validation finale** : la course se lance depuis la copie du jeu, les IA montent sans se bloquer, l'arrivée
est détectée en haut.

---

## Projet D : DoubleTap (combiner deux bonus)

**Objectif** : savoir si le DoubleTap coupé peut être réactivé.

**Étapes** :

1. Lire les réglages DoubleTap de `pickups.bin` (`pickups/PickupLevel/...`) et les comparer aux versions normales.
2. Dans Ghidra, trouver le code qui lit le champ `DoubleTap` des `PickupType`, et voir s'il est encore appelé.
3. Selon le résultat : modification des données seulement, ou du code (bien plus lourd).

**Validation** : en jeu (copie), deux bonus identiques donnent l'effet DoubleTap défini dans les données.

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
