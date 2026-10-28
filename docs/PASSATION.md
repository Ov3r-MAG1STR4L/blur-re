# Passation (2026-10-23) — à lire avant de reprendre le projet

Ce document résume l'état du projet et ce qui reste à faire, pour un nouvel assistant (GitHub Copilot ou autre).
Les découvertes détaillées sont dans `CONNAISSANCES.md` ; les projets et le journal dans `CAHIER_DES_CHARGES.md`.

## Règles absolues (ne jamais les enfreindre)

- **Ne jamais modifier le jeu installé** `C:\Program Files (x86)\Activision\Blur(TM)` : l'utilisateur y joue en ligne
  (AMAX). Lecture seule. Tous les essais se font dans la copie `C:\Users\sanqu\Jeux_WII\Blur_test`.
- **Ne jamais modifier `Blur.exe`** (ni utiliser une copie modifiée de l'exe dans nos outils).
- **Mémoire du jeu : lecture seule** (`trackrec.py`, `aispeedrec.py` ne font que lire).
- **Rien de modifié ne va en ligne** sans l'accord explicite de l'utilisateur. La copie de test n'a pas
  `amax_auth.asi`, `amax_pfp.dll`, `blur_rpc.dll` ni `amax\config` (pas de connexion).
- **Aucun fichier du jeu ni aucune musique dans le dépôt** (dépôt privé `Ov3r-MAG1STR4L/blur-re`).
- Installer dans `Blur_test` **seulement quand Blur est fermé** (`tasklist | grep -i blur.exe`).
- La sauvegarde est partagée avec le jeu en ligne : toujours lancer la copie avec **« Tester le mod.bat »**
  (sauvegarde puis restauration automatiques).
- Toute découverte → `CONNAISSANCES.md` + journal du cahier des charges → commit.

## Méthode d'installation (pourquoi ça marche sans exe modifié)

Un pak gagne sur les fichiers en clair : dans `Blur_test\cache`, `gamedata.pak`, `root.pak` et `root_streaming.pak`
sont renommés en `.off` et leurs fichiers posés en clair (`gamedata\`, racine, `audio\`). Les mods sont générés
dans `blur_extracted\mods\<mod>\files` puis copiés dans `Blur_test` (boucle `cmp`/`cp`, puis `sha1sum -c`).
`make_test_copy.ps1` recrée la copie complète.

## Outils principaux (dans `blur_tools`)

| Outil | Rôle |
|---|---|
| `make_reverse.py OUT` | génère tout le mod « routes inversées » (+ IA, Evil Shannon, plugins AMAX, rampes) |
| `make_music.py` / `music_menu.py` / `Choisir la musique.bat` | playlists de musique de course |
| `Tester le mod.bat` | lance Blur_test en protégeant la sauvegarde ; remélange la musique |
| `blurbaf.py` | banques audio `.baf` (lecture, ADPCM décodage/encodage, ajout de sons) |
| `jboadump.py` | affichage lisible d'un graphe audio JBOA (`audio/dat/*.dat`, fichiers d'origine seulement) |
| `addramp.py` (+ `bmb_levelphysics.py`, MIT, MDPRO) | rampe invisible ajoutée à la collision d'un niveau |
| `aidreverse.py`, `gridreverse.py`, `blurroute.py` | tracé IA `.aid`, grille de départ |
| `kslfwrite.py`, `blurxt.py` | lecture/écriture des `.bin` (KSLF) |
| `blurbpr.py`, `thumbreverse.py` | images du menu (`ui_frontend.bpr`) |
| `trackrec.py`, `aispeedrec.py`, `racegaps.py` | enregistrement des positions/vitesses (lecture mémoire) |

## Travail en cours / à faire (par priorité)

### 1. Musique : effets en 3 niveaux (corrections du mode « non » à faire)

`music_menu.py` propose `oui` / `partiellement` / `non` et mémorise `effets` comme `oui` / `partiel` / `non` dans
`derniere_selection.json`. `make_music.build()` accepte aussi les anciens booléens. Les transformations ont été
reconstruites et relues hors jeu depuis le `finalsubmix.dat` d'origine. Premier retour en course : le mode « non »
fonctionne globalement, mais il reste une modification sonore lors de l'activation de tous les bonus sauf nitro et
bouclier, ainsi qu'un effet lorsque la voiture a très peu de vie. Identifier et neutraliser ces deux sources.

| Effet | Objet | Réglage appliqué pour « non » |
|---|---|---|
| Passe-bas « bonus » sur tout le mixage : bouclier (`ShieldFilterCutOff` 98, `ShieldMODFilterCutOff` 99) et épave | `PerkFilterCutOff` (100, type 42 = minimum des termes) → `PerkSurroundLowPass` (124) | référence vers une variable type 20 à 1.0 ; ne pas laisser 0 terme |
| Baisse de volume sur les chocs | `FinalSubMixCarAddedMixer` (125) : volume = objet 108 `CollisionVolumeRMSDucking` | remplacer la paire `(108, 0)` par `(0xFFFF, 1.0)` |
| Passe-haut sur les chocs | `CollisionSurroundHighPass` (126) : 3e paramètre `(105, 1.0)` | mettre `(0xFFFF, 0.0)` (coupure 0 = pas de filtre) |
| « Bit crusher » sur les gros dégâts | `RGBBitCrusher` (127), profondeur = 118 | référence vers une variable type 20 à 32.0 (neutre) |

Ces filtres sont appliqués APRÈS le mixage final : ils touchent la musique ET les sons du jeu. L'utilisateur
accepte que « non » les coupe pour tout.

Comportement demandé et implémenté :
- **oui** : comportement du jeu + étouffement en épave ;
- **partiellement** (« plus agréable ») : baisse sur les bonus réduite de moitié (`MusicMixerPerkDuckVolume`, y à x=1 :
  0 → 0,5), passe-bas nitro adouci (`NitrousLowPass`, 0,003 → 0,25), bouclier adouci (`ShieldCutOffVariable` et
  valeurs écrites par les scripts : 0,004/0,1 → 0,4), épave plus légère (`WRECK_CUTOFF` 0,02 → 0,06), sans bit
  crusher, passe-haut ni baisse sur les chocs ;
- **non** : aucun de ces effets sur le mixage final.

Formats JBOA : voir `CONNAISSANCES.md` (« Audio et musique ») : courbe type 21, type 42, scripts (`0x1000`
déclencher, 3 mots ; `0x1002` affecter ; `0x1004` empiler ; `0x1101` saut ; `0x1200` appel ; `0x1202` fin ;
`0x1317` comparer). Ajouter des objets UNIQUEMENT en fin de liste (aucun index existant ne bouge).

Corrections après essai en jeu du mode « non » :
- les changements sonores subsistent à l'activation de certains bonus (tous sauf nitro et bouclier) ; identifier
  les entrées du `finalsubmix.dat` responsables et les neutraliser ;
- un changement sonore se produit aussi quand la voiture est en danger (presque plus de vie) ; identifier l'entrée
  liée à la santé et la neutraliser.

### 2. Ordre du menu de course perso

Fait dans les données (`make_reverse.py`, étape 4 : chaque route inversée juste après son original), installé,
**pas vérifié en jeu**. Si le menu Lua trie lui-même les routes, regarder le script BZUI du menu (`blurui.py` pour
extraire, `luadis.py` pour lire), qui lit `MultiplayerConfig.routes`.

### 3. Inverser d'autres routes

Premier lot testé en jeu le 2026-10-24 : Tokyo tombait à travers le sol; tu confirmes maintenant que Tokyo est
corrigé avec le placement vertical des grilles. Les vignettes des routes inversées restent blanches, le texte de
grille est à l'envers et les bonus ne sont pas orientés dans le sens inverse. Le comportement des IA reste à évaluer.

Le lot Sausalito est installé dans `Blur_test` et testé : **Sausalito 1 Reverse fonctionne ; Sausalito 2 Reverse
fait tomber la voiture avant le lancement de la course**. `RouteNumber=2` et les UID sont corrects. La grille multi
reverse est proche du `MainLoop` (1,5–1,8 m horizontalement, y relatif -1,5 à +1,2 m) ; les places solo 13/15 sont
~28 m/~21 m des lignes, mais elles étaient déjà ~12 m/~6 m dans la grille source. Le mesh Route 2 décodé ne contient
pas la vraie surface sous ces places. Priorité : vérifier quelle liste utilise le Custom Game et mesurer le sol réel
au spawn avec `trackrec.py` si nécessaire; ne pas déplacer les voitures à l'aveugle ni lancer le lot suivant.

Ordre des corrections avant de poursuivre les inversions :
1. Réparer les vignettes de toutes les routes inversées et les vérifier en jeu. `blurbpr.Bpr.rebuild()` ajoute des
  entrées avec offsets relatifs alignés sur 16 octets ; l'aller-retour sans ajout est identique à l'octet et un
  ajout de test préserve les 226 payloads d'origine. Le BPR agrandi reste à valider en jeu.
2. Corriger l'orientation des textes de la grille de départ.
3. Orienter les bonus dans le sens inverse.
4. Vérifier que les IA suivent correctement les routes inversées ; améliorer leur trajectoire seulement si leur
  comportement est d'abord jugé correct. Ne pas modifier leur trajectoire avant la discussion avec Claude.

Ne pas lancer le lot suivant ni faire de commit avant ces corrections et la validation en course. Sur les routes à
raccourcis, le build `routes_only` garde l'IA sur la boucle principale. Noms de développeurs libres par ville : voir
`CONNAISSANCES.md`.
- Obstacles à sens unique (marche, quai, saut) : rampe invisible avec `addramp.py` / `RAMPS` dans `make_reverse.py`,
  mesurée en roulant avec `trackrec.py`. Plus tard : vrais objets (voir Map Builder).

### 4. Trajectoires des IA sur les routes inversées

Méthode du Map Builder : rétrécir le couloir de la ligne IA (position et largeur des nœuds `Main`) autour d'une
trajectoire qui coupe l'intérieur des virages. Mesurer avant/après (`trackrec.py --all`, `racegaps.py`).

### 5. Choix des chemins par les IA (projet G du cahier des charges)

Règles des jonctions `.aid` (types 5 / 9) non décodées ; exemple Concrete Basin.

### 6. Blur Map Builder (MDPRO)

Code source MIT lu (voir `CONNAISSANCES.md`). Il construit des paks complets et utilise un exe modifié
(« Blur REBORN »). Pour l'intégrer à NOTRE méthode : générer une carte avec son outil dans une copie séparée, puis
récupérer les fichiers produits (dossier de niveau, `.aid`, `actorpack`, collision, entrées `amax.bin` /
`multiplayer.bin`, images) et les poser en clair dans `Blur_test`. Aucun exe modifié n'est nécessaire avec notre
méthode, puisque nos paks d'origine sont déjà mis de côté. À tester.
