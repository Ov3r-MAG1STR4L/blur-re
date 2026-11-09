#!/usr/bin/env python3
"""Menu: pick the race-music playlists (folders of make_music.MUSIC_DIR) and the game effects on the music, build
them and install them in the test copy. Launched by "Choisir la musique.bat". Answer: one number, or several ("1 2").
The choice is saved (LAST); "--remelanger" (called by "Tester le mod.bat") rebuilds it with a new shuffle order."""
import json, os, re, sys
import make_music

LAST = os.path.join(make_music.MUSIC_DIR, "derniere_selection.json")


def run(folders, effects, pcm16=False):
    effects = make_music.normalize_effects(effects)
    print(make_music.build(folders, effects=effects, pcm16=pcm16))
    make_music.install()


def main():
    if "--remelanger" in sys.argv:
        if not os.path.exists(LAST):
            return                                            # music never chosen: nothing to shuffle
        last = json.load(open(LAST, encoding="utf-8"))
        effects = make_music.normalize_effects(last["effets"])
        print("Nouvel ordre aléatoire pour la musique...")
        run(last["dossiers"], effects, last.get("haute_qualite", False))
        if last["effets"] != effects:
            last["effets"] = effects
            with open(LAST, "w", encoding="utf-8") as f:
                json.dump(last, f, ensure_ascii=False, indent=1)
        return
    root = os.path.abspath(make_music.MUSIC_DIR)
    lists = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if not lists:
        sys.exit(f"Aucune playlist : crée des dossiers dans {root}")
    print("Playlists (dossiers dans", root + ") :\n")
    for k, d in enumerate(lists, 1):
        n = sum(f.lower().endswith(make_music.AUDIO_EXT) for f in os.listdir(os.path.join(root, d)))
        label = re.sub(r"^\d+\s*-\s*", "", d)                       # folders may be numbered for sorting
        print(f"  {k}. {label}" + (f"  ({n} morceaux)" if n else "  (morceaux du jeu)"))
    print(f"\n  Plusieurs à la fois : par exemple « 1 2 ». Ajoute un dossier dans {root} pour une nouvelle playlist.")
    while True:
        picks = [int(x) for x in re.findall(r"\d+", input("\nTon choix : "))]
        if picks and all(1 <= p <= len(lists) for p in picks):
            break
        print("Réponds avec un ou plusieurs numéros de la liste.")
    print("\nEffets du jeu sur le son : 1. oui  2. partiellement  3. non")
    choices = {"1": "oui", "oui": "oui", "2": "partiel", "partiel": "partiel",
               "partiellement": "partiel", "3": "non", "non": "non"}
    while True:
        rep = input("Ton choix [1] : ").strip().lower() or "1"
        if rep in choices:
            effects = choices[rep]
            break
        print("Réponds par 1, 2 ou 3 (oui, partiellement, non).")
    pcm16 = False     # uncompressed PCM16 tracks: silent in game (tested 2026-10-21), kept in make_music for research
    chosen = [os.path.join(root, lists[p - 1]) for p in dict.fromkeys(picks)]
    print("\nPréparation de :", ", ".join(lists[p - 1] for p in dict.fromkeys(picks)))
    print("(un morceau jamais utilisé est encodé une seule fois : ça peut prendre quelques minutes)\n")
    run(chosen, effects, pcm16)
    with open(LAST, "w", encoding="utf-8") as f:
        json.dump({"dossiers": chosen, "effets": effects, "haute_qualite": pcm16}, f, ensure_ascii=False, indent=1)
    print("\nC'est prêt. Lance le jeu avec « Tester le mod.bat » (il remélange l'ordre à chaque lancement).")


if __name__ == "__main__":
    main()
