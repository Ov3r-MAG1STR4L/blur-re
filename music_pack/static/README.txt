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
  - Python 3 with numpy and numba, and ffmpeg (used to convert your music to the game's format).
    "Choose music.bat" offers to install them for you (with winget, Windows 10/11).


INSTALL (step by step)
----------------------
  1. Close Blur.
  2. Unzip the "Blur_Music" folder INTO the Blur folder, next to Blur.exe.
     Example: C:\Program Files (x86)\Activision\Blur(TM)\Blur_Music\
  3. Put your music in the "Music" folder. Each sub-folder is a playlist:
        Music\1 - Blur original\    = the game's own 23 race tracks (leave it as it is)
        Music\2 - My playlist\      = put your files here
     You can create as many folders as you like (e.g. "3 - Rock", "4 - Electro").
  4. Double-click "Choose music.bat" and accept the administrator prompt
     (the Blur folder is protected by Windows).
       - If Python or ffmpeg are missing, answer Y to install them, then run the .bat again.
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
  Do NOT delete the "backup" folder while the pack is installed.


HOW IT WORKS (for the curious)
------------------------------
  Blur reads its files from signed archives (cache\root.pak, cache\root_streaming.pak) and only
  looks at loose files that are NOT in an archive. So on the first run the pack unpacks these two
  archives from YOUR game into the game folder and renames them to .pak.off. Then it rebuilds the
  race music bank (audio\ingamemusic.baf), the music controller and the two final mix graphs
  (audio\dat\*.dat). The next-track key is an AMAX Lua plugin (amax\plugins\musicctl).
  No file from the game is included in this pack.


TROUBLESHOOTING
---------------
  "Blur is running": close the game (check the task manager), then try again.
  "A previous installation was interrupted": run "Uninstall.bat", then "Choose music.bat".
  "cache\root.pak not found": another mod already unpacked the game; this pack cannot be combined
      with it. Uninstall the other mod first.
  No music in race: check the in-game audio options (Music must not be off).
  The skip key does nothing: AMAX must be installed; skips are limited to one every 2 seconds.
