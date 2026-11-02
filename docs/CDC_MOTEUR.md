# Cahier des charges : moteur commun des studios de cartes (v1, 2026-11-02)

Ce document remplace la façon actuelle de travailler, avec un outil par projet et des scripts globaux, par **un
seul moteur**. Il sert à NFS Studio (lieux venus d'autres jeux), à Reverse Studio (routes de Blur inversées) et
aux futurs importeurs. Les règles communes du [cahier des charges](CAHIER_DES_CHARGES.md) s'appliquent (jeu
installé jamais modifié, copie de test hors ligne, mémoire du jeu en lecture seule).

## 1. Problèmes constatés (point de départ)

| # | Problème | Vu où | Cause connue ? |
|---|---|---|---|
| P1 | Lieux modifiés affichés abîmés dans NFS Studio : bâtiments en grillage ou transparents, triangles en « éclats » (tours de droite), morceaux qui flottent, vide bleu à la place du sol ou de l'eau | studio (captures du 2026-11-02, Dubaï) | **diagnostic 2026-11-02** (voir CONNAISSANCES « Diagnostic P1 ») : grillage = alphaTest sur les vitres (affichage + export) ; 8 pâtés absents (LOD seuls) ; à confirmer en jeu |
| P2 | Plantages fréquents de NFS Studio | studio | non. Pistes : tout le lieu chargé d'un coup (géométrie + PNG), mémoire GPU jamais libérée au changement de lieu |
| P3 | Collision partielle : seule la route HP (40 m) et le sol plat de Map Builder | jeu | oui (choix du 2026-10-28) |
| P4 | Bonus et départ placés « à l'aveugle » : rien ne compare la position dans le studio à la position réelle en jeu | studio ↔ jeu | oui (pas de retour du jeu) |
| P5 | Chemins IA tracés à la main en lignes : chevauchements, chemins mal placés, respawn hors de la route, blocages | jeu | oui (une ligne ne dit pas où la route s'arrête) |
| P6 | Scripts globaux qui écrasent des cartes déjà validées | reverse | **réglé** pour les routes inversées : `maplock.py` (2026-11-02) |

## 2. Principes

1. **Une carte = une fiche** (`maps/<id>.json`) : source unique de vérité, éditée par le studio. Les fichiers
   du jeu en sont **générés**, jamais modifiés à la main.
2. **Verrou par carte** : une carte validée en jeu est figée (empreinte des fichiers produits). Aucun
   traitement global ne la change sans déverrouillage explicite (même principe que `maplock.py`).
3. **Le studio montre ce que le jeu fera** : chaque contrôle tourne avant la construction (places de grille sur
   le sol, bonus sur la route, zones IA sans chevauchement…). Une carte en défaut ne se construit pas.
4. **Le jeu confirme le studio** : retour en jeu en lecture seule (voir 3.4).
5. **Formats d'entrée en greffons** : chaque jeu source (Hot Pursuit Wii aujourd'hui, d'autres demain) fournit
   un importeur qui produit le même format intermédiaire (maillages, matériaux, shaders, textures, points de
   repère). Le reste du moteur ne connaît pas le jeu source.

## 3. Exigences

### 3.1 Rendu fiable et léger (P1, P2)
- Lieu découpé en **tuiles** (ex. 256 m) chargées autour de la caméra, avec niveaux de détail ; mémoire GPU
  libérée à la sortie d'une tuile et au changement de lieu (`dispose`).
- Budget affiché : triangles, textures, mémoire. Alerte avant dépassement.
- **Mode diagnostic** : couleur par matériau, par fiche, transparence coupée, normales, UV. Il sert à dire si
  une erreur vient de l'import (fichier source mal lu) ou seulement de l'affichage.
- Validation : même vue (position, angle) en capture studio et en capture jeu ; écarts listés.

### 3.2 Collision de tout le circuit (P3)
- Collision générée depuis la géométrie du lieu, pas seulement la route : sol, trottoirs, murs, bâtiments
  proches, avec une surface par matériau (Tarmac, Dirt, Grass…).
- Murs invisibles en bord de zone roulable (pas de chute dans le vide).
- Aperçu de la collision superposée au rendu dans le studio.
- Validation : aucune chute en roulant tout le circuit (`trackrec.py --all`, 20 voitures).

### 3.3 Zones roulables en polygones et IA (P5)
- Le joueur dessine des **polygones** (zones roulables) et des **raccords** entre eux, à la place des lignes.
- Le moteur en déduit automatiquement : la ligne centrale, les largeurs par nœud et les jonctions du `.aid`
  (le nœud d'un `.aid` est un BORD de route), la trajectoire de course, les points de respawn (toujours dans
  un polygone, orientés dans le sens de la course).
- Contrôles bloquants : polygones qui se chevauchent sans raccord, chemin sans sortie (blocage), respawn
  hors zone, virage plus serré que ce que l'IA sait prendre.
- Validation : course de 20 IA sur 3 tours sans IA bloquée et sans respawn hors de la route.

### 3.4 Aperçu réel studio ↔ jeu (P4)
- Lecture seule de la mémoire du jeu (`blur_live.py`, `trackrec.py`) : position des voitures en direct,
  affichée dans le studio sur la carte.
- Outil « relevé » : on se gare en jeu sur un emplacement, le studio enregistre le point (départ, bonus,
  hauteur du sol réel).
- Validation : écart studio ↔ jeu < 0,5 m sur les places de grille et les bonus.

### 3.5 Contenu de la carte
- Grille de départ (solo et multi : la course perso utilise la multi), lignes départ / arrivée, bonus
  (rangées, type, nombre), plateformes et rampes (`addramp.py`), objets de Blur réutilisés (`actorpack`).
- Aperçus : vignette de chargement (`ui_frontend.bpr`), tracé de la mini-carte (`.ipf`), ambiance / ciel.

### 3.6 Construction et test
- Construction **par carte** (pas de passe globale), journal complet des erreurs, installation dans la copie
  de test seulement.
- Chaque construction relance les contrôles des cartes verrouillées (`maplock.py check`).

## 4. Ordre de travail proposé

| Étape | Contenu | Fini quand |
|---|---|---|
| 1 | Diagnostic P1 : même vue en studio et en jeu sur Dubaï | on sait si c'est l'affichage ou les fichiers |
| 2 | Rendu en tuiles + libération mémoire (P2) | 30 min de navigation sans plantage, mémoire stable |
| 3 | Fiche de carte commune + verrou (généraliser `maplock`) | NFS Studio et Reverse Studio lisent la même fiche |
| 4 | Polygones roulables → `.aid` + respawn (P5) | critère 3.3 |
| 5 | Collision complète (P3) | critère 3.2 |
| 6 | Retour du jeu en direct (P4) | critère 3.4 |
| 7 | Greffon d'import n° 2 (autre jeu) | un 2e jeu source importé sans toucher au moteur |

## 5. Questions ouvertes
- P1 : l'abîme se voit-il **en jeu** ? (à tester par l'utilisateur sur la dernière construction de Dubaï)
- Quel deuxième jeu source viser pour valider les greffons ?
