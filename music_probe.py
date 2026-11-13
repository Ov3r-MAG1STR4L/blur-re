#!/usr/bin/env python3
"""Projet L probe (Blur_test only): can a Lua plugin choose the race track, and show a text in a race?
Builds the saved music selection (make_music) into Blur_test, then:
  - music_controller.dat: RaceStartScript plays track A when MusicType == 2, track B when MusicType == 3 (before its
    single play call). The plugin reaches it through the "Music" option (music_type): 0 first (MusicTypeGate threshold
    0.5: crossing it runs MusicTypeResetScript = stop + RaceStart 0.5 s later), then 2 or 3. If the engine clamps the
    option to 0 / 1, a random track plays instead of A / B.
  - hud.loc: a text under a hash of our own (TEXT_HASH); the plugin shows it with ChangeText(id, number) in the game's
    MP rank-up popup (GUI.mp_rank_up_ids, TimeLineActive "mp_rank_up"), then an absent string key.
  - amax plugin musicprobe (R3, or the 8 key: next step, in a race); log in memory: read_luamarks.py MPROBE.
probe 6 (2026-11-13): R3 / 8 = track + "Now playing" popup shown still 4 s (no game animation), 3 places, then back to normal.
usage: music_probe.py [--undo]   (Blur closed. --undo: hud.loc and plugins.lua back, plugin removed; the music is put
                                 back to normal by "Choisir la musique.bat")"""
import hashlib, json, os, shutil, sys
import blurloc, make_music as mm

