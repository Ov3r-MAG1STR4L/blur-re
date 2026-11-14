#!/usr/bin/env python3
"""Blur music pack for other players (English): their own race-music playlists, the next-track key (musicctl), the
game's effects on the sound (on / partial / off). Shipped in Blur_Music\\tools\\ (built by music_pack/make_zip.py);
the Blur_Music folder goes next to Blur.exe.

usage: pack.py menu | uninstall
First run (menu): a pak wins over loose files, so cache\\root.pak and cache\\root_streaming.pak are laid loose from the
PLAYER'S OWN paks (root -> <game>\\, root_streaming -> <game>\\audio\\, existing loose files kept) and set aside as
.off; the few originals the music build needs are kept in its data\\ folder. Everything is recorded in <game>\\Blur_Music_backup\\ (added
files, renamed paks, files saved before being replaced) so uninstall puts the game back as it was."""
import hashlib, json, os, re, shutil, subprocess, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(TOOLS)
def find_game(here):
    """The Blur folder: the pack's parent, or (Blur_Music unzipped next to the game folder instead of inside it, a
    player's report 2026-11-13) the one sub-folder of that parent that holds Blur.exe."""
    if os.path.exists(os.path.join(here, "Blur.exe")):
        return here
    found = [os.path.join(here, d) for d in sorted(os.listdir(here))
             if os.path.isfile(os.path.join(here, d, "Blur.exe"))]
    return found[0] if len(found) == 1 else here


GAME = find_game(os.path.dirname(PACK))
STATE = os.path.join(GAME, "Blur_Music_backup")      # outside the pack folder: survives a pack update (player, 2026-11-13)
DONE = os.path.join(STATE, "installed.txt")
ADDED = os.path.join(STATE, "added.txt")
RENAMED = os.path.join(STATE, "renamed.txt")
SAVED = os.path.join(STATE, "files")
DATA = os.path.join(STATE, "data")
MUSIC = os.path.join(PACK, "Music")
LAST = os.path.join(MUSIC, "last_selection.json")
os.environ.update({"BLUR_MUSIC_E": DATA, "BLUR_MUSIC_MUSIC_DIR": MUSIC, "BLUR_MUSIC_TEST": GAME,
                   "BLUR_MUSIC_PLUGIN": os.path.join(TOOLS, "musicctl.lua"),   # the plugin template, shipped in tools
                   "BLUR_MUSIC_CACHE": os.path.join(TOOLS, "cache"), "BLUR_MUSIC_OUT": os.path.join(TOOLS, "build")})
sys.path.insert(0, TOOLS)
import blurpak, make_music  # noqa: E402  (after the environment above)

PAKS = (("root", ""), ("root_streaming", "audio"), ("gamedata", ""))   # gamedata: hud.loc (track titles of the banner)
NEEDED = {"root": ["audio/dat/music_controller.dat", "audio/dat/finalsubmix.dat", "audio/dat/finalperksubmix.dat",
                   "audio/ingameui.baf", "audio/menumusic_ns.baf"],
          "root_streaming": ["ingamemusic.baf"],
          "gamedata": ["gamedata/xt/loc/hud.loc"]}
