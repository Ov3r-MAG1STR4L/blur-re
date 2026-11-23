# Atelier de maps : audit (phases 1 et 2), 2026-11-23

Lecture seule : aucune map reconstruite, aucun fichier du jeu modifié. Les niveaux de confiance suivent ceux de
`CONNAISSANCES.md`.

## 1. Ce qui existe

| Élément | Où | État |
|---|---|---|
| Atlas 3D de Dubaï (artifact) | `b2viewer.py` → `viewer/dubai/{dubai.json, dubai.b64.txt, index.html}` | **Lecture seule.** Couches de collision Unity (route, raide, vers le bas, murs `15d`, barrières `route_N`), tours roulés, 4 grilles officielles (x, z seulement), profil de hauteur. Pas de sélection, pas d'édition, pas d'export. |
| Éditeur de tracé (NFS Studio) | `nfs_studio.py` + `nfs_web.py` | Édition du tracé, des embranchements, des bonus et des rangées, puis construction (`make_b2_map`) et installation. C'est **le seul éditeur qui écrit**. |
| Tracés | `blur2_aid/dubai/dubai_routeN_trace.json`, `b2trace.py` (recollage au sol) | 4 routes, embranchements seulement sur Marina. |
| Collision | `b2collision.py` (Unity → `.levelphysics`, `BACKSTOP` 1 m, `ORIENT` = 0) | Construite pour les 4 routes. |
| Zones de gravité | `b2gravity_zones.py`, `natif/b2gravity/<route>/b2gravity.txt` | 29 / 11 / 28 / 27 zones (vérifié). DLL v14, avec HandOfGod coupé et son filet de sécurité. |
| Installation | `b2install.py`, `Installer route Dubai.bat` | Une route à la fois dans `flat_earth`. |
| Lecture de la mémoire du jeu | `blur_live.py`, `trackrec.py` (pymem, lecture seule) | Chaîne statique vers les véhicules, **position, vitesse et matrice de rotation** de chaque voiture, joueur repéré. Confirmé en jeu (2026-10-18). |
| Grille (circuits d'origine) | `gridreverse.py`, `blurroute.py` | Positions `StartPosition` des `MultiplayerActorLists` (WorldMatrix) lues et réécrites pour les routes inversées (projet C, confirmé). |
| Trajectoires IA | `.aid` : lecture et écriture complètes (`aidreverse.py`, `lap2aid.py`, `gen_aid` de Map Builder) | Format connu à 100 % (33/33), règles des embranchements connues d'après le code source. |
| Map Builder de Md | Nous utilisons la **1.0.0 en Python** + `nfs_studio.patch` (`bmb_game`) | Les fonctions 2.x (murs invisibles, `branches`, animations, C#) ne sont **pas** dans notre chaîne. |

Petit défaut trouvé : `b2viewer.py` lit encore `natif/b2gravity/b2gravity.txt`, qui n'existe plus depuis que les
fichiers sont rangés par route. Une nouvelle génération de l'Atlas n'aurait donc plus de zones de gravité.

## 2. Découverte : le sens des faces écrites ne vient pas de Unity (Fort)

`addramp.mesh_object` (utilisé par `b2collision` pour **tous** les triangles) **réenroule chaque triangle pour
que sa normale pointe vers le haut**, comme le sol du gabarit (`if n[1] * sign < 0: swap`). Conséquences :

1. Pour une paroi verticale, la face gardée dépend du **signe d'une très petite inclinaison** (|n.y| < 0,02 pour
   51 à 80 % des triangles raides), pas du sens Unity. Simulation sur les triangles raides à moins de 20 m du tour :

   | Route | Couche | Face au tour (sens Unity) | Face au tour (sens écrit) |
   |---|---|---|---|
   | Business Bay | murs `15d` | 73 % | **51 %** (pile ou face) |
   | Business Bay | route raide `17f` | 80 % | 70 % |
   | Business Bay | barrières `route_1` | 100 % | 100 % |
   | Marina | murs `15d` | 62 % | 56 % |
   | Marina | route raide `17f` | 54 % | 65 % |
   | Marina | barrières `route_4` | 89 % | 89 % |

2. Le retournement `ORIENT` était **défait à l'écriture** : un triangle tourné vers le tour était réenroulé vers le
   haut, et la copie « deux faces » devenait un **doublon de même sens**. Cela peut expliquer le résultat
   « chaotique » : le correctif ne faisait pas ce qu'on croyait. `ORIENT = 0` reste la bonne décision tant que ceci
   n'est pas corrigé.
3. La couche `BACKSTOP` est elle aussi réenroulée vers le haut.
4. Les surfaces **tournées vers le bas** (haut du looping, dessous de pont) sont toutes écrites face vers le haut,
   donc dos à une voiture qui roule dessous.

**Hypothèse Marina / Business (à vérifier en jeu)** : les barrières `physics_route_N` sont exactement verticales
(n.y = 0, donc pas de réenroulement) et gardent le sens Unity, qui est bon à 89-100 %. Les murs `15d` deviennent
eux un pile ou face. Si les « grands murs » de Marina sont des barrières `route_4` et les murs traversables de
Business des `15d`, la différence vient du **type de collider et de la façon dont on l'écrit**, pas du moteur.
Le matériau n'y est pour rien : tous nos triangles reçoivent le même drapeau de surface, celui du gabarit.

## 3. Faisabilité par domaine

| Domaine | Données | Faisable | Limite |
|---|---|---|---|
| A. Grille | `StartPosition` (WorldMatrix) dans les listes d'acteurs. Sur nos maps Dubaï, la grille est posée par Map Builder depuis le tracé, avec un décalage déjà constaté (~270 m après `start_m` sur Marina). | Afficher la grille réelle (relue dans la map construite) et la déplacer avant construction : **oui**. Ajouter des places : jusqu'à 20 seulement. | Joueurs et IA ne sont pas distingués dans les données connues : l'ordre des places décide. **À rechercher.** |
| B. Surfaces praticables | Couches Unity (`17f`, `8017f`, `15d`…), `.levelphysics` (types de formes, drapeaux par triangle) | Afficher, classer et ajouter des rampes ou des plans (`addramp`) : **oui**. | Les drapeaux de surface de Blur 1 ne sont pas décodés (adhérence, son, et pas d'« attribut de collage » connu côté Blur 1). Le sens de `8017f` par rapport à `17f` (0x80000 en plus ?) reste à étudier (est-ce l'attribut de wall-driving dont parle uKER ?). |
| C. Trajectoires IA | `.aid` complet, tracés JSON, embranchements Marina | Afficher le sens, les nœuds et la largeur, éditer et contrôler (point hors route, traversée de mur par lancer de rayon sur la collision) : **oui, hors jeu**. | Embranchements dynamiques (bit 128 + règles) écrits par personne : Map Builder n'écrit que 2, 4, 8, 16 et 64. |
| D. Routes et murs | Collision = triangles qu'on écrit nous-mêmes | Murs invisibles (triangles à deux faces volontaires), voir les normales et les faces : **oui**. | Il faut d'abord corriger l'écrivain (point 2), sinon chaque correction est réenroulée. |
| Capture de position | `blur_live` : position, vitesse, matrice (cap) | **Oui, fiable** (lecture mémoire, déjà confirmée). | Le jeu se met en pause s'il perd le focus : un `.bat` cliqué met le jeu en pause, mais la position reste lisible. Mieux : une petite aide en fond avec une **touche globale** (lue sans voler le focus). Le nom de la map n'est pas encore localisé en mémoire : on le prend de `b2install.py --etat` et du tracé le plus proche. |
| Comparer Blur 2 / Unity / Blur 1 | Blur 2 X360 (collision relue, 98 % à 2 m de Unity), Unity (MeshColliders), Blur 1 (notre `.levelphysics`) | Trois couches superposées dans l'Atlas, avec l'écart par triangle : **oui**. | Le relecteur `.levelphysics` actuel (`bmb_levelphysics.read_mesh`) ne lit que le 1er objet : il faut le lire en entier. |

## 4. Proposition d'ordre

**Étape 1 faite (2026-11-23, à valider en jeu)** : `poscapture.py` + `Jeux_WII\Capturer position.bat`.
- F9 capture (touches lues par `GetAsyncKeyState`, le jeu garde le focus) ; F5 / F6 / F7 = bloquant / traversable /
  anormal sur la dernière capture. Commentaires : `poscapture.py annoter <chemin> <résultat> <texte>`.
- Données : x, y, z, cap (degrés, depuis l'axe avant +0xE4), les 3 axes de la voiture, vitesse (vecteur et km/h),
  date, identifiant unique, circuit et statut d'identification, exe du jeu, nombre de voitures.
- Rangement : `blur_tools/captures/<Circuit>/session_AAAA-MM-JJ_HH-MM-SS/capture_NNN.json`, une session par
  circuit et par lancement, création exclusive (jamais d'écrasement), numérotation reprise après redémarrage.
  Circuit = route installée dans la copie qui tourne + voiture à ≤ 60 m de son tracé, sinon `Non_identifie` (avec
  la route supposée et la distance) ; `poscapture.py classer` la range plus tard (session `_reclassement`).
- Export `captures/captures_toutes.csv` (`;`, UTF-8 pour Excel) : à l'arrêt (Ctrl+C) ou avec `export`.
- Refuse un jeu lancé depuis `Program Files (x86)\Activision` (installation d'origine). Lecture mémoire = chaîne
  de `blur_live.chain`. Auto-test hors jeu : `poscapture.py test`.

1. **Capture de position** (`Capturer position.bat` + `poscapture.py`) : touche F9 en jeu, CSV `captures.csv`
   (n°, date, map, x, y, z, cap, vitesse, résultat, commentaire), lecture seule de la mémoire. Petit, utile tout de
   suite, sans risque.
2. **Diagnostic des faces dans l'Atlas** : relire la collision **réellement écrite** (tous les objets), afficher la
   normale de chaque triangle, colorer « face au tour / dos au tour », afficher les captures et le collider Unity le
   plus proche de chacune (nom, suffixe, sens).
3. **Test en jeu Marina / Business** : quelques captures devant les murs, pour confirmer ou rejeter l'hypothèse du
   point 2.
4. Ensuite seulement, **corriger l'écrivain** (option : garder le sens fourni au lieu de « vers le haut ») sur une
   seule route, dans la copie de test, avec retour en arrière.
5. Puis l'édition (grille, murs invisibles, trajectoires) dans l'éditeur qui écrit déjà (NFS Studio), l'Atlas
   restant la vue de diagnostic. Cela évite d'avoir deux éditeurs.

À rechercher avant l'édition : joueur / IA dans la grille, drapeaux de surface Blur 1, sens de `8017f`, nom de la
map en mémoire.
