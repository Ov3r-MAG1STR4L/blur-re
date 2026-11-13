# Audit A : relations entre ciel, cubemaps et éclairage (Blur 2 → Blur 1)

Audit en lecture seule, 2026-11-13. Rien n'a été modifié dans les fichiers du jeu, Blur n'a pas été lancé, aucun commit.
Niveaux de confiance utilisés :

- **[F] Fait** : lu dans les données ou, pour Blur 1, dans le code (audit BlurRebuilt, réutilisé) ;
- **[H] Hypothèse plausible** : déduite, cohérente, mais non lue telle quelle ;
- **[?] Indéterminable** sans analyse du moteur Blur 2 (`.xex`) ou sans essai en jeu.

Une relation n'est jamais déduite du seul fait que deux paramètres sont dans le même enregistrement.

## 1. Où vit chaque donnée

| Donnée | Blur 1 (PC) | Blur 2 (X360, août / 4 nov / 10 nov) | Source |
|---|---|---|---|
| Soleil, ciel (ambiant), « baked », émissif | `LightingSettings` dans `amax.bin` (via `City.EnvironmentSettings`) | `LightingSettings` dans **`environmentalsettings.bin`** (via `City.EnvironmentSettings` dans **`tracks.bin`**) | [F] |
| Brouillard de distance et de hauteur | idem (`FogSettings`) | idem + **`LayerFogSettings`** (nouveau, 1 enregistrement, Ski Resort) | [F] |
| Texture du ciel, rotation, intensité, brouillard du ciel | `SkySettings` dans `LightingSettings` | idem (même structure) | [F] |
| Exposition (min / max / gris moyen), bloom | `PostProcess` (`hdrSettings`) dans `LightingSettings` | idem | [F] |
| Étalonnage (LUT), grain, vignette, matrices de couleur | `PostFxSettings` | idem | [F] |
| Cubemap « global » d'un réglage | `LightingSettings.cubemapTexture` | idem, **vide pour toutes les villes Blur 2** | [F] |
| Cubemap(s) localisés du niveau | bloc `CubePt2` du `levelrender` | 31 août : `CubePt2` ; nov : bloc **`CubePt3`** (nom + position) | [F] |
| Échantillons de lumière | `LSData` (24 o/échantillon) + `LSTree` | 31 août : **24 o partout** et `CubePt2` (format Blur 1) ; 4 et 10 nov : **16 o** sur les maps refaites, 24 o sur les maps héritées | [F] |
| Lightmaps | non pour le décor (quelques props) | pages `lightmap_*-a/-b`, samplers `g_tLightmap0/1` (Dubaï 10 nov) | [F] |
| Réglages éclairage voitures (SH, cubemap) | `CarLightSettings` | idem | [F] |

Schéma `LightingSettings` (188 o, identique dans les trois builds Blur 2 et compatible avec les offsets de
Map Builder pour Blur 1) : `LightingInfo` (Sun/Sky/Baked/Emissive en RGBA, +0), `FogSettings` (+64),
`cubemapTexture` (chaîne, +108), `SkySettings` (+112 : texture, rotation, intensity, fogColour, fogCurve,
blackHeight, blackSize), `PostProcess` (+152 : exposureMin, exposureMax, middleGrey, bloomScale, bloomScale0..3,
bloomThreshold). [F] (`scripts/env_records.py`, schéma lu dans le fichier lui-même).

Écart à signaler : Map Builder nomme +152 « middle grey » et +160 « exposure max » ; le schéma Blur 2 donne
+152 `exposureMin`, +156 `exposureMax`, +160 `middleGrey`. Le schéma Blur 1 n'a pas été relu ici : **[?]** lequel est
juste pour Blur 1. Les valeurs d'Amboy, identiques dans les deux jeux (2,25 / 3,0 / 0,1 dans l'ordre du schéma Blur 2,
et dans `lighting_presets.json` de Map Builder : `middle_grey` 0,1, `exposure_min` 2,25, `exposure_max` 3,0), montrent
que Map Builder lit en fait les bons octets sous des noms décalés ou l'inverse : à trancher en relisant le schéma
`amax.bin` PC.

