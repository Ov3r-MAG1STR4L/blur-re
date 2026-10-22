# Blur (PC, 2010) : base de connaissances

Tout ce qui a été découvert, avec le niveau de confiance. Règle : **ne jamais présenter une
hypothèse comme un fait**. Chaque entrée porte une étiquette :

- **Confirmé** : vérifié (en jeu, ou sur toutes les données, avec un test reproductible)
- **Fort** : très probable, une seule vérification indirecte
- **Hypothèse** : piste à valider

Dernière mise à jour : 2026-10-19.

---

## 1. Règles du projet

- **Ne jamais modifier les fichiers d'origine** du jeu installé dans
  `C:\Program Files (x86)\Activision\Blur(TM)` : l'utilisateur joue en ligne via AMAX
  (amax-emu.com). Les tests de mods se font sur une **copie** du dossier du jeu.
- Les outils mémoire sont en **lecture seule** (aucune écriture dans le processus).
- **Blur se met en pause quand sa fenêtre perd le focus.** Tout enregistrement mémoire doit
  attendre que le jeu reprenne (voir `blur_live.py record`).
- Aucun fichier du jeu dans ce dépôt (exe, fichiers extraits, enregistrements mémoire).

## 2. Environnement

| Élément | Emplacement |
|---|---|
| Jeu installé | `C:\Program Files (x86)\Activision\Blur(TM)` |
| Outils (ce dépôt) | `C:\Users\sanqu\Jeux_WII\blur_tools` |
| Données extraites (hors dépôt) | `C:\Users\sanqu\Jeux_WII\blur_extracted` |
| Projet Ghidra | `C:\Appli\ghidra\projects\Blur` (copie de `Blur.exe` : le `.bat` de Ghidra casse sur « (TM) ») |
| Script de décompilation | `C:\Appli\ghidra\scripts\Decomp.java` (arguments : fichier de sortie, puis adresses) |

Décompiler une fonction (projet en lecture seule, sans réanalyse) :

```
analyzeHeadless.bat C:\Appli\ghidra\projects\Blur Blur -process Blur.exe -noanalysis -readOnly
  -scriptPath C:\Appli\ghidra\scripts -postScript Decomp.java C:\chemin\sortie.c 0xADRESSE
```

### Exécutables

- `Blur.exe` (13,7 Mo, compilé en mai 2010) : **non protégé**, idéal pour Ghidra. Base 0x400000,
  `.text` RVA 0x1000 (fichier 0x400), `.rdata` RVA 0xA53000 (fichier 0xA51E00), `.data` RVA 0xB6C000
  (fichier 0xB6A000). **Confirmé.**
