# Sécurité et protection des travaux : studios web locaux

Concerne NFS Studio (`nfs_web.py`, port 8765), Reverse Studio (`reverse_web.py`, 8766) et Tracés Blur 2
(`b2track.py`, 8767). Les trois restent des outils indépendants ; les protections communes sont dans
`studio_safe.py`. Priorité 1 de la feuille de route (audit du 2026-11-10), mise en place le 2026-11-10.

## 1. Requêtes venues d'autres sites (CSRF) et DNS rebinding

Avant : n'importe quel site ouvert dans le navigateur pouvait envoyer un POST « simple » à 127.0.0.1 et écraser un
circuit, lancer une construction ou une installation, supprimer des retouches (Reverse).

Maintenant (`studio_safe.refus`, appelé en tête de chaque requête des 3 serveurs) :
- toute requête : en-tête `Host` = `127.0.0.1:PORT` ou `localhost:PORT`, sinon 403 (un site qui ferait pointer son
  propre nom vers 127.0.0.1 envoie son nom dans `Host`) ;
- toute requête qui écrit ou lance quelque chose (tous les POST, et `GET /api/load` de NFS Studio) : `Origin`, s'il
  est présent, doit être la page du studio (`http://127.0.0.1:PORT` ou `http://localhost:PORT`) ; `Sec-Fetch-Site`,
  s'il est présent, doit valoir `same-origin` ou `none`. Sinon 403. Un autre studio (autre port) est aussi refusé.

Les pages des studios envoient elles-mêmes `Origin` = leur adresse : rien à changer côté page.

## 2. Noms et chemins de fichiers

Listes blanches (aucun nom reçu n'entre dans un chemin sans être reconnu) :
- Reverse Studio : `name` doit être une route de `make_reverse.ROUTES` (`route_name`), pour `/api/route`,
  `/api/cams`, `/thumb`, `/api/edits`, `/api/lock`, `/api/unlock`. Sinon 404. Avant : `name = "../../x"` écrivait
  ou supprimait un `.json` hors de `blur_extracted\edits` / `locks`.
- NFS Studio : `/api/load?stm=` doit être un des `.stm` de `ENV_DIR` (la liste de `/api/locations`). Avant :
  n'importe quel fichier du disque était lu et un cache écrit pour lui. `/cache/...` : `studio_safe.dans_dossier`
  (chemin réel, liens résolus, `commonpath`) ; avant, un dossier voisin `web_cache_xxx` passait le test `startswith`.
- Tracés Blur 2 : `map=` doit être une clé de `MAPS`, sinon 404 (avant : erreur et connexion coupée).

## 3. Écriture des fichiers de projet

`studio_safe.ecrire_json` : fichier complet écrit à côté (`.studio_*.tmp`, `fsync`), l'ancien copié en `.bak`, puis
renommage (un plantage ne laisse jamais un fichier tronqué ; un échec ne laisse ni `.tmp` ni `.bak` neuf).
Utilisé pour : `world*.json` (NFS Studio, avant écrasé sans copie), retouches et caméras de Reverse Studio
(`edits\<route>.json`, `.cams.json`), tracés de Tracés Blur 2.
Plus de suppression : vider les retouches / caméras ou déverrouiller une route renomme le fichier en `.bak`.
Contenus vérifiés avant écriture : structure de `world.json` (`locations[].maps[]`), tracé (points `{x, z, w, h}`,
embranchements, surfaces), retouches / caméras du bon type. Corps limité à 64 Mo (413 au-delà), JSON invalide = 400.

## 4. Installation dans Blur_test

`studio_safe.installer` (NFS Studio et Tracés Blur 2) :
1. refus si la destination n'a pas `COPIE_DE_TEST_HORS_LIGNE.txt` (seule la copie de test est acceptée : jamais le
   jeu installé), si la sortie est vide ou contient un fichier vide ;
