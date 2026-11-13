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
probe 2 (2026-11-13): the plugin steps now try displays (HUD templates cloned on GUI.*_ids roots).
usage: music_probe.py [--undo]   (Blur closed. --undo: hud.loc and plugins.lua back, plugin removed; the music is put
                                 back to normal by "Choisir la musique.bat")"""
import json, os, shutil, sys
import blurloc, make_music as mm

TEXT_HASH = 0x0B1E0001
TEXT_KEY = "BLURMUSIC_PROBE_TEXT"
TEXTS = {"en": "Blur Music probe: hash text OK", "fr": "Sonde Blur Music : texte par hash OK"}
HUD_LOC = os.path.join(mm.TEST, "gamedata", "xt", "loc", "hud.loc")
PLUGINS = os.path.join(mm.TEST, "amax", "plugins", "plugins.lua")
PLUGIN_DIR = os.path.join(mm.TEST, "amax", "plugins", "musicprobe")
BACKUP = os.path.join(mm.E, "music_probe_backup")
REQUIRE = 'require("musicprobe.musicprobe"),'
PLUGIN = r'''-- musicprobe: projet L probe (Blur_test only). R3 (or the 8 key) = next step, in a race.
local M = { info = { name = "MusicProbe", description = "Projet L probe", version = 0.1 } }
local TEXT_HASH = @HASH@
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
local made = {}
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

local function first(t)
	if type(t) ~= "table" then return nil end
	return t[1] or t[0]                                  -- viewport loop: 1-based or 0-based, not known
end

local function show(template, child, parent_table)
	wrap_hud()
	local hud = rawget(_G, "HUD")
	if not logged_hud and type(hud) == "table" then
		logged_hud = true
		log("HUD keys " .. keys(hud, 40))
		log("HUD.ViewportId3d " .. (type(hud.ViewportId3d) == "table" and keys(hud.ViewportId3d, 6) or tostring(hud.ViewportId3d))
			.. " | HUD.ViewportId " .. (type(hud.ViewportId) == "table" and keys(hud.ViewportId, 6) or tostring(hud.ViewportId)))
	end
	local gui, how = hud_gui()
	local parent, from = nil, ""
	if parent_table == "ViewportId3d" or parent_table == "ViewportId" then
		parent, from = type(hud) == "table" and first(hud[parent_table]), "HUD." .. parent_table
	else
		parent, from = gui and first(gui[parent_table]), "GUI." .. parent_table .. " (" .. how .. ")"
	end
	log(template .. ": parent " .. from .. " = " .. tostring(parent))
	if parent == nil then return end
	local ok, err = pcall(function()
		local id = UIButtons.CloneXtGadgetByName("hud_objects", template)
		log("  clone " .. tostring(id))
		made[#made + 1] = id
		UIButtons.SetParent(id, parent, UIEnums.Justify.TopLeft)
		pcall(UIButtons.ChangeText, id, TEXT_HASH)
		if child then
			local c = UIButtons.FindChildByName(id, child)
			log("  child " .. child .. " " .. tostring(c))
			if c then UIButtons.ChangeText(c, TEXT_HASH) end
		end
		UIButtons.SetActive(id, true)
	end)
	log("  " .. (ok and "ok" or ("FAILED " .. tostring(err))))
end

local function hide_all()
	for _, id in ipairs(made) do pcall(UIButtons.SetActive, id, false) end
	log("hidden " .. #made)
	made = {}
end

local STEPS = {
	function() show("Points_Title", "Points_Amount", "ViewportId3d") end,       -- 1: HUD global table
	function() show("Position_Title", "Position_Amount", "ViewportId") end,     -- 2
	function() show("Points_Title", "Points_Amount", "inter_3d_ids") end,       -- 3: captured GUI
	function() show("Position_Title", "Position_Amount", "safe_2d_ids") end,    -- 4
	function() show("Checkpoint_Title", nil, "ViewportId3d") end,               -- 5
	function()                                                                  -- 6: rank-up popup, HUD's GUI
		local gui = hud_gui()
		local ids = gui and gui.mp_rank_up_ids
		log("rank-up ids " .. tostring(ids) .. " root " .. tostring(ids and ids.root) .. " info " .. tostring(ids and ids.rank_info))
		if ids and ids.root and ids.rank_info then
			local ok, err = pcall(function()
				UIButtons.ChangeText(ids.rank_info, TEXT_HASH)
				UIButtons.SetActive(ids.root, true)
				UIButtons.TimeLineActive("mp_rank_up", true, 0.0)
			end)
			log("  rank-up popup " .. (ok and "ok" or ("FAILED " .. tostring(err))))
		end
	end,
	function() hide_all() end,                                                  -- 7
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
		local ok, t = pcall(Amax.Options)
		orig_type = ok and type(t) == "table" and t.music_type or nil
		log("race, music_type " .. tostring(orig_type) .. ", UIText.HUD_POS " .. tostring(UIText and UIText.HUD_POS)
			.. " (" .. type(UIText and UIText.HUD_POS) .. "), tracks A " .. TRACK_A .. " B " .. TRACK_B)
	end
	if not race and in_race then hide_all() end
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
    mt = probe_music_type(j, *objs)
    open(path, "wb").write(j.build())
    print(f"sonde graphe : MusicType (objet {mt}) = 2 -> {names[0]} ; = 3 -> {names[1]}")
    mm.install()
    os.makedirs(BACKUP, exist_ok=True)
    for name, src in (("hud.loc", HUD_LOC), ("plugins.lua", PLUGINS)):
        if not os.path.exists(os.path.join(BACKUP, name)):
            shutil.copy2(src, os.path.join(BACKUP, name))
    d = blurloc.parse_raw(open(os.path.join(BACKUP, "hud.loc"), "rb").read())
    blurloc.add_text(d, TEXT_KEY, TEXT_HASH, TEXTS)
    os.chmod(HUD_LOC, 0o666)
    open(HUD_LOC, "wb").write(blurloc.build(d))
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    lua = PLUGIN.replace("@HASH@", str(TEXT_HASH)).replace("@A@", names[0]).replace("@B@", names[1])
    open(os.path.join(PLUGIN_DIR, "musicprobe.lua"), "w", encoding="utf-8", newline="\n").write(lua)
    lst = open(PLUGINS, encoding="utf-8").read()
    if REQUIRE.rstrip(",") not in lst:
        k = lst.rstrip().rfind("}")
        os.chmod(PLUGINS, 0o666)
        open(PLUGINS, "w", encoding="utf-8", newline="\n").write(lst[:k].rstrip() + "\n\t" + REQUIRE + "\n}\n")
    open(os.path.join(BACKUP, "ACTIVE"), "w").write("music_probe\n")   # music_menu --remelanger keeps the probe
    print("installé dans", mm.TEST, ": hud.loc (clé", TEXT_KEY, hex(TEXT_HASH) + "), plugin musicprobe")


if __name__ == "__main__":
    main()
