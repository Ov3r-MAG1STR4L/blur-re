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
probe 7 (2026-11-13): R3 / 8 = track A / B + our banner (bottom-left, flickers on, 3.5 s, slides left), then back to normal.
usage: music_probe.py [--undo]   (Blur closed. --undo: hud.loc and plugins.lua back, plugin removed; the music is put
                                 back to normal by "Choisir la musique.bat")"""
import hashlib, json, os, shutil, sys
import blurloc, make_music as mm

TEXT_HASH = 0x0B1E0001                                  # probes 1-4: "Blur Music probe: hash text OK" (shown in game)
TITLE_HASH, TRACK_A_HASH, TRACK_B_HASH = 0x0B1E0002, 0x0B1E0003, 0x0B1E0004
GRID = [(x, y, 0x0B1E0100 + k) for k, (x, y) in enumerate((x, y) for y in (0, 10, 20, 30, 40)   # HUD units (diag)
                                                       for x in (0, 20, 40, 60, 80))]
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

-- never create at load time a table a hook fills: AMAX's lua5.1.dll and the game's own Lua (Blur.exe) are two Lua
-- copies, an empty table of the first filled by the second crashes the game (probe 4 crash, 2026-11-13).
-- Probes 2-6 (CONNAISSANCES, projet L): GUI is only set while the HUD's code runs; the global HUD table holds the
-- viewport roots (HUD.ViewportId[1]); the rank-up popup works but its game animation is hard to read in a race.

-- probe 7: our own banner (player's design, 2026-11-13), made of two HUD templates: Pos_Backing (the black gradient
-- behind "Position", texture hud_grad) and Position_Title (the blue "Position" label, style Secondary, Main_1), its
-- number children hidden. Bottom-left; lights up like a failing lamp, holds HOLD s, slides left while fading out.
-- Units: the HUD's panel units (Position_Title row = 1.5 high). Tuning knobs below; everything is logged.
-- ChangePosition works in HUD units, as sizes (position diagnostic 2026-11-13: the HUD's own "Position" label is at
-- 1.0, -0.25 under HUD.ViewportId3d; 'Position' = 4.94 units long, about 18 px of a 1552 px wide screenshot). Origin
-- = the HUD's top-left (where the Position panel starts), y down; the screen is about 85 x 47 units there. A moved
-- gadget shows one frame at its default place first (the "flash").
-- Measured on screen (grid + banner, 2026-11-13, parent HUD.ViewportId3d): x = 1 unit ~ 17.75 px of a 1552 px wide
-- screenshot, origin at the Position panel (~122 px); y = 36 drew the banner at ~178 px. Start: bottom-left (player's
-- red circle), y scale estimated; keys 1/2 (y -/+10), 5/6 (y -/+2), 3/4 (x -/+1) move it live, values logged.
local POS_X, POS_Y = -6.5, 205.0
local TEXT_DX, TEXT_DY = 1.0, -0.5      -- text inside the banner (as Position_Title vs Pos_Backing in the HUD)
local TEXT_SCALE = 1.25                 -- a bit bigger than "Position"
local WIDTH_K, WIDTH_PAD, WIDTH_MIN = 1.0, 2.5, 6.0   -- backing width = text length * K * scale + pad
local HOLD, SLIDE, SLIDE_DIST = 3.5, 0.6, 14.0
local FLICKER = { 0.0, 0.0, 0.05, 0.7, 0.10, 0.05, 0.18, 0.9, 0.22, 0.1, 0.35, 0.6, 0.40, 0.0, 0.48, 1.0, 0.53, 0.3, 0.60, 1.0 }

local banner = nil                      -- created in a hook (never at load time)

local function banner_build()
	-- HUD.ViewportId3d: the parent of the HUD's own "Position" label (diag); HUD.ViewportId (origin at the screen
	-- centre) showed nothing of ours but a small rectangle at the centre (2026-11-13)
	local parent = type(HUD) == "table" and type(HUD.ViewportId3d) == "table" and (HUD.ViewportId3d[1] or HUD.ViewportId3d[0])
	if not parent then log("banner: no HUD.ViewportId") return nil end
	local b = {}
	b.bg = UIButtons.CloneXtGadgetByName("hud_objects", "Pos_Backing")
	b.txt = UIButtons.CloneXtGadgetByName("hud_objects", "Position_Title")
	for _, child in ipairs({ "Position_Amount", "Position_AmountOf" }) do
		local c = UIButtons.FindChildByName(b.txt, child)
		if c then UIButtons.SetActive(c, false) end
	end
	UIButtons.SetParent(b.bg, parent, UIEnums.Justify.BottomLeft)
	UIButtons.SetParent(b.txt, parent, UIEnums.Justify.BottomLeft)
	UIButtons.ChangeScale(b.txt, TEXT_SCALE, TEXT_SCALE, 1.0)
	local w, h = UIButtons.GetSize(b.bg)
	b.h = h
	local vw, vh = UIButtons.GetSize(parent)
	local dx0, dy0, dz0 = UIButtons.GetPosition(b.bg)
	b.z = dz0 or 0.0                                  -- keep z: forcing 0 hid everything (grid, 2026-11-13)
	log("banner default position " .. tostring(dx0) .. ", " .. tostring(dy0) .. ", z " .. tostring(dz0))
	b.y = POS_Y
	log("viewport size " .. tostring(vw) .. " x " .. tostring(vh) .. ", banner y " .. tostring(b.y))
	log("banner built: bg " .. tostring(b.bg) .. " size " .. tostring(w) .. " x " .. tostring(h) .. ", txt " .. tostring(b.txt)
		.. ", 'Position' length " .. tostring(UIButtons.GetStaticTextLength(b.txt)))
	return b
end

local function banner_place(dx, alpha)
	UIButtons.ChangePosition(banner.bg, POS_X + dx, POS_Y, banner.z)
	UIButtons.ChangePosition(banner.txt, POS_X + dx + TEXT_DX, POS_Y + TEXT_DY, banner.z)
	UIButtons.ChangeAlpha(banner.bg, alpha)
	pcall(UIButtons.SetAlphaIntensity, banner.bg, alpha, alpha)   -- backing: IntensityAsAlpha, ChangeAlpha alone did nothing
	UIButtons.ChangeAlpha(banner.txt, alpha)
end

local function now_playing(info_hash)
	local ok, err = pcall(function()
		banner = banner or banner_build()
		if not banner then return end
		UIButtons.ChangeText(banner.txt, info_hash)
		local len = UIButtons.GetStaticTextLength(banner.txt) or 0
		local w = math.max(WIDTH_MIN, len * WIDTH_K * TEXT_SCALE + WIDTH_PAD)
		UIButtons.ChangeSize(banner.bg, w, banner.h)
		banner.t0 = clock
		banner.hash = info_hash
		banner_place(0, 0.0)
		UIButtons.SetActive(banner.bg, true)
		UIButtons.SetActive(banner.txt, true)
		log("  banner: text length " .. tostring(len) .. ", backing width " .. tostring(w))
	end)
	if not ok then log("  banner FAILED " .. tostring(err)) end
end

local function banner_hide()
	if banner and banner.t0 then
		pcall(UIButtons.SetActive, banner.bg, false)
		pcall(UIButtons.SetActive, banner.txt, false)
		banner.t0 = nil
	end
end

local function banner_tick()                              -- called every frame
	if not (banner and banner.t0) then return end
	local t = clock - banner.t0
	local on = FLICKER[#FLICKER - 1]
	local ok = pcall(function()
		if t < on then                                    -- failing lamp: last key at or before t
			local a = 0.0
			for i = 1, #FLICKER - 1, 2 do
				if FLICKER[i] <= t then a = FLICKER[i + 1] end
			end
			banner_place(0, a)
		elseif t < on + HOLD then
			banner_place(0, 1.0)
		elseif t < on + HOLD + SLIDE then
			local p = (t - on - HOLD) / SLIDE
			banner_place(-SLIDE_DIST * p * p, 1.0 - p)    -- accelerates to the left, fades out
		else
			banner_hide()
		end
	end)
	if not ok then banner_hide() end
end

-- calibration grid (player's idea, 2026-11-13): probe 7 put the banner nowhere and flashed something at the centre,
-- so the ChangePosition origin is not known. GRID labels, each showing its own "x,y", are placed with ChangePosition
-- under HUD.ViewportId[1] (justify TopLeft); a screenshot gives the mapping. The default position is logged too.
local GRID = { @GRID@ }
local grid, grid_auto = nil, false                       -- grid created in a hook; shown at each race start

local function grid_toggle()
	if grid then
		for _, id in ipairs(grid) do pcall(UIButtons.SetActive, id, false) end
		grid = nil
		log("grid off")
		return
	end
	-- HUD.ViewportId3d: the parent of the HUD's own "Position" label (diag); HUD.ViewportId (origin at the screen
	-- centre) showed nothing of ours but a small rectangle at the centre (2026-11-13)
	local parent = type(HUD) == "table" and type(HUD.ViewportId3d) == "table" and (HUD.ViewportId3d[1] or HUD.ViewportId3d[0])
	if not parent then log("grid: no HUD.ViewportId") return end
	grid = {}
	for i = 1, #GRID, 3 do
		local ok, err = pcall(function()
			local id = UIButtons.CloneXtGadgetByName("hud_objects", "Position_Title")
			for _, child in ipairs({ "Position_Amount", "Position_AmountOf" }) do
				local c = UIButtons.FindChildByName(id, child)
				if c then UIButtons.SetActive(c, false) end
			end
			UIButtons.SetParent(id, parent, UIEnums.Justify.TopLeft)
			local x0, y0, z0 = UIButtons.GetPosition(id)
			if i == 1 then
				local x, y = x0, y0
				log("grid: default position after SetParent " .. tostring(x) .. ", " .. tostring(y))
			end
			if i == 1 then log("grid: default z " .. tostring(z0) .. " (label 1 stays at the default position)")
			else UIButtons.ChangePosition(id, (x0 or 0) + GRID[i], (y0 or 0) + GRID[i + 1], z0 or 0) end
			UIButtons.ChangeText(id, GRID[i + 2])
			UIButtons.SetActive(id, true)
			grid[#grid + 1] = id
		end)
		if not ok then log("grid FAILED " .. tostring(err)) break end
	end
	log("grid on: " .. #grid .. " labels")
end

-- position diagnostic (2026-11-13): the grid and the banner flash then vanish. Hypothesis: ChangePosition starts a
-- move (tween) instead of placing; the HUD sometimes passes a 5th argument true. At each race start, two test labels
-- are moved by (+60, +40): A plain, B with true; their positions are logged every 6 frames for 3 s, with the HUD's own
-- "Position" label for reference (screen spot known from screenshots). Nothing to look at: read the log.
local diag = nil

local function pos(id)
	local ok, x, y, z = pcall(UIButtons.GetPosition, id)
	if not ok then return "?" end
	return string.format("%.1f,%.1f,%.2f", x or -1, y or -1, z or -1)
end

local function diag_start()
	local vp = HUD.ViewportId[1] or HUD.ViewportId[0]
	local ok, err = pcall(function()
		local w, h = UIButtons.GetSize(vp)
		log("diag: viewport " .. tostring(vp) .. " size " .. tostring(w) .. " x " .. tostring(h) .. " pos " .. pos(vp))
		for _, root in ipairs({ vp, HUD.ViewportId3d[1] or HUD.ViewportId3d[0] }) do
			local p = UIButtons.FindChildByName(root, "Position_Title")
			log("diag: HUD Position_Title under " .. tostring(root) .. " = " .. tostring(p) .. (p and (" pos " .. pos(p)) or ""))
		end
		local d = { t0 = clock, n = 0 }
		for k, flag in ipairs({ false, true }) do
			local id = UIButtons.CloneXtGadgetByName("hud_objects", "Position_Title")
			for _, child in ipairs({ "Position_Amount", "Position_AmountOf" }) do
				local c = UIButtons.FindChildByName(id, child)
				if c then UIButtons.SetActive(c, false) end
			end
			UIButtons.SetParent(id, vp, UIEnums.Justify.TopLeft)
			UIButtons.ChangeText(id, TRACK_B_HASH)
			UIButtons.SetActive(id, true)
			local x0, y0, z0 = UIButtons.GetPosition(id)
			log("diag: label " .. k .. " default " .. pos(id))
			if flag then
				UIButtons.ChangePosition(id, x0 + 60, y0 + 40 * k, z0, true)
			else
				UIButtons.ChangePosition(id, x0 + 60, y0 + 40 * k, z0)
			end
			d[k] = id
		end
		diag = d
	end)
	if not ok then log("diag FAILED " .. tostring(err)) end
end

local function diag_tick()
	if not diag then return end
	diag.n = diag.n + 1
	if diag.n % 6 == 0 then
		log(string.format("diag t+%.2f A %s B %s", clock - diag.t0, pos(diag[1]), pos(diag[2])))
	end
	if clock - diag.t0 > 3.0 then
		log("diag done")
		diag = nil
	end
end

local STEPS = {
	function() grid_toggle() end,                                                -- 1: calibration grid on
	function() grid_toggle() end,                                                -- 2: grid off
	function() set_music(0) pending = { 45, 2 } now_playing(TRACK_A_HASH) end,   -- 3: track A
	function() set_music(0) pending = { 45, 3 } now_playing(TRACK_B_HASH) end,   -- 4: track B
	function() banner_hide() set_music(0) pending = { 45, orig_type or 1 } end,  -- 5: back to normal
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
	banner_tick()
	if grid_auto and type(HUD) == "table" and type(HUD.ViewportId) == "table" then grid_auto = false grid_toggle() end
	diag_tick()
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
		local move = ({ CMN_1 = { 0, -10 }, CMN_2 = { 0, 10 }, CMN_5 = { 0, -2 }, CMN_6 = { 0, 2 }, CMN_3 = { -1, 0 }, CMN_4 = { 1, 0 } })[key]
		if move then
			POS_X, POS_Y = POS_X + move[1], POS_Y + move[2]
			log(string.format("tune POS_X %.1f POS_Y %.1f", POS_X, POS_Y))
			now_playing((banner and banner.hash) or TRACK_A_HASH)
		end
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
		banner, grid, grid_auto, diag = nil, nil, true, nil   -- the HUD reloads each race: new gadgets; grid shown at once
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
    for gx, gy, gh in GRID:
        blurloc.add_text(d, f"BLURMUSIC_GRID_{gh & 0xFF}", gh, {"en": f"{gx},{gy}"})
    os.chmod(HUD_LOC, 0o666)
    open(HUD_LOC, "wb").write(blurloc.build(d))
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    lua = (PLUGIN.replace("@TITLE@", str(TITLE_HASH)).replace("@HA@", str(TRACK_A_HASH)).replace("@HB@", str(TRACK_B_HASH))
           .replace("@GRID@", ", ".join(f"{gx}, {gy}, {gh}" for gx, gy, gh in GRID))
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