2. chaque fichier copié à côté de sa destination (`.studio_tmp`) et comparé octet par octet ; un seul écart annule
   tout : Blur_test reste inchangé (avant, NFS Studio s'arrêtait au milieu, Blur_test à moitié copié) ;
3. originaux remplacés gardés une seule fois (la 1re version gardée reste l'originale) ; les fichiers qui
   n'existaient pas avant la 1re installation sont notés dans `_absents.json` de la sauvegarde (jamais pris pour des
   originaux ensuite) ; puis les copies renommées à leur place.

Sauvegardes : NFS Studio → `blur_extracted\mods\nfs_dubai\backup_studio` (nouveau ; avant : aucune sauvegarde).
L'ancien `nfs_dubai\backup_blur_test` (installation manuelle) n'est pas touché. Tracés Blur 2 → toujours
`b2_dubai_marina\backup_blur_test` ; son `_absents.json` a été déduit une fois (7 morceaux de route `road_21_31…37`
ajoutés par nos installations : présents dans Blur_test, absents de la sauvegarde que l'ancien code remplissait
avant toute copie). Tracés Blur 2 **signale** (sans rien remettre ni supprimer) les fichiers d'une installation
précédente absents de la nouvelle map (voir « Étape 0 » plus bas).

Nettoyage contrôlé de la sortie (`studio_safe.ecarter_perimes`) : à la fin d'une construction réussie, les fichiers
de la sortie que cette construction n'a pas réécrits (restes d'une construction précédente) sont **déplacés** dans
`perimes\<date>\` à côté (NFS : `nfs_dubai\perimes`, Tracés : `<sortie>\perimes`), donc ni installés ni supprimés.

## 5. Délais, verrous, erreurs

- Map Builder (`build.py`) : 30 min au plus (`nfs_atlas.rebuild`, `make_b2_map`) ; Tracés Blur 2 arrête aussi toute
  la construction (`taskkill /T`) après 60 min.
- NFS Studio : verrou pris par la requête elle-même (`acquire` non bloquant) et rendu par le thread : deux
  constructions ne peuvent plus partir ensemble. Changer de lieu, de réglages ou enregistrer le circuit pendant une
  construction / installation = 409 (avant : entrées de la construction changées en cours de route).
- Erreurs : réponse JSON lisible dans la page (400 données, 403 refus, 404 inconnu, 409 occupé, 413 trop gros,
  500 erreur serveur) au lieu d'une connexion coupée. La page NFS dit « NON enregistré » si l'enregistrement échoue
  (avant : « enregistré » même en cas d'échec).
- Reverse Studio refuse un 2e lancement sur le même port (comme les deux autres).

## Tests

`python -m unittest tests.test_studio_safe tests.test_studios_http` (depuis `blur_tools`, ~15 s) :
- `test_studio_safe` (16) : origine / hôte / Sec-Fetch-Site, corps JSON, écriture atomique et `.bak`, échec en cours
  d'écriture, chemins hors dossier, fichiers périmés, installation (normale, sans fichier témoin, sortie vide ou
  fichier vide, copie fautive annulée, réinstallation, `_absents`), installation Tracés Blur 2 (originaux remis,
  ajouts signalés) ;
- `test_studios_http` (21) : les 3 vrais serveurs sur les ports 18765-18767 (`BLURRE_PORT`, `BLURRE_NO_BROWSER`).
  NFS Studio sur des dossiers temporaires (`BLURRE_STM_WORK`, `BLURRE_NFS_OUT`, `BLURRE_BLUR_TEST`) : enregistrement,
  `.bak`, installation complète et refus sans fichier témoin. Reverse et Tracés sur les vrais dossiers, requêtes
  refusées seulement, avec empreinte avant / après de `edits`, `locks` et `marina_trace.json`.
Vérifié à la main (2026-11-10) : les 3 pages dans le navigateur (lieux, chargement, réglages ; routes, vignette,
caméras ; tracé, surfaces, enregistrement sur une copie).

## Limites restantes

- Un programme lancé sur la machine (pas un site web) peut toujours appeler les studios : ce n'est pas l'objet de
  ces protections. Un vieux navigateur qui n'envoie ni `Origin` sur un POST ni `Sec-Fetch-Site` n'est pas couvert.
- Les GET de lecture restent ouverts (page ouverte depuis un lien) ; leurs réponses ne sont pas lisibles par un
  autre site (pas d'en-tête CORS).
- three.js vient toujours du CDN unpkg, sans contrôle d'intégrité.
- Pas encore d'historique de versions ni de sauvegarde automatique (un seul `.bak` par fichier).
- Les sauvegardes de Blur_test sont propres à chaque outil ; NFS Studio et Tracés Blur 2 installent tous deux dans
  `flat_earth` : la sauvegarde de chacun garde l'état d'avant SA première installation.
- NFS Studio : `builtins.print` toujours détourné pendant la construction (journal) ; `maplock.lock` écrit le
  verrou sans écriture atomique ; caches `web_cache\<lieu>\index.json` écrits directement (données recalculables).
- Fichiers ajoutés par une ancienne installation et absents de la map courante : signalés, jamais supprimés
  automatiquement (à décider à la main).

## Incident du 2026-11-10 (pendant la mise en place) et réparation

Des serveurs lancés à la main pour vérifier les pages (ports 18765-18767, vraie configuration) tournaient encore
quand les tests ont été relancés : le nouveau serveur NFS du test n'a pas pu prendre le port et le test a parlé à
l'ancien. Conséquences : `nfs_dubai\files` installé dans le vrai Blur_test (194 fichiers, par-dessus Marina) et nom
du lieu de `stm_work\world.json` changé en « essai ». Réparé : Blur_test remis depuis `nfs_dubai\backup_studio`
(créé par cette installation : l'état d'avant), les 191 fichiers de Marina vérifiés identiques à sa sortie de
construction ; nom remis à « NFS Dubai » (celui de `world_v1`, `world_v2`, `world_guide`, le seul champ changé).
Restent dans Blur_test 3 fichiers ajoutés par l'installation fautive, sans effet (Marina s'arrête à `road_21_37`) :
`models\objects\flat_earth\road_21_38.model`, `_39`, `_40` (supprimés le 2026-11-10 avec l'accord de l'utilisateur).
`nfs_dubai\backup_studio` contient donc l'état « Marina installée » : c'est bien l'état d'avant la 1re
installation par NFS Studio.
Correctif des tests : refus de démarrer si le port est déjà pris, processus lancé vérifié vivant, et le serveur NFS
doit servir le circuit temporaire marqué `TEST_TEMPORAIRE` avant tout envoi ; sinon les tests s'arrêtent.

## Étape 0 de l'historique (2026-11-10) : plus de remise automatique depuis les sauvegardes

Avant : à la fin de chaque installation, `b2track.install` recopiait dans Blur_test **tout fichier de
`b2_dubai_marina\backup_blur_test` absent de la nouvelle map** (but : effacer les `road_21_KK` en trop d'une map
plus grande). Or cette sauvegarde suit la règle « 1re version vue » : chaque fichier y a été gardé au moment où une
installation l'a écrasé pour la première fois, donc à des dates différentes. Mesuré par empreintes : son
`level.levelphysics` est celui de NFS Dubaï phase B, son `level.levelrender` celui de l'époque Rio, aucun n'est
l'original du jeu. Une map plus petite que la précédente aurait donc reçu des fichiers d'autres générations.
(Pas arrivé jusqu'ici : Blur_test = sortie Marina, vérifié.)

Maintenant : la boucle de remise est retirée. L'installation copie seulement la sortie de la map (copies vérifiées,
originaux sauvegardés une fois, inchangé) ; les fichiers d'une installation précédente absents de la nouvelle map
**restent tels quels** et sont listés dans le message (« laissés en place (rien remis ni supprimé) »). Pas de
suppression automatique à la place : un nettoyage destructif attendra l'historique commun (`studio_history`).

Conséquence connue : après une map plus petite, des morceaux de route de la précédente restent dans Blur_test
(sans effet tant que le niveau ne les référence pas, comme `road_21_38…40` le 2026-11-10). Ils sont signalés à
chaque installation.

Test : `tests.test_studio_safe.InstallationTraces.test_map_avec_moins_de_routes` (dossiers temporaires) : sauvegarde
héritée mélangée (`road_21_09` d'une autre génération, un `levelrender` « époque Rio »), map à 3 routes puis map à 1
route → la route installée est la nouvelle, `road_21_02` / `03` restent ceux de la 1re map (pas les « états
d'avant » de la sauvegarde), `road_21_09` et le `levelrender` hérités ne sont jamais copiés, les restes sont
signalés, la sauvegarde héritée est identique avant / après. Suite complète : 37 tests ; empreinte de toutes les
sauvegardes `mods\*\backup_*` identique avant / après ; aucun fichier de Blur_test modifié.

## Étape 1 de l'historique (2026-11-10) : noyau `studio_history.py`

Noyau seul : aucun serveur, aucune installation, aucune page n'y fait encore appel (intégration = étape 3). Aucun
dossier d'historique réel n'a été créé ; il sera `Jeux_WII\studio_history\` à l'intégration.

**Dossier d'un historique** (`Historique(racine)`) :
- `objets\<2 premiers>\<sha256>` : contenu d'un fichier, stocké une fois (dédoublonné). Écrit à côté puis lié à sa
  place (`os.link` : échoue si la cible existe → jamais écrasé). Déjà présent : revérifié ; s'il est abîmé, refus
  (`ObjetCorrompu`) au lieu d'une réécriture silencieuse. Chaque lecture recalcule l'empreinte (`lire_objet`,
  `verifier_objet` → `ObjetManquant` / `ObjetCorrompu`). Fichier modifié pendant sa copie : refus.
- `versions\<AAAAMMJJ-HHMMSS-xxxxxx>.json` : photo complète `{chemin relatif « / »: sha256 | null (absent)}`, avec
  date, studio, opération, cible, version précédente. Immuable (même écriture sans écrasement : un identifiant déjà
  pris = refus). `differences(v1, v2)` → ajoutés / modifiés / retirés ; `verifier_version` contrôle tous ses objets.
- `journal.jsonl` : une ligne par événement (`debut` d'une opération, avec version « avant », studio, pid, jeton
  du verrou ; `fin` avec version « après » et résultat), ajoutée avec `fsync`, jamais réécrite. Chaque ligne porte
  son rang `n` et l'empreinte de la précédente `prec` : ligne modifiée, supprimée **au milieu** ou déplacée →
  `JournalAbime`. **Correction (voir « Ancres du journal ») : la chaîne seule ne détecte ni une fin coupée, ni un
  journal vidé ou supprimé, ni un ancien journal valide remis à sa place** ; c'est le rôle des ancres.
  Dernière ligne incomplète (écriture coupée) → `JournalAbime` et aucun ajout tant qu'on n'a pas examiné (rien
  n'est « réparé » en silence). Une 2e fin pour la même opération est refusée.
- `verrou` : créé de façon exclusive (`O_CREAT | O_EXCL`) avec studio, opération, pid, date, jeton. Une 2e opération
  (même processus ou autre) → `VerrouOccupe` avec le studio et l'opération en cours. Verrou dont le processus est
  mort (Windows : `OpenProcess` / `GetExitCodeProcess`) ou illisible → `VerrouOccupe(orphelin=True)`, message
  « supprimer à la main après vérification » : jamais retiré automatiquement. On ne retire que son propre verrou
  (même jeton). `commencer` / `terminer` exigent le verrou détenu.

**Statuts** : le statut d'une version vient du journal (« en_cours » tant que l'opération qui la cite n'a pas sa
fin, sinon « terminée » ; photo hors opération = terminée). `interrompues()` = opérations sans fin dont le verrou
n'est plus vivant : leur version « avant » est la base d'une future reprise.

**Chemins** : relatifs seulement ; refus des absolus, lecteurs (`C:`), `.`, `..`, segments vides, et des liens qui
mènent hors du dossier photographié (chemin réel, `studio_safe.dans_dossier`). Erreurs : `ErreurHistorique` et ses
sous-classes, message explicite et code HTTP pour les studios.

**Tests** : `python -m unittest tests.test_studio_history` (20, dossiers temporaires) : dédoublonnage ; objet existant
jamais écrasé ; corruption et objet manquant ; écriture d'objet interrompue (rien laissé) ; fichier modifié pendant
la copie ; photo / lecture / différences (ajouté, modifié, retiré, absent) ; version jamais écrasée ; version à objet
corrompu ou manquant ; identifiants et précédente invalides ; 11 chemins hors dossier ; lien symbolique vers
l'extérieur ; opération complète et statuts ; interruption simulée ; journal falsifié et ligne supprimée ; ligne
incomplète ; sans verrou ; concurrence dans le même processus et depuis un autre processus ; verrou orphelin
(signalé, intact) ; verrou illisible ; libération par un autre refusée. Suite complète : 57 tests, 2 passages.

**Limites** : pas encore utilisé par les studios ; pas de restauration (étape 4) ; pas de purge (les objets
s'accumulent : à décider plus tard, avec accord) ; un journal abîmé bloque toute opération jusqu'à examen manuel ;
un pid réutilisé par un autre programme ferait passer un verrou orphelin pour vivant (signalé comme occupé, sûr) ;
`os.link` exige un disque NTFS (le cas ici).

## Ancres du journal (2026-11-10) : troncature et anciens états

**Constat** (essai sur le noyau `1ef4562`, journal de 6 lignes) : détectés = ligne supprimée au milieu, ligne coupée
par une interruption ; **non détectés, opération suivante acceptée** = dernière ligne supprimée, deux dernières,
toutes (fichier vide), journal supprimé, journal remplacé par un ancien état valide. Une chaîne de hachage prouve
l'ordre des lignes, pas l'endroit où le journal doit finir.

**Correction** : deux copies d'une ancre `{n lignes validées, empreinte de la ligne n, date, racine}` :
`<historique>\ancre.json` et `%LOCALAPPDATA%\blurre\ancres\<clé du chemin de l'historique>.json` (hors de
`Jeux_WII`). Écriture de chaque ligne, dans cet ordre : ligne ajoutée au journal (`fsync`), ancre externe, ancre
locale (chacune écrite à côté, `fsync`, puis remplacement atomique). Les anciennes lignes ne sont jamais réécrites.

