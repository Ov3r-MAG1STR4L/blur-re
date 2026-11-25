# Étude : réduire une voiture détaillée pour Map Builder (1000tipla, 2026-11-25)

But : un 1000tipla fidèle au modèle Assetto Corsa dans la limite de Map Builder (budget de l'étude : **8 000
triangles**, choisi par l'utilisateur ; avec la Vulcan, ~8 700 avaient débordé dans l'habitacle : à vérifier en jeu).
Méthode validée **sur une seule pièce** avant la voiture entière. Rien essayé dans Map Builder ni en jeu.

Scripts : `etude_reconstruction/` (banc de rendu, mesure, cuisson, méthodes C et D). Fichiers de travail (hors dépôt,
usage perso) : `Jeux_WII/tipla_src/study`. Planches : `docs/etude_reconstruction/`.

## 1. Audit des essais précédents (causes des déformations)

| Défaut vu | Cause |
|---|---|
| Pièces déchirées, budget gaspillé (`glb_reduce_blender.py`) | Decimate au même taux partout : le budget suit la **densité** du modèle d'origine, pas la surface visible. Un feu de 15 000 triangles reçoit 25 fois plus qu'une grande tôle |
| Tôles « cabossées comme après un train » | En partie de **l'ombrage, pas de la forme** : les normales d'origine (OBJ) restent figées après la réduction et s'interpolent mal (taches sombres). Recalculées, la même géométrie est lisse (planche D / D2) |
| Coque molle (reconstruction voxel) | Remaillage voxel + Decimate : creux comblés, arêtes adoucies ; voxels plus fins = surface bruitée que Decimate froisse |
| Lambeaux (Instant Meshes) | Modèle fait de panneaux séparés et superposés (autocollants, élargisseurs) : Instant Meshes ne sait pas les relier |
| Simplification bloquée (MeshLab, UV d'origine) | Coutures d'UV très nombreuses : la réduction qui garde les textures s'arrête vers 3 000 triangles pour 843 visés |
| Relief fin perdu | Map Builder ne lit pas les normal maps (`ModelImport.cs`) : seuls des triangles ou l'ombrage cuit dans la couleur peuvent le rendre |

## 2. Banc d'essai

Pièce : aile arrière gauche (élargisseur, passage de roue, feu arrière, bas de caisse), boîte x 0,45..1,15,
y 0,05..1,25, z −2,15..−0,35 (repère AC), 34 maillages, **58 161 triangles**, 10,5 % de la surface extérieure →
**843 triangles** sur 8 000. Pour chaque méthode : `.glb`, triangles comptés, même caméra et même lumière (texture +
gris brillant), écart de Hausdorff (pymeshlab, 200 000 points, les deux sens). Contrôle : original contre lui-même = 0.

## 3. Résultats (même budget)

| Méthode | Triangles | Formes perdues moy / max (mm) | Déformations moy / max (mm) | À l'œil |
|---|---|---|---|---|
| A. Blender Decimate, pièce par pièce | 811 | 26,9 / 472 | 2,5 / 70 | forme générale, tôles cassées |
| B. Instant Meshes (surface soudée) + cuisson | 845 | 31,9 / 356 | 3,2 / 46 | lambeaux, inutilisable |
| C. MeshLab, UV d'origine | 2 969 | 17,5 / 154 | 13,3 / 214 | n'atteint pas le budget |
| C. MeshLab géométrie seule (passes) + cuisson | 843 | 30,4 / 233 | 4,6 / 34 | élargisseur et passage de roue perdus |
| **D. Hybride : budget par surface, textures d'origine** | 819 | **1,8 / 33** | **1,3 / 39** | fidèle, ombrage taché |
| **D2. = D + normales recalculées (30°)** | 819 | **1,8 / 33** | **1,3 / 39** | **le plus proche de l'original** |

Simplygon : non testé (compte Microsoft nécessaire).

## 4. Conclusion

**Méthode retenue : D2** (`etude_reconstruction/method_D_blender.py --normales`). Pièces d'origine conservées avec
leurs textures (pas de cuisson), chacune soudée seule, doublons retirés, budget **proportionnel à sa surface**, normales
recalculées. Environ **15 fois moins de formes perdues** que les autres méthodes au même budget.
Limites : les pièces petites mais très détaillées (ampoules du feu arrière) restent froissées ; les plus petites
peuvent disparaître (minimum 2 triangles). Pistes : plancher de triangles pour les feux, ombrage cuit en plus.

Prochaine étape (après accord) : D2 sur la voiture entière à 8 000 triangles, vitres comprises, puis essai dans Map
Builder.
