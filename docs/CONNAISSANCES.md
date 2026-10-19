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
  Code encore présent ou non : **inconnu**.
- « Reversed » = tir dans l'autre sens (vu en jeu : « Forward fire Mine »). **Fort.**
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