TEXT_HASH = 0x0B1E0001                                  # probes 1-4: "Blur Music probe: hash text OK" (shown in game)
TITLE_HASH, TRACK_A_HASH, TRACK_B_HASH = 0x0B1E0002, 0x0B1E0003, 0x0B1E0004
HUD_LOC = os.path.join(mm.TEST, "gamedata", "xt", "loc", "hud.loc")
PLUGINS = os.path.join(mm.TEST, "amax", "plugins", "plugins.lua")
PLUGIN_DIR = os.path.join(mm.TEST, "amax", "plugins", "musicprobe")
BACKUP = os.path.join(mm.E, "music_probe_backup")
REQUIRE = 'require("musicprobe.musicprobe"),'
PLUGIN = r'''-- musicprobe: projet L probe (Blur_test only). R3 (or the 8 key) = next step, in a race.
local M = { info = { name = "MusicProbe", description = "Projet L probe", version = 0.1 } }
local TITLE_HASH, TRACK_A_HASH, TRACK_B_HASH = @TITLE@, @HA@, @HB@
local TRACK_A, TRACK_B = "@A@", "@B@"
local n_log, in_race, step, clock, pending, last_key = 0, false, 0, 0, nil, ""
local wrapped_frame, wrapped_msg = false, false
local orig_type = nil

local function log(text)
	n_log = n_log + 1
	MPROBE_BODY = (MPROBE_BODY or "") .. "\n" .. text
	MPROBE_ALL = "MPROBE#" .. n_log .. "#" .. MPROBE_BODY .. "#ALLEND"
end

local function set_music(v)
	local ok, t = pcall(Amax.Options)
	if not ok or type(t) ~= "table" then log("no options") return end
	t.music_type = v
	local ok2, err = pcall(Amax.UpdateAudioOptions, t)
	log("music_type = " .. tostring(v) .. (ok2 and "" or (" FAILED " .. tostring(err))))
end

-- probe 2 (display): clone a HUD template, hang it on a viewport root the HUD fills in every race (GUI.*_ids[1]),
-- write our hud.loc text (by hash) in it and in its text child, show it. Probe 1 (music_type 2 / 3) worked in game.
-- never create at load time a table a hook fills: AMAX's lua5.1.dll and the game's own Lua (Blur.exe) are two Lua
-- copies, an empty table of the first filled by the second crashes the game (probe 4 crash, 2026-11-13)
-- probe 3: the plugin's GUI is not the HUD's (inter_3d_ids empty in probe 2): each screen script probably runs in
-- its own environment. Functions the HUD script defines keep it: getfenv(HUD_xxx).GUI = the HUD's GUI.
local function keys(t, n)
	local out, k = {}, 0
	for key, v in pairs(t) do
		k = k + 1
		if k > n then break end
		out[#out + 1] = tostring(key) .. ":" .. type(v)
	end
	return table.concat(out, " ")
end
-- probe 4: probe 3 found GUI nil and the HUD_* functions in _G: the game sets the global GUI only while the HUD's own
-- code runs. (a) the global table HUD holds the viewport roots (HUD.ViewportId3d[vp], parent of the fan messages);
-- (b) fallback: wrap every global HUD_* function and keep the GUI it sees while it runs.
local captured_gui, wrapped_hud, logged_hud = nil, false, false
local function wrap_hud()
	if wrapped_hud then return end
	wrapped_hud = true
	local n = 0
	for name, f in pairs(_G) do
		if type(f) == "function" and type(name) == "string" and string.sub(name, 1, 4) == "HUD_" then
			n = n + 1
			_G[name] = function(...)
				local g = rawget(_G, "GUI")
				if captured_gui == nil and type(g) == "table" and g.inter_3d_ids then
					captured_gui = g
					log("GUI captured in " .. name .. ": keys " .. keys(g, 20))
				end
				return f(...)
			end
		end
	end
	log("wrapped " .. n .. " HUD_ functions")
end
local function hud_gui()
	if type(GUI) == "table" and GUI.inter_3d_ids then return GUI, "global GUI" end
	return captured_gui, captured_gui and "captured" or "not captured yet"
end

-- probe 5: the rank-up popup (centred, animated by the game) as "now playing": its title becomes our hud.loc text,
-- its rank icon is hidden, rank_info = the track name (hud.loc, our hashes); the track starts through music_type.
-- Popup layout (ui.json, hud_objects): mp_rank_up_dummy > mp_rank_up_rank (icon) > mp_rank_up_rank_num,
-- mp_rank_up_rank_title ("Rank Up", MP_RANK_UP), mp_rank_up_rank_info, mp_rank_up_clouds.
local function popup_ids()
	local gui = hud_gui()
	return gui and gui.mp_rank_up_ids
end

-- probe 6: the game's animation (timeline "mp_rank_up": 2 s, title zoom x10 in / x5 out in 0.25 s, track name
-- sliding 300 up, scrolling clouds) is hard to read in a race. No timeline here: the popup is shown still for
-- SHOW_TIME s (our timer), title smaller, track name bigger, clouds hidden, moved by dy. restore_popup undoes it all.
local SHOW_TIME, TITLE_SCALE, INFO_SCALE = 4.0, 0.6, 1.4
local hide_at, home = nil, nil                          -- home: original popup position (never a load-time table)

local function popup_parts(ids)
	return UIButtons.FindChildByName(ids.root, "mp_rank_up_rank_title"), UIButtons.FindChildByName(ids.root, "mp_rank_up_clouds")
end

local function now_playing(info_hash, dy)
	local ids = popup_ids()
	if not (ids and ids.root and ids.rank_info) then
		log("no rank-up popup (GUI captured: " .. tostring(captured_gui ~= nil) .. ")")
		return
	end
	local ok, err = pcall(function()
		local title, clouds = popup_parts(ids)
		if home == nil then
			local x, y, z = UIButtons.GetPosition(ids.root)
			home = { x, y, z }
			log("  popup home " .. tostring(x) .. " " .. tostring(y) .. " " .. tostring(z))
		end
		UIButtons.ChangePosition(ids.root, home[1], home[2] + dy, home[3])
		if title then
			UIButtons.ChangeText(title, TITLE_HASH)
			UIButtons.ChangeScale(title, TITLE_SCALE, TITLE_SCALE, 1.0)
		end
		if clouds then UIButtons.SetActive(clouds, false) end
		if ids.rank then UIButtons.SetActive(ids.rank, false) end
		UIButtons.ChangeText(ids.rank_info, info_hash)
		UIButtons.ChangeScale(ids.rank_info, INFO_SCALE, INFO_SCALE, 1.0)
		UIButtons.SetActive(ids.root, true)
		hide_at = clock + SHOW_TIME
	end)
	log("  now playing dy " .. dy .. " " .. (ok and "ok" or ("FAILED " .. tostring(err))))
end

local function hide_popup()
	hide_at = nil
	local ids = popup_ids()
	if ids and ids.root then pcall(UIButtons.SetActive, ids.root, false) end
end

local function restore_popup()                          -- a real rank-up looks as the game made it
	hide_popup()
	local ids = popup_ids()
	if not (ids and ids.root) then return end
	local ok, err = pcall(function()
		local title, clouds = popup_parts(ids)
		if title then
			UIButtons.ChangeText(title, UIText.MP_RANK_UP)
			UIButtons.ChangeScale(title, 1.0, 1.0, 1.0)
		end
		if clouds then UIButtons.SetActive(clouds, true) end
		if ids.rank then UIButtons.SetActive(ids.rank, true) end
		UIButtons.ChangeScale(ids.rank_info, 1.0, 1.0, 1.0)
		if home then UIButtons.ChangePosition(ids.root, home[1], home[2], home[3]) end
	end)
	log("  popup restored " .. (ok and "ok" or ("FAILED " .. tostring(err))))
end

local STEPS = {
	function() set_music(0) pending = { 45, 2 } now_playing(TRACK_A_HASH, 0) end,        -- 1: same place, still
	function() set_music(0) pending = { 45, 3 } now_playing(TRACK_B_HASH, 330) end,      -- 2: lower
	function() set_music(0) pending = { 45, 2 } now_playing(TRACK_A_HASH, -70) end,      -- 3: higher
	function() restore_popup() set_music(0) pending = { 45, orig_type or 1 } end,         -- 4: back to normal
}

local function next_step()
	step = step % #STEPS + 1
	log(string.format("t %.1f step %d", clock, step))
	pcall(function() UISystem.PlaySound(UIEnums.SoundEffect.MotorMashCount) end)
	local ok, err = pcall(STEPS[step])
	if not ok then log("step error " .. tostring(err)) end
end

local function tick()
	clock = clock + 1 / 60
	if not in_race then return end
	if not wrapped_hud and rawget(_G, "HUD_UpdateCombo") then wrap_hud() end   -- before the first key press
	if hide_at and clock >= hide_at then hide_popup() end
	if pending then
		pending[1] = pending[1] - 1
		if pending[1] <= 0 then local v = pending[2] pending = nil set_music(v) end
	end
	local ok, key = pcall(UIButtons.GetKeyInput)
	key = ok and tostring(key or "") or ""
	if key ~= last_key then
		last_key = key
		if key ~= "" then log("key " .. key) end
		if key == "CMN_8" then next_step() end
	end
end

local function on_message(msg)
	if not in_race then return end
	for k, v in pairs(UIEnums.Message) do
		if v == msg and k == "RightThumb" then next_step() end
	end
end

function M.GoScreen(screen, _opts)
	if not wrapped_frame and type(FrameUpdate_Wrapper) == "function" then
		wrapped_frame = true
		local org = FrameUpdate_Wrapper
		FrameUpdate_Wrapper = function(...) local r = org(...) pcall(tick) return r end
	end
	if not wrapped_msg and type(MessageUpdate_Wrapper) == "function" then
		wrapped_msg = true
		local org = MessageUpdate_Wrapper
		MessageUpdate_Wrapper = function(msg, ...) pcall(on_message, msg) return org(msg, ...) end
	end
	local s = string.lower(tostring(screen))
	local race = s == "ingame\\hud.lua" or s == "ingame\\paused.lua"
	if race and not in_race then
		wrapped_hud, captured_gui, home, hide_at = false, nil, nil, nil   -- the HUD reloads each race: new functions, GUI, popup
		local ok, t = pcall(Amax.Options)
		orig_type = ok and type(t) == "table" and t.music_type or nil
		log("race, music_type " .. tostring(orig_type) .. ", UIText.HUD_POS " .. tostring(UIText and UIText.HUD_POS)
			.. " (" .. type(UIText and UIText.HUD_POS) .. "), tracks A " .. TRACK_A .. " B " .. TRACK_B)
	end
	if not race and in_race and orig_type ~= nil and pending then pending = nil set_music(orig_type) end   -- left mid-test
	in_race = race
end
M.PushScreen = M.GoScreen

function M.init() return true end
return M
'''