WRITTEN = ["gamedata/xt/loc/hud.loc", "audio/ingamemusic.baf", "audio/dat/music_controller.dat", "audio/dat/finalsubmix.dat",
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
        return upgrade()
    if os.path.exists(STATE):
        stop("A previous installation was interrupted: run \"Uninstall.bat\" first, then try again.")
    if not os.path.exists(os.path.join(GAME, "Blur.exe")):
        stop(f"Blur.exe not found in {GAME} nor in its sub-folders: put the Blur_Music folder inside the Blur folder "
             "(the one that contains Blur.exe).")
    cache = os.path.join(GAME, "cache")
    aside = [pak for pak, _ in PAKS if not os.path.exists(os.path.join(cache, pak + ".pak"))]
    if aside:
        if not all(os.path.exists(os.path.join(cache, pak + ".pak.off")) for pak in aside):
            stop(f"cache\\{aside[0]}.pak not found: cannot install.")
        print(f"cache\\{aside[0]}.pak was renamed to .pak.off, by another mod or by an older Blur Music install that"
              " was interrupted\n(older versions kept their backup inside the Blur_Music folder).")
        if input("Was it an older Blur Music install? Put the game files back and continue? (Y/N): ").strip().lower() != "y":
            stop("Nothing changed. Uninstall the other mod first, then run \"Choose music.bat\" again.")
        for pak in aside:                                 # the loose files it left are taken back below (same content)
            for ext in (".pak", ".sig"):
                if os.path.exists(os.path.join(cache, pak + ext + ".off")):
                    os.replace(os.path.join(cache, pak + ext + ".off"), os.path.join(cache, pak + ext))
    free = shutil.disk_usage(GAME).free
    if free < 3 * 1024 ** 3:
        stop(f"About 3 GB of free space is needed on the game's drive ({free / 1024 ** 3:.1f} GB free).")
    print(f"Blur folder: {GAME}")
    print("First run: unpacking the game's audio and data files (a few minutes, about 1.7 GB)...")
    os.makedirs(SAVED)
    unpack(PAKS, WRITTEN, aside)
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


def upgrade():
    """An install made by an older pack lacks the archives added since (gamedata.pak, v1.1: hud.loc for the banner;
    player crash, 2026-11-14): unpack only those, the way a first run does."""
    missing = [(pak, dest) for pak, dest in PAKS
               if not all(os.path.exists(os.path.join(DATA, pak, n.replace("/", os.sep))) for n in NEEDED[pak])]
    if not missing:
        return
    for pak, _ in missing:
        if not os.path.exists(os.path.join(GAME, "cache", pak + ".pak")):
            stop(f"cache\\{pak}.pak not found: run \"Uninstall.bat\", then \"Choose music.bat\" again.")
    print("Updating an installation made by an older Blur Music version...")
    # only the files these archives provide: the others in the game folder are already this pack's own versions
    rels = [f"{dest}/{n}" if dest else n for pak, dest in missing for n in NEEDED[pak]]
    unpack(missing, [r for r in WRITTEN if r in rels and not os.path.exists(os.path.join(SAVED, r.replace("/", os.sep)))], [])


def unpack(paks, backup, aside):
    """Unpack paks into the game folder (loose files win once the pak is set aside), keeping NEEDED originals in DATA.
    backup: WRITTEN files to save first (the player's own versions, put back by uninstall)."""
    for rel in backup:
        if os.path.exists(game_path(rel)):
            dst = os.path.join(SAVED, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(game_path(rel), dst)
    same = set()
    with open(ADDED, "a", encoding="utf-8") as added:     # written as we go: an interrupted run can be undone
        for pak, dest in paks:
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
                new = not os.path.exists(game_path(rel))
                if new:
                    os.makedirs(os.path.dirname(game_path(rel)), exist_ok=True)
                    open(game_path(rel), "wb").write(data)
                elif aside and open(game_path(rel), "rb").read() == data:
                    # recovery only (player answered Y): an older run's leftover, same as the pak. In a normal install
                    # an existing loose file is the player's (their own old extraction...): never taken, never deleted
                    # (player, 2026-11-13)
                    same.add(rel)
                if new or rel in same:
                    added.write(f"{rel}\t{hashlib.sha1(data).hexdigest()}\n")   # uninstall: only if unchanged
                    added.flush()
                if k % 500 == 0 or k == len(p.files):
                    print(f"  {pak}.pak: {k} / {len(p.files)}")
            p.f.close()
            if want:
                stop(f"Files missing from {pak}.pak: {sorted(want)}")
    for rel in same & set(backup):                        # not the player's version: no backup to put back
        os.remove(os.path.join(SAVED, rel.replace("/", os.sep)))
    for pak, _ in paks:                                   # a pak wins over loose files: set it aside
        for ext in (".pak", ".sig"):
            src = os.path.join(GAME, "cache", pak + ext)
            if os.path.exists(src):
                os.replace(src, src + ".off")
                with open(RENAMED, "a", encoding="utf-8") as f:
                    f.write(f"cache/{pak}{ext}\n")


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
    print(f"\nDone: effects {EFFECT_NAMES[EFFECTS[rep]]}. Start Blur as usual (Blur.exe, TextMod...): "
          "each session starts at a random point of the shuffled order.")


def uninstall():
    blur_closed()
    if not os.path.exists(STATE):
        stop("The pack is not installed.")
    lines = [l.split("\t") for l in open(ADDED, encoding="utf-8").read().splitlines() if l] if os.path.exists(ADDED) else []
    added, kept = [l[0] for l in lines], []
    print("Removing the files the pack added (checking each one, a few minutes)...")
    for rel, *sha in lines:
        p = game_path(rel)
        if not os.path.exists(p):
            continue
        # changed since the pack wrote it (another mod...): not ours any more. The audio files the pack rebuilds
        # (WRITTEN) are always its own; lines of older versions have no hash.
        if sha and rel not in WRITTEN and hashlib.sha1(open(p, "rb").read()).hexdigest() != sha[0]:
            kept.append(rel)
            continue
        os.remove(p)
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
    if kept:
        print(f"\n{len(kept)} file(s) unpacked by the pack were changed since (by another mod?) and were left in place:")
        for rel in kept[:20]:
            print("  " + rel.replace("/", "\\"))
        if len(kept) > 20:
            print(f"  ... and {len(kept) - 20} more")
        print("The game reads its archives first: these files are only used if another mod set the archives aside.")


ADMIN = ("Windows does not let this window write in the Blur folder (it is protected, e.g. in Program Files).\n"
         "Right-click the .bat file and choose \"Run as administrator\".")


def writable():
    """The .bat files do not ask for administrator rights by themselves (antivirus false positive, 2026-11-13)."""
    test = os.path.join(GAME, "blur_music_write_test.tmp")
    try:
        open(test, "w").close()
        os.remove(test)
    except PermissionError:
        stop(ADMIN)


VERSION = "1.2.1"                                     # this pack's release tag (update it with each GitHub release)
RELEASES = "https://github.com/Ov3r-MAG1STR4L/blur-music-pack/releases/latest"


def check_update():
    """Tell the player when GitHub has a newer release (notice only, nothing downloaded; silent when offline)."""
    import urllib.request
    try:
        req = urllib.request.Request("https://api.github.com/repos/Ov3r-MAG1STR4L/blur-music-pack/releases/latest",
                                     headers={"User-Agent": "BlurMusicPack", "Accept": "application/vnd.github+json"})
        tag = json.load(urllib.request.urlopen(req, timeout=3)).get("tag_name", "")
        ver = lambda t: tuple(int(x) for x in t.lstrip("vV").split(".") if x.isdigit())
        if ver(tag) > ver(VERSION):
            print(f"A new version of Blur Music is available: {tag} (you have {VERSION}).")
            print(f"Download it here: {RELEASES}")
            print("(keep your Music folder when you replace Blur_Music)")
            print()
    except Exception:
        pass


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "menu"
    writable()
    if cmd == "uninstall":
        return uninstall()
    blur_closed()
    try:                                                  # checked before touching the game
        import numba  # noqa: F401  (blurbaf's encoder)
    except ImportError:
        stop("Python module numba not found: see \"REQUIREMENTS\" in README.txt.")
    if not shutil.which("ffmpeg"):
        stop("ffmpeg not found: see \"REQUIREMENTS\" in README.txt.")
    check_update()
    prepare()
    menu()


if __name__ == "__main__":
    try:
        main()
    except PermissionError as e:                          # a protected file deeper in the game folder
        stop(f"{e}\n{ADMIN}\nThen run it again (an interrupted first run asks to run \"Uninstall.bat\" first).")
