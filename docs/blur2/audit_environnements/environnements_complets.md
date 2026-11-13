# Audit A : environnements et systèmes atmosphériques de Blur 2

Audit en lecture seule (2026-11-13). Aucun fichier de jeu modifié, Blur non lancé, aucun modèle installé, aucun
commit, aucune conversion de texture. Seules 4 petites tables (≈ 160 Ko) ont été extraites de l'archive d'août et
3 × 4 tables des paks X360 déjà extraits ; les `levelrender` des archives ont été lus **en mémoire** (`7z e -so`).

Confiance : **[F]** fait lu dans les données, **[H]** hypothèse plausible, **[?]** indéterminable sans moteur ou essai.

Livrables du dossier :

| Fichier | Contenu |
|---|---|
| `environnements_complets.md` | ce rapport |
| `environnements.json` | inventaire par build et par ville (réglages résolus, ressources et présence dans les paks) + par niveau (`levelrender`) + Unity |
| `relations_eclairage.md` | ciel / cubemaps / échantillons / exposition : ce qui est lié, ce qui ne l'est pas |
| `compatibilite_blur1.md` | portage catégorie par catégorie |
| `scripts/` | `inv_paks.py`, `env_records.py`, `link_maps.py`, `archive_maps.py`, `levelrender_scan.py`, `unity_env.py`, `extract_tables.py` (premier essai, remplacé par `env_records.py`) |
| `data/` | sorties brutes : tables `.bin` + `env_records.json` par build, `paks_env.json`, `textures_citees.json`, `archives_maps.json`, `levelrender_env.json`, `unity_env.json`, listings des 3 archives |