def track_objects(j, ks):
    """Sound object index of InGameMusic<k>: the stop script lists them in order ([0x1000, obj << 16, 1] per track)."""
    _, code = j.code("InGameLicensedMusicStopScript")
    objs = [code[p + 1] >> 16 for p, op in mm.script_ops(code) if op == 0x1000]
    return [objs[k] for k in ks]


def wave_of(j, k):
    s = j.find(60, "InGameMusic%02d" % k)
    w = j.w[s + 3]
    return bytes(j.names[w:j.names.index(b"\0", w)]).decode()


def probe_music_type(j, obj_a, obj_b):
    """RaceStartScript: if MusicType == 2 play obj_a, == 3 play obj_b, just before its single play call."""
    mt = mm.obj_index(j, "MusicType")
    s, rs = j.code("RaceStartScript")
    calls = [p for p, op in mm.script_ops(rs) if op == 0x1200]
    assert len(calls) == 1, calls
    ins = calls[0]
    new = list(rs)
    for p, op in mm.script_ops(rs):                      # jumps past the insertion point move with it
        if op == 0x1101 and rs[p + 1] >= ins:
            new[p + 1] = rs[p + 1] + 10
    a = len(rs) + 10
    new[ins:ins] = [0x1317, mt << 16, mm.f32(2), 0x1101, a, 0x1317, mt << 16, mm.f32(3), 0x1101, a + 4]
    new += [0x1000, obj_a << 16, 0, 0x1202, 0x1000, obj_b << 16, 0, 0x1202]
    j.set_code(s, rs, new)
    return mt