## 2. Réponses aux questions

### 2.1 Le ciel est-il uniquement une ressource de rendu du fond ?
- **[F]** Le ciel est désigné par `SkySettings.texture`, un champ séparé de `cubemapTexture` et des cubemaps
  `CubePt2/3`. Aucun `levelrender` ne cite une texture de ciel (relevé de chaînes, `data/levelrender_env.json`).
- **[F]** Blur 1 : un objet reçoit son éclairage ambiant de `g_SHNode` (échantillon le plus proche à moins de 10 m)
  et ses reflets de `g_tEnvironment` (cubemap localisé) ; ni l'un ni l'autre n'est calculé à partir de la texture du
  ciel (`C_EnvironmentSampler`, audit BlurRebuilt §2.B).
- **[H]** Blur 2 garde la même chaîne : `CubePt3` remplace `CubePt2`, `g_tEnvironment` est toujours déclaré. Le ciel
  serait donc **un fond**, avec son brouillard propre (`SkySettings.fogColour/fogCurve`) et son assombrissement bas
  (`blackHeight/blackSize`).
- **[?]** Qu'aucun shader Blur 2 n'échantillonne la texture du ciel ailleurs (eau, reflets de route) : à vérifier
  dans les shaders X360 (`shaders-speed.pak` des archives, non décodés).

### 2.2 Les cubemaps servent-ils aux réflexions ?
- **[F]** Blur 1 : oui, `g_tEnvironment` = cubemap `CubePt2` le plus proche, intensité R × Fresnel (G14 ; reflet
  visible en jeu en G13-C).
