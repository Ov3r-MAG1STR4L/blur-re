BLUR MUSIC PACK
===============

Play YOUR OWN music during races in Blur (PC), and:
  - skip to the next track during a race:
      controller: press L3 (left stick click) twice quickly
      keyboard (French AZERTY layout): the 9 / ç key or the 0 / à key of the top row
      (2 seconds minimum between two skips; a short sound confirms the skip)
  - shuffle: every track plays once in a random order, then the order repeats; each game session
    starts at a random point of that order;
  - choose how the game's effects change the sound (power-ups, crashes, wrecked, low health):
      on      = as in the original game
      partial = softer effects
      off     = no effect on the sound at all

No music is included: you bring your own files (mp3, wav, flac, ogg, m4a).


REQUIREMENTS
------------
  - Blur for PC. The next-track key needs AMAX (amax folder in the game folder).
  - About 3 GB of free disk space (the game's audio is unpacked once, see "How it works").
  - Python 3 and ffmpeg (used to convert your music to the game's format). Install them once:
      Python 3: https://www.python.org/downloads/  (tick "Add python.exe to PATH" in the installer)
      ffmpeg:   in a command prompt, type   winget install Gyan.FFmpeg
                (or download it from https://www.gyan.dev/ffmpeg/builds/ and add its "bin" folder
                to PATH)
    Then close and reopen any open command prompt. The Python modules numpy and numba are installed
    by "Choose music.bat" itself (with pip, Python's own installer).


INSTALL (step by step)
----------------------
  1. Close Blur.
  2. Unzip the "Blur_Music" folder INTO the Blur folder, next to Blur.exe.
     Example: C:\Program Files (x86)\Activision\Blur(TM)\Blur_Music\
  3. Put your music in the "Music" folder. Each sub-folder is a playlist:
        Music\1 - Blur original\    = the game's own 23 race tracks (leave it as it is)
        Music\2 - My playlist\      = put your files here
     You can create as many folders as you like (e.g. "3 - Rock", "4 - Electro").
  4. Double-click "Choose music.bat".
       - If Blur is in a protected folder (e.g. C:\Program Files (x86)\...), Windows does not let it
         write there: right-click "Choose music.bat" and choose "Run as administrator" instead.
         The window tells you when this is needed. Same for "Uninstall.bat".
       - The FIRST run unpacks the game's files: it takes a few minutes. Do not close the window.
  5. Answer the two questions:
       - which playlists, by number (several at once: "1 2" mixes the game's tracks with yours);
       - the game effects: 1 on, 2 partial, 3 off.
     Each new track is converted once (about 10 to 30 s per track), then kept for next time.
  6. Play: start Blur as you usually do (Blur.exe, TextMod or any other launcher). Nothing else
     to run: each session starts at a random point of the shuffled order. A brand new order is
     drawn each time you run "Choose music.bat".

Changing playlists or effects, or a new shuffled order: close Blur, run "Choose music.bat" again.
Added a track to a folder: same thing, run "Choose music.bat" again.


UNINSTALL
---------
  Close Blur and double-click "Uninstall.bat": every file the pack added is removed, every file it
  replaced is put back, and the game is exactly as before. Then you can delete the Blur_Music folder.
  Do NOT delete the "Blur_Music_backup" folder (in the Blur folder) while the pack is installed:
  Uninstall.bat needs it.


UPDATING THE PACK
-----------------
  Close Blur, then replace the Blur_Music folder with the new one (keep your "Music" folder).
  Your installation stays in "Blur_Music_backup", next to it: no need to uninstall first.
  Run "Choose music.bat" again.


HOW IT WORKS (for the curious)
------------------------------
  Blur reads its files from signed archives (cache\root.pak, root_streaming.pak, gamedata.pak) and
  only looks at loose files that are NOT in an archive. So on the first run the pack unpacks these
  three archives from YOUR game into the game folder and renames them to .pak.off. Then it rebuilds
  the race music bank (audio\ingamemusic.baf), the music controller and the two final mix graphs
  (audio\dat\*.dat), and adds the track titles to gamedata\xt\loc\hud.loc. The next-track key and
  the "now playing" banner are an AMAX Lua plugin (amax\plugins\musicctl).
  No file from the game is included in this pack.


TROUBLESHOOTING
---------------
  "Blur is running": close the game (check the task manager), then try again.
  "A previous installation was interrupted": run "Uninstall.bat", then "Choose music.bat".
  "Was it an older Blur Music install?": the game archives were set aside (renamed .pak.off).
      Answer Y if an older version of this pack did it (older versions kept their backup inside the
      Blur_Music folder, so replacing that folder lost it): the pack puts the archives back, takes
      over the files that older install left, and continues normally (Uninstall.bat then removes
      them too). Answer N if another mod did it, and uninstall that mod first: both cannot be combined.
  "cache\root.pak not found: cannot install": the game archive is missing; repair or reinstall Blur.
  No music in race: check the in-game audio options (Music must not be off).
  The skip key does nothing: AMAX must be installed; skips are limited to one every 2 seconds.