def undo():
    for name, dst in (("hud.loc", HUD_LOC), ("plugins.lua", PLUGINS)):
        src = os.path.join(BACKUP, name)
        if os.path.exists(src):
            os.chmod(dst, 0o666)
            shutil.copy2(src, dst)
            print("remis :", dst)
    shutil.rmtree(PLUGIN_DIR, ignore_errors=True)
    if os.path.exists(os.path.join(BACKUP, "ACTIVE")):
        os.remove(os.path.join(BACKUP, "ACTIVE"))         # "Tester le mod.bat" reshuffles again
    print("plugin musicprobe retiré ; relance « Choisir la musique.bat » pour la musique normale.")


def main():
    if "--undo" in sys.argv:
        return undo()
    last = json.load(open(os.path.join(mm.MUSIC_DIR, "derniere_selection.json"), encoding="utf-8"))
    print(mm.build(last["dossiers"], effects=last["effets"], pcm16=last["haute_qualite"]))
    path = os.path.join(mm.OUT, "audio", "dat", "music_controller.dat")
    j = mm.Jboa(open(path, "rb").read())
    try:
        objs = track_objects(j, (23, 24))
        ks = (23, 24)
    except IndexError:                                   # original tracks only
        objs, ks = track_objects(j, (0, 1)), (0, 1)
    names = [wave_of(j, k) for k in ks]
    files = chosen_files(last["dossiers"])               # display names: the added tracks' file names, in build order
    titles = [os.path.splitext(files[k - 23])[0] if k >= 23 else names[i] for i, k in enumerate(ks)]
    mt = probe_music_type(j, *objs)
    open(path, "wb").write(j.build())
    print(f"sonde graphe : MusicType (objet {mt}) = 2 -> {names[0]} ; = 3 -> {names[1]}")
    mm.install()
    os.makedirs(BACKUP, exist_ok=True)
    for name, src in (("hud.loc", HUD_LOC), ("plugins.lua", PLUGINS)):
        if not os.path.exists(os.path.join(BACKUP, name)):
            shutil.copy2(src, os.path.join(BACKUP, name))
    d = blurloc.parse_raw(open(os.path.join(BACKUP, "hud.loc"), "rb").read())
    blurloc.add_text(d, "BLURMUSIC_NOW_PLAYING", TITLE_HASH, {"en": "Now playing", "fr": "En écoute"})
    blurloc.add_text(d, "BLURMUSIC_TRACK_A", TRACK_A_HASH, {"en": titles[0]})
    blurloc.add_text(d, "BLURMUSIC_TRACK_B", TRACK_B_HASH, {"en": titles[1]})
    os.chmod(HUD_LOC, 0o666)
    open(HUD_LOC, "wb").write(blurloc.build(d))
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    lua = (PLUGIN.replace("@TITLE@", str(TITLE_HASH)).replace("@HA@", str(TRACK_A_HASH)).replace("@HB@", str(TRACK_B_HASH))
           .replace("@A@", names[0]).replace("@B@", names[1]))
    open(os.path.join(PLUGIN_DIR, "musicprobe.lua"), "w", encoding="utf-8", newline="\n").write(lua)
    lst = open(PLUGINS, encoding="utf-8").read()
    if REQUIRE.rstrip(",") not in lst:
        k = lst.rstrip().rfind("}")
        os.chmod(PLUGINS, 0o666)
        open(PLUGINS, "w", encoding="utf-8", newline="\n").write(lst[:k].rstrip() + "\n\t" + REQUIRE + "\n}\n")
    open(os.path.join(BACKUP, "ACTIVE"), "w").write("music_probe\n")   # music_menu --remelanger keeps the probe
    print("installé dans", mm.TEST, ": hud.loc (Now playing + 2 titres :", titles, "), plugin musicprobe")


def chosen_files(folders):
    """File names of the added tracks, in make_music.build's order (sorted per folder, same content counted once)."""
    files, seen = [], set()
    for d in folders:
        for f in sorted(x for x in os.listdir(d) if x.lower().endswith(mm.AUDIO_EXT)):
            key = hashlib.sha1(open(os.path.join(d, f), "rb").read()).hexdigest()
            if key not in seen:
                seen.add(key)
                files.append(f)
    return files


if __name__ == "__main__":
    main()
