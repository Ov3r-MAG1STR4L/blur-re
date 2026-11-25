# V16000 + encadrements de fenêtres (2026-11-26)

**Statut : construite, contrôlée et inspectée en rendu ; non validée, non importée dans Blur.** KN5, V8600, V12000,
V16000 et les autres reconstructions non modifiés. Fichier : `glb/1000tipla_D2_16000.glb` — **15 644 triangles,
131 pièces (127 extérieures + 4 cadres), 16 matériaux, 14 images, INTÈGRE** (`glb_check.py`).

## Méthode
1. Les 4 pièces relues dans le KN5 original (`kn5.py`).
2. **Visibilité extérieure** (`visible_faces_blender.py`) : face gardée si vue par son côté avant depuis au moins une
   des 72 caméras autour de la voiture (24 azimuts x 3 hauteurs, 7 m), sans rien devant ; vitres transparentes.
3. Faces visibles + **2 rangées** de voisines (les bords de coupe tombent dans la partie cachée).
4. Découpe et fusion avec la base extérieure (`trim_merge_blender.py`), matériaux noirs d'origine (`BlackMatte`).
5. Répartition par tolérance sous 16 000 (`planchers.csv`), détails de V16000 jamais réduits, cadres traités comme
   des contours de vitre (≤ 5 mm), refus des faces retournées.

| Pièce | Faces du KN5 | Vues de l'extérieur | Gardées (+2 rangées) | Bords de coupe | Triangles dans le GLB | Écart moy / max |
|---|---|---|---|---|---|---|
| `Fiat_Multipla_96` | 51 050 | 35 906 | 47 380 | 1 298 | **1 387** | 0,6 / 4,9 mm |
| `Fiat_Multipla_94.002` | 2 138 | 1 191 | 1 777 | 86 | **47** | 1,3 / 4,3 mm |
| `Fiat_Multipla_94.003` | 2 138 | 1 182 | 1 764 | 96 | **36** | 1,6 / 4,7 mm |
| `Fiat_Multipla_135` | 6 544 | 4 991 | 6 239 | 21 | **283** | 0,8 / 4,3 mm |
| **Ajoutés** | | | | | **1 753** | |

Une grande part de ces pièces se voit vraiment de l'extérieur (à travers les vitres transparentes : cadres intérieurs
de portes, bas de vitre) ; la découpe ne retire que ~7 %. Elle rend aussi `Fiat_Multipla_96` **plus coûteuse** à
réduire (bords de coupe) : 2 168 triangles à 4 mm contre 1 386 pour la pièce entière ; d'où 5 mm pour les cadres.
Les bords de coupe longent des faces jamais vues par leur côté avant (cachées, ou vues de dos et donc non dessinées
par Blur) : pas d'ouverture nouvelle attendue, confirmé sur les gros plans.

## Bilan des triangles
| | V16000 | V16000 + cadres |
|---|---|---|
| Cadres ajoutés | 0 | **1 753** |
| Autres pièces | 15 745 | **13 891** (−1 854 redistribués) |
| **Total** | 15 745 | **15 644** |

Pièces qui ont cédé des triangles (pire écart V16000 → nouvelle version) : tôles peintes −935 (4,0 → 5,8 mm), chromes
−286 (3,9 → 4,7), bouclier −126, supports de roue −125 (3,5 → 4,7), diffuseur −115 (3,9 → 5,0), autres pièces noires
−105, bas de caisse −86, aileron −76 (3,6 → 5,0). Détails (feux, échappements, contours, rétros, vitres) **inchangés**.

## Contrôles
- 131/131 pièces présentes ; **aucune face retournée** (> 1 %) ; 0 primitive sans UV ; matériaux d'origine (les cadres
  en `BlackMatte`), aucun matériau en double.
- Relevé par rayons des fenêtres (1 cm, deux flancs) contre le KN5 complet : surfaces remplies dans le KN5 et vides
  dans la reconstruction **5 652 cm² → 154 cm²** (≈ 97 % retrouvés) ; reste : bords à quelques mm (`_96` 68 cm²,
  `body_main.040` 24 cm²) et habitacle (`Cage`, retiré volontairement) ; 74 cm² vus de dos où le KN5 montre la face.
- Bug trouvé et corrigé pendant la construction : l'export OBJ de Blender change les espaces des noms en « _ » ; les
  planchers de `Turnsignal left/right` et `FL 1.002` ne s'appliquaient pas (fichier refait, `reduce_d2_blender.py`
  s'arrête désormais sur un nom inconnu).

## Comparaison visuelle (`cmp_<zone>.png` : KN5 complet / V16000 / V16000 + cadres, texture et gris)
- **Contours supérieur et inférieur** : cadre noir continu retrouvé, plus de jour clair.
- **Montant avant** (pare-brise, rétro) : cadre retrouvé, raccord propre avec la carrosserie.
- **Montant central** : présent, mais un peu dentelé avec de fines lignes claires le long du joint (bords réduits à 5 mm).
- **Joints noirs périphériques** : présents ; les rainures fines du profil sont simplifiées.
- **Continuité cadres / carrosserie** : bonne sur les flancs ; deux petites fentes claires à l'avant du toit, déjà
  présentes dans V16000 (`body_main.040`).

## Points à décider
1. Validation de cette version (ou cadres à 4 mm contre ~800 triangles pris ailleurs, ou pièce `_96` entière sans
   découpe : 1 386 à 4 mm).
2. Correction de l'ombrage de la portière (défaut de V16000, toujours présent).
