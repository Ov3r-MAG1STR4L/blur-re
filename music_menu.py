#!/usr/bin/env python3
"""Menu: pick the race-music playlists (folders of make_music.MUSIC_DIR), build them and install them in the test copy.
Launched by "Choisir la musique.bat". Answer: one number, or several ("1 2" or "1+2")."""
import os, re, sys
import make_music


def main():
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
        rep = input("\nTon choix : ").strip()
        picks = [int(x) for x in re.findall(r"\d+", rep)]
        if picks and all(1 <= p <= len(lists) for p in picks):
            break
        print("Réponds avec un ou plusieurs numéros de la liste.")
    chosen = [os.path.join(root, lists[p - 1]) for p in dict.fromkeys(picks)]
    print("\nPréparation de :", ", ".join(lists[p - 1] for p in dict.fromkeys(picks)))
    print("(un morceau jamais utilisé est encodé une seule fois : ça peut prendre quelques minutes)\n")
    print(make_music.build(chosen))
    make_music.install()
    print("\nC'est prêt. Lance le jeu avec « Tester le mod.bat ».")


if __name__ == "__main__":
    main()
