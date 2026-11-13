# Audit A : compatibilité des ressources d'environnement Blur 2 avec Blur 1

Lecture seule, 2026-11-13. Aucun shader ni aucune ressource modifiés. Confiance : **[F]** fait, **[H]** hypothèse,
**[?]** à déterminer (moteur ou essai en jeu). Détails par map : `environnements.json` ; relations :
`relations_eclairage.md`.

## Synthèse

| Catégorie | Direct | Conversion | Shader / moteur | Limites |
|---|---|---|---|---|
| Réglages `LightingSettings` (soleil, ciel, baked, émissif, brouillard, ciel, exposition, bloom) | **oui, champ à champ** [F] : même structure de 188 o | inversion d'octets (X360 → PC), puis écriture dans l'enregistrement `amax.bin` d'une ville (méthode Map Builder `lighting.prepare`) | non | échelle d'exposition différente (Blur 2 : gris moyen 0,18, `bloomScale` 10) : à recalibrer à l'œil [H] ; copie d'enregistrement = ciel blanc (piège connu Map Builder), écrire **en place** |
| Ciels communs aux deux jeux (`HFD_HemiSunset18/27`, `HFD_HemiTwilight06`, `hf03/10/12`, `s10`, `t02c/d`, `v06c`, `v09/b`, `f01c`, `Night_Cloudy_*`, `night_cloudy_moon_06`, `hdr_sunset12_ldr`) | **oui** [F] : même nom dans `root.pak` PC (1 048 660 o) | aucune : il suffit de citer le chemin dans `SkySettings.texture` | non | contenu identique non vérifié pixel à pixel [H] |
| Ciels propres à Blur 2 (`deep_blue_sky`, `pink_sunset`, `HFD_HemiClouds17` ; août : `HFD_HemiClouds08/12/16`, `hdr_cloudy07_ldr`, `hdr_stormy01_ldr`) | non | conteneur `Texture` X360 → PC : en-tête différent (124 o contre 84), données Xenon (gros-boutiste, tuilées) → DXT5 PC 2048 × 512 (1 Mo) [H : dimensions déduites de la taille, même classe que les ciels Blur 1] ; `HFD_HemiClouds17` = 4 Mo (4096 × 1024 ou 2048 × 2048 [?]) | non pour 2048 × 512 ; **[?]** si Blur 1 accepte un ciel de 4 Mo | détuilage Xenon à écrire (pas d'outil actuel) ; textures `dontship` (`Istanbul_TEST_2`, `hdr_cloudy09`…) = provisoires |
| LUT d'étalonnage (`*_LUT.dds`, 131 200 o = 32³ RGBA) | **oui** pour les 30+ LUT communes [F] (mêmes noms, mêmes tailles dans `root.pak` / `lut_rampak.pak` PC) | `Dubai_Sunny_LUT_01`, `Brighton_Storm/Sunny_LUT_0x` (août, en clair dans l'archive) : DDS ordinaire → probablement direct [H] | non | la LUT par défaut des villes Blur 2 de novembre est `LA_Downtown_02` (réglage générique), pas une LUT propre |
| Cubemaps de reflet (`CubePt3` → `Dubai_EnvDefault`, `default`, `amboy_001`) | non | bloc `CubePt3` (nom + position) → `CubePt2` (sans nom ni position) [F format différent] ; texture cube X360 → DDS cube PC (256², DXT1 dans Unity) | **modification du niveau** : écrire le `CubePt2` du `levelrender` de la carte (`flat_earth`) — format de `CubePt2` partiellement compris, pas d'essai | un seul cube par niveau dans Blur 1 [F : un `CubePt2` par niveau mesuré sur 23 niveaux PC] ; la plupart des maps Blur 2 citent un cube générique (`default.dds`, `amboy_001.dds`) : peu de valeur, sauf Dubaï 10 nov |
| `LSData` / `LSTree` (ambiant des objets) | **oui pour tout le build du 31 août** (Dubaï 73 357 points, Brighton Storm/Sunny, arènes MP) et les maps à 24 o du 10 nov (graphical, fx_testlevel, la_freeway…) [F : même taille d'enregistrement ; ordre des octets à inverser] | maps refaites (16 o) : format différent, conversion en 3 × 4 SH demandée [H sur le sens des 8 valeurs] ; positions `LSTree` en f16 | non si on réécrit au format Blur 1 | le rayon fixe de 10 m de Blur 1 impose des points près de chaque objet (G8-G11) ; Map Builder écrit déjà ces blocs (`lighting.write_level_light`) |
| Lightmaps du décor (`lightmap_*-a/-b`) | non | cuisson dans les textures (`b2bake`) ou en couleurs de sommet (`b2vcolor_poc`) : **validé hors jeu et en jeu** (G3-G5, POC) | non avec la voie couleurs de sommet | lightmap B non décodée ; précision limitée par la densité de sommets |
| `LayerFogSettings` (brouillard en couche, Ski Resort) | **non** [F] : type absent de Blur 1 | approximation par `HeightFog` (hauteur, densité, atténuation) [H] | oui pour un rendu fidèle | brouillard en couche de 900 m perdu tel quel |
| `PostFxSettings` (matrices couleur, grain, vignette, flares d'objectif) | **oui** [F] : même type ; Blur 1 le lit déjà | inversion d'octets ; graphe `PostFxMatrix` = pointeurs internes à recréer | non | le graphe n'est pas décodé ici (pointeurs non suivis, `env_records.py`) |
| `CarLightSettings`, `RoadTrackSettings`, `ShadowSettings`, `WindSettings`, `LightFlareSettings` | **oui** [F] : mêmes types | inversion d'octets | non | les villes Blur 2 de novembre n'ont pas de `RoadTrackSettings` (référence nulle) |
| `CutSceneLightDef` (`lighting.bin`, 251) | [?] : table absente de Blur 1 PC sous ce nom | — | — | sert aux cinématiques / vitrine, pas aux niveaux [H] |
| Lumières ponctuelles de Dubaï (`dubai_lights`, 44, Unity) | non (format Unity) | → `Lights` du `levelrender` ou acteurs lumière [?] | [?] | positions déjà en coordonnées monde Unity |

## Priorité pratique
1. **Réglages + ciel + LUT d'une ville** : zéro shader, zéro conversion de texture si le ciel est commun. Pour Dubaï,
   deux ambiances sont disponibles :
   - **août** : ciel `HFD_HemiClouds16` (à convertir), rotation 0,273, intensité 0,5, exposition 3,0 / 10,0,
     LUT `Dubai_Sunny_LUT_01` (en clair dans l'archive d'août) — la seule ambiance faite pour Dubaï ;
   - **10 nov** : ciel `HFD_HemiSunset27` (présent dans Blur 1), rotation 0,85, intensité 1,0, LUT `LA_Downtown_02` —
     réglage générique partagé avec 8 autres villes.
2. **Échantillons de lumière** : le Dubaï du **31 août** a des `LSData` déjà au format Blur 1 (24 o) et un bloc
   `CubePt2` (`Dubai_Sunny_001`). Il suffit d'inverser l'ordre des octets, sans décoder le format 16 o. Condition
   **[?]** : la géométrie d'août doit correspondre à la map Marina. À défaut, il faut décoder les 16 o du 10 nov.
3. **Cubemap de Dubaï** dans `CubePt2` : améliore les vitres (reflet confirmé en G13-C). Deux sources :
   - le `CubePt2` d'août, déjà au bon format, mais sa texture `Dubai_Sunny_001` n'a pas été localisée ;
   - `Dubai_EnvDefault` du 10 nov, à convertir depuis `CubePt3`.

   Dans les deux cas, il faut convertir le cube et faire un essai.

## Ce qui demande le moteur
- Brouillard en couche (`LayerFogSettings`) fidèle.
- Plusieurs cubemaps localisés par niveau, si Blur 2 en a plusieurs (une seule entrée `CubePt3` vue à Dubaï).
- Lightmaps doubles en temps réel (shader `blend3_lm`, `g_tLightmap0/1`) ; la voie couleurs de sommet les contourne.
- Échelle d'exposition Blur 2 (si l'opérateur de tonalité diffère [?]).