Réutilisé sans le refaire : G6 (placement), G14 (matériaux, capacités Blur 1), audit BlurRebuilt (chaîne
d'éclairage Blur 1), CONNAISSANCES (formule du shader Unity, cubemap Unity de Dubaï, Map Builder `lighting.py`).

## 1. Sources

| Source | Chemin | Ce qui a servi |
|---|---|---|
| Blur 2 X360 10 nov | `blur_extracted\b2_x360_nov\gamedata.pak`, `…\full\Blur 2 (Nov 10, 2010)\cache\root.pak`, `levels\dubai\` ; archive `Downloads\Blur 2 (Nov 10, 2010 prototype).rar` | tables, textures (noms), `levelrender` de 40 niveaux |
| Blur 2 X360 4 nov | `blur_extracted\b2_x360_nov04\!Blur 2 (Nov 04, 2010) [Unreleased]\cache\*.pak`, `levels\dubai\` | tables, textures, Dubaï |
| Blur 2 X360 31 août | `Downloads\Blur 2 (Aug 31, 2010 prototype).rar` (`KanzenDev\gamedata\xt\*.bin` en clair) | tables (copie dans `data\aug31`), listing, `levelrender` |
| Blur2DubaiTest (Unity) | `Jeux_WII\Blur2DubaiTest\Blur2DubaiTest_Data` | `RenderSettings`, lumière, skybox, `sky_rotation_offsets.csv`, `dubai_lights` |
| Blur 1 PC (référence) | `C:\Program Files (x86)\Activision\Blur(TM)\cache\*.pak`, `levels\*\level.levelrender` (lecture) | présence des textures, `CubePt2`, `LSData` |

Décodage : `env_records.py` est un décodeur KSLF X360 « plat ». Deux pièges trouvés et contournés :
- les **drapeaux de champ** X360 ont leurs deux octets inversés (`0x300` = struct en ligne, `0x500` = référence) ;
  `blurxt_be.py` les lit tels quels, d'où des enregistrements faux ou une récursion infinie ;
- les graphes `PostFxMatrix` (pointeurs internes) font exploser la récursion : non suivis ici.

## 2. Où sont les environnements (structure)

**[F]** Blur 2 a sorti les réglages d'ambiance de `amax.bin` (Blur 1) vers des tables dédiées, **avec les mêmes types** :

- `tracks.bin` : `City` (46 en novembre, 38 en août), champ `EnvironmentSettings` et `FlashbackSettings` (refs) ;
- `environmentalsettings.bin` : `LightingSettings` (92 à 98), `PostFxSettings` (92-93), `CarLightSettings` (22),
  `RoadTrackSettings` (23-25), `ShadowSettings` (6), `WindSettings` (9-11), `LightFlareSettings` (22),
  `EnvironmentSettings` (9 préréglages), `EnvironmentSettingsFX` (1), `LayerFogSettings` (1, nov) /
  `VehicleRainSettings` (1, août) ;
- `lighting.bin` : 251 `CutSceneLightDef` (4 lumières directionnelles avec couleur, cap, élévation) ;
- `amax.bin` réduit à 4 Ko (friction, budgets, un `EnvironmentSettings` vide).

`amax.bin` de Blur 2 ne contient donc **plus** les ambiances : la piste `amax.bin` du cahier des charges mène à
`environmentalsettings.bin` + `tracks.bin`.

Schéma `LightingSettings` : voir `relations_eclairage.md` §1.

## 3. Ciels

### 3.1 Textures de ciel [F]
- Dossier `graphics/textures/skies/` dans `root.pak` X360 (et `root.pak` PC pour Blur 1). Conteneur `Texture`.
- Blur 1 PC : 1 048 660 o, en-tête `Texture`/`Header`/`Data`, format **DXT5 2048 × 512, 1 niveau** (lu dans
  l'en-tête de `HFD_HemiSunset27`) : panorama hémisphérique en bande, pas un cubemap.
- Blur 2 X360 : 1 048 700 o (même classe, en-tête X360 de 124 o, données Xenon) ; `HFD_HemiClouds17` : 4 194 424 o
  (4 × plus grand : [?] 4096 × 1024 ou 2048 × 2048).
- **Ciels propres à Blur 2** (absents de Blur 1 PC) : `deep_blue_sky` (10 nov seulement, Ski Resort), `pink_sunset`
  (10 nov, référencé par aucune ville), `HFD_HemiClouds17` (Brighton Storm d'août) ; dans l'archive d'août en
  fichiers libres : `HFD_HemiClouds08/12/16/17`, `hdr_cloudy07_ldr`, `hdr_stormy01_ldr` (4 Mo), `v06c`.
- Dossier `dontship/textures/skies/` (10 nov) : `hdr_cloudy01/03/04/09`, `hdr_stormy01`, `hdr_sunset02..15`
  (1 Mo chacun) : ciels de travail. `hdr_cloudy09` sert à `_Test_Lighting`.
- Aucune rotation / position / échelle n'est stockée dans la texture : rotation et intensité sont dans
  `SkySettings` (`rotation` en radians [H, 0..6,3 dans Map Builder], `intensity`), plus `blackHeight` / `blackSize`
  (bande sombre sous l'horizon) et `fogColour` / `fogCurve`.

### 3.2 Ciel par ville (réglage normal, pas Flashback)

| Ville | Août (31/08) | 4 nov | 10 nov |
|---|---|---|---|
| **Dubai** | `HFD_HemiClouds16`, rot 0,273, int 0,5, LUT **`Dubai_Sunny_LUT_01`**, expo 3,0-10,0 | défaut ¹ | défaut ¹ (copie dédiée, valeurs identiques) |
| **Ski_Resort** | `HFD_HemiSunset27`, rot 0,193, int 0,05 (réglage « graphical ») | défaut ¹ | **`deep_blue_sky`**, soleil (5,86 ; 5,68 ; 4,10), brouillard bleu 0,004, `LayerFog` 900 m, clip 8 000 m |
| UK_Brighton_Storm | `HFD_HemiClouds17`, LUT `Brighton_Storm_LUT_02`, expo 4,5-5,0 | — | — |
| UK_Brighton_Sunny | `HFD_HemiClouds08`, LUT `Brighton_Sunny_LUT_04`, expo 3,5-4,0 | — | — |
| Hong_Kong, Liverpool | `dontship/s16d.dds`, int 0,02, cube `LA_River_CubeMap`, soleil a = 20 | défaut ¹ | défaut ¹ |
| LA_City, Detroit, North_Africa, Odessa | `dontship/Istanbul_TEST_2.dds` (absent de tous les paks) | défaut ¹ | défaut ¹ |
| Miami | `v09b`, LUT `Hollywood_01` | défaut ¹ | défaut ¹ |
| LA_Freeway | — | `t02c`, rot 0,62, int 0,4 | idem |
| Villes Blur 1 (Amboy, Barcelone, Brighton, Hackney, LA, NY, SF, Tokyo, Haruna) | réglages Blur 1 repris (ex. Amboy `s10`, 0,78 / 0,5, expo 2,25-3,0 = valeurs Blur 1) | idem pour celles encore présentes | idem |

¹ **défaut** = enregistrement `@0a6eee76` : `HFD_HemiSunset27`, rot 0,85, int 1,0, brouillard 0,002 dès 100 m, soleil
(1,0 ; 0,96 ; 0,82, force 0), baked (1, 1, 1, 0), exposition 0,4-2,0, gris moyen 0,18, bloom 10, LUT `LA_Downtown_02`
(chaîne tronquée « `.dd` » dans les données). **[F]** 19 villes le partagent le 4 nov, 17 le 10 nov.
Le 10 nov, Dubaï reçoit son propre enregistrement `@58c1f104`, **identique octet pour octet** au défaut (hors nom) :
emplacement créé, pas encore réglé. **[H]** Les villes Blur 2 de novembre n'ont pas encore d'ambiance finale ;
l'ambiance Dubaï la plus « auteur » est celle d'**août**.

Variantes communes : `HFD_HemiSunset27` est le ciel le plus cité (68 villes-builds sur 130) ; 17 ciels
`graphics/textures/skies` cités sont communs à Blur 1 et Blur 2 (même nom dans les deux `root.pak`). Liste complète :
`data/textures_citees.json`.

### 3.3 Unity (Blur2DubaiTest) [F]
Le ciel affiché par la reconstruction est le **skybox procédural par défaut d'Unity** (`Default-Skybox`, exposition
1,3, soleil simple) et son cube 128² : ce n'est pas un ciel de Blur 2. `sky_rotation_offsets.csv` donne un décalage
de rotation par niveau (Dubaï −30°, `_test_lighting` −176°, autres 30°) : réglage de la reconstruction pour aligner
un ciel, pas une donnée X360 [H].

## 4. Paramètres atmosphériques

Tous les champs sont dans `environnements.json` (`builds.<build>.villes.<ville>.EnvironmentSettings`, chaque
référence résolue avec son hash `@xxxxxxxx`). Résumé :

| Paramètre | Champ | Remarques |
|---|---|---|
| Couleur et force du soleil | `LightingInfo.SunColour` (RGB + a) | a = 0 presque partout (Blur 1 et Blur 2) ; Ski Resort 10 nov a une couleur forte mais a = 0 |
| Direction du soleil | **absente** de `LightingSettings` [F] | seules sources : `RoadTrackSettings.FakeSunLightPosition`, `CarLightSettings.FakeSunBlobShadowPosition` (Dubaï : (2 868 ; 3 497 ; 1 412)), `CutSceneLightDef.Heading/Elevation` ; et cuite dans les lightmaps |
| Ciel / ambiant | `SkyColour` | 0 dans le défaut Blur 2 ; 1 dans les villes Blur 1 |
| Baked / émissif | `BakedColour`, `EmissiveColour` | multiplicateurs ; Unity : `_BakedColour` sur les lightmaps |
| Brouillard | `FogColour`, `DepthFog` (densité, distance de départ, échelle), `HeightFog` (hauteur, densité, atténuation, échelle), `LayerFogSettings` (couleur, hauteur, atténuation, densité) | `LayerFog` nouveau en novembre |
| Brouillard du ciel | `SkySettings.fogColour`, `fogCurve` | défaut : `fogCurve` 1 000 000 |
| Exposition | `PostProcess.exposureMin/Max`, `middleGrey` | échelle différente de Blur 1 (voir relations §2.4) |
| Bloom | `bloomScale`, `bloomScale0..3`, `bloomThreshold`, `PostFxSettings.bloomThresholdCurve`, `bloomFeedback` | |
| Post-traitement | `PostFxSettings` : LUT 3D 32³ (`lookupTexture`), matrices de couleur (teinte, contraste, luminosité, saturation, multiplication, addition), grain, vignette, `tunnelAmount`, flares d'objectif, `blurType` | graphe de matrices non décodé |
| Distances | `City.mainFarClip`, `environmentFarClip` | 0 partout sauf Ski Resort (8 000) |
| Résolutions | `City.reflectionResolution` (Low_256x128 / Medium_512x256 / High_1024x512), `environmentResolution` (High_256) | [H] texture de reflet de route et cube dynamique |
| Vent | `WindSettings` | |

Contraste et luminosité : uniquement via les matrices `PostFxMatrixContrast` / `Brightness` du graphe PostFx (non
décodé ici) et la LUT.

## 5. Cubemaps et réflexions

| Cubemap | Où | Origine | Utilisateurs |
|---|---|---|---|
| `Dubai_EnvDefault.dds` | `CubePt3` de `levels/dubai/level.levelrender` (10 nov) ; position (−899,4 ; 14,8 ; −189,7) | prise de vue du décor de Dubaï (Unity `tex_lr6_dubai_envdefault`, 256², DXT1, 6 faces + 9 mips) | ~1 040 matériaux à `_EnvironmentCube` (G14 : dalles, murs, vitres) |
| `default.dds`, `amboy_001.dds` | `CubePt3` de la plupart des autres niveaux Blur 2 (voir §7) | génériques | [?] |
| `Dubai_Sunny_001.dds`, `Brighton_Storm_001.dds`, `Brighton_Sunny_001.dds` | `CubePt2` des niveaux du 31 août (§7) | un cube par circuit, comme Blur 1 | texture non trouvée sous ce nom [?] |
| `<Ville>_001.dds` (Blur 1 : `LA_River_001`, `Brighton_001`…) | `CubePt2`, un par niveau PC | un cube par circuit | tout matériau à `g_tEnvironment` |
| `LA_River_CubeMap`, `Hackney_CubeMap`, `LA_Downtown_001` | `LightingSettings.cubemapTexture` (24 réglages, dont Hong Kong / Liverpool d'août) | `dontship` | réglages de test |
| `Environment.dds` | `dontship/textures` (Blur 1 PC et les 3 archives) | DDS cube 256², DXT1 | outil / test [H] |
| `Default-Skybox-Cubemap` | Unity | Unity | reconstruction seulement |

Distinction avec le ciel [F] : les ciels sont des bandes 2048 × 512 dans `graphics/textures/skies`, référencées par
`SkySettings` ; les cubemaps sont des cubes 256² référencés par `CubePt2/3` (niveau) ou `cubemapTexture`. Aucune
version pré-filtrée séparée n'a été trouvée : le flou vient des mips (`lod 7·(1-G)` dans le shader Unity) [F Unity,
H X360].

Format `CubePt3` [F partiel] : u32 (1), 3 × f32 position [H], u32 longueur + nom (`Dubai_EnvDefault`), u32 −1, u32 1,
u32 0x80000000, …, dossier et chemin source du `.dds`. `CubePt2` (Blur 1) : pas de position ni de nom, dossier +
chemin. Le 4 nov, le `CubePt3` de Dubaï pointe encore `amboy_001.dds` en (0, 0, 0) : le cube de Dubaï est arrivé
entre le 4 et le 10.

## 6. Échantillons de lumière et lightmaps
- `LSData` : 24 o / échantillon dans Blur 1 (3 × 4 SH en f16) [F] ; **16 o** dans les niveaux Blur 2 refaits [F] ;
  lecture [H] dans `relations_eclairage.md` §2.5.
- Lightmaps doubles (`lightmap_*-a/-b`, `g_tLightmap0/1`) : Dubaï 10 nov ; absentes le 4 nov (CONNAISSANCES).
- Lumières dynamiques : bloc `Lights` du `levelrender` ; Unity `dubai_lights` (44 points : façades, lampadaires,
  portée 22 à 71 m).

## 7. Niveaux (levelrender)

116 `levelrender` lus sans erreur (23 Blur 1 PC, Dubaï 4 nov, 41 au 10 nov, 51 au 31 août) ; détail par niveau dans
`environnements.json` → `niveaux` et `data/levelrender_env.json`. « — » = pas de bloc `LSData` (niveau non cuit ou
fichier vide).

**Changement de format entre août et novembre [F]** :

| Build | Bloc cube | `LSData` | Lecture |
|---|---|---|---|
| Blur 1 PC | `CubePt2` (23/23) | 24 o (23/23) | format de référence |
| Blur 2, 31 août | **`CubePt2`** (50/51) | **24 o** (tous les niveaux cuits) | **même format que Blur 1** |
| Blur 2, 4 nov (Dubaï) | `CubePt3` | 16 o | nouveau format |
| Blur 2, 10 nov | `CubePt3` (40/41) | 16 o (maps refaites) ou 24 o (maps reprises) | nouveau format, cuisson partiellement refaite |

Le passage `CubePt2` → `CubePt3` et 24 → 16 o a donc eu lieu entre le 31 août et le 4 nov.

**31 août, niveaux Blur 2 propres** :

| Niveau | `LSData` (n × o) | Cubemap (`CubePt2`) |
|---|---|---|
| `dubai` | **73 357 × 24** | **`Racer2010\…\Cubemaps\Dubai_Sunny_001.dds`** |
| `uk_brighton_storm` | 7 887 × 24 | `Brighton_Storm_001.dds` |
| `uk_brighton_sunny` | 32 022 × 24 | `Brighton_Sunny_001.dds` |
| `mparena_carpark / skiresort / skyscrapers / superbowlhard / temple` | 3 013 à 5 778 × 24 | `Racer2010\…\Default.dds` |
| `kanzen_la_river` | 47 335 × 24 | `default.dds` |
| `kanzen_la_downtown` | 20 998 × 24 | (aucun cube) |
| `hong_kong`, `la_city`, `detroit`, `liverpool`, `miami`, `north_africa`, `odessa`, `ski_resort`, `ai_circuit_*`, tests | — | `Kanzen\…\default.dds` |

Les 21 niveaux repris de Blur 1 (Amboy, Brighton, Hackney, LA, Barcelone, Tokyo, Haruna, Dumbo, San Francisco,
Showroom…) gardent leur cube Blur 1 (`<Ville>_001.dds`) et des `LSData` à 24 o.

**10 nov** :

| Niveau | `LSData` (n × o) | Cubemap (`CubePt3`, nom, position) |
|---|---|---|
| `dubai` | 24 917 × 16 | `Dubai_EnvDefault` en (−899,4 ; 14,8 ; −189,7) ; 2 pages de lightmap ; `g_tEnvironment`, `g_tLightmap0/1` |
| `hong_kong` | 167 193 × 16 | `default.dds`, (0, 0, 0) |
| `miami` | 190 660 × 16 | `amboy_001.dds` |
| `odessa` | 150 489 × 16 | `default.dds` |
| `north_africa` | 114 443 × 16 | `amboy_001.dds` |
| `la_city` | 107 732 × 16 | `default.dds` |
| `ski_resort` | 45 540 × 16 | `amboy_001.dds` |
| `detroit` | 37 086 × 16 | `default.dds` |
| `liverpool` | 20 176 × 16 | `default.dds` |
| `mp_barcelona / bowlarena / detriot / skiresort / skyscrapers / temple` | 30 661 à 59 299 × 16 | `amboy_001.dds` |
| `_test_*` (9) | 0 à 61 007 × 16 | `amboy_001` ou `default` ; `_test_shadertech` : `locator1` en (−3 ; −1,2 ; 19) |
| `la_freeway` | 65 044 × 24 | `default.dds` |
| maps reprises (`usa_amboy`, `spa_barcelona_*`, `usa_la_longbeachdocks`, `graphical`, `showroom`, `fx_testlevel`, `vehicletestscene`…) | 13 198 à 176 321 × 24 | `<Ville>_001.dds` (même cube que Blur 1) |
| `barcelona_gracia`, `usa_la_observatory`, `quickexport`, `_test_traffic` | — | cube cité, pas de `LSData` |
| `traffictestlevel2` | — | `CubePt2` (fichier ancien) |

Observations [F] :
- Au 10 nov, **Dubaï est le seul niveau Blur 2 avec un cube propre**, nommé et positionné. Partout ailleurs, le
  `CubePt3` porte le nom générique `kanzen`, la position (0, 0, 0) et un cube générique : la cuisson des reflets
  n'était pas faite.
- Au 31 août, Dubaï avait un **autre** cube (`Dubai_Sunny_001`) et des échantillons au **format Blur 1**. Ce n'est
  pas la même cuisson : 73 357 points contre 24 917, et l'ambiance d'août est différente (§4).
- `Dubai_Sunny_001.dds`, `Brighton_Storm_001.dds` et `Brighton_Sunny_001.dds` ne figurent sous ce nom ni dans les
  listings des archives ni dans les paks lus. Leur texture se trouve peut-être dans un pak de niveau, sous un nom
  converti **[?]**.
- **[?]** La géométrie du Dubaï d'août correspond-elle à celle du 10 nov et de la map Marina ? Les points `LSData`
  sont en coordonnées monde : sans correspondance, ils ne s'appliquent pas tels quels.

## 8. Limites et données manquantes
- Graphe `PostFxMatrix` (contraste, saturation, teintes) non décodé : pointeurs internes non suivis.
- Format interne des textures X360 (tuilage Xenon) non décodé : dimensions des ciels Blur 2 déduites de la taille.
- `CubePt3` et `LSData` 16 o : lecture partielle, à confirmer dans le `.xex` Blur 2.
- Build du 4 nov : seuls les tables et Dubaï ont été lus (pas les autres `levelrender`, quasi identiques au 10 nov
  d'après les tailles).
- Paks d'août (`root.pak`, `lut_rampak.pak`) non lus : la présence des textures d'août est déduite du listing de
  l'archive (fichiers libres) seulement.
- Aucun rendu ni essai en jeu : toutes les conséquences visuelles restent à vérifier.
- `FlashbackSettings` (ambiance du ralenti « flashback ») inventoriés dans le JSON mais non analysés.