- **[F]** Blur 2 (Unity, reconstruction d'uKER) : `_EnvironmentCube` sur ~1 040 matériaux de Dubaï, un seul cubemap
  (`tex_lr6_dubai_envdefault` 256², DXT1), lu dans la direction réfléchie avec un flou `lod 7·(1-G)` (CONNAISSANCES,
  désassemblage du shader).
- **[F]** Blur 2 X360 : le `levelrender` de Dubaï (10 nov) déclare `g_tEnvironment` et un `CubePt3`
  `Dubai_EnvDefault` placé en (-899,4 ; 14,8 ; -189,7) (axes du fichier ; lecture de la position **[H]**).
- **[F]** `CarLightSettings` a `StaticLightCubemapFactor` / `DynamicLightCubemapFactor` / `LightCubemapMax` : les
  voitures utilisent aussi un cubemap. Lequel (`CubePt3`, ou cube dynamique de la ville, `environmentResolution`
  « High_256 ») : **[?]**.

### 2.3 Une ressource dérivée du ciel sert-elle à l'éclairage ambiant ?
- **[F]** Rien dans les données ne relie la texture du ciel à un cube, une lightmap ou des échantillons.
  `Dubai_EnvDefault` est une prise de vue du décor de Dubaï, sombre, pas un ciel (CONNAISSANCES, aperçu du cube Unity).
- **[H]** Échantillons et lightmaps sont calculés hors ligne par l'outil d'export de Bizarre ; le ciel a pu servir de
  source **à ce moment-là**, mais rien dans les fichiers ne le montre.
- **[F]** Unity : l'ambiant trilinéaire et la sonde SH de `RenderSettings` (Blur2DubaiTest) sont générés par Unity à
  partir de son **skybox procédural par défaut** (`Default-Skybox`, `_SUNDISK_SIMPLE`). Ce sont des réglages de la
  reconstruction, pas des données Blur 2. Le shader `Blur2/InspectionSurface` n'utilise des SH que si `_HasSHNode`,
  jamais actif à Dubaï (G14).

### 2.4 Soleil, ciel, brouillard et exposition sont-ils indépendants ?
- **[F]** Ce sont des champs distincts, réglés séparément (ex. Ski Resort 10 nov : soleil propre, ciel
  `deep_blue_sky`, brouillard 0,004, exposition 0,4 / 2,0).
- **[F]** Seul couplage explicite : `SkySettings.fogColour` (couleur propre au brouillard du ciel). Elle est égale à
  `FogSettings.FogColour` dans la plupart des réglages, pas dans tous : convention de saisie, pas calcul.
- **[F]** La force du soleil (`SunColour.a`) vaut **0** dans toutes les villes Blur 1 et dans les réglages Blur 2 des
  villes jouables, sauf Hong Kong / Liverpool d'août (a = 20) et `_Test_Lighting` (a = 1). Blur 1 n'éclaire pas les
  objets par le soleil direct (constaté par Map Builder) ; **[H]** même convention dans Blur 2, la lumière directe
  étant cuite (mesure Unity : B.y ≈ 0, le terme soleil ne compte presque pas).
- **[F]** L'échelle d'exposition change : Blur 1 `middleGrey` 0,1 et exposition 2-3,5 ; réglage par défaut des villes
  Blur 2 de novembre `middleGrey` 0,18, exposition 0,4-2,0, `bloomScale` 10 ; Dubaï d'août 3,0-10,0.
  **[?]** si l'opérateur de tonalité est le même (même formule, autre calibrage) : à lire dans les shaders X360.

### 2.5 Les échantillons de lumière sont-ils précalculés et indépendants du ciel au runtime ?
- **[F]** Précalculés : blocs `LSData` / `LSTree` stockés dans chaque `levelrender` (Blur 1 et Blur 2).
- **[F]** Blur 1 : lus tels quels par `C_LightSamplePointScene` (rayon fixe 10 m), sans référence au ciel.
- **[F]** Blur 2 : enregistrement de **16 o** (8 demi-flottants) sur les maps refaites (Dubaï 10 nov : 24 917,
  Hong Kong : 167 193, LA City : 107 732…), 24 o sur les maps reprises de Blur 1 ou anciennes (graphical,
  fx_testlevel, la_freeway). Moyennes à Dubaï : (0,01 ; 0,11 ; 0,01 ; 0,21) puis (1,00 ; 1,00 ; 1,00 ; 0,54).
  **[H]** SH de luminance à 4 termes (y dominant, comme la lumière venant du haut) + teinte RGB + un coefficient,
  contre 3 × 4 SH RGB dans Blur 1.
- **[?]** Qu'aucun facteur runtime (`SkyColour`, `BakedColour`) ne les module : plausible (la formule Unity
  `lerp(_BakedColour, _Blur2EnvBakedColour, _Blur2EnvBlend)` s'applique aux lightmaps), non lu pour les échantillons.

## 3. Schéma de synthèse

```
tracks.bin  City ──EnvironmentSettings──► environmentalsettings.bin
                                           ├─ LightingSettings ─┬─ LightingInfo (soleil, ciel, baked, émissif)
                                           │                    ├─ FogSettings
                                           │                    ├─ cubemapTexture (vide en Blur 2)
                                           │                    ├─ SkySettings ──► graphics/textures/skies/*.texture  (FOND)
                                           │                    └─ PostProcess (exposition, bloom)
                                           ├─ PostFxSettings ──► graphics/textures/postprocess/*_LUT.dds
                                           ├─ CarLightSettings (SH / cubemap des voitures)
                                           └─ LayerFogSettings, RoadTrack, Shadow, Wind, LightFlare
levels/<map>/level.levelrender
     ├─ CubePt3 ──► cubemaps/<Nom>.dds  (REFLETS, g_tEnvironment, localisé)
     ├─ LSData / LSTree (AMBIANT des objets, précalculé)
     └─ lightmap_*-a/-b (ÉCLAIRAGE CUIT du décor fixe, Blur 2)
```

## 4. Pour lever les [?]
1. Désassembler les shaders X360 (`shaders-speed.pak`) : tonalité, usage éventuel du ciel, lecture des 16 o de
   `LSData`.
2. Lire le lecteur de `levelrender` de Blur 2 dans le `.xex` déchiffré (déjà fait pour les messages, `easter_eggs`)
   pour `CubePt3` et `LSData` 16 o.
3. En jeu (Blur 1, copie de test) : changer seulement `SkySettings.texture` d'une ville et vérifier que l'éclairage
   des objets ne bouge pas (attendu d'après le code Blur 1).
