#!/usr/bin/env python3
"""Blur music pack for other players (English): their own race-music playlists, the next-track key (musicctl), the
game's effects on the sound (on / partial / off). Shipped in Blur_Music\\tools\\ (built by music_pack/make_zip.py);
the Blur_Music folder goes next to Blur.exe.

usage: pack.py menu | reshuffle | uninstall
First run (menu): a pak wins over loose files, so cache\\root.pak and cache\\root_streaming.pak are laid loose from the
PLAYER'S OWN paks (root -> <game>\\, root_streaming -> <game>\\audio\\, existing loose files kept) and set aside as
.off; the few originals the music build needs are kept in tools\\data. Everything is recorded in backup\\ (added
files, renamed paks, files saved before being replaced) so uninstall puts the game back as it was."""
import json, os, re, shutil, subprocess, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(TOOLS)
GAME = os.path.dirname(PACK)
STATE = os.path.join(PACK, "backup")
DONE = os.path.join(STATE, "installed.txt")
ADDED = os.path.join(STATE, "added.txt")
RENAMED = os.path.join(STATE, "renamed.txt")
SAVED = os.path.join(STATE, "files")
DATA = os.path.join(TOOLS, "data")
MUSIC = os.path.join(PACK, "Music")
LAST = os.path.join(MUSIC, "last_selection.json")
os.environ.update({"BLUR_MUSIC_E": DATA, "BLUR_MUSIC_MUSIC_DIR": MUSIC, "BLUR_MUSIC_TEST": GAME,
                   "BLUR_MUSIC_CACHE": os.path.join(TOOLS, "cache"), "BLUR_MUSIC_OUT": os.path.join(TOOLS, "build")})
sys.path.insert(0, TOOLS)
import blurpak, make_music  # noqa: E402  (after the environment above)

PAKS = (("root", ""), ("root_streaming", "audio"))
NEEDED = {"root": ["audio/dat/music_controller.dat", "audio/dat/finalsubmix.dat", "audio/dat/finalperksubmix.dat",
                   "audio/ingameui.baf", "audio/menumusic_ns.baf"],
          "root_streaming": ["ingamemusic.baf"]}
WRITTEN = ["audio/ingamemusic.baf", "audio/dat/music_controller.dat", "audio/dat/finalsubmix.dat",
           "audio/dat/finalperksubmix.dat", "audio/ingameui.baf", "amax/plugins/plugins.lua",
           "amax/plugins/musicctl/musicctl.lua"]
REQUIRE = 'require("musicctl.musicctl"),'
EFFECTS = {"1": "oui", "2": "partiel", "3": "non"}
EFFECT_NAMES = {"oui": "on", "partiel": "partial", "non": "off"}


def stop(msg):
    print("\n" + msg)
    sys.exit(1)


def blur_closed():
    if b"Blur.exe" in subprocess.run(["tasklist", "/fi", "imagename eq Blur.exe"], capture_output=True).stdout:
        stop("Blur is running: close it and try again.")


def game_path(rel):
    return os.path.join(GAME, rel.replace("/", os.sep))


