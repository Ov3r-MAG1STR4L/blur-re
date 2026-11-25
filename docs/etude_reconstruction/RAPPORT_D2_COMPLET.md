# 1000tipla complète en D2 : rapport (2026-11-25)

**Statut : construit et inspecté en rendu, PAS validé, PAS importé dans le jeu** (en attente de l'examen de
l'utilisateur). Méthode : `blur_tools/reduce_d2_blender.py` (étude : `blur_tools/docs/ETUDE_RECONSTRUCTION_1000TIPLA.md`).

## Sources et sorties
- Source Assetto Corsa lue seulement : `raw/.../1000Tipla by Vilebrequin.kn5`, empreinte sha256 `a5db37eed04b9a58…`
  identique avant et après.
- Modèle d'entrée : `src_obj/` (`kn5.py`) = 127 pièces extérieures, **361 918 triangles**, 13 textures d'origine.
  Retirés comme dans les versions précédentes : habitacle (`COCKPIT_HR` et pièces intérieures rangées dans la caisse,
  liste `../interior_skip.txt`), roues et suspensions (Map Builder pose ses roues). **Calandre en nid d'abeille
  remise** (elle avait été retirée dans les versions précédentes).
- Sorties : `glb/1000tipla_D2_6000.glb`, `_7000.glb`, `_8000.glb` (4,3 Mo chacun) ; comptage par pièce
  `glb/pieces_<budget>.csv` ; rendus `rendus/`. Les anciennes reconstructions (`../glb/`) sont intactes.

## Réglages
- Budget par surface (D2), poids x3 pour les éléments importants : matériaux vitres / feux / miroirs et pièces de
  `importants.txt` (sorties d'échappement `Circle.018/019/020`, rétros `Cube.001/002`, `BrakeLights`,
  `REverseLight`, phares hauts `Fiat_Multipla_66/69/71/74`).
- Plancher **par pièce** : le plus petit nombre de triangles (8, 16, 32…) qui garde la pièce sous la tolérance d'écart.
  Tolérance la plus stricte qui tient : 2 cm demanderait ~9 700 triangles, **3 cm** retenu pour les trois budgets
  (4 317 triangles de planchers, le reste réparti par surface).
- Pièces que Decimate ne réduit pas (> 2 000 triangles, encore > 100 au plancher) remplacées par une **carte** : plaque
  fermée (voxels 6 mm) avec leur couleur cuite (512 px) : calandre `Circle.027` (20 448 tri.) et montants / support
  d'aileron `Circle.015` (3 592 tri., trous d'allègement peints, plus percés).
- Normales d'origine effacées et recalculées (lissage 30°) ; UV et textures d'origine gardées (aucune réduction de
  résolution : 3 textures en 4096 px, voir « Points à décider »).

## Résultats
| Budget | Triangles (GLB) | Pièces | Supprimées | Cartes | Déformées (moy > 5 mm) | Au plancher |
|---|---|---|---|---|---|---|
| 6 000 | 5 991 | 127 | 0 | Circle.015, Circle.027 | 26 | 46 |
| 7 000 | 6 990 | 127 | 0 | Circle.015, Circle.027 | 21 | 40 |
| 8 000 | 7 992 | 127 | 0 | Circle.015, Circle.027 | 18 | 40 |

Aucune pièce au-delà de 3 cm d'écart max. Pièces déformées à 8 000 (écart moyen > 5 mm, toutes sous 3 cm au max) :

| Pièce | Matériau | Tri. origine | Tri. réduits | Écart moy mm | Écart max mm |
|---|---|---|---|---|---|
| Fiat_Multipla_90 | BlackMatte | 13 532 | 6 | 10,0 | 29,1 |
| Fiat_Multipla_128 | BlackMatte | 2 400 | 15 | 9,3 | 24,5 |
| Fiat_Multipla_123 | BlackMatte | 2 400 | 15 | 9,1 | 22,1 |
| polymsh_detached19 à 22 | Metal | 75-85 | 16 | 8,4-8,7 | 27-29 |
| Circle.009 | BlackMatte | 1 552 | 36 | 7,3 | 17,8 |
| Circle.030 | Chrome_Matte | 128 | 8 | 6,6 | 18,1 |
| Circle.029 | BlackMatte | 350 | 32 | 6,0 | 22,3 |
| body_main.041 | CarPaint | 2 640 | 15 | 5,6 | 25,4 |
| Fiat_Multipla_97, _53 | BlackMatte | 1 472 / 2 880 | 29 / 16 | 5,4 | 17 |
| Fiat_Multipla_69, _74 (phares hauts) | Chrome_Matte | 512 | 10 | 5,3-5,4 | 23 |
| Fiat_Multipla_124 (feu arrière) | Chrome_Matte | 5 296 | 31 | 5,3 | 26,8 |
| body_main.053 | CarPaint | 1 664 | 8 | 5,3 | 30,0 |
| Fiat_Multipla_65.001 (feu rouge) | light_red | 3 136 | 7 | 5,1 | 18,5 |

## Intégrité des GLB (`blur_tools/glb_check.py`)
Les trois fichiers : **INTÈGRES**. En-tête et longueurs, accesseurs dans les buffers, index < sommets, positions /
normales (unitaires) / UV finies, 15 images décodables, références de textures et matériaux valides, triangles sous le
budget. 17 matériaux (15 d'origine + 2 cartes), vitre `Car_windshield_glass` en `BLEND` (reconnue « glass » par Map
Builder). Bug trouvé et corrigé pendant le contrôle : les deux cartes partageaient une seule image (noms coupés au
point par l'export glTF).

## Inspection visuelle (rendus `rendus/planche_8000_texture.png`, `_gris.png`, `planche_budgets.png`)
Fidèle : silhouette, toit, capot, portes, élargisseurs, aileron, rétros, feux, 4 sorties d'échappement, calandre,
livrée. Défauts : supports noirs des passages de roue arrière un peu dentelés ; montants d'aileron pleins (trous
peints) ; ailettes du diffuseur légèrement dentelées ; bas du bouclier avant un peu ondulé ; feux arrière simplifiés.
Peu de différence visible entre 6 000, 7 000 et 8 000 à cette distance.

## Points à décider
- Budget réel de Map Builder (8 000 = débordement possible dans l'habitacle, vu avec la Vulcan à ~8 700).
- Textures 4096 px (pare-chocs, spoiler) : à réduire si Map Builder ou le jeu peinent.
