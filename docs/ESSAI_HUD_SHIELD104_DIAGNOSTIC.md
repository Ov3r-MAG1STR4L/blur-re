# Essai HUD Shield 104 : hexagone en caméra extérieure, diagnostic

2026-11-17, lecture seule : aucun fichier du jeu, aucune copie, aucune DLL modifiés. Suite de
`ESSAI_HUD_SHIELD104.md`. Outils : capstone sur `Blur.exe` (adresses VA, base 0x400000), `blurxt.py`, `blurtex.py`,
`blurmesh.py`.

## 1. Résultats en jeu (rapportés par l'utilisateur, copie `Blur_test_hud`)

| Élément | Vu |
|---|---|
| Carrousel en caméra extérieure | hexagone (case 7) |
| Carrousel en caméra pare-chocs | étoile (case 104) |
| Icône au-dessus d'une IA qui porte un Bouclier | étoile (case 104) |
| Bouclier activé | normal, bulle de 6 s |

Pas encore de capture d'écran du cas « caméra extérieure ».

## 2. Chemin de la caméra extérieure (**Confirmé**, exe)

1. Gadget `Perks_MainAttached` (élément 22 de l'écran `hud_objects` de `ui.bin`), classe **`UIPerks2`**, champ
   `attached_to_car` = vrai (+0x180 dans l'objet), parent `Perks_Dummy` (`UIDummy`). La classe a été relue dans le
   fichier modifié (type de bloc KSLF).
2. Rendu : vtable `0xEEAFF0`, entrée 10 → **`UIPerks2::Render` `0xC58130`**.
3. Choix de caméra (`0xC581FA`-`0xC58252`) :
   - `call 0x434E00` lit le type de caméra (`[caméra+0x4C]` ; `E_VFCamera_Hollywood` = 0, `E_VFCamera_Bumper` = 1)
     et met `bl` = (pare-chocs) ;
   - avec un seul écran (`[eax+0x84] == 1`) : pare-chocs et `attached` → sortie ; extérieur et pas `attached` →
     sortie.

   Donc **en caméra extérieure, seul `Perks_MainAttached` dessine**.
4. Partie propre au gadget attaché (`0xC58258`-`0xC590C8`) : matrice de la voiture, lumière ponctuelle, état de rendu.
   **Aucun accès à un bonus ni à un index** dans cette partie.
5. Icône : `0xC59293` `call 0xC554C0` (`UIPerks2::GetPerkInfo`), qui fait `jmp 0xC55320` avec
   `ecx = [0x124291C] + 0x70`. Ensuite `0xC592B6` `mov eax,[edi]` (`texture_index`), `cmp eax, 0x64`, puis
   `GetTextureParam(6/7)`, puis le calcul de V (`0xC59896`).

## 3. Chemin de la caméra pare-chocs (**Confirmé**, exe)

Gadget `Perks_MainHUD` (élément 61), classe **`UIPerks2`**, `attached_to_car` = faux. **Même vtable, même
`Render` `0xC58130`**. Il saute la partie attachée (`0xC5824B` → `0xC590C8`) puis suit **exactement les mêmes
instructions** à partir de `0xC59293`.

L'icône au-dessus des IA passe par `UIPerks::Render` `0xC57E90` → `call 0xC55320` (`0xC57F9B`), avec la même
structure globale.

## 4. Différences entre les deux chemins

| Point | Extérieur (`Perks_MainAttached`) | Pare-chocs (`Perks_MainHUD`) |
|---|---|---|
| Classe / fonction | `UIPerks2` / `0xC58130` | identique |
| Type et nombre de tirs | `mPickupStore[i]` du véhicule local (`0xC59293`) | identique |
| Source de `texture_index` | `[[0x124291C] + 0x70 + entrée]`, lue **à chaque image**, sans copie | identique |
| Seuil / planche | `0xC592B8` → textures 6 / 7 | identique |
| Textures du gadget (`ui.bin`) | 0 `perk_sheet` … 6 `perk_sheet_support` (0,0) (1 ; 0,1875), 7 `…_inverted` | **identiques** (relu) |
| Ce qui diffère | placement 3D derrière la voiture, lumière, panneau | placement dans le calque 3D du HUD |

**Une seule configuration** :

- `[0x124291C]` n'est écrit que par le rappel XT `0xC2E920` : `0xC2E938` à l'événement 0 (chargement), `0xC2E92E` à
  l'événement 1 (mise à 0) ;
- `gamedata\Xt\UI.bin` (chaîne `0xEEB4D4`) n'est chargé qu'à un endroit, `0xC3BD15`, dans le constructeur de la
  couche d'interface `0xC3B160` (vtable `0xEEB284`) ;
- ce constructeur a **un seul appelant** (`0xC31272`).

Aucune copie de `PerkDisplayParameters` n'a été trouvée dans les gadgets. Comme la caméra pare-chocs et les IA
montrent 104, la configuration chargée vaut 104.

Conclusion du désassemblage : **au même instant, les deux carrousels ne peuvent pas lire deux index différents**.
Hypothèses 1 à 7 de la demande : aucune n'est visible dans le code. Il n'y a ni autre structure, ni autre instance de
configuration, ni cache, ni autre fonction, ni transformation de l'index, ni autre texture pour le gadget attaché.

## 5. Cause (**Confirmée en jeu** par les captures du 2026-11-17, voir `ESSAI_HUD_SHIELD104.md` §8)

**L'hexagone vu en caméra extérieure n'est pas le carrousel : ce sont les Boucliers posés sur la piste.**

- Le Bouclier sur la piste est le modèle `models\Perks\Pickups\ShieldPickup.model` (`pickups.bin`, `PickupType`
  #399, `PickupSpecialFX`, `FarDistance` 350). Ce modèle porte ses **propres textures**, dans `root.pak`, et ne lit
  pas `ui.bin` :
  - `icon_shield_01` (DXT1 256², 9 mips) : case arrondie lumineuse et hexagone ;
  - `icon_shield_01_inverse` (DXT1 256²).

  Elles ont été extraites par `blurtex.py`. Leur dessin est presque celui de la case 7 du HUD.
- Pendant l'essai, **seul le Bouclier était coché** : tous les bonus visibles sur la piste étaient des hexagones.
- En caméra extérieure, la vue est haute et en arrière : les bonus de la piste et le carrousel attaché (petit, incliné,
  juste derrière la voiture) se retrouvent dans la même zone de l'écran.
- Autre candidat écarté : l'effet de ramassage `shieldengulf1.model` (2 s, voiture du joueur, vu seulement de
  l'extérieur). Son maillage (639 sommets, relu par `blurmesh`) est une **bulle ellipsoïdale avec une traînée**, ses
  textures sont `light_lines_08` et `mine_pulse_03` : pas d'hexagone.

**Autre explication moins probable** : le carrousel attaché n'était pas affiché, ou pas lisible, au moment de
l'observation. Sans capture, on ne peut pas trancher.

Constat annexe : `gamedata_boot.pak` est resté actif dans la copie et contient le `ui.bin` d'**origine** (entrée
`p6`, 1 004 480 o). Puisque l'étoile s'affiche, c'est bien le fichier en clair qui a été chargé. **Confirmé** par
l'effet, mais la priorité exacte entre ce pak et le dossier reste à mesurer (Process Monitor).

## 6. Incertitudes

- Pas de capture du cas extérieur : l'hypothèse du §5 n'est pas prouvée.
- Le cas « deux caméras changées pendant le même tour, avec le même Bouclier en réserve » n'est pas documenté.
- Rendu du panneau 3D du gadget attaché (`E_GameSpritePanel_VP0`) non désassemblé : seule la sélection de l'icône l'a
  été.

## 7. Correction minimale (non appliquée)

- **Aucune correction du HUD** si le §5 se confirme : le carrousel extérieur affiche déjà l'étoile.
- Si le but est que **tout** ce qui représente le Bouclier change : remplacer aussi les deux textures intégrées à
  `shieldpickup.model` (`blurtex.py inject`), ou pointer `PickupType.PickupSpecialFX` du Bouclier vers l'effet du
  SuperShield (`ShieldSuperPickup.model`, l'étoile). Ce sont des données, sans rustine.
- Si le §5 est infirmé (capture du carrousel attaché avec un hexagone) : faire un relevé mémoire en lecture seule
  (`blur_live.py`) de `[[0x124291C]+0x70+0x288]` pendant la course, et poser un point d'arrêt matériel sur ce mot
  avec un débogueur, pour trouver qui le lit.

## 8. Protocole de vérification (copie `Blur_test_hud`, sans rien modifier)

1. Course perso avec **Shield et Nitro** cochés : les bonus sur la piste mélangent alors hexagones et doubles
   chevrons verts.
2. Ramasser un Bouclier, **s'arrêter** sur une portion sans bonus en vue, rester en caméra extérieure : capture du
   carrousel derrière la voiture (3 cases inclinées, juste derrière le pare-chocs arrière).
3. Sans rien ramasser d'autre, passer en caméra pare-chocs : capture, puis revenir en caméra extérieure : capture.
4. Capture d'un Bouclier posé sur la piste, de près.
5. Attendu si le §5 est juste :
   - carrousel extérieur = **étoile** sur les deux captures ;
   - Bouclier sur la piste = **hexagone** ;
   - l'essai est alors entièrement réussi pour le HUD.
6. Les captures vont dans `blur_extracted\mods\hud_shield104\captures\`. Noter le résultat dans
   `ESSAI_HUD_SHIELD104.md` §8.

## 9. Résultat (2026-11-17)

Captures faites (`hud_shield104\captures-03`) :

- en caméra extérieure, le carrousel derrière la voiture montre **l'étoile** ;
- le Bouclier posé sur la piste montre **l'hexagone**.

Le §5 est **confirmé**, et il n'y a rien à corriger dans le HUD.