def prepare():
    """First run only: loose paks, originals, key sound, plugin. An interrupted run must be uninstalled first."""
    if os.path.exists(DONE):
        return
    if os.path.exists(STATE):
        stop("A previous installation was interrupted: run \"Uninstall.bat\" first, then try again.")
    if not os.path.exists(os.path.join(GAME, "Blur.exe")):
        stop(f"Blur.exe not found in {GAME}: put the Blur_Music folder inside the Blur folder (next to Blur.exe).")
    for pak, _ in PAKS:
        if not os.path.exists(os.path.join(GAME, "cache", pak + ".pak")):
            stop(f"cache\\{pak}.pak not found (already set aside by another mod?): cannot install.")
    free = shutil.disk_usage(GAME).free
    if free < 3 * 1024 ** 3:
        stop(f"About 3 GB of free space is needed on the game's drive ({free / 1024 ** 3:.1f} GB free).")
    print("First run: unpacking the game's audio and data files (a few minutes, about 1.7 GB)...")
    os.makedirs(SAVED)
    for rel in WRITTEN:                                   # the player's own versions, put back by uninstall
        if os.path.exists(game_path(rel)):
            dst = os.path.join(SAVED, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(game_path(rel), dst)
    with open(ADDED, "a", encoding="utf-8") as added:     # written as we go: an interrupted run can be undone
        for pak, dest in PAKS:
            p = blurpak.Pak(os.path.join(GAME, "cache", pak + ".pak"))
            want = set(NEEDED[pak])
            for k, e in enumerate(p.files, 1):
                path = e.path.lstrip("\\/").replace("\\", "/")
                data = p.read(e)
                if path.lower() in want:
                    keep = os.path.join(DATA, pak, path.replace("/", os.sep))
                    os.makedirs(os.path.dirname(keep), exist_ok=True)
                    open(keep, "wb").write(data)
                    want.discard(path.lower())
                rel = f"{dest}/{path}" if dest else path
                if not os.path.exists(game_path(rel)):
                    os.makedirs(os.path.dirname(game_path(rel)), exist_ok=True)
                    open(game_path(rel), "wb").write(data)
                    added.write(rel + "\n")
                    added.flush()
                if k % 500 == 0 or k == len(p.files):
                    print(f"  {pak}.pak: {k} / {len(p.files)}")
            p.f.close()
            if want:
                stop(f"Files missing from {pak}.pak: {sorted(want)}")
    for pak, _ in PAKS:                                   # a pak wins over loose files: set it aside
        for ext in (".pak", ".sig"):
            src = os.path.join(GAME, "cache", pak + ext)
            if os.path.exists(src):
                os.replace(src, src + ".off")
                with open(RENAMED, "a", encoding="utf-8") as f:
                    f.write(f"cache/{pak}{ext}\n")
    make_music.music_key_sounds(make_music.OUT)           # next-track sound, in ingameui.baf
    shutil.copyfile(os.path.join(make_music.OUT, "audio", "ingameui.baf"), game_path("audio/ingameui.baf"))
    lst = game_path("amax/plugins/plugins.lua")
    if os.path.exists(lst):
        plugin = game_path("amax/plugins/musicctl/musicctl.lua")
        os.makedirs(os.path.dirname(plugin), exist_ok=True)
        shutil.copyfile(os.path.join(TOOLS, "musicctl.lua"), plugin)
        lua = open(lst, encoding="utf-8").read()
        if REQUIRE.rstrip(",") not in lua:
            k = lua.rstrip().rfind("}")
            os.chmod(lst, 0o666)                          # the original plugins.lua is read-only
            open(lst, "w", encoding="utf-8", newline="\n").write(lua[:k].rstrip() + "\n\t" + REQUIRE + "\n}\n")
    else:
        print("AMAX not found (amax\\plugins\\plugins.lua): the next-track key will not work.")
    open(DONE, "w").write("ok\n")


def build(folders, effects):
    print(make_music.build(folders, effects=effects))
    make_music.install()


def menu():
    lists = sorted(d for d in os.listdir(MUSIC) if os.path.isdir(os.path.join(MUSIC, d)))
    print("\nPlaylists (folders in Music):\n")
    for k, d in enumerate(lists, 1):
        n = sum(f.lower().endswith(make_music.AUDIO_EXT) for f in os.listdir(os.path.join(MUSIC, d)))
        label = re.sub(r"^\d+\s*-\s*", "", d)
        print(f"  {k}. {label}" + (f"  ({n} track{'s' * (n > 1)})" if n else "  (the game's own tracks)" if "original" in d.lower()
                                  else "  (empty: add music files to this folder)"))
    print("\n  Several at once: for example \"1 2\".")
    while True:
        picks = [int(x) for x in re.findall(r"\d+", input("\nYour choice: "))]
        if picks and all(1 <= p <= len(lists) for p in picks):
            break
        print("Answer with one or more numbers from the list.")
    print("\nGame effects on the sound (power-ups, crashes, wrecked, low health):")
    print("  1. on (as in the game)  2. partial (softer)  3. off")
    while (rep := input("Your choice [1]: ").strip() or "1") not in EFFECTS:
        print("Answer 1, 2 or 3.")
    chosen = [os.path.join(MUSIC, lists[p - 1]) for p in dict.fromkeys(picks)]
    print("\nPreparing... (each new track is converted only once: the first time can take a few minutes)\n")
    build(chosen, EFFECTS[rep])
    json.dump({"folders": chosen, "effects": EFFECTS[rep]}, open(LAST, "w", encoding="utf-8"), indent=1)
    print(f"\nDone: effects {EFFECT_NAMES[EFFECTS[rep]]}. Start the game with \"Launch Blur.bat\" "
          "(new random order each time) or Blur.exe (same order as last time).")


def uninstall():
    blur_closed()
    if not os.path.exists(STATE):
        stop("The pack is not installed.")
    added = [l for l in open(ADDED, encoding="utf-8").read().splitlines() if l] if os.path.exists(ADDED) else []
    for rel in added:
        if os.path.exists(game_path(rel)):
            os.remove(game_path(rel))
    for rel in (open(RENAMED, encoding="utf-8").read().splitlines() if os.path.exists(RENAMED) else []):
        if rel and os.path.exists(game_path(rel) + ".off"):
            os.replace(game_path(rel) + ".off", game_path(rel))
    plugin = "amax/plugins/musicctl/musicctl.lua"
    if not os.path.exists(os.path.join(SAVED, plugin.replace("/", os.sep))) and os.path.exists(game_path(plugin)):
        os.remove(game_path(plugin))
        added.append(plugin)
    for root, _, files in os.walk(SAVED):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.join(GAME, os.path.relpath(src, SAVED))
            if os.path.exists(dst):
                os.chmod(dst, 0o666)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    dirs = set()                                          # folders the pack created and left empty
    for rel in added:
        d = os.path.dirname(game_path(rel))
        while len(d) > len(GAME):
            dirs.add(d)
            d = os.path.dirname(d)
    for d in sorted(dirs, key=len, reverse=True):
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
    for d in (STATE, DATA, make_music.OUT):
        for root, _, files in os.walk(d):                 # saved plugins.lua keeps its read-only flag
            for f in files:
                os.chmod(os.path.join(root, f), 0o666)
        shutil.rmtree(d, ignore_errors=True)
    if os.path.exists(STATE):
        stop(f"Could not delete {STATE}: delete it by hand before installing again.")
    for f in (LAST,):
        if os.path.exists(f):
            os.remove(f)
    print("Uninstalled: the game is back as it was (your converted tracks stay in tools\\cache).")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "menu"
    if cmd == "uninstall":
        return uninstall()
    blur_closed()
    if cmd == "reshuffle":
        if os.path.exists(DONE) and os.path.exists(LAST):
            last = json.load(open(LAST, encoding="utf-8"))
            print("New random order for the race music...")
            build(last["folders"], last["effects"])
        return
    if not shutil.which("ffmpeg"):
        stop("ffmpeg not found: run \"Choose music.bat\" again, it offers to install it.")
    prepare()
    menu()


if __name__ == "__main__":
    main()