Contrôle (`etat_integrite`) avant **toute** photo, début, fin, liste des opérations ou des versions ; en cas d'échec
`JournalAbime` avec un message explicite, et **tout est bloqué** :
- chaîne rompue ou dernière ligne incomplète ;
- ancre absente, illisible, d'un contenu inattendu, ou emplacement inaccessible (`LOCALAPPDATA` absente, chemin qui
  n'est pas un dossier) ;
- ancres divergentes (même si chacune est cohérente avec un journal : on ne choisit jamais l'une des deux) ;
- journal plus court que `n` (lignes validées disparues : troncature, journal vidé ou supprimé, ancien journal) ;
- ligne `n` d'une autre empreinte (journal remplacé, même de même longueur) ;
- plus d'une ligne au-delà de `n`.
Une seule ligne de plus que `n` est acceptée : c'est l'état laissé par une coupure entre la ligne et les ancres ;
elle est forcément chaînée à la ligne ancrée, et l'ajout suivant l'ancre avant d'écrire la sienne.
Historique vierge (ni journal, ni ancres, ni version) : accepté ; dès la 1re donnée (photo ou ligne), les deux
ancres sont écrites, donc un historique qui a des données sans ancres est refusé. Une ancre absente ou illisible
n'est **jamais reconstruite automatiquement**.

Interruptions et pannes :
- coupure pendant l'ajout de la ligne → ligne incomplète → blocage (rien ajouté par-dessus) ;
- disque plein à l'ouverture du journal → opération refusée, journal inchangé ;
- coupure (ou échec) après la ligne, avant / pendant l'ancre externe → une ligne d'avance, accepté ; l'ancienne ancre
  reste intacte (pas de fichier temporaire laissé) ;
- coupure entre l'ancre externe et l'ancre locale → ancres divergentes → **blocage, réancrage manuel** (fenêtre de
  quelques millisecondes ; c'est le prix de la règle « divergence = blocage ») ;
- `%LOCALAPPDATA%` inaccessible dès la 1re écriture → photo refusée, aucune version créée sans ancres.

**Réancrage** (`apercu_reancrage`, puis `reancrer(verrou, motif, confirmation)`) : manuel et explicite. L'aperçu
montre le nombre de lignes, l'empreinte de la dernière et le contenu des deux ancres actuelles. Le réancrage exige
le verrou, un motif non vide et, en confirmation, l'empreinte exacte de la dernière ligne (si le journal a changé
depuis l'aperçu, refus). Il refuse un journal à chaîne rompue ou à ligne incomplète. Il **ajoute** au journal une
ligne `reancrage` (anciennes ancres, motif, studio), puis écrit les deux ancres (avec le motif) : rien d'autre n'est
modifié, l'événement reste dans l'historique.

**Ce que ça protège, et ce que ça ne protège pas** :
- **Accidents** (le but) : troncature, fichier vidé ou supprimé, copie partielle, restauration d'un ancien journal ou
  d'un **ancien dossier d'historique complet** (l'ancre externe, plus récente, diverge), mauvaise manipulation,
  coupure de courant, disque plein. Tous détectés, opérations bloquées avec un message.
- **Une personne qui a accès aux deux emplacements** (`Jeux_WII` et `%LOCALAPPDATA%`, donc ce compte Windows) peut
  réécrire le journal ET les deux ancres de façon cohérente : ce n'est **pas** détecté. Ce n'est pas une protection
  contre une personne malveillante sur ce PC ; il faudrait pour cela une signature par une clé hors de sa portée.

**Limites** : une coupure entre les deux ancres demande un réancrage manuel ; changer de PC ou de compte Windows
(ancre externe absente) aussi ; une restauration volontaire de l'historique depuis une sauvegarde aussi (tracée par
la ligne `reancrage`). Le blocage est total tant que l'intégrité n'est pas rétablie (choix prudent).

**Tests** (`tests.test_studio_history`, 43 ; dossiers temporaires, `LOCALAPPDATA` redirigé vers le dossier du test) :
les 7 altérations (+ un journal d'une autre histoire de même longueur) ; ancre locale / externe / les deux absentes ;
ancres illisibles (texte abîmé, contenu inattendu) ; ancres divergentes ; historique vierge puis 1re photo ;
coupure après la ligne, entre les deux ancres, pendant l'écriture d'une ancre ; disque plein à l'ajout de la ligne ;
`LOCALAPPDATA` inaccessible ou absente, y compris dès la 1re écriture ; ancien dossier complet remis ; réancrage
accepté (puis opérations de nouveau possibles) et refusé (sans verrou, sans motif, mauvaise confirmation, chaîne
rompue, journal changé après l'aperçu) ; dans chaque cas d'intégrité non garantie, photo, début, fin, liste des
opérations / versions / interruptions refusés. Suite complète : 80 tests, 2 passages, aucun ignoré.

Incident pendant le développement : un premier passage des tests (avant la redirection de `LOCALAPPDATA`) a créé
`%LOCALAPPDATA%\blurre\ancres\` avec 2 ancres d'historiques temporaires ; dossier créé par ce passage, retiré aussitôt.
Les tests redirigent maintenant la variable elle-même.
