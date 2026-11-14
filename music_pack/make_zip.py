#!/usr/bin/env python3
"""Build the community music pack: <JEUX>\\Blur_Music.zip, one folder "Blur_Music" (goes next to Blur.exe).
Contents: static\\ (bat files, README.txt), Music\\ (the original-tracks marker + an empty playlist), tools\\ (pack.py
and the repository's own make_music / blurbaf / blurpak + the musicctl plugin). No game file, no music.
usage: python music_pack/make_zip.py [OUT.zip]"""
import os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TOOLS = [os.path.join(HERE, "pack.py")] + [os.path.join(REPO, f) for f in ("make_music.py", "blurbaf.py", "blurpak.py", "blurloc.py")] \
    + [os.path.join(REPO, "mod_static", "amax", "plugins", "musicctl", "musicctl.lua")]
MUSIC = {"Music/1 - Blur original/About this folder.txt":
         "This folder stands for the game's own 23 race tracks. Leave it empty (no music file in it).\r\n",
         "Music/2 - My playlist/Put your music here.txt":
         "Put your music files here (mp3, wav, flac, ogg, m4a), then run \"Choose music.bat\".\r\n"
         "Create more folders next to this one for more playlists.\r\n",
         "tools/ffmpeg/Put ffmpeg.exe and ffprobe.exe here.txt":
         "Optional: copy ffmpeg.exe and ffprobe.exe (from the bin folder of an ffmpeg download) into this folder.\r\n"
         "Choose music.bat then finds them without any PATH setting.\r\n"}


def main(out):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(os.path.join(HERE, "static"))):   # CRLF: cmd misreads labels / goto with LF
            text = open(os.path.join(HERE, "static", f), "rb").read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            z.writestr("Blur_Music/" + f, text)
        for name, text in MUSIC.items():
            z.writestr("Blur_Music/" + name, text)
        for f in TOOLS:
            z.write(f, "Blur_Music/tools/" + os.path.basename(f))
    print(out, os.path.getsize(out) // 1024, "Ko")
    for n in zipfile.ZipFile(out).namelist():
        print(" ", n)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "..", "Blur_Music.zip"))