- `Blur_debug.exe` (28,9 Mo) : malgré son nom, ce n'est **pas** une version de débogage. C'est la
  même chose plus une section protégée `.8thSin` (point d'entrée dedans). **Confirmé.**

### AMAX (jeu en ligne)

- `d3d9.dll` (proxy), `amax/dlls/lua_hooks.asi` (blur-lua-loader de tobii-dev, en Rust) lance
  `amax/init.lua`, puis les plugins listés dans `amax/plugins/plugins.lua`.
- API exposée minimale : `print_api`, `BlurAPI.set_fps`, et le rappel `M.GoScreen(screen)` avec les
  noms d'écrans Lua du jeu (`Ingame\Hud.lua`…).
- `amax/config/amax-redirect.cfg` redirige les serveurs Demonware vers amax-emu.com.
- `d3d9.dll` charge **tous** les modules de `amax/dlls` : `lua_hooks.asi` (Lua), `amax_auth.asi` (connexion
  AMAX), `amax_pfp.dll`, `blur_rpc.dll` (Discord). **Confirmé** (chaînes).
- Plugins actifs : `resprays`, `laps` (tours jusqu'à 99 pour l'hôte ; intercepte `GetCustomRaceRoutes`),
  `block_popups`, **`solo`** (« race alone in LAN » : intercepte `MpLobby_HostCanPressStart`, d'où la touche
  F1 pour lancer seul une partie perso en réseau local), `fps`, `revs`. Sans AMAX, **pas de partie perso en
  solo**. Le chemin pour lancer un circuit : Online → Local Network → Custom Game → Game Settings (Lieu, Circuit).
- `Amax.*` côté Lua est l'espace de noms du **jeu** (nom de code « amax » de Bizarre Creations), pas du serveur AMAX.

---

## 3. Formats de fichiers

### 3.1 `.pak` (« 2KAP ») : **Confirmé** — outil `blurpak.py`

- En-tête `2KAP`, pages de 0x800 octets.
- Page 1 : u32 taille, puis table des chemins séparés par des NUL, XOR avec la clé de 14 octets
  ``xVXo40j3@$%\%` `` (indice de clé `(i+1) % 14`).
- Entrées de 40 octets (64 avec empreinte dans `gamedata*.pak`) :
  `[hash, nameOfs, dirOfs, usize, crc, ?, startPage, flags, hash2, csize]`.
- Données à `startPage*0x800` : boot/root = blocs deflate ; gamedata = flux zlib ; root_streaming = brut.
- `shaders-speed.pak` (version 1) : non décodé.
- Le jeu vérifie des signatures RSA (`.sig`) sur les paks. Fichiers en clair : seulement pour
  les fichiers absents du pak, voir 3.1 bis (**Confirmé**).

### 3.1 bis Chargement des fichiers (« LogicalFs ») : **Confirmé** (Process Monitor, 2026-10-19)

- **Le pak passe avant le dossier.** Le jeu ne cherche `<jeu>\gamedata\<chemin>` en clair que pour un fichier
  **absent** de `gamedata.pak` (vu : `gamedata\xt\loc\racebookscripts\pressday.loc` et
  `gamedata\levels\showroom\showroom.aid` → PATH NOT FOUND). Un fichier présent dans le pak n'est jamais
  remplacé par un fichier en clair.
- Donc : un fichier **nouveau** (ex. `jpn_mharuna_7.aid`) peut être posé en clair ; pour **modifier** un fichier
  existant (`amax.bin`, `multiplayer.bin`, `actorpack.xt`), il faut retirer le pak et tout poser en clair
  (« unpacked files » de la commu), ou reconstruire le pak.
- **Vérifié en jeu** : `cache\gamedata.pak` + `.sig` renommés en `.off` dans la copie, les 588 fichiers posés en
  clair dans `<jeu>\gamedata\` → le jeu démarre, aucun pak gamedata ouvert, et le menu course perso compte
  **31 routes** dont `JPN_MHaruna_7` (Index 3, `LocString` « Ascent ») : la route ajoutée et ses références
  par hash (`0xFFFF0001..3`) sont résolues. Le `.sig` n'empêche pas de démarrer sans le pak.
- **Grille de départ (essai 2026-10-19)** : avec nos listes clonées (`#67`, `#68`) bien chargées et bien
  référencées par la route, les voitures sont **parties de la grille d'origine** (en haut), puis ont fini dans le
  lac du sommet. Hypothèse (**Fort**) : les acteurs sont retrouvés par `SerialisableUid`, et nos clones gardaient
  ceux de l'original. Dans un pack, un `SerialisableUid` identifie un acteur ; les autres occurrences sont des
  **références** (ex. `HandOfGodEntry.VehicleMessage.ResetPositionActor` → l'acteur de sortie). Correctif :
  nouveaux uids (`0xB1E00000+`) pour les 56 acteurs clonés, références internes conservées. À vérifier en jeu.
- **2e course (uids corrigés)** : le joueur apparaît bien sur notre grille du bas (1324, 510, −3355), puis tombe
  à travers la route en boucle (réapparition, chute). Cause (**Fort**) : `RouteNumber` choisit le bloc `Route`
  de `level.levelphysics` (collision de la route) ; Haruna n'a que les blocs 0 (vide) et 1. Avec 7, aucune
  collision de route. Le `.aid` est trouvé par le **nom** de la route
  (`.\gamedata\levels\<ville>\<Nom>.aid`, `0xBBDD80`), donc `RouteNumber = 1` garde notre piste inversée.
- **3e course (RouteNumber 1)** : la collision de route est là (2 voitures tiennent sur la grille), mais
  (a) la grille d'origine est décentrée (fraction 0,72 à 1,13 d'une route de 36 m) : recopiée en bas sur 20 m,
  une colonne était hors route (−12 m pour ±9,8 m) ; (b) la **collision s'arrête ~250 m après l'ancienne
  arrivée** (vers 13 780 m du tracé d'origine) : la place la plus en arrière tombait. Correctif dans
  `gridreverse.py` : grille centrée et resserrée (`MAX_BEHIND` = 219 m derrière la ligne, 1re rangée gardée).
- **Relevé en roulant (Descent complète, `trackrec.py`, 2026-10-19)** : **le nœud d'un `.aid` est un BORD de la
  route**, pas son centre. Position du joueur rapportée à la largeur : 0,04 à 0,95 (médiane 0,50) sur 13,5 km.
  Point d'une ligne en XZ = `(x, z) + latéral2D × frac × largeur`. **Confirmé** (1 765 points). L'ancienne formule
  `(frac − 0,5)` était fausse : elle n'avait été vérifiée que sur les hauteurs. Le vecteur à +24 a la même
  direction XZ que +16 mais une grosse composante y (0,8) : ce n'est pas un décalage latéral utilisable.
  Conséquences : l'inversion doit déplacer le nœud au bord opposé (`aidreverse.py` corrigé ; sinon les lignes
  des IA sont symétriques, hors de la route : les IA « allaient tout droit ») ; la grille doit se placer avec ce
  modèle. Fond d'Haruna : murs invisibles de 0 à ~19 m, mur du fond vers 13 760 m du tracé, sol à +13 à +14 m
  au-dessus des nœuds.
- **Haruna montée jouable (2026-10-19)** : départ en bas, IA qui suivent la route, bonus en place, pas de
  chute. Seul défaut vu : texte d'arrivée trop loin. Règle mesurée sur l'original : un texte `Start_Text_*` est
  posé **juste après le premier nœud de sa porte** (Start : +20 m, Finish : +4 m), au milieu de la route.
  Recopiés tels quels, nos textes étaient ~90 m après le début des portes ; corrigé dans `gridreverse.py`.
- **Mesurer sur l'axe central** : le nœud est un bord, et le bord ne fait pas la même longueur dans les deux sens
  (écarts jusqu'à ~75 m en bas d'Haruna). `gridreverse.py` travaille sur `nœud + latéral × largeur / 2`
  (13 975 m dans les deux sens). Sur l'original : grille solo 4 m avant la porte Start, grille multi **124 m**
  avant, texte « Start » 16 m après la porte, texte « Finish » au début de la porte Finish. En sens inverse,
  l'arrivée se déclenche ~77 m dans la porte (retour joueur), et le texte y est placé (`FINISH_TEXT_AFTER`).
- **Lignes peintes d'Haruna** (arrêt dessus en Descent, `trackrec.py`, 2026-10-19) : départ (−2474,1 ; 1051,0 ;
  −1305,1) = 547,6 m de l'axe central, **exactement** le texte « Start » d'origine ; arrivée (1112,4 ; 524,5 ;
  −3071,2) = 13 439 m, au début de la porte Finish (13 443). **Confirmé.** Ascent : textes posés sur ces lignes
  (inversées), première rangée 20 m derrière la ligne de départ (comme la grille solo d'origine).
- **Une course démarre / finit au premier nœud de sa porte** (**Fort**) : original, porte Start 16 m avant la ligne
  peinte, porte Finish 4 m après ; inversées telles quelles, les portes commençaient ~92 m avant les lignes et
  l'arrivée se déclenchait avant le texte (vu en jeu). `aidreverse.move_gate` fait glisser une porte le long de
  la route (même nombre de nœuds, même largeur, centrée) et rattache ses références de la table de logique par
  géométrie (la table pointe aussi vers les nœuds de porte : 84 réf. Start, 28 Finish sur Haruna). À vérifier
  en jeu.
- **Encodeur DXT1** (`blurbpr.dxt1`) : axe principal des couleurs + moindres carrés ; ~40 % d'erreur en moins que
  Pillow sur le symbole néon (Pillow donnait un halo pixélisé en jeu).
- **Routes : point à point ou boucle** (`.aid`) : **Haruna est la seule route point à point** (Main type 0, portes
  Start 0x02 + Finish 0x04). Les 32 autres sont des **boucles** (bloc de course type 0x01, une seule porte Start qui sert
  de départ et d'arrivée, logique 0x21) ; presque toutes ont des jonctions. Sans jonction : `uk_brighton_1`,
  `uk_brighton_5`, `usa_la_downtown_multiplayer_figureof8`. Une jonction : `jpn_tokyo_shutoko_2`,
  `uk_london_hackney_2` / `_4`, `usa_la_downtown_3` / `_4`, `usa_sanfran_russianhill_1`. Les noms de sections varient
  (`mainLoop`, `START`, `Start_line`…) : `aidreverse.roles` les reconnaît par les bits de type.
- **Brighton 1 d'origine** (axe central) : porte Start à 1 036 m, les 4 textes sur la ligne à 1 040 m, grille solo
  (`#27`) de 664 à 996 m. La liste multi (`#97`) a sa grille, mais nommée **`NewStartPosition0..19`** : une place de
  départ se reconnaît à son **type** (champ `StartNumber`), pas à son nom (filtrées par nom, elles restaient sur
  la grille d'origine, dans l'ancien sens : vu en jeu).
- **Textes inutilisés « Reverse »** (`cityandroutenames.loc`) : `CRN_ROUTE_1_REVERSE` « Route 1 Reverse » / « Route 1
  Miroir », `CRN_ROUTE_2_REVERSE`, `CRN_TOKYO_SHUTOKO_R1` « Tokyo Shutoko Reverse 1 » ; aussi `RBC_REVERSED`
  « reversed » / « miroir ». **Les développeurs avaient prévu des routes inversées.**
- `.bpr` : avec la bonne lecture, **les 6 doublons ont des images identiques** → 6 emplacements libres pour les
  images des routes inversées (noms d'au plus 11, 14, 19, 22, 23, 25 caractères).
- **IA en course perso (LAN)** : réglage « Max AI » (`MP_CUSTOM_RACE_AIPADDING`, l'« AI padding » du jeu de base,
  pas d'AMAX), jusqu'à 18 (= 20 voitures − 2 joueurs supposés). Puis le jeu limite à `MultiplayerConfig.max_ai_per_console`
  IA **par joueur** (4 : seul = 4 IA, 2 joueurs = 8, 3 = 12 ; texte `MP_CRHELP_AIPADDING`). Mod : 19 →
  **18 IA seul, confirmé en jeu**.
  Aussi : `ai_padding_limit` = 10 (rôle inconnu), `number_of_ai_players` = [19, 8, 5, 4] (écran partagé 1 à 4
  joueurs ?), 20 `ai_characters`. `GetCustomRaceLimits` (0xC60140) ne renvoie que max_laps, max_time, time_step.
  **20 voitures est une limite du moteur** (20 places de départ, 20 colonnes de difficulté, classement à 20 cases).
  **Testé en jeu** : menu et `max_ai_per_console` à 49 → le jeu coupe à 20 voitures, sans planter (plafond fixe dans le code).
- **Scripts des menus et du HUD** : dans `Blur.exe`, archive **`BZUI`** (après la chaîne de révision du build) :
  gros-boutiste, u32 nombre (144), puis 144 × (u32 nom, u32 données, u32 taille compressée, u32 taille), table des
  noms, données (positions comptées depuis la table des noms) ; chaque script = flux zlib d'un chunk Lua 5.1
  compilé (petit-boutiste). **Confirmé** (`blurui.py` extrait les 144, `luadis.py` les désassemble).
- **Plafond « Max AI » = 18** : constante du script `Screens\Multiplayer\Shared\MpCustomRaceAdvanced.lua`,
  `for i = 2, 18 do UIButtons.AddItem(GUI.ai_padding_id, i, "GAME_NUM_" .. i, true) end`. Sans toucher l'exe :
  plugin AMAX `ai19` (dans `mod_static/`) qui enveloppe `UIButtons.AddItem` et ajoute 19 après 18. **Confirmé en jeu :
  19 IA, 20 voitures.**
- Plugin AMAX `laps` : met aussi `point_to_point = false` pour `JPN_MHaruna_1` (tours sur Haruna).
- `gamedata_boot.pak` n'est **pas ouvert** en jeu normal : le `multiplayer.bin` utilisé est celui de `gamedata.pak`.
- Fichiers ouverts au démarrage : `boot.pak`, `root.pak`, `root_streaming.pak`, `shaders-speed.pak`,
  `lut_rampak.pak`, `gamedata.sig` puis `gamedata.pak`, `levels\<carte>\level.*`, `amax\...` (Lua),
  `%APPDATA%\bizarre creations\blur\settings.xml` et `save\blursave`.

Ancien constat (avant Process Monitor) :

- **Essai en jeu (2026-10-19)** : `gamedata/xt/amax.bin` et `gamedata/xt/multiplayer.bin` posés en clair dans la
  copie ont été **ignorés**. En mémoire, la liste du menu a toujours 30 routes et la chaîne `JPN_MHaruna_7` est
  absente. Le montage du dossier du jeu est pourtant inconditionnel (`0xCB2400` renvoie toujours 1, montage
  sur `/` en `0xCB1610`). Pistes : mauvais chemin logique (les noms internes du pak commencent par `\gamedata\`,
  d'où un essai en `gamedata/gamedata/...`), ou des paks lus sans passer par cette recherche. À trancher avec
  Process Monitor.
- `gamedata_boot.pak` (2010) contient 48 fichiers aussi présents dans `gamedata.pak` (2013). `xt/amax.bin` est
  identique dans les deux, mais **`xt/multiplayer.bin` diffère** (`MultiplayerConfig` = `#735` d'un côté,
  `#736` de l'autre, 30 routes chacun). On ne sait pas encore lequel est chargé.

- Les sources de fichiers sont rangées en **couches** (`0xCB54C0`, un tableau par couche).
  - **Couche 0** : `CFileSystem` = le système de fichiers Windows, monté à la racine, donc **le dossier du jeu**
    (`0xCB1610`, drapeaux 0x11).
  - **Couche 1** : les paks (`0x42D160`, `0xBC3390`) : `root.pak` sur `/`, `root_streaming.pak` sur `/audio/`,
    `shaders-speed.pak` sur `/graphics/shaders/speed/`, `gamedata.pak` sur `/gamedata/` (plus `gamedata_boot.pak`,
    `boot.pak`, `boot_rampak.pak` selon des drapeaux).
- La recherche d'un fichier (`0xCB5700`) liste les candidats **couche 0 d'abord, puis couche 1**, et dans chaque
  couche du dernier montage au premier. **Un fichier en clair dans le dossier du jeu passe donc avant le pak.**
  Non vérifié : la boucle qui ouvre ensuite le premier candidat existant.
- Signature : `0xCBA840` charge `cache/gamedata.sig` (et `gamedata_boot.sig`) s'il existe et a la bonne taille
  (clé publique de 0x8C octets en `0xE678F8`) ; elle porte sur les paks. `Util.LogicalFs.VerifyPaks` est une
  commande de débogage (rappel `0xCB2420`). Un fichier en clair n'est pas concerné.
- `Mercury.FileSystemGlobals.FileAccessOrder` n'est qu'un nom de statistique (aucun code ne lit sa valeur).
- **Où poser un fichier modifié** (dans la copie du jeu) : le chemin du pak, sous la racine du jeu. Exemples :
  `gamedata/xt/amax.bin`, `gamedata/xt/multiplayer.bin`, `gamedata/levels/jpn_mharuna/jpn_mharuna_7.aid`
  (chemin construit en `0xBBDD80`). Les `levels/<nom>/Level.*` sont déjà en clair dans le dossier du jeu.

### 3.2 `.loc` (« OLTX », textes) : **Confirmé** — outil `blurloc.py`

5 langues (en, fr, de, it, es), chaînes UTF-16, clés en clair + hash 32 bits (fonction de hash inconnue,
pas nécessaire pour lire).

### 3.3 `.bin` / `.xt` (« KSLF », le format « Flask ») : **Confirmé** — outil `blurxt.py`

Tables de données du jeu (voitures, IA, épreuves, bonus…). 26 fichiers `.bin` + les `actorpack.xt` des niveaux.

- En-tête : `KSLF`, u32 version (1 ou 2), puis 8 couples (offset, nombre) :
  0 types (12 o), 1 parents (u32), 2 champs (8 o), 3 noms, 4 index (8 o), 5 enregistrements (16 o),
  6 chunks (6 o), 7 données.
- **Noms chiffrés** (version 2) : fonction `0x5871B0` de `Blur.exe`
  (`dl=0xCC ; out=(dl-(b^0xB3))&255 ; dl=(dl+out-i)&255`). L'encodeur inverse est en `0x5871F0`.
- Types : (nameOfs, nbChamps, aUnParent, genre, primitif, taille) ; genre 3 = structure, 2 = drapeaux,
  1 = énumération, 0 = primitif. Les champs (et les valeurs d'énumération) se suivent dans la table des champs.
- Enregistrement : (idx, nbChunks, tailleDonnées, tailleChaînes). Les chunks se suivent, puis une zone
  de chaînes chiffrée comme les noms.
- Tableau = `(chunk | début<<16, nombre)` ; pointeur interne = `chunk | élément<<16` ;
  chunk avec drapeau pointeur ≠ 0 = éléments de 4 octets ; `0xFFFFFFFF` = nul.
- Référence externe (drapeau 5) = case de l'index (section 4) donnant le hash de la cible ; si l'élément
  local vaut 0xFFFF, la cible est dans un autre fichier (on la retrouve par son hash).
- Chaîne de chargement dans l'exe : `0x585660` (entrée) → `0x584700` (validation, « Flask failed validation »)
  → `0x5850D0` (schéma).

**Écriture** (2026-10-19) :
- `encode_names` (inverse de `0x5871B0`) : aller-retour **identique à l'octet** sur les 49 fichiers KSLF
  (zones de noms) et sur les 6 622 zones de chaînes des enregistrements. **Confirmé.**
- Modification **sur place** d'un nombre, booléen ou énumération, par chemin :
  `blurxt.py --set ENTREE.bin SORTIE.bin "Enregistrement" "engine.engineTorque_Rpm.dataPoints[7]" 1.5`.
  Testé sur 7 cas (réel, élément de tableau, réel imbriqué, énumération, booléen, profil IA, voiture) :
  la valeur se relit, et un seul enregistrement change. **Confirmé** hors jeu ; **jamais testé en jeu**.
- **Reconstruction complète** (`kslfwrite.py`, 2026-10-19) : les 49 fichiers sont relus puis réécrits
  **identiques à l'octet**. **Confirmé.** Règles de disposition : sections contiguës à partir de 0x48, seule la
  section données alignée sur 4 (zéros) ; l'`idx` d'un enregistrement est toujours son emplacement dans l'index ;
  enregistrements alignés sur 4, zone de chaînes multiple de 4.
- **Ajouts** :
  - `clone(source, nouveau_nom, hash)` : copie un enregistrement avec un nouveau nom ;
  - `add_external(hash, type)` : déclare une référence vers un enregistrement d'un autre fichier ;
  - `append_to_array(propriétaire, champ, emplacement)` : ajoute une référence à une liste et **décale les
    tableaux et pointeurs qui suivent** dans le même chunk.
  - Test : route `JPN_MHaruna_7` clonée dans `amax.bin` et ajoutée à `MultiplayerConfig.routes` (30 → 31,
    arènes intactes) ; relecture complète : seuls ces deux enregistrements changent. **Confirmé hors jeu.**
  - Les nouveaux enregistrements reçoivent un hash au-dessus de tous les existants (le plus haut : 0xFFFE3216),
    donc ajoutés en fin d'index sans décaler les emplacements. La fonction de hash du jeu (nom → hash) reste
    inconnue : une recherche par nom pourrait ne pas trouver un ajout. **Risque, non testé en jeu.**
- Aussi : `clone` accepte les enregistrements sans nom (ex. `LevelActorList`, nommés `#<emplacement>`) ;
  `set_array_ref(propriétaire, champ, i, emplacement)` remplace une référence dans une liste.
- Grilles de départ (actorpack) : une `Route` désigne ses objets par `ActorLists` (solo) et `MultiplayerActorLists` ;
  sur Haruna, la grille est dans les listes #62 (solo) et #15 (multi), avec le point et les zones « Hand of God »
  et les textes `Start_Text_*`. Matrice d'un objet : `az` = avant, `ax` = opposé de l'axe latéral des `.aid` (le nœud `.aid` est un bord de la route),
  `aw` = position. Sur Haruna, les hauteurs des `.aid` sont ~11-14 m sous le sol réel. **Confirmé** (mesuré).
- Pas encore possible : modifier une chaîne existante, insérer dans un tableau d'éléments non-référence.
- Attention : une fiche physique peut être partagée par plusieurs voitures (ex. `*_Shannon`).

Commandes : `blurxt.py FICHIER` (schéma), `blurxt.py --json FICHIER`,
`blurxt.py --all DOSSIER_XT SORTIE levels/*/actorpack.xt` (tout, références résolues :
**0 référence non résolue**).

### 3.4 `.model` / `.texture` : **Fort** — outils `blurmodel.py`, `blurtex.py`

- Textures = DDS sans en-tête (DXT1/DXT5). `blurtex.py` extrait toutes les textures d'un `.model`
  (intégrées + niveaux de mip en flux) et sait les **réinjecter** (`blurtex.py inject`).
  Aller-retour vérifié sur bmw_m3e92_tuner ; **jamais testé en jeu**.
- La peinture de carrosserie est faite par des shaders (`veh_Paint_*`), pas par une texture.
  Les voitures avec une texture de livrée (modifiables) sont listées dans le cahier des charges.

### 3.5 Fichiers de niveau (`levels/<nom>/`) : en cours

| Fichier | Format | Contenu | État |
|---|---|---|---|
| `.level` | « CP » (chunks) | Header, MdlDat, NavDat, Advert, MtaDbg (journal d'export) | Structure lue |
| `.levelphysics` | « CP » | Physic { Header, Main (collision), Routes { Route… } } | Structure lue, contenu non décodé |
| `.levelrender` | « CP » + archive « ARCH » | rendu (`RenderingData::CullNode`…) | Non décodé |
| `.levelstream` | archive « ARCH » | géométrie en flux | Non décodé |

Format « CP » (outil `cpdump.py`) : magie `"  CP"`, puis des chunks
`[tag 8 o][u32 taille, en-tête de 16 o inclus][u16 nombre][u16 'C' conteneur ou 'A' données]`. **Confirmé.**

Dans `gamedata/levels/<nom>/` (extrait des `.pak`) :

- `actorpack.xt` (format KSLF) : **objets placés sur la carte**. Positions de départ (`StartPosition`, grilles
  de 20), bonus (dont `Stopwatch`, placé 60 fois sur Amboy), zones de déclenchement (`FailTriggerRegion`,
  `FanTriggerRegion`), objets physiques, effets… Lu et décodé. **Confirmé.**
- `<nom>_<n>.aid` : **trajectoires de l'IA et logique de course**, voir 3.6.

Les `Routes` de `.levelphysics` (Amboy : 4 chunks Route ; un Route = en-tête, 4 compteurs comme
462/219/5188/77, boîte englobante, 462 points groupés en « portes », puis ~970 Ko compactés) : **non décodées**.

### 3.6 `.aid` (données de piste de l'IA) : **Confirmé** (structure) — outil `blurroute.py`

**Les 33 fichiers se lisent intégralement, jusqu'au dernier octet.**
Le vocabulaire vient des noms de débogage de l'exe : `AmaxAI.DebugDraw.TrackData.{Racing, RacingSpline,
RacingWidth, ExtremeWidth, Segment, Junctions, Logic, LogicStart, LogicInter1, LogicInter2, LogicFinish}`.

- Fichier : f32 version (6.0), u32 nbBlocs, les blocs, puis la table logique.
- Chaînes : u32 longueur + caractères (sans NUL ni bourrage). Nœud = **323 octets**.
- **Bloc section** : nom, u32 0, u32 0, u32 type, [u32 en plus si type & 0x80], u32 nombre, nœuds.
  Bits du type : 0x01 boucle fermée, 0x02 départ, 0x04 arrivée, 0x08 intermédiaire 1, 0x10 intermédiaire 2,
  0x20 ligne logique, 0x80 entier supplémentaire, 0x400 inconnu (5 boucles principales).
  0 = tronçon (raccourci / variante), 1 = boucle principale, 0x21 = logique en boucle, 0x20 = logique d'un point à un autre.
- **Bloc jonction** : nom, section de départ, section d'arrivée, u32 drapeaux (0x40 ou 0xC0).
  Si drapeaux & 0x80 : u32 genre, puis genre 5 → u32 + 3 réels, 9 → u32 + 2 réels, 6 → u32 + 1 réel,
  2 → nom de section + u32. Ensuite u32 nombre + nœuds.
  Signification des valeurs (poids de choix de route pour l'IA ?) : **Hypothèse**.
- **Table logique** (fin du fichier) : u32 N (= nombre de nœuds de la ligne logique), puis pour chaque
  nœud logique : u32 n, n × (u32 index de nœud, nom de section). 137 032 renvois au total, **tous valides**.
- **Nœud (323 octets) = en-tête de 48 octets + 11 « lignes » de 25 octets.** Statistiques mesurées sur
  les 99 181 nœuds des 33 fichiers :

  | Offset | Contenu | Confiance |
  |---|---|---|
  | +0 / +4 / +8 | position x, y, z (**Z inversé** par rapport au niveau) | Confirmé |
  | +12 | largeur (m) : l'échelle latérale des 11 lignes (plus grande sur la ligne logique : un couloir) | Confirmé |
  | +16 / +20 | direction latérale (vecteur unitaire en X, Z), perpendiculaire à la route (produit scalaire médian -0,999) | Confirmé |
  | +24 / +28 / +32 | même axe latéral en 3D, incliné par le **dévers** (partie horizontale identique à 100 %) | Confirmé |
  | +36 / +40 | hauteurs basse et haute, plus larges que celles des lignes (plancher et plafond du volume de piste ?) | Hypothèse |
  | +44 | toujours 0 | Confirmé |

  Ligne k (k = 0 à 10), à l'offset 48 + 25 × k :

  | Offset | Contenu | Confiance |
  |---|---|---|
  | +0 | lié à l'angle de virage de la ligne entre deux nœuds (corrélation 0,65) : indication de braquage ? | Hypothèse |
  | +4 | longueur jusqu'au nœud suivant le long de cette ligne (m ; écart médian 0,015) | Confirmé |
  | +8 | toujours 0 | Confirmé |
  | +12 | hauteur du point de la ligne (écart médian 0 avec y + dévers × décalage latéral) | Confirmé |
  | +16 | position latérale de 0 à 1 (médianes 0,24 … 0,77 ; ligne 5 au centre, 0,5) | Confirmé |
  | +20 à +24 | toujours 0 | Confirmé |

  Point d'une ligne = (x, y, z) + axe latéral 3D × (fraction − 0,5) × largeur. Les 11 lignes sont donc des
  trajectoires parallèles à travers la route, au même nombre sur chaque nœud (rôle exact pour l'IA :
  choix de ligne, dépassement ? **Hypothèse**). `blurroute.py --full` les exporte.
  Pour inverser une route (projet C), les champs orientés sont : la direction latérale et l'axe 3D (à
  retourner), l'ordre des 11 lignes et leurs fractions (1 − f), `+4` (longueur vers le nœud *suivant*,
  à décaler d'un cran) et le signe de `+0` (si c'est bien un virage).
- Validation visuelle : les trajets passent par les grilles de départ ; Brighton est en huit ;
  Haruna est une descente d'un point à un autre. Exports JSON + PNG dans `blur_extracted\routes`.
- Chaque carte a une ou plusieurs routes (Amboy : `_1`, `_3` ; Brighton : `_1`, `_2`, `_3`, `_5` ;
  Haruna : `_1`). Il y a parfois plus de grilles de 20 que de routes (Haruna : 2 grilles, toutes deux en haut,
  dans le même sens ; sans doute une par mode). Chemin construit par l'exe en `0xBBDD80` :
  `.\gamedata\levels\%s\%s.aid`.
- **Les hauteurs des `.aid` ne décrivent pas fidèlement le relief** : certains tronçons sont plats à hauteur
  constante (Amboy `Catch` à 0 m, `CrossRamp` à 4,31 m ; boucles de Brighton 1 et 5, figure de 8), et `AltRamp`
  ne montre qu'une descente douce. Le jeu trouve sans doute le sol par la collision. Les `.aid` seuls ne
  permettent donc pas de détecter un saut. **Confirmé.**
- Indices de sauts dans les actorpacks : Brighton `Jump_Entry/Exit_Trigger_Box` ×4 + `JumpFailResetPosition` ×4
  (sur la boucle de la route 2) ; Downtown `Building_TopofJump` (à 92 m de haut, 40 m des routes 1 et 6) ;
  River `FloodgateLanding` ×6 et Docks `Ramp` ×2 (110 à 600 m des tracés). Tronçons nommés : Amboy 1
  (`AltRamp`, `CrossRamp`, `FlatbedRamp`), Docks 3 (`Ramp`, `RampCatch`), River 3 et 6 (`Altjump`).
- **Écriture** : `blurroute.parse(b, raw=True)` garde l'ordre des blocs et les 323 octets de chaque nœud ;
  `blurroute.build(d)` réécrit le fichier. Aller-retour **identique à l'octet sur les 33 fichiers**. **Confirmé.**
- Non validé en course.

---

### 3.6 bis `.bpr` (« 2RZB », images de l'interface) : **Confirmé** — outil `blurbpr.py`

- En-tête de 0x14 o : `2RZB`, u16 version 0x203, u16 = octets de la table + des noms, u32 octets de la table
  (n × 28), u32 octets des données, u32 0.
- n entrées de 28 o à 0x14 : u16 0x1C, u16 début du nom (table des noms), u32 début des données, u32 1, u32 taille,
  u32 0, u16 format (1 = DXT1, 5 = DXT5, 6 = RGBA), u16 nombre de mips, u16 largeur, u16 hauteur.
- Puis la table des noms, puis les données, qui commencent **juste après les noms** (`0x14 + u16 à +6`), puis
  du bourrage jusqu'à la fin du fichier (1 392 o pour `ui_frontend.bpr`). **Confirmé** en jeu : lues depuis
  « fin − taille des données », toutes les images sortaient décalées de 1 392 o (= 174 blocs DXT1 = une rangée
  + 184 px : coupure verticale et image enroulée, le même genre de décalage que sur NFS).
- Vérifié sur les 4 `.bpr` : réécriture identique à l'octet ; 224/226 tailles égales au calcul (format, mips).
- **Images de présentation des circuits** (menu « Track » et écran de chargement) : dans
  `root.pak` `ui\data\ui_frontend.bpr`, **nommées comme la route** (`JPN_MHaruna_1` : DXT1 512×256, 2 mips ; le menu
  montre la partie gauche ~330 px). Le champ `Thumbnail` de la `Route` n'est pas utilisé pour ça : le Lua reçoit
  le nom (`+0x10`). Sans image du bon nom → fond blanc lumineux (vu en jeu).
- `JPN_MHaruna_7` : image de la Descent + symbole demi-tour néon (`thumbreverse.py`). `root.pak` passe avant
  les fichiers en clair : dans la copie de test, `root.pak` est mis de côté et son contenu posé en clair.
  **Essai 1** : image ajoutée à la fin du fichier → le jeu trouve le nom (écran noir au lieu de blanc) mais
  n'affiche rien (budget mémoire des textures d'interface ? **Hypothèse**). **Essai 2** : `ui_frontend.bpr` contient
  6 noms en double ; `USA_Amboy_3` a deux copies identiques, la 2e est reprise pour `JPN_MHaruna_7` (nom écrit
  dans les octets libres après les noms). **Résultat : TOUTES les images d'interface corrompues.** Cause
  (**Confirmé** par l'effet) : le u16 à +6 (table + noms) donne au jeu le **début des données** ; l'augmenter de
  14 octets a décalé toutes les images. **Essai 3** : l'en-tête et la table ne changent plus ; le 2e
  `USA_LA_Downtown_FigureOf8` (images identiques, nom de 25 caractères) reçoit « JPN_MHaruna_7 » écrit **sur son
  propre nom** (complété de zéros) et notre image. À voir en jeu.
- **Règle d'écriture d'un `.bpr`** : ne jamais changer la taille de la table ni des noms (le début des données
  en dépend) ; remplacer en place. Doublon réellement identique (bonne lecture) : `JPN_Tokyo_Shutoko_4` (n° 17 et
  101), le 2e est repris pour `JPN_MHaruna_7`.

### 3.7 Inventaire du dossier du jeu (2026-10-19) : ce qui reste non lu

| Zone | Taille | Contenu | État |
|---|---|---|---|
| `levels/*/level.levelrender`, `.levelstream` | ~4,9 Go (avec `.level*`) | géométrie et rendu des cartes | **non décodé** |
| `levels/*/level.levelphysics` | | collision : `Main` + un bloc `Route` par `RouteNumber` (route jouable) | structure ; contenu non décodé |
| `levels/*/level.level` | | MdlDat, NavDat, Advert, MtaDbg | structure seulement |
| `root.pak` `ui\data\*.bpr` (4) | 46 Mo | images des menus / HUD, magie `2RZB` | **décodé** (3.6 bis) ; pas de Lua dedans |
| `root.pak` `ui\data\ipf\*.ipf` (75) | 29 Mo | images d'interface, dont une **mini-carte par carte** (`minimap\jpn_mharuna_game.ipf`) | **non décodé** (utile pour le HUD) |
| `root.pak` `ui\data\pf\*.pf`, `ui_font_eur.*` | | polices | non décodé |
| scripts Lua des menus (`Screens\...\MpCustomRace.lua`…) | ~0,4 Mo | **dans `Blur.exe`** : archive `BZUI` (144 scripts Lua 5.1 compilés, zlib) | **extraits** (`blurui.py`), lisibles (`luadis.py`) |
| `root.pak` `animations` (`.cycle`, `.skeleton`) | ~1 300 fichiers | animations (pilotes, foule…) | non décodé |
| `root.pak` `audio` (`.baf`, `.dat`, `.wbl`) + `root_streaming.pak` | ~700 Mo | sons, musique | non décodé |
| `shaders-speed.pak` | 6 Mo | shaders | non décodé |
| `root.pak` `dontship` (42) | 16 Mo | restes de développement : police de débogage, cubemaps, textures de test | lu (rien de jouable) |
| `UI/movies/*.bik` (31) | 1,3 Go | vidéos Bink (tutoriels, boss vaincus) | format standard |
| `Docs/` | | lisez-moi, licences | sans intérêt technique |

## 4. Données de jeu décodées

Exports JSON de tous les `.bin` : `blur_extracted\xt_json`. Récap des voitures :
`carsummary.py` → `blur_extracted\blur_voitures.csv` (81 voitures).

| Fichier | Contenu utile |
|---|---|
| `amax.bin` | `AmaxVehicle` (81 voitures : classe, `GameplayTopSpeed`, stats d'interface, lien vers la physique…) |
| `racingphysics.bin` | `RP_CarDynamics` (62 fiches : masse, moteur et courbe de couple, rapports, pneus, freins…) |
| `air.bin` | profils IA : `AISkillz`, `AIPerkSkillz`, `AIPerkPrefs`, `AISteering` |
| `singleplayer.bin` | 86 épreuves `AmaxEvent`, avec réglages Easy/Medium/Hard (`DifficultySettings`) |
| `pickups.bin` | bonus (11 `PickupType` et leurs variantes) |
| `finalracebook.bin` | pilotes (`RaceBookCharacter`) et leurs voitures (`RaceBookVehicle`) |

Fichiers de difficulté : `gamedata/events/*_easy|medium|hard.csv`, désignés par `AIBalancingFileName`.
Chaque colonne = une voiture (colonne 0 = joueur). Une ligne donne l'`Index` du profil `AIPerkSkillz`, la suivante
celui de `AIPerkPrefs`. **Confirmé** (correspondance des valeurs et lecture en mémoire).

### Circuits et menus : **Confirmé** (données)

- `amax.bin` déclare **22 villes** (`City` = une carte) et **70 routes** (`Route`), chaque route avec : ville,
  `RouteNumber`, nom affiché (`LocString`), vignette (`Thumbnail`), `CircuitType`, `OnlyAllowSingleLap`…
- Seules 33 routes ont un `.aid`. Les autres : une **route 0** sans `.aid` pour chaque ville (rôle inconnu ;
  `JPN_MHaruna_0` est de type « Hilly » alors que la route jouée `_1` est « Technical »), des routes de test
  (`*_OBJTest`, `QuickExport_0…6`, `VehicleTestScene`).
- **Les menus utilisent des listes explicites**, il n'y a pas de parcours automatique des routes :
  - multijoueur / course perso : `multiplayer.bin` → `MultiplayerConfig.routes` = exactement les **30 routes
    jouables** ; `arenas` = 4 arènes ; `defaults.track` = USA_Amboy_3 ; aussi `online_playlists`,
    `splitscreen_playlists`, `system_link_playlists` ;
  - carrière : `singleplayer.bin` → `SP_TierData` = 9 paliers (épreuves avec restriction de classe et
    objectif de fans) et 9 boss ; chaque `AmaxEvent` désigne sa route ;
  - écran partagé : `splitscreen.bin` → `AmaxSplitScreenEvent` ;
  - succès : `achievements.bin` → `AllCitiesInTheGame` (14 villes).
- **Ajouter un circuit au menu** = déclarer la `Route` (et la `City` si nouvelle carte), un texte `.loc`,
  une vignette, puis l'ajouter à `MultiplayerConfig.routes` et/ou créer une épreuve dans un palier.
  Aucun bouton à coder, mais il faut savoir **écrire** le KSLF. Ce qui se passe si on touche au multijoueur
  en ligne : **inconnu**, à éviter.
- **Menu course perso (Lieu / Circuit)** : **Confirmé** (code). Les fonctions Lua `GetCustomRaceCities(mode)`
  (`0xC6C4F0`) et `GetCustomRaceRoutes(id)` (`0xC6C760`) parcourent la liste de routes à `[0x10FBF90]+0x88`
  (`+0x90` pour le mode 3 = arènes) = `MultiplayerConfig.routes`. Les lieux sont dédoublonnés par ville,
  les circuits filtrés par ville. Elles renvoient au Lua l'id, le nom (`LocString`), la vignette, `debug_tag`
  et `point_to_point`. En mémoire, un enregistrement est décalé de +8 par rapport au fichier (`City` à `+0x20`).
  Les écrans de menu sont des scripts Lua (`Screens\Multiplayer\Shared\MpCustomRace.lua`…) dont les noms sont
  dans l'exe. On ne les a pas trouvés dans les paks.
- **Texte inutilisé « Ascent » / « Montée »** : clé `CRN_MOUNT_HARUNA_2`, hash **226956641**, dans
  `cityandroutenames.loc`. Les développeurs avaient prévu une montée d'Haruna. On s'en sert comme nom de
  `JPN_MHaruna_7` (`LocString` = hash de la clé).

### Bonus et contenu laissé par les développeurs

| Bonus (nom interne) | Variantes dans `pickups.bin` |
|---|---|
| Nitrous (Nitro) | Normal, DoubleTap, Reversed |
| Shunt | Normal, DoubleTap, Reversed |
| Bomb (Mine) | Normal, DoubleTap, Reversed, Mini, Modified |
| Shock | Normal, DoubleTap |
| Shield | Normal, DoubleTap |
| Blindfire (Bolt) | Normal, Reversed, Modified, ReversedModified |
| Barge, Repair | Normal |
| SuperShield | Normal (non rencontré en jeu : **Hypothèse** contenu coupé) |
| Stopwatch | Normal (placé dans les niveaux, donc **utilisé**, sans doute en mode checkpoint) |
| Fan | Normal (bonus de fans) |

- **DoubleTap** (combiner deux bonus) : coupé avant la sortie, mais 5 bonus ont encore leurs réglages
  DoubleTap. Noms restés dans `Blur.exe` : `DoubleTap`, `ReversedDoubleTap`, `NitrousDoubleTapBalancingData`,
  `BombDoubleTapBalancingData`, `ShuntDoubleBalancingData`, `DoubleShuntReverse`, `PickupShuntDoubleSpecialFX`.
  **Mis à jour 2026-10-19 :**
  - Réglages DoubleTap (`pickups.bin`, `PickupType.DoubleTap` → `PickupLevel`) : Nitro = **faille** (RiftRadius 30 m,
    force 500–1500, 2,5 s) ; Bouclier = Lifetime **12 s** (6 normal) ; Mine = rayon 2 / zone 5 m, vie 3 s (60) ;
    Shunt = `ShotDelay` 0,5 (tir double ?) ; Shock = zone 14,5 m (14). Effets visuels propres à chaque niveau.
  - **Le code des effets est vivant** : recyclé en capacités de voitures de boss, champ `AmaxVehicle.BossAbilitySlot`
    (`Dodge_ViperGTSR_Stock_Carver` = `BossNitroRift`, `Foose_Stallion_Stock_Khan` = `BossDoubleShield`, autres boss :
    ShotgunBlindfire, RepairBonus, AdditionalBlindfireShots, FansNitroGift, AdditionalShockDomes, ShuntDamage),
    et en multijoueur `MultiplayerAbility` « Slot4 ».
  - Déclencheur d'origine (combiner deux bonus) : variables de débogage `Perks.DoubleNitrous.ForceDoubleNitrous`,
    `Perks.DoubleShield.ForceDoubleShield`, `Perks.DoubleShock.*`, `Perks.DoubleBomb.NumMines/SpreadDistance`,
    `Perks.DoubleShuntReverse.*`. Leur fichier de valeurs `debug_values.xml` / `User\debug_values.xml` a un chargeur
    (`0xD62140` → `0xD61DF0`) **jamais appelé** (code orphelin) : pas activable sans modifier l'exe.
  - `GetXtVar` / `SetXtVar` (Lua) : propriétés des éléments d'interface, pas les variables de réglage.
  - Scrambler (mod multijoueur) : tirs inversés qui bloquent les bonus adverses ; réutilise la faille du nitro
    (`scrambler_enabled_nitro_rift`).
  - **Essai « niveau DoubleTap à la place du normal » (`pickups.bin`, en jeu 2026-10-19)** : les IA utilisent les
    5 sans souci. Pour le joueur : **Bouclier OK (12 s)** ; Mine OK (vie ~3 s, mêmes dégâts) ; Shock OK (aucune
    différence visible) ; Nitro : aucun effet (réglages d'un autre type, la faille passe par `BossNitroRift`) ;
    **Shunt : plantage** (réglages DoubleTap incomplets : pas de Radius/FallRate/ECM*).
- « Reversed » = tir dans l'autre sens (vu en jeu : « Forward fire Mine »). **Fort.**

**Restes de développement (passe du 2026-10-19)** :
- **Menu de débogage des développeurs** (scripts BZUI `Screens\Debug\*`) : `DebugScreen` (menu), `DebugEventScreen`
  (lancer n'importe quelle épreuve), `DebugCarScreen` (n'importe quelle voiture), `DebugLoadReplays`,
  `DebugContentServer` (« CONTENT SERVER TEST BED »), `DebugUI`, `QuitandWin` (depuis la pause : « QUIT AND WIN »).
  Entrée : écran titre, touche Y, **si `UIGlobals.DevMode == true`** (`StartScreen` : `allow_debug_buttons`) ; la
  gâchette droite bascule « DEV MODE : DEBUG / MASTER » (`Amax.GetSetDebugDevMode`). Un plugin AMAX pourrait
  mettre `UIGlobals.DevMode = true` (non testé).
- **Triche « voiture chromée »** : dans le garage solo, `Amax.CheckChromeVehicleGarageCheat(id)` attend une séquence
  de 4 touches clavier (A–Z) devant une voiture donnée. Données `DLCCheatChromeVehicle` (« dlc pack offer e
  deployed », « walmart deployed ») : un seul enregistrement « Test » (BMW Série 1 → version chromée), code vide :
  bonus de précommande jamais finalisés. `UnlockViperCheat` (Lua) débloque la Viper.
- **Mode coupé « Motor Mash »** : textes « Motor Mash Test », « Motor Mash test bowls », champ `DisabledInMotormash`
  des bonus.
- Textes de développeurs : « [TODO] Please fill out my description in sorcery!!! », « QA - Don't test this :) »,
  « This is all debug colors and layout!!!!! », « Placeholder Results Screen », « Racing (Beta) », playlist « Debug
  earn Fans quickly », voitures « Astra Extreme (Physics Test) » / « Nemesis (Physics Test) », démo commerciale
  (« Code accepted. Thank you for playing the Demo. », « Demo Event 1 - Barcelona Oval », « … 2 - LA Downtown »),
  bêta multijoueur (« The Blur multiplayer Beta is now closed. »).
- Pistes IA sans route : `uk_brighton_5` (= Brighton 1 à 100 %, 2 954 m) et `usa_la_downtown_3` (= Downtown 4,
  3 409 m) : anciennes numérotations, **pas de tracé inédit**. Les blocs de collision `Route` 2, 3, 5 de Downtown sont
  vides. Les 4 « routes hors menu » restantes sont les arènes (`MultiplayerConfig.arenas`).
- Niveaux et routes de test : `VehicleTestScene`, `QuickExport_0..6`, `*_OBJTest`, `Graphical_1` (« Cut Scene Test »),
  `ShowRoom` ; textes « AI Test Level », « Particle Test », « Physical Object Test Scene ».
- Autres restes : toute une physique de moto (`RP_Motorbike*`, sans doute venue du moteur partagé),
  triches (`Cheats.Difficulty`, `Cheats.NumEventLaps`, `UnlockViperCheat`…), débogage (`SetupDebugRace`,
  `UseDebugHud`, `E3EnablePlayerControls`), épreuves de test (« Balancing Test 1 à 13 »,
  « Freeze Powered Up Test »…), niveaux `vehicletestscene` et `quickexport`.

---

## 5. Mémoire du jeu en course (lecture seule) — outil `blur_live.py`

### Liste des véhicules : **Confirmé** (plusieurs courses)

```
R = [[[[0x11AA04C] + 0xC90] + 0x30] + 0xA10]     gestionnaire des véhicules de la course
[R + 0x1A0]           nombre de véhicules
[R + 0x64 + i*0x10]   handle du véhicule i (PAS un pointeur)
[R + 0x68 + i*0x10]   objet du véhicule i
octet [R + 0x2EC]     index du véhicule du joueur (0 dans toutes nos courses)
```

Trouvé via la fonction Lua `GetPlayerVehicleIndex` (`0xC31F30` → `0xB824A0` → `0x49B310`).

### Objet véhicule

| Donnée | Offset | Confiance | Comment c'est validé |
|---|---|---|---|
| Position (m, Y = hauteur) | +0x130 / +0x134 / +0x138 | Confirmé | copies en +0xF0, +0x1CC, +0x5B0 |
| Vitesse (m/s, ×3,6 = km/h) | +0x13C / +0x140 / +0x144 | Confirmé | rapport 1,006 avec le déplacement mesuré |
| Vecteur avant (unitaire) | +0x124 (copie +0xE4) | Fort | aligné à 99,7 % avec la vitesse |
| Vecteur latéral (unitaire) | +0x10C (copie +0xCC) | Fort | perpendiculaire à l'avant |
| Nom de la fiche physique | [+0x2A8] → chaîne | Fort | parfois invalide (`?`) : mémoire réutilisée |
| Objet physique | [+0x238], masse en +0x1D4 | Confirmé | 20/20 masses identiques aux fichiers |
| Chrono `+0x638` | +0x638 | Hypothèse | même valeur pour toutes les voitures, ~0,98 s/s, remis à 0 pour une voiture : temps au tour ? |
| `+0x1FC` | +0x1FC | — | suit les virages mais n'est PAS une vitesse angulaire en rad/s |
| Accélération, vitesse angulaire | — | — | non stockées ici : à calculer depuis la vitesse et la rotation |

### Pilotes : **Fort**

`[0x1134DCC]` = vecteur `{données, capacité, nombre}` des objets pilote ; objet pilote +0xC = objet véhicule.

### Profils IA en course : **Confirmé** (2 courses de carrière, épisodes différents)

```
X = [[0x1134DC0] + 0x2C]        (vtable 0xEC3B94)
[X + 0x48] = tableau de 20 entrées {paliers, capacité, n}   (une par colonne du CSV, même ordre que les véhicules)
palier = 0x20 octets, 10 par voiture :
  +0x00 i32   +0x04 f32 (ligne CSV « 0,400,3,5… »)   +0x08 f32 (ligne « 1,0.95,0.91… »)
  +0x10 i32 (ligne « 1,1,0… »)   +0x18 hash AIPerkSkillz   +0x1C hash AIPerkPrefs
Listes chargées : [0x1134E9C] × [0x1134EA4] AIPerkSkillz ; [0x1134E84] × [0x1134E8C] AIPerkPrefs
  enregistrement en mémoire : +0x10 nom, +0x14 hash, +0x18 Index
```

Exemples vérifiés : Hummer = « T4 Drayke Skills 400 » (boss Drayke) ; les deux Skyline R34 =
« T7 Ayumi/Harumi Skills 700 » (les jumelles). Le CSV est lu par le « RaceDirectorSystem » (`0x4C5E20`),
la préparation de l'épreuve est en `0xBC1E70`.

### Caractéristiques de l'IA : inventaire (2026-10-19)

Trois couches :

1. **Profils** (`air.bin`) : `AIPerkSkillz` (50 : par bonus Offensive / Defensive / Avoidance, plus Racing,
   Aggression, Blocking, Slamming, Mistakes ; « Difficulty 1..10 » = Index 50..59, « Tier 0..10 Skills »),
   `AIPerkPrefs` (33 : préférence par bonus), `AISkillz` (32 : BackwardFiring, ForwardFiring, Defensive, Offensive,
   Racing, Aggression, Blocking, Slamming, Mistakes), `AISteering` (6 : PID de direction, ForwardsDist,
   SteeringRate…), `AI` (2 : `Air_Default` = BrakingCoefficient 1.0, FrictionCoefficient 1.212, Block ;
   `DEBUG_Easy`). Chaque `RaceBookCharacter` (pilote) a un `AITemplate` (Air_Default pour les boss).
2. **Race Director** (`RaceDirectorSystem`, `RubberbandingAI`, `air.rubberbanding`) : fichiers
   `events/<épreuve>_easy|medium|hard.csv` (course perso : `multiplayer_*.csv`, écran partagé :
   `splitscreen_*.csv`). En-tête (1.0, 10 paliers, 20 voitures), puis par palier 7 lignes × 20 colonnes :
   i32, f32 distances (`0,-3,3,5,35…`), f32 facteurs (`1, 0.84…0.87`), f32 (`0.55`), i32 (`1,1,1,1,0…`), i32,
   Index `AIPerkSkillz`, Index `AIPerkPrefs`. Sens exact des lignes chiffrées : **à établir** (rattrapage ?).
   **Les profils « Difficulty 1..10 » (Index 50..59) utilisés par `multiplayer_hard.csv` sont identiques** (même
   valeurs, nom et Index mis à part) : en Hard, toutes les IA ont le même profil moyen. Profils forts :
   `Tier 10 Skills` (70) et `T9 Shannon` (900), 1,0 partout en attaque et défense.
   Référence mesurée (Brighton 1, 3 tours, 19 IA Hard, classement officiel) : 1er 2'41"15, médiane 2'56"87,
   dernier 3'03"63. Le chrono officiel ≈ temps entre le 1er et le 4e passage de ligne (la grille est derrière
   la ligne).
   **Essai 1 (Tier 10 Skills pour toutes les IA, tous les paliers)** : 1er 2'42"14, médiane 2'57"05, dernier
   3'04"12 → **mêmes temps** (< 1 s), alors que le joueur a roulé autrement (3'04 contre 4'37). Le profil
   d'habileté règle l'usage des bonus, pas le rythme ; **le rythme est imposé par le Race Director** (**Fort**),
   cohérent avec l'observation « freinage juste après un nitro ».
   Décodeur (`0x4C5E20`) : ligne distances → palier +4 ; ligne facteurs → +8 = facteur − X[+0x44], au moins
   X[+0x48] (X = objet lié à la difficulté) ; ligne 0.55 → +0xC. Les variables `AmaxAI.DebugCar.Player.
   BrakeTrackSpeedPercentage{,Easy,Medium,Hard}` (0x1134C30/68/A0, défaut 0,95 / 1 / 1) concernent l'aide au
   freinage du **joueur**. **Essai 2 (facteurs à 1,2 pour toutes les IA)** : 1er 2'35"39 (−5,8 s), médiane
   2'43"86 (−13,0 s), dernier 2'48"93 (−14,7 s), écart 1er–dernier 13,5 s au lieu de 22,5 s. **La ligne des
   facteurs est le plafond de vitesse de chaque IA (Confirmé)** : original 1,0 pour les 4 premières IA, 0,84–0,87
   pour les autres (d'où le freinage après un nitro).
   **Essai 3 (facteurs 1,5)** : 1er 2'30"38, médiane 2'45"77, dernier 2'51"24 → médiane et dernier comme à 1,2
   (±2 s de variation d'une course à l'autre), seul le 1er gagne encore 5 s : **au-delà de ~1,2 les IA sont à leur
   limite physique** (voiture, tenue de route).
3. **Aides** : variables de débogage `AmaxAI.DebugCar.CorneringBoost`, `…Player.BrakeBoost`,
   `…BrakeTrackSpeedPercentageEasy/Medium/Hard`, `AISpeed` ; rattrapage du **joueur** en multijoueur :
   `MultiplayerConfig.player_rubber_banding_settings` (maxDistanceBetweenGroupMembers 2000, minDistanceForFullBanding
   600, light 0.25 / medium 0.666, courbe d'impulsion ±100).
- **Observation joueur (2026-10-19)** : après un nitro, les IA freinent fort pour revenir à un certain niveau de
  vitesse (on le voit et on l'entend). **Hypothèse** : plafond de vitesse imposé par le Race Director (ligne de
  facteurs `1, 0.84…0.87` des CSV ?) ou `BrakeTrackSpeedPercentage*`. À vérifier sur les enregistrements
  (`trackrec.py --all`) : hausse brutale de vitesse suivie d'une chute immédiate.

### Evil Shannon (2026-10-20)

- `ShannonEvil` et `Shannon` (`finalracebook.bin`) sont **le même pilote** : même modèle 3D, même `AITemplate`, mêmes
  voitures (Mégane R26, Opel Astra Extreme à physique propre), même nom affiché ; seuls l'identifiant et
  `AvatarID` (16 / 22) diffèrent. Sa force en finale (T9E6, contre le joueur) vient du fichier de difficulté :
  aucun réglage spécial (pas de bouclier permanent, santé normale, pas de bonus offerts).
- `ShannonEvil` n'est pas référencée dans `multiplayer.bin` (l'y ajouter demande d'insérer un hash dans un index
  trié : pas encore géré par `kslfwrite`).
- Mod (copie) : avatar 22 pour `Shannon` (liste des IA de course perso) et profil `T9 Shannon` « ultime » (Racing,
  Aggression, Blocking, Slamming 1,0, Mistakes 0 : aucun profil d'origine n'a ces valeurs). Avec le Hard « sans
  bridage » (facteurs 1,2, profil 900 pour toutes les IA), toutes les IA ont ce profil. À tester.

### Mods (Mod Shop) et IA (2026-10-20)

- Mods = `MultiplayerAbility` (`multiplayer.bin`, 33) ; slots 1 à 3 pour les joueurs (`MultiplayerAbilityLoadOut`
  Default1 / Custom1..3, **joueur seulement**) ; slot 4 = pouvoirs de boss (`Boss*`).
- **Aucun champ de loadout pour les IA** dans les données : ni dans `RaceBookCharacter` (seulement `PerkLevel`), ni dans
  `air.bin`, ni dans les CSV. Le seul mod d'IA trouvé : `AmaxVehicle.BossAbilitySlot` (`amax.bin`), lié à la
  **voiture de boss** : Shannon (Mégane R26) BossAdditionalBlindfireShots, Carver BossNitroRift, Khan BossDoubleShield,
  Talon BossRepairBonus, Ayumi / Harumi BossShotgunBlindfire, Rhymer BossFansNitroGift, Natalya
  BossAdditionalShockDomes, Drayke BossShuntDamage. Modèles d'effets dédiés aux IA (`shuntbuildai`,
  `silentrunningai`…). Si les IA de course perso reçoivent des mods (rang `ai_average_mp_rank_*`) : **à établir**.
- Solo : `OpponentSetup` (`singleplayer.bin`) : `HealthOverride`, `AlwaysShields`, `OnlyAttacksPlayer`,
  `PerkSlotsOverride`, `PerkGiftTimer` / `PerkGiftTypes` (bonus offerts) ; `DifficultySettings.AIPerkUse`
  (`PerkToGrant`, `GrantTimeMin/Max`), `AIBalancingFileName` (le CSV). Rien de tel en course perso.
- **Lecture du Race Director (Hypothèse forte)** : chaque palier place un **groupe de 4 rivales** (drapeau 1,
  plafond 1,0) à ±5 m du joueur, et les 15 autres IA (plafond 0,84–0,87) à des écarts fixes (`distances`, m, positif
  = derrière le joueur). Palier 1 : toutes derrière ; dernier palier : toutes devant (−210 m). Le groupe de rivales
  change de colonnes d'un palier à l'autre : le palier suit la place du joueur.

### Essai « meute de rivales » (2026-10-20)

- Hard modifié : les 19 IA avec le drapeau de rivale (ligne 4 = 1), des distances de −18 à +18 m, un facteur de 1,2 et le
  profil 900. Mesure avec `racegaps.py` (écart de chaque IA au joueur toutes les 20 s) sur trois courses gagnées par le
  joueur : Brighton 1, LA River 3 (Concrete Basin) et Sausalito 2 (Bay Area Tour).
- Résultat : **aucun rattrapage**. Les IA restent toutes derrière ; l'écart grandit sans cesse (la meilleure IA perd
  ≈ 10 m/s ; 2,8 km après 300 s à LA River) et ne se referme jamais. Le Race Director ne sait que **ralentir** les IA (un
  plafond) ; il ne les pousse pas au-delà de leur limite physique. Le peloton reste groupé derrière (**Fort**).
- **Essai adhérence** (`Air_Default` FrictionCoefficient 1,212 → 1,6, LA River 3) : **aucun effet** (même écart, IA
  217 → 216 km/h de moyenne). Joueur 270 km/h de moyenne contre 217 pour les IA (+25 %) : l'écart vient sans doute
  des **voitures** (rang moyen des IA Hard 44, `ai_average_mp_rank_hard`), pas du pilotage. À vérifier.
- **Profil de vitesse le long de la piste** (LA River 3, tronçons de 400 m) : dans les virages, IA ≈ joueur (96–98 %) ;
  **en ligne droite, les IA plafonnent vers 240–250 km/h** (joueur 300–370 en enchaînant les nitros). Après chaque
  nitro, une IA reperd ≈ 100 km/h en 2 à 4 s (médiane sur 207 nitros), souvent sous sa vitesse d'avant ; joueur 65.
  Ce n'est ni la voiture (Audi R8, classe A jugée moyenne), ni une physique propre aux IA (`UseAiDynamics` = false
  pour les 81 voitures), ni l'adhérence.
- **Essai facteur 2,0** : identique au facteur 1,2 (même profil, même écart). Au-delà d'environ 1,2, le facteur du
  Race Director ne bride plus : **le freinage après nitro vient du pilote IA lui-même (code)** (**Fort**). Réglages
  candidats seulement en variables de débogage (`AmaxAI.DebugCar.CorneringBoost`, `AmaxAI.Perks.General.NitroCoolDown`),
  non modifiables sans toucher à l'exe.
- **Zigzag des IA** : régulateur de direction `AISteering` (`air.bin`, 6 profils ; `AI_Steering_Controller_Default`
  pour 52 voitures sur 81) : PID P ≈ 32, D ≈ 3,7 (peu amorti), visée `ForwardsDist` ≈ 15 m, `AIOffset` désactivé.
  **Essai D 7 + visée 20 m + ligne 0,55 → 1,0** (LA River 3) : oscillation latérale mesurée (écart au tracé lissé
  sur 2 s, médiane des IA) 5,2 → 3,7 m ; **rythme inchangé** (même écart au joueur). La ligne 0,55 n'a pas d'effet
  visible sur la vitesse.
- **Code IA (lecture seule de l'exe, 2026-10-20)** : les 70 variables `AmaxAI.*` sont des objets (constructeur
  `0x4F6BA0`, valeur en +0x24) ; défauts : `NitroCoolDown` 6 s (obj `0x1134F40`, lu en `0x4BCB8B`), `CorneringBoost`
  2,25 (lu en `0x4BDFB6`), `Friction` 1,05 (`0x4C01EE`), `Torque` 0,1, `TorqueDamp` 5, `AirForce` 1000 ; contrôleur de
  direction `SteeringRate` 30 / `SteeringTimeStep` 0,03 (module `0xB05xxx`).
  Application des commandes : `0x4C28F0` (accélérateur, frein, direction bornés à [0,1] / [−1,1]). Aide au freinage du
  joueur : si vitesse (`voiture+0x134`) > **vitesse cible de piste** (`+0x36C` d'un objet de suivi) ×
  `BrakeTrackSpeedPercentage` → frein 1, accélérateur 0. La vitesse cible est écrite en `0xB0507A` : valeur de base
  (+0x40) × facteur borné à [0,2 ; 1] (`0xB04EE0`). Hypothèse : les IA freinent après un nitro parce qu'elles
  dépassent cette vitesse cible. À confirmer en lisant la mémoire pendant une course.
- **Vitesse cible des IA : confirmé en mémoire (2026-10-20, `aispeedrec.py`)**. Chaîne : gestionnaire IA `0x1134D88`,
  interface `[+0x2C]`, tableau `[I+0x4C]` ; objet de suivi = `[[tableau + 4·i] + 0x10] + 8` : `+0x134` vitesse (m/s),
  `+0x36C` vitesse cible (m/s, entière). Course LA River 3 (Hard modifié) : cible médiane 259 km/h (p90 306) ; en
  ligne droite 266–295 km/h, alors que le joueur roule à 330–360. **Nitros des IA (65)** : 232 → pic 354 km/h pour une
  cible de 266 → **retombée à 214 en 1,6 s** : la vérification de freinage s'applique aussi aux IA (**Confirmé**).
- **Origine de la cible** (`0xB04EC0`) : `octet[voiture][nœud][ligne] × échelle (+0x354)`, puis × facteur borné à
  [0,2 ; 1] (d'où l'absence d'effet des facteurs > 1 du CSV). Les tables d'octets (m/s) sont **calculées au chargement
  pour chaque voiture** (`0xB178B0`, 11 lignes, deux passes, message « SECOND : Potentially bad data ») en simulant
  sa physique (`0xB11E00`) : c'est la vitesse que la voiture peut tenir **sans nitro**. Dispersion entre voitures sur un
  même nœud ≈ 19 km/h. Pas de table dans les fichiers du niveau.
- Conséquence : un nitro d'IA est toujours « coupé » par le frein dès qu'il dépasse la vitesse sans nitro. Leviers
  possibles sans toucher à l'exe : la physique des voitures (touche aussi le joueur), ou l'échelle `+0x354`
  (origine à trouver).
- **Échelle `+0x354` de la vitesse cible = adhérence de surface vue par l'IA** (`0x4BF9F0`, écrite en `0x4C01F2` /
  `0x4C0297`). Trois sources : (1) initialisation = variable de débogage `AmaxAI.DebugCar.Friction` (1,05) ; (2) normal =
  surface sous la voiture (`0x7BC290`) : `GripScaleStatic + (GripScaleDynamic − GripScaleStatic) × min(v / GripScaleDynamicSpeed_Mph, 1)`
  (`racingphysics.bin`, `RP_SurfaceMappingList.properties` : Tarmac 1/1, Dirt et Grass 1 → 0,8 à 60…) ;
  (3) si l'épreuve a `OverrideAISurface` : `OverrideAISurfaceValue` bornée à **[0,8 ; 1,5]**, pour les IA seulement.
  Lu en course (LA River 3) : 0,80 à 1,00 selon les voitures.
- `OverrideAISurface` n'existe que dans `AmaxEvent` (**carrière**, `singleplayer.bin` : 15 épreuves sur 86 à True / 1,0 ;
  `splitscreen.bin` n'a aucune épreuve). La course perso (`MultiplayerRace`) n'a pas ce champ : **en course perso, pas
  de levier « IA seulement » sur la vitesse cible** sans toucher à l'exe ; en carrière, `OverrideAISurfaceValue` 1,5
  relèverait la cible des IA (à tester).
- Lu en course perso (2026-10-20) : la configuration lue par l'IA (`[0x111EDBC]+8`) a le drapeau +0x51 à 0 et la valeur
  +0x54 à 0 ; les IA prennent l'adhérence de la surface (0,94 à 1,0). Rien dans `MultiplayerRace` ne remplit ce
  drapeau : **pas de levier en course perso** sans écrire en mémoire ni modifier l'exe (interdits).
- **Essai carrière `OverrideAISurfaceValue` 1,5 (86 épreuves, T1E0 Barcelona Oval)** : appliqué (adhérence lue 1,5
  pour toutes les IA). Cible médiane 223 km/h (p90 236), IA 198 km/h, joueur 227. **Le freinage après nitro reste** : 78
  nitros, pic 251 pour une cible de 223 → retombée à 185. La cible en ligne droite reste la vitesse de pointe sans nitro
  (limitée par la physique, pas par l'adhérence). Gain dans les virages : non mesuré (il manque une course de
  référence sans le mod).
- Pistes restantes : la physique des IA (`AI.Air_Default` : FrictionCoefficient 1,212, BrakingCoefficient 1,0), la
  ligne 0,55 (rôle inconnu), les variables `AmaxAI.DebugCar.CorneringBoost` / `AISpeed`.

### Course perso (LAN) : Easy / Medium / Hard (2026-10-20)

- `events/multiplayer_easy|medium|hard.csv` sont **identiques sauf la ligne des facteurs** (plafond de vitesse) :
  Easy 0,8 pour les 3 premières IA, 0,60–0,62 pour les autres ; Medium 0,99 puis 0,79–0,81 ; Hard 1,0 puis 0,84–0,87.
  Mêmes distances (−210 à +200), même ligne 0,55, mêmes profils (« Difficulty 1..10 », tous identiques entre eux),
  mêmes préférences (Balanced, Defensive Rules 1, Aggressive, Short Distance, Catch Up, Nitro…).
- **La difficulté de la course perso = uniquement le plafond de vitesse des IA.**
- `multiplayer_default.csv` : 1 palier, profils par défaut, facteurs 0,75–0,90, distances 0.
- `MultiplayerConfig` : rang multijoueur moyen des IA easy 4, medium 24, hard 44 (écart 5) : sans doute leurs
  voitures et mods.

### Boss : profils et duels (2026-10-19)

- `AIPerkSkillz`, somme sur les 8 bonus (max 8) attaque / défense / esquive : **T9 Shannon (900) 8 / 8 / 8, le seul
  profil à 1,0 partout** ; Tier 10 Skills (70) 8 / 8 / 2 ; Natalya (500) 5,95 / 4,11 / 1,9 ; Drayke (400) 5,5 / 4,83 /
  1,9 ; Carver (800) 5 / 4 / 1,6 ; Khan (200) 4,95 / 3,75 / 1,7 ; Talon (600) 4,9 / 4 / 1,9 ; Rhymer (300) 4,8 / 4 /
  1,6 ; Shannon T1 (1000) 4,5 / 4 / 1,65 ; Ayumi/Harumi (700) 4,45 / 4,25 / 1,6. Versions EASY plus faibles.
- Racing 0,5 et Aggression 0,5 pour **tous** ; Blocking, Slamming, Mistakes à 0 pour tous (personne à 1,0).
- Duels `events/bossbattlet<N>_<diff>.csv` (1 IA ; 2 pour T7 les jumelles et T9) : Easy = profil EASY du boss,
  facteur 0,65–0,8 ; Medium = profil du boss, 0,75–0,97 ; **Hard = profil générique Tier 10 Skills (70) pour tous
  les boss**, facteur 0,89 (T1), 0,91 (T2), **1,0 (T3 à T8)**, 0,96 (T9 Shannon).

### Non trouvé (à faire)

- **Classement** : ni dans l'objet véhicule ni dans l'objet pilote. La structure `0x12260A8`
  (`GetVehiclePosition`, 20 cases de 0xD4 à partir de +0x10C8) est **vide pendant la course** (remplie
  à l'arrivée ?).
- **Palier IA actif**, **bonus détenus**, **tour en cours / progression**, **état accélérateur/frein**.
- Prochaine étape prévue : `deeprec.py` (enregistre aussi les objets pointés, profondeur 1) avec une
  séquence jouée et notée par l'utilisateur.

---

## 6. Adresses de `Blur.exe`

| Adresse | Rôle |
|---|---|
| 0x5871B0 / 0x5871F0 | décodage / encodage des noms KSLF |
| 0x585660 / 0x584700 / 0x5850D0 | chargement / validation / schéma KSLF |
| 0xC31F30, 0xB824A0, 0x49B310 | index du véhicule du joueur (Lua `GetPlayerVehicleIndex`) |
| 0xBBD420, 0xBBD460 | position en course ↔ véhicule (objet 0x12260A8) |
| 0x4C5E20 | lecture du CSV de difficulté (RaceDirectorSystem) |
| 0xBC1E70 | préparation de l'épreuve |
| 0xBBDD80 | construction des chemins `.level` / `.aid` |
| 0xB11870 | constructeur de la classe à vtable 0xEC3A68 |
| 0xC6C4F0 / 0xC6C760 | Lua `GetCustomRaceCities` / `GetCustomRaceRoutes` (menu course perso) |

Globales : `0x11AA04C` (jeu), `0x1134DC0` (→ profils IA), `0x1134DCC` (pilotes),
`0x1134E84` / `0x1134E9C` (listes de profils), `0x12260A8` (positions).

---

## 7. Communauté (Discord Blur / wiki AMAX)

- Pas de décodeur public des `.bin` / `.xt` connu (la page « outils » du wiki était vide en 2026-09).
- « Md » a fait un éditeur de cartes (tracé 2D, objets 3D du jeu, compilation et installation, test en jeu
  avec IA), un réglage de bloom, et travaille sur le déblocage des FPS (la physique est calée sur 30 images/s).
- Un moddeur réactive le DoubleTap.
- Demande récurrente : circuits en sens inverse (« galère » selon la commu).
- 2026-10 : un joueur a fait tourner des cartes Mario Kart (.obj converti en `.level*`) avec Claude Code,
  Ghidra et des relevés **Process Monitor** filtrés sur Blur. Il joue avec les **fichiers dépaquetés**, ce qui
  appuie la règle « le fichier en clair passe avant le pak ». Son pack modifie `Blur.exe` : on ne l'utilise pas.
  TimberStalker : « ajouter des cartes, c'est dans les fichiers xt ; les fichiers de niveau sont plus durs ».
- Vidéo d'un moddeur (2026-10-14) : lieu « Flat Earth », circuit « Home Run v1 », lancé avec `Blur_mod.exe`
  (exe modifié) via Local Network → Custom Game.

## Audio et musique (2026-10-20)

- **Banques `.baf`** (`root.pak` `audio/*.baf` ; musiques dans `root_streaming.pak` : `ingamemusic.baf` 329 Mo,
  `ingamecustommusic.baf`, `menumusic.baf`, `vistamusic.baf`) : format « BANK » v4 décrit par vgmstream (`meta/baf.c`,
  Blur PS3 = même disposition). Entrées `WAVE` de 0x4C : codec +0x08, nom +0x0C, position absolue +0x2C, taille +0x30,
  fréquence +0x40, échantillons par canal +0x44, boucle +0x48, canaux +0x4B. Données alignées sur 0x800 dans les banques
  en streaming. **Codec 7 = ADPCM PlayStation, trames de 0x21 octets** (1 octet filtre/décalage + 64 quartets),
  entrelacées par canal ; codec 3 = PCM16. Outil : `blurbaf.py` (liste, décodage WAV ; **Confirmé** : décodage propre).
- `InGameMusic` : **24 morceaux** de course en 48 kHz stéréo (AtomicMoog, BLUR_track1..5, Bump, Coleen, Delucid,
  DemNaLikeMe, EverythingIsUnderControl, GadgetFunk, HarvestDance, LetThereBeLight, MakeItSo, Nothing2Step2, OnTheRun,
  PatPong, RedLaserBeam, Stompbox, SWAG, TeQuiero, ThatGirl, BLUR_menu). `InGameCustomMusic` = **musique adaptative déjà
  existante** : Checkpoint (`MX_Chk_Low/Med/High/Last`), Destruction (`MX_Destruct_Low/Med/High`), duels de boss
  (`MX_OOO_Boss_Lead/Neutral/Player_Leads`, intro par boss), chacun avec une piste `sync_loop` (PCM 16 Hz, repères).
- **Contrôleurs `audio/dat/*.dat`, format « JBOA »** (365 graphes : moteurs, roues, interface, ambiances, musique) :
  graphe d'objets (variables, portes, scripts, boucles, mixeurs, sorties ; constantes `ffff0000 <f32>`). Musique :
  `music_controller` (menu, chargement, jingles de circuit `VistaID`, morceaux de course `InGameMusic00..22`, fin de
  course), `music_boss`, `music_checkpoint`, `music_destruction`, `music_upmixer` (volumes, `DuckMusic`). Format
  interne : **à décoder**.
- **Entrées envoyées par le jeu aux graphes** (noms `*Input` / `*ActionIn`) : musique = `RaceStart`, `RaceFinishPass/
  Fail`, `LevelStart/Finish`, `MusicType`, `VistaID`, `BossID/Distance/RelativeSpeed`, `RacePosition`,
  `CheckpointTimeRemaining`, `DestructionTimeRemaining`. Ailleurs : `finalsubmix` = `PerkNitrousActivated`, `Wrecked`,
  tirs / impacts de chaque bonus, `CurrentHealthLevel` ; `ingameuistereo` = `MPPositionIn`, `PassedCheckpoint`,
  `HealthLow`, `Wrecked` ; `ingameui` = fans, `RaceFinished` ; `aisubmix` = bonus des IA. Piste pour une musique qui
  réagit aux actions : faire jouer des couches musicales depuis ces graphes (à condition de savoir ajouter des objets JBOA).
- **JBOA, structure (partielle)** : en-tête `JBOA`, u32 version 0x2000B, u32 taille jusqu'aux noms, u32 0, u32 nombre
  d'objets, puis objets à la suite `[u32 type][u32 nom = position dans la table de noms finale][paramètres]`.
  Références d'objet = index << 16 ; constantes = `0xFFFF` + valeur. Types vus : 1 / 32 / 40 entrées du jeu, 20
  variable, 52 variable lissée, 54 porte (seuil), 60 son en mémoire `[banque][son]`, 64 son en streaming
  `[banque][son]`, 73 mixeur, 189 script (bytecode, opcodes 0x1000–0x1317 : affecter, comparer, sauter, jouer).
- Morceaux de course : un objet par morceau (`InGameMusic00..22` → banque `InGameMusic` + nom du son) et un sélecteur
  `InGameMusicSelectorIndex` à **23 entrées** (valeur, poids 1). Ajouter un morceau = ajouter le son dans
  `ingamemusic.baf` (reconstruire la banque, données alignées sur 0x800) + un objet `InGameMusic23` + une entrée au
  sélecteur (+ mixeur si nécessaire), sans casser les index d'objets.
- **Ajout d'un morceau de course : Confirmé en jeu (2026-10-20)** avec `make_music.py` (« Shut Up And Drive » =
  `InGameMusic23`) : MP3 → ffmpeg 48 kHz stéréo → ADPCM (`blurbaf.encode_psx`, aller-retour 33 dB) → ajouté à
  `ingamemusic.baf` (entrée dans le remplissage avant 0x800, données en fin de banque, alignées sur 0x800, précédées de
  `DATA` + taille + 8) ; objet son ajouté **en fin de liste** du graphe (index 115 : aucune référence ne bouge) ;
  sélecteur 24 entrées (type 33 : `[33, nom, FFFF, 0, n]` + n × 8 mots `[FFFF, k.0, FFFF, 1.0, FFFF, 0, FFFF, 1.0]`) ;
  mixeur (type 73, n << 16 en +6, 17 mots par entrée dont `(19 << 16) | objet`) ; script de lecture (`[189, nom, long]`,
  n cas `[4887, sélecteur, k.0, 4353, cible]`, `4610`, n corps `[4096, objet, 0, 4610]`, cible = index de mot dans le
  script) ; script d'arrêt (`long | long << 16`, n × `[4096, objet, 1]`). Le morceau suivant est retiré au hasard à la
  fin du précédent (test forcé = boucle sur le même morceau, normal).
- Copie de test : `root_streaming.pak` → `.off`, ses 67 fichiers en clair dans `audio\` (le pak l'emporte sinon).
- **Volume des morceaux** (EBU R128, 60 s au milieu de chaque morceau) : originaux de −11,7 à −8,6 LUFS, médiane −10,2 ;
  `make_music.py` règle chaque ajout sur −9 LUFS (un peu au-dessus des originaux, pour passer sous les moteurs ; gain + limiteur à −1 dBFS). Morceaux entiers : originaux −12,2 à −8,7 LUFS.
- **La musique passe par `finalsubmix`** (entrée `MusicSurroundInput`, volume `MusicMixerVolume`), qui reçoit aussi les
  événements nitro, épave, tirs et impacts. Effets déjà présents : baisse de la musique sur les bonus
  (`MusicMixerPerkDuckAmount`), passe-bas pendant le nitro (`NitrousLowPass`), « bit crusher » selon les dégâts
  (`RGBBitCrusher`, `RGBMedium` / `RGBHard`). `system` : compresseur maître, fondus musique (`StartMusicFadeIn/Out`).
  C'est l'endroit où brancher une musique qui réagit aux actions.
- **Musique étouffée en épave : Confirmé en jeu (2026-10-20)** (`make_music.wreck_muffle`, `finalsubmix.dat`) : objets
  de contrôle ajoutés en fin de liste (variable `WreckMusicVariable`, courbe `WreckMusicCutOff` 0 → 0,02 / 1 → 1),
  ajoutés au minimum `PerkFilterCutOff` (type 42) qui pilote le passe-bas `PerkSurroundLowPass` du mixage final
  (musique, IA, décor ; pas la voiture du joueur) ; `WreckedInput` lance une copie de `RaceFinishedScript` qui met la
  variable à 0, `ResetLevelScript` la remet à 1. Formats : variable `[0x14, nom, f32]` ; courbe type 21 `[entrée,
  FFFF 1.0, n, x0, (FFFF y0), x1, (FFFF y1)…]` (un y peut être `(objet, 0)`) ; type 42 `(0x34 << 16) | n` + paires
  `(objet, 0)` ; scripts : `0x1004 val` empiler, `0x1002 objet<<16` affecter, `0x1000 objet<<16 arg` déclencher,
  `0x1202` fin. Des objets de contrôle placés après leurs lecteurs fonctionnent. Outil `jboadump.py`.
- Morceaux de course : 23 d'origine + 13 ajoutés (Rihanna + 12 de la sélection « BLUR reimagined » ; 8 retirés après écoute le 2026-10-21) = 36, sélecteur 18 + 18 + pile ou face. Rotation variée confirmée en jeu.
- **Sélecteur à plus de 32 entrées : défaillant (Fort)**. Avec 44 entrées, l'entrée n° 32 (« Rabbit In Your
  Headlights ») passait 3 courses sur 4 et les entrées suivantes jamais ; aucun sélecteur d'origine ne dépasse 23
  entrées. Contournement (`make_music.split_selector`) : deux sélecteurs de 22 (`InGameMusicSelectorIndex`,
  `…IndexB`) + un pile ou face (`InGameMusicGroupSelector`) tirés par `InGameLicensedMusicNextTrackScript`
  (`0x1000 objet 0` = tirer, `0x1200 script` = appeler) ; le script de lecture teste le groupe puis le bon sélecteur.
  Simulation : 44 tirages → 44 morceaux distincts. À confirmer en jeu.
- **Départ de course** : `RaceStartScript` tire lui-même le sélecteur (`0x1000 sélecteur 0`) puis appelle le script de
  lecture (`0x1200`), sans passer par `NextTrackScript` ; le morceau suivant n'est tiré qu'à la fin d'un morceau. Après
  la coupure en deux sélecteurs, seul le groupe A sortait au départ (2026-10-21 : 15 min d'originaux) ; corrigé :
  B et le pile ou face sont aussi tirés au départ (cibles de saut `0x1101` décalées de 6). Longueurs des
  instructions : `0x1000` 3, `0x1002` 2, `0x1004` 2, `0x1101` 2 (saut si vrai), `0x1200` 2, `0x1202` 1, `0x1317` 3
  (comparer) (`make_music.script_ops`).

## Blur Map Builder (MDPRO, v1.0.0, 2026-10-20) : ce que son code nous apprend

Source MIT lue le 2026-10-21 (zip de la page GitHub `MdPro64/blur-map-builder`, rien d'exécuté). Éditeur de circuits
complet (route, collisions, tracé IA, objets, lumière, surfaces, partage `.blurmap`).
- **Installation** : « Blur REBORN.exe » = copie de `Blur.exe` + 4 changements : **vérification de signature des paks
  coupée** (`0x8B667A` : `75` → `EB`) et `gamedata.pak` / `root.pak` lus dans `rebrn\` (chaînes `0xA668F8`,
  `0xA66628`, `0xA66978`). Il reconstruit des paks complets. Notre méthode (paks d'origine mis de côté en `.off`,
  fichiers en clair) évite toute modification de l'exe.
- **`.aid`** (complète nos notes) : point = 11 f32 `{x, hauteur, −z, largeur, a, b, c, inclinaison, d, h1, h2}` ;
  (a, −b) = direction latérale ; (c, d) = la même multipliée par le dévers, `inclinaison` = sa part verticale (= notre
  « vecteur +24 ») ; `hauteur`, h1, h2 = un « tube » où circulent IA et projectiles (mesuré sur LA River 6 : ligne IA
  route +7,8 / −2,9 / +7,8 ; Logic et portes à la hauteur de la route, sinon l'arrivée ne se déclenche pas).
  Table des liens en fin de fichier : point Logic p → points p−1..p+1 de la ligne IA et points de porte proches.
  **Longueurs de voie (échantillon +4) à 0 = gel au chargement** : la recherche de distance de freinage de l'IA
  (`0xB1A8B0`) fait le tour de la boucle à l'infini.
- **KSLF** : `kslf_write.insert_uid` ajoute une entrée **à sa place dans l'index trié** et renumérote toutes les
  références (u32 index de la section 4) et la première valeur de chaque ligne de la section 5. C'est ce qui manquait à
  notre `kslfwrite` (ajout de `ShannonEvil` dans `multiplayer.bin`).
- Divers : objets plaçables par location, limites 144 (décor, physique, animés) et 356 (cassables) ; IDs d'acteurs
  libres pris dans `0x7A000000..0x7AFFFFFF` ; plugin AMAX `quickstart` (lance une course LAN sur la carte) ; outils de
  recherche (`research/tools` : désassemblage, recherche des tours, des seuils).
- **Playlists (2026-10-21)** : `C:\Users\sanqu\Jeux_WII\Blur_musiques\<playlist>\` (hors dépôt), un dossier par
  playlist ; un dossier sans fichier audio dont le nom contient « original » = les 23 morceaux du jeu. Menu
  `Choisir la musique.bat` → `music_menu.py` → `make_music.build()` + `install()` dans la copie de test. Encodage une
  seule fois par fichier (cache `blur_extracted/music_cache`, clé = contenu + niveau visé) : première préparation
  ~1 min par morceau, ensuite ~5 s. `playlist()` construit le tirage pour n'importe quelle liste d'objets son : groupes de
  32 au plus (sélecteur du jeu + sélecteurs ajoutés + sélecteur de groupe), script de lecture réécrit, tirages ajoutés à
  `NextTrackScript` et `RaceStartScript` ; `play_targets()` simule le tirage et bloque si un morceau est inatteignable.
- **Qualité (2026-10-21)** : morceaux ajoutés en PCM 16 bits non compressé (codec 3, entrée 0x50 copiée des
  `*_sync_loop` : +0x3C fréquence, +0x40 16, +0x44 canaux, +0x48 0, +0x4C 0xFF ; `blurbaf.add_pcm_wave`) : **silence en
  jeu** pour les objets son de course (type 60) ; les seuls PCM du jeu passent par des objets type 64. Encodeur ADPCM
  avec recherche en faisceau (8) : 33,1 → 33,9 dB pour 15x plus de temps, abandonné. Plafond = ADPCM 4 bits du jeu
  (comme les originaux) ; sources actuelles MP3 192 kb/s.
- **Lecture « aléatoire en boucle » (2026-10-21)** : `make_music.shuffle_loop` : un ordre tiré à chaque préparation,
  variable `InGameMusicShuffleIndex` (type 20) ; script de lecture = cas sur la variable, chaque bloc joue son morceau
  puis range l'index suivant (`0x1004 val`, `0x1002 var`) ; `NextTrackScript` = appel du script de lecture ;
  `RaceStartScript` ne tire plus le sélecteur. `Tester le mod.bat` remélange à chaque lancement
  (`music_menu.py --remelanger`, choix mémorisé dans `Blur_musiques\derniere_selection.json`). Option « effets non » :
  plus d'étouffement en épave et `MusicMixerVolume` sans le terme `MusicMixerPerkDuckVolume` (plus de baisse sur les
  bonus) ; le passe-bas du nitro agit sur tout le mixage final.
- **Russian Hill Route 1 Reverse (2026-10-21)** : `USA_SanFran_RussianHill_R` (nom ≤ 25 car. : plus long emplacement
  d'image libre `USA_LA_Downtown_FigureOf8`, n° 121 ; plus aucun emplacement libre ensuite pour ce format), texte
  `CRN_ROUTE_1_REVERSE` (partagé avec Brighton). La route a un raccourci (bloc `Carpark` + `JunctionCarpark`) : retirés du
  tracé IA avant l'inversion (`make_reverse.load_aid(drop=…)`) ; les IA ne prennent plus le parking, le joueur oui.
  Longueurs de voie nulles : 33, comme l'original (nœuds 0, 689, 690 = jonction de la boucle). À tester en jeu.
- **New York à l'envers (2026-10-22)** : `USA_NY_Dumbo2R` (« Route 2 Reverse », `CRN_ROUTE_2_REVERSE`) et
  `USA_NY_Dumbo_3R` (« East River Run », `CRN_NY_DUMBO_4`, nom de route prévu et jamais utilisé ; `CRN_NY_DUMBO_1`
  « Fulton Loop » est aussi libre). Tous les chemins alternatifs retirés du tracé IA (4 sur Dumbo 2, 6 sur Dumbo 3).
  Images dans les deux derniers emplacements libres (`USA_Amboy_Bowl`, 14 car. ; `USA_LA_LongBeachDocks_2`, 23 car.) :
  **plus aucun emplacement d'image 512 × 256 libre** dans `ui_frontend.bpr` (route suivante : sans image, ou trouver une
  autre méthode). À tester en jeu.
- **Trajectoire IA du Map Builder** : il ne touche pas aux 11 lignes ; il rétrécit le couloir de la ligne IA (position
  et largeur des nœuds de `Main`) à ~12 m autour d'une trajectoire qui coupe l'intérieur des virages (rayon ≤ 70 m =
  corde complète, lissage ±40 m). Piste pour améliorer nos routes inversées (à mesurer).
