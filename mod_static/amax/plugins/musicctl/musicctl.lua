-- MusicCtl: race music driven by the plugin, with a "now playing" banner (projet I + L; also in the community pack).
--
-- How it works (CONNAISSANCES, projet L, all confirmed in game in Blur_test 2026-11-13):
--  - The audio graph (music_controller.dat, make_music.position_start) starts the shuffle at position p when the
--    "Music" option (music_type) is p + 2, then goes on in order by itself. The engine passes any value to the graph.
--  - TRACKS (written by make_music.write_titles) = {hud.loc hash of the title, seconds} per shuffle position, so the
--    plugin always knows which track plays: it picks a random start, follows the track ends with a timer, and shows
--    the title in a banner (HUD templates Pos_Backing + Position_Title cloned under HUD.ViewportId3d).
--  - Next track: L3 twice, or the keys ç / à (AZERTY: CMN_9 / CMN_0): music_type 0 then p + 2 (crossing the graph's
--    0.5 gate restarts the music at position p).
--  - 0.5 (2026-11-20, player reports): the plugin drives every track change in a race, like a skip, at the end it
--    computes (make_music.managed_chain: a track that ends no longer starts the next while MusicType is ours), so
--    the banner and the sound always change together (the old timer drifted from the graph's own chain); a race starts
--    either on the track still playing (enough of it left) or on a new one with MusicType FORCE + p
--    (make_music.force_start); career destruction / checkpoint events have their own music: the plugin stays out;
--    music volume 0 = no banner; clock = the frame times the game passes (os.time counted whole seconds).
-- Two rules learnt the hard way: never create at load time a table a hook fills (AMAX's lua5.1.dll and the game's
-- own Lua are two Lua copies: crash), and keep a gadget's z when moving it.
local M = {
	info = {
		name = "MusicCtl",
		description = "Race music: next track key (L3 x2, ç / à) and a now-playing banner",
		version = 0.5,
	},
}

local TRACKS = {}                         -- filled by make_music.write_titles: { {title hash, seconds, info hashes...}, ... }
local COVERS = {}                         -- filled by make_music.write_titles: { [position + 1] = {atlas, u, v} } (no cover: absent)

local NEXT_MSG = "LeftThumb"              -- UIEnums.Message of L3 (R3 = RightThumb; the d-pad is used by the game)
local NEXT_KEY1, NEXT_KEY2 = "CMN_9", "CMN_0"
local SFX_NEXT = "MotorMashCount"         -- its ingameui.baf wave is our next-track sound (make_music.music_key_sounds)
local COOLDOWN = 2.0                      -- s between two skips
local DOUBLE_PRESS = 0.5                  -- s: L3 twice within this = next
local SWITCH_TIME = 0.75                  -- s between music_type 0 and p + 2 (> the graph's 0.5 s gate delay)
local SKIP_START = 1.5                    -- s from a skip to the new track's start (switch 0.75 + RaceStartDelay 0.5)
local FIRST_START = 4.0                   -- s from the race intro to the first track (estimate: countdown)
local FORCE = 1000                        -- music_type FORCE + p: the race starts position p, whatever played (make_music.FORCE_BASE)
local KEEP_MIN = 20.0                     -- s: a track with less than this left is not carried into the next race

-- banner (player's design and placement, 2026-11-13; HUD units, parent HUD.ViewportId3d)
local POS_X, POS_Y = -4.5, 8.0
local TEXT_DX, TEXT_DY = 1.0, -0.5
local TEXT_SCALE = 1.25
local INFO_SCALE, INFO_LINES, LINE_DY = 0.85, 2, 1.6   -- info lines under the title (artist, album)
-- light streak across the screen (player's pick, 2026-11-13): the fan-demand win swirl (shp_FanSwirlWin, 854 x 482,
-- texture light_paint_02, green Support_0), cloned, recoloured to the blue of "Position" (Main_1 = 12 125 253) and
-- played with its own timeline (fan_demand_win_on: texture scroll 0.5-3 s, fade in and out) when the banner shows
local SWIRL, SWIRL_COLOUR, SWIRL_TL = true, "!255 12 125 253", "fan_demand_win_on"
local SWIRL_LEN = 3.2                            -- s: the swirl timeline (fade out ends at 3.125 s)
local SW_X, SW_Y, SW_SCALE = -44.0, 124.0, 1.2   -- streak offset from its default place and scale: placed by the player
                                                -- with live keys (2026-11-13): along the banner, bottom-left
local MID_MIN = 0.2                             -- backing middle piece height with no info line (HUD units)
local WIDTH_K, WIDTH_PAD, WIDTH_MIN = 1.0, 2.5, 6.0
local HOLD, SLIDE, SLIDE_DIST = 3.5, 0.6, 14.0
-- album cover (idea: Лагман; opening of the fan message "Mine Hotshot", idea: Md; artprobe, 2026-11-16): a clone of
-- Position_Team_Icon showing a cell of our atlas in ui_common.bpr (make_music.write_covers, rounded corners): ChangeTexture
-- then ChangeEffectIndex MultiTexture (without it: a white glow). Layout (player, 2026-11-16): the cover on the left of the
-- banner, the text at its bottom right, one backing for both (the banner's, raised by ART_PANEL); no cover = the banner
-- as before. Opens from its centre like fan_message, closes on itself.
local ART_X, ART_Y, ART_SIZE = 4.2, 8.1, 7.7    -- cover centre and side (HUD units, parent ViewportId3d, BottomLeft)
local ART_GAP = 0.6                              -- text shift right = ART_SIZE + ART_GAP
local ART_PANEL = 7.5                            -- backing middle height with a cover (the panel grows upward)
local TUNE = false                               -- test build only: keys 1-8 move the layout (log: read_luamarks.py MCALL)
local ART_GREY = 200                             -- a little below white: the HUD bloom (covers are levelled at build)
local ART_OPEN, ART_CELL = 0.19, 0.25            -- s to open / close (fan_message keys); cell size in UV (4 x 4)
local ART_HOLD = 4.1                             -- s the cover stays open after a track starts (then closes on itself)
-- Md's idea (2026-11-15): a track change while the cover is open does not reopen it: the picture changes under a
-- short flicker, and the closing timer starts again
local ART_FLICK = { 0.0, 0.25, 0.05, 1.0, 0.09, 0.35, 0.14, 1.0 }
-- a damaged lamp (player, 2026-11-16): now and then the cover dims for a few frames
local LAMP_CHANCE, LAMP_DIM, LAMP_LEN = 0.015, 150, 0.08   -- per frame; grey level while dimmed; s
-- one lap of a thin white line along the cover's edge once it is open, and again with a track change (player,
-- 2026-11-16: one lap, about 3-4 cm long, thin, bright): a bar (hud_grad slice, white) moved clockwise from top-left
local LAP, LINE_LEN, LINE_W = 0.9, 5.5, 0.12     -- s per lap; bar length and thickness (HUD units)
local FLICKER = { 0.0, 0.0, 0.05, 0.7, 0.10, 0.05, 0.18, 0.9, 0.22, 0.1, 0.35, 0.6, 0.40, 0.0, 0.48, 1.0, 0.53, 0.3, 0.60, 1.0 }

local in_race = false
local on_value = nil                      -- the player's Music option at race start (0 = off)
local own_music = false                   -- career destruction / checkpoint: the game's own music, the plugin stays out
local suspended = false                   -- in a Shared\ screen from the pause menu (Options, Help, garage)
local shuffled = false                    -- the session's random start is drawn
local clock = 0                           -- s: sum of the frame times the game passes to FrameUpdate (1/60 if none)
local pending = nil                       -- { time, music_type } (created in hooks)
local last_action, last_l3, last_key = -100, -100, ""
local pos, track_start, shown = 0, nil, false   -- shuffle position playing, its start (clock), its banner shown
local banner = nil
local hud_ready = false                   -- the race HUD screen is up (gadgets made under the intro sit elsewhere)
local n_log = 0
local wrapped_frame, wrapped_msg = false, false

local function log(text)
	n_log = n_log + 1
	MUSICCTL_BODY = (MUSICCTL_BODY or "") .. "\n" .. text
	MUSICCTL_ALL = "MCALL#" .. n_log .. "#" .. MUSICCTL_BODY .. "#ALLEND"
end

local function options()
	local ok, t = pcall(Amax.Options)     -- UIGlobals.OptionsTable is nil in a race
	if ok and type(t) == "table" then return t end
	return nil
end

local function set_music(v)
	local t = options()
	if not t then log("no options table") return end
	t.music_type = v
	local ok, err = pcall(Amax.UpdateAudioOptions, t)
	if not ok then log("UpdateAudioOptions failed: " .. tostring(err)) end
end

-- banner -------------------------------------------------------------------------------------------------------------
local function clone_label(parent, scale)               -- a "Position" label without its number children
	local id = UIButtons.CloneXtGadgetByName("hud_objects", "Position_Title")
	for _, child in ipairs({ "Position_Amount", "Position_AmountOf" }) do
		local c = UIButtons.FindChildByName(id, child)
		if c then UIButtons.SetActive(c, false) end
	end
	-- BottomLeft: the anchor the player's placement (-4.5, 8) was tuned with in music_probe (TopLeft put it at the top)
	UIButtons.SetParent(id, parent, UIEnums.Justify.BottomLeft)
	UIButtons.ChangeScale(id, scale, scale, 1.0)
	return id
end

local function banner_build()
	local parent = type(HUD) == "table" and type(HUD.ViewportId3d) == "table" and (HUD.ViewportId3d[1] or HUD.ViewportId3d[0])
	if not parent then return nil end
	local b = { info = {} }
	b.bg = UIButtons.CloneXtGadgetByName("hud_objects", "Pos_Backing")
	-- the backing is three hud_grad pieces (ui.json): Pos_Backing (top), its child Pos_BackingMiddle (stretchable) and
	-- that one's child Pos_BackingBottom: all three get the same width, the middle the height of the info lines (the
	-- "hole" of 2026-11-13 was the middle hidden while the bottom stayed, 12 wide)
	b.mid = UIButtons.FindChildByName(b.bg, "Pos_BackingMiddle")
	b.bottom = b.mid and UIButtons.FindChildByName(b.mid, "Pos_BackingBottom")
	log("backing pieces " .. tostring(b.bg) .. " " .. tostring(b.mid) .. " " .. tostring(b.bottom))
	UIButtons.SetParent(b.bg, parent, UIEnums.Justify.BottomLeft)
	b.txt = clone_label(parent, TEXT_SCALE)
	for i = 1, INFO_LINES do b.info[i] = clone_label(parent, INFO_SCALE) end
	local _, h = UIButtons.GetSize(b.bg)
	local _, _, z = UIButtons.GetPosition(b.bg)
	b.h, b.z, b.lines = h, z or 0.0, 0
	log("banner built: backing body " .. tostring(b.mid))
	local okc, art = pcall(UIButtons.CloneXtGadgetByName, "hud_objects", "Position_Team_Icon")
	if okc and art then
		UIButtons.SetParent(art, parent, UIEnums.Justify.BottomLeft)
		local _, _, az = UIButtons.GetPosition(art)
		UIButtons.ChangeSize(art, ART_SIZE, ART_SIZE)
		UIButtons.ChangePosition(art, ART_X, ART_Y, az or 0.0)
		pcall(UIButtons.ChangeColour, art, "!255 " .. ART_GREY .. " " .. ART_GREY .. " " .. ART_GREY)
		UIButtons.ChangeAlpha(art, 1.0)
		pcall(UIButtons.SetAlphaIntensity, art, 1.0, 1.0)
		UIButtons.SetActive(art, false)
		b.art = art
	end
	log("cover square " .. tostring(okc) .. " " .. tostring(art))
	local okl, light = pcall(UIButtons.CloneXtGadgetByName, "hud_objects", "Position_Team_Icon")   -- after: drawn over
	if okl and light and b.art then
		UIButtons.SetParent(light, parent, UIEnums.Justify.BottomLeft)
		local _, _, lz = UIButtons.GetPosition(light)
		b.light_z = lz or 0.0
		-- a plain bar: the bright end of hud_grad (intensity ~0.76 at u 0.9, more at 0.95), drawn as alpha, in white
		pcall(UIButtons.ChangeTexture, { filename = "hud_grad", pos = { u = 0.97, v = 0.5 }, size = { u = 0.0, v = 0.0 } }, 0.0, light)
		pcall(UIButtons.ChangeEffectIndex, light, UIEnums.EffectIndex.IntensityAsAlpha)
		pcall(UIButtons.ChangeColour, light, "!255 255 255 255")
		UIButtons.ChangeAlpha(light, 1.0)
		pcall(UIButtons.SetAlphaIntensity, light, 1.0, 1.0)
		UIButtons.SetActive(light, false)
		b.light = light
	end
	log("cover light " .. tostring(okl) .. " " .. tostring(light))
	local vp = type(HUD.ViewportId) == "table" and (HUD.ViewportId[1] or HUD.ViewportId[0])
	-- two twin streaks played in turn (player, 2026-11-14): a timeline starts by its label for every gadget that has it,
	-- so a second start of the same one would restart the streak still crossing; the fan-demand fail swirl is the
	-- same picture and animation under another label (fan_demand_fail_on). Skips 2 s apart, 3.2 s long: two suffice.
	b.swirls = {}
	if SWIRL and vp then
		for _, t in ipairs({ { "shp_FanSwirlWin", SWIRL_TL }, { "shp_FanSwirlFail", "fan_demand_fail_on" } }) do
			local ok, sw = pcall(UIButtons.CloneXtGadgetByName, "hud_objects", t[1])
			if ok and sw then
				UIButtons.SetParent(sw, vp, UIEnums.Justify.MiddleCentre)
				local sx, sy, sz = UIButtons.GetPosition(sw)
				pcall(UIButtons.ChangeColour, sw, SWIRL_COLOUR)
				b.swirls[#b.swirls + 1] = { id = sw, label = t[2], home = { sx or 0, sy or 0, sz or 0 } }
			end
			log("swirl " .. t[1] .. " " .. tostring(ok) .. " " .. tostring(sw))
		end
	end
	return b
end

local function banner_place(dx, alpha)
	-- with a cover: the text moves right of it and the backing grows upward (its middle piece taller, its top raised:
	-- the bottom stays where it was), so the text sits at the cover's bottom right
	local mid = MID_MIN + LINE_DY * banner.lines
	local raise = banner.cover and math.max(0, ART_PANEL - mid) or 0
	local tx = banner.cover and ART_SIZE + ART_GAP or 0
	if banner.mid then UIButtons.ChangeSize(banner.mid, banner.w + tx, mid + raise) end
	UIButtons.ChangeSize(banner.bg, banner.w + tx, banner.h)
	if banner.bottom then UIButtons.ChangeSize(banner.bottom, banner.w + tx, banner.h) end
	UIButtons.ChangePosition(banner.bg, POS_X + dx, POS_Y + raise, banner.z)
	UIButtons.ChangePosition(banner.txt, POS_X + dx + TEXT_DX + tx, POS_Y + TEXT_DY, banner.z)
	UIButtons.ChangeAlpha(banner.txt, alpha)
	for i = 1, banner.lines do                            -- info lines under the title (y goes up)
		UIButtons.ChangePosition(banner.info[i], POS_X + dx + TEXT_DX + tx, POS_Y + TEXT_DY - LINE_DY * i, banner.z)
		UIButtons.ChangeAlpha(banner.info[i], alpha)
	end
	UIButtons.ChangeAlpha(banner.bg, alpha)
	for _, piece in ipairs({ banner.bg, banner.mid, banner.bottom }) do   -- the backing draws its intensity as alpha
		pcall(UIButtons.SetAlphaIntensity, piece, alpha, alpha)
	end
end

local function banner_drop()                            -- hide every piece and forget them (a new set is built later)
	if banner then
		for _, sw in ipairs(banner.swirls or {}) do pcall(UIButtons.SetActive, sw.id, false) end
		for _, k in ipairs({ "bg", "txt", "art", "light" }) do
			if banner[k] then pcall(UIButtons.SetActive, banner[k], false) end
		end
		for i = 1, INFO_LINES do
			if banner.info[i] then pcall(UIButtons.SetActive, banner.info[i], false) end
		end
	end
	banner = nil
end

local function banner_hide()
	if banner and banner.t0 then
		pcall(UIButtons.SetActive, banner.bg, false)
		for _, sw in ipairs(banner.swirls or {}) do               -- both done by then (3.2 s < the banner's 4.7 s)
			pcall(UIButtons.SetActive, sw.id, false)
			sw.t0 = nil
		end
		pcall(UIButtons.SetActive, banner.txt, false)      -- (the cover has its own timer: art_tick)
		for i = 1, INFO_LINES do pcall(UIButtons.SetActive, banner.info[i], false) end
		banner.t0 = nil
	end
end

local function art_show(cover)                          -- cover = COVERS entry of the new track, or nil
	local b = banner
	if not b.art then return end
	local open = b.art_t0 ~= nil and clock < b.art_close   -- opening or holding (not closing)
	if not cover then                                      -- no cover for this track: no square (player, 2026-11-16)
		if open then b.art_close = math.max(clock, b.art_t0 + ART_OPEN) end
		return
	end
	UIButtons.ChangeTexture({ filename = cover[1], pos = { u = cover[2], v = cover[3] },
		size = { u = ART_CELL, v = ART_CELL } }, 0.0, b.art)
	UIButtons.ChangeEffectIndex(b.art, UIEnums.EffectIndex.MultiTexture)
	if open then
		b.art_fl = clock                                   -- Md: stays open, the new picture comes in with a flicker
		b.lap_t0 = clock                                   -- and the light goes round once more
	else
		b.art_t0, b.art_fl, b.lap_t0 = clock, nil, clock + ART_OPEN   -- the lap once the square is open
		for _, id in ipairs({ b.art }) do
			UIButtons.ChangeScale(id, 0.0, 1.0, 1.0)
			UIButtons.SetActive(id, true)
		end
	end
	b.art_close = clock + ART_HOLD
end

local function art_tick()                               -- opens from its centre, holds, closes on itself (fan_message)
	local b = banner
	if not (b and b.art and b.art_t0) then return end
	local t, sx = clock - b.art_t0, 1.0
	if t < ART_OPEN then sx = t / ART_OPEN end
	if clock > b.art_close then sx = math.min(sx, 1 - (clock - b.art_close) / ART_OPEN) end
	if sx <= 0 then
		for _, id in ipairs({ b.art }) do UIButtons.SetActive(id, false) end
		b.art_t0 = nil
		if b.light then UIButtons.SetActive(b.light, false) end
		return
	end
	if b.light then                                       -- one lap of a thin bar along the edge, clockwise (y goes up)
		local q = b.lap_t0 and (clock - b.lap_t0) / LAP
		if q and q >= 0 and q < 1 and clock <= b.art_close then
			local h = ART_SIZE / 2                            -- the cover's edge (its position is its centre: it opens from it)
			local corners = { { -h, h }, { h, h }, { h, -h }, { -h, -h }, { -h, h } }
			local d = q * 4 * ART_SIZE                        -- distance run along the edge
			local k = math.min(3, math.floor(d / ART_SIZE))
			local c = d - k * ART_SIZE                        -- bar centre on side k, clipped to the side: clean corners
			local a0, a1 = math.max(0, c - LINE_LEN / 2), math.min(ART_SIZE, c + LINE_LEN / 2)
			local c0, c1 = corners[k + 1], corners[k + 2]
			local ux, uy = (c1[1] - c0[1]) / ART_SIZE, (c1[2] - c0[2]) / ART_SIZE
			local m = (a0 + a1) / 2
			local len = math.max(0.01, a1 - a0)
			UIButtons.ChangeSize(b.light, ux ~= 0 and len or LINE_W, uy ~= 0 and len or LINE_W)
			UIButtons.ChangePosition(b.light, ART_X + c0[1] + ux * m, ART_Y + c0[2] + uy * m, b.light_z)
			UIButtons.ChangeAlpha(b.light, math.min(1, 8 * q, 8 * (1 - q)))   -- fades in and out at the ends of the lap
			UIButtons.SetActive(b.light, true)
		else
			UIButtons.SetActive(b.light, false)
		end
	end
	-- damaged lamp: a short dim now and then (pseudo-random from the clock: no math.random needed)
	local r = (math.sin(clock * 127.1 + 311.7) * 43758.5453) % 1
	if not b.lamp_t0 and r < LAMP_CHANCE then b.lamp_t0 = clock end
	local g = ART_GREY
	if b.lamp_t0 then
		if clock - b.lamp_t0 < LAMP_LEN then g = LAMP_DIM else b.lamp_t0 = nil end
	end
	if g ~= b.lamp_g then
		b.lamp_g = g
		UIButtons.ChangeColour(b.art, "!255 " .. g .. " " .. g .. " " .. g)
	end
	for _, id in ipairs({ b.art }) do UIButtons.ChangeScale(id, sx, 1.0, 1.0) end
	local a = 1.0
	if b.art_fl then
		local f = clock - b.art_fl
		if f < ART_FLICK[#ART_FLICK - 1] then
			for i = 1, #ART_FLICK - 1, 2 do
				if ART_FLICK[i] <= f then a = ART_FLICK[i + 1] end
			end
		else
			b.art_fl = nil
		end
	end
	UIButtons.ChangeAlpha(b.art, a)
end

local function banner_show(p)                           -- true once dealt with (shown, or hidden on purpose)
	local track = TRACKS[p + 1]
	if not track or not hud_ready then return false end
	local t = options()
	if t and tonumber(t.music_vol) == 0 then              -- music volume 0: no banner (player, 2026-11-20)
		banner_hide()
		return true
	end
	local ok, err = pcall(function()
		banner = banner or banner_build()
		if not banner then return end
		UIButtons.ChangeText(banner.txt, track[1])
		local w = (UIButtons.GetStaticTextLength(banner.txt) or 0) * TEXT_SCALE
		banner.lines = 0
		for i = 1, INFO_LINES do
			local h = track[2 + i]                         -- TRACKS entry: title hash, seconds, info line hashes
			if h then
				banner.lines = i
				UIButtons.ChangeText(banner.info[i], h)
				w = math.max(w, (UIButtons.GetStaticTextLength(banner.info[i]) or 0) * INFO_SCALE)
			end
			UIButtons.SetActive(banner.info[i], h ~= nil)
		end
		banner.w = math.max(WIDTH_MIN, w * WIDTH_K + WIDTH_PAD)   -- sizes set by banner_place (with or without cover)
		banner.cover = COVERS[p + 1] ~= nil and banner.art ~= nil
		banner.t0 = clock
		banner_place(0, 0.0)
		UIButtons.SetActive(banner.bg, true)
		for _, sw in ipairs(banner.swirls) do               -- the game's own streak animation, in blue: a free one
			if not sw.t0 or clock - sw.t0 > SWIRL_LEN then  -- (the other may still be crossing: it ends on its own)
				sw.t0 = clock
				UIButtons.SetActive(sw.id, true)
				pcall(UIButtons.ChangePosition, sw.id, sw.home[1] + SW_X, sw.home[2] + SW_Y, sw.home[3])
				pcall(UIButtons.ChangeScale, sw.id, SW_SCALE, SW_SCALE, 1.0)
				pcall(UIButtons.TimeLineActive, sw.label, true, 0.0)
				break
			end
		end
		UIButtons.SetActive(banner.txt, true)
		art_show(COVERS[p + 1])
	end)
	if not ok then                                       -- dead gadgets (HUD rebuilt): drop them, rebuilt next time
		log("banner failed: " .. tostring(err))
		banner = nil
	end
	return true
end

local function banner_tick()
	if not (banner and banner.t0) then return end
	local t = clock - banner.t0
	local on = FLICKER[#FLICKER - 1]
	local ok = pcall(function()
		if t < on then                                    -- a failing lamp: last key at or before t
			local a = 0.0
			for i = 1, #FLICKER - 1, 2 do
				if FLICKER[i] <= t then a = FLICKER[i + 1] end
			end
			banner_place(0, a)
		elseif t < on + HOLD then
			banner_place(0, 1.0)
		elseif t < on + HOLD + SLIDE then
			local q = (t - on - HOLD) / SLIDE
			banner_place(-SLIDE_DIST * q * q, 1.0 - q)    -- slides left, faster and faster, fading out
		else
			banner_hide()
		end
	end)
	if not ok then banner_hide() end
end

-- music --------------------------------------------------------------------------------------------------------------
local function music_on()
	return on_value ~= nil and on_value ~= 0 and #TRACKS > 0 and not own_music
end

local function own_music_event()                         -- career events with their own music graph (music_destruction,
	for _, f in ipairs({ "SP_IsDestructionRace", "SP_IsDestructionFD", "SP_IsCheckpointRace", "SP_IsCheckpointFD" }) do
		local ok, yes = pcall(Amax[f])                   -- music_checkpoint): names read in HUD.lua
		if ok and yes == true then return f end
	end
	return nil
end

local function switch_to(p)                              -- like a skip: 0 crosses the gate (the graph stops the track),
	pos = p                                              -- then p + 2 once the value is back starts position p
	set_music(0)
	pending = { clock + SWITCH_TIME, pos + 2 }
	track_start = clock + SKIP_START
	shown = banner_show(pos)
end

local function next_track()
	if clock - last_action < COOLDOWN or not music_on() then return end
	last_action = clock
	switch_to((pos + 1) % #TRACKS)
	pcall(function() UISystem.PlaySound(UIEnums.SoundEffect[SFX_NEXT]) end)
	log("next: position " .. pos)
end

local function catch_up()                                -- tracks the graph chained by itself while MusicType was 1
	while clock - track_start >= TRACKS[pos + 1][2] do
		track_start = track_start + TRACKS[pos + 1][2]
		pos = (pos + 1) % #TRACKS
	end
end

local function race_start()
	suspended = false
	local t = options()
	on_value = t and t.music_type or nil
	if on_value ~= nil and on_value >= 2 then on_value = 1 end   -- a value of ours left by a crash
	shown = false                                        -- the title in play is shown once the HUD is up
	own_music = false
	if on_value == nil or on_value == 0 or #TRACKS == 0 then log("race, music off or no track list") return end
	local event = own_music_event()
	if event then
		-- the game plays its own music here; a value of ours would start the playlist on top of it (player,
		-- 2026-11-20): leave the option alone, and start a known track at the next race
		own_music, track_start = true, nil
		log("race, " .. event .. ": the game's own music")
		return
	end
	if track_start then
		-- the previous race's track goes on into this race (RaceStartScript keeps a track that plays); in menus the
		-- graph chains the tracks itself (MusicType 1): catch up with the ones that ended meanwhile
		catch_up()
		if TRACKS[pos + 1][2] - (clock - track_start) > KEEP_MIN then
			set_music(pos + 2)                           -- 1 -> p + 2: no gate crossing, the track goes on
			log("race, music goes on at position " .. pos)
			return
		end
		pos = (pos + 1) % #TRACKS                        -- almost over (or the timer is off after the menus): a new one
	elseif shuffled then
		pos = (pos + 1) % #TRACKS                        -- after a destruction / checkpoint event: the order goes on
	else
		math.randomseed(os and os.time and os.time() or 0)
		pos = math.random(0, #TRACKS - 1)
		shuffled = true
	end
	set_music(FORCE + pos)                               -- RaceStartScript stops whatever plays and starts position pos
	track_start = clock + FIRST_START
	log("race, start position " .. pos .. " of " .. #TRACKS)
end

-- pause -> Options / Help / garage (Shared\...) or a popup (Popups\...): still the race. Before 0.5 these screens ended the race and the HUD
-- started a new one (a forced start mid-race does nothing: lost track). The option goes back to the player's value
-- (the Options screen shows it), the graph chains by itself meanwhile, and the race resumes on the HUD.
local function suspend()
	suspended, hud_ready = true, false
	banner_drop()
	-- ponytail: a skip half-way (0 sent, p + 2 pending) is resolved by the graph's own path (MusicType 1)
	pending = nil
	if music_on() then set_music(on_value) end
	log("race suspended (" .. tostring(pos) .. ")")
end

local function resume()
	suspended, shown = false, false
	local t = options()
	on_value = t and t.music_type or on_value            -- the player may have changed it in Options
	if on_value ~= nil and on_value >= 2 then on_value = 1 end
	if music_on() and track_start then
		catch_up()
		set_music(pos + 2)                               -- 1 -> p + 2: no gate crossing
	end
	log("race resumed at position " .. pos)
end

local function race_end()
	pending, suspended = nil, false
	banner_hide()
	if on_value ~= nil and not own_music then set_music(on_value) end   -- ours -> 1: no gate crossing, the music goes on
	log("race over (position " .. pos .. " goes on)")    -- track_start kept: the track plays on into the next race
end

local function tick(dt)
	-- the frame time the game passes: seconds (GuiBank.lua), milliseconds accepted in case; else 1/60
	-- ponytail: a frame longer than 0.25 s (loading) counts 1/60: the timer may lag after menus (wrong title on a
	-- carried-over track); the next switch_to puts it right. Add os.time() for long frames if players see it.
	dt = tonumber(dt)
	if dt and dt > 0 and dt < 0.25 then
		clock = clock + dt
	elseif dt and dt >= 4 and dt < 250 then
		clock = clock + dt / 1000
	else
		clock = clock + 1 / 60
	end
	if not in_race or suspended then return end
	if pending and clock >= pending[1] then
		local v = pending[2]
		pending = nil
		set_music(v)
	end
	if track_start and music_on() and clock >= track_start then
		if not shown and hud_ready then                   -- the track has started and the HUD is up
			shown = banner_show(pos)
		end
		if not pending and clock - track_start >= TRACKS[pos + 1][2] then
			switch_to((pos + 1) % #TRACKS)                -- its end by our clock: we start the next one ourselves
			log("track end: position " .. pos)
		end
	end
	banner_tick()
	if not pcall(art_tick) and banner then banner.art_t0 = nil end
	if UIButtons and UIButtons.GetKeyInput then
		local ok, key = pcall(UIButtons.GetKeyInput)
		key = ok and tostring(key or "") or ""
		if key ~= last_key then                           -- a held key keeps its value: new keys only
			last_key = key
			if key == NEXT_KEY1 or key == NEXT_KEY2 then next_track() end
			-- test build only: 1 / 2 cover x, 3 / 4 cover y, 5 / 6 text shift, 7 / 8 panel height (0.1 unit a press)
			local d = TUNE and ({ CMN_1 = { -1, 0, 0, 0 }, CMN_2 = { 1, 0, 0, 0 }, CMN_3 = { 0, -1, 0, 0 },
				CMN_4 = { 0, 1, 0, 0 }, CMN_5 = { 0, 0, -1, 0 }, CMN_6 = { 0, 0, 1, 0 },
				CMN_7 = { 0, 0, 0, -1 }, CMN_8 = { 0, 0, 0, 1 } })[key]
			if d then
				ART_X, ART_Y = ART_X + d[1] * 0.1, ART_Y + d[2] * 0.1
				ART_GAP, ART_PANEL = ART_GAP + d[3] * 0.1, ART_PANEL + d[4] * 0.1
				if banner and banner.art then
					local _, _, az = UIButtons.GetPosition(banner.art)
					UIButtons.ChangePosition(banner.art, ART_X, ART_Y, az or 0.0)
					if banner.t0 then banner_place(0, 1.0) end
				end
				log(string.format("tune ART_X %.2f ART_Y %.2f ART_GAP %.2f ART_PANEL %.2f", ART_X, ART_Y, ART_GAP, ART_PANEL))
			end
		end
	end
end

local function on_message(msg)
	if not in_race then return end
	local flow = UIEnums.GameFlowMessage
	if msg == flow.OutroStarted or msg == flow.QuitRace or msg == flow.RaceFailed then
		in_race = false
		race_end()
		return
	end
	if msg == UIEnums.Message[NEXT_MSG] then
		if clock - last_l3 <= DOUBLE_PRESS then           -- double press: a single one is too easy to make by mistake
			last_l3 = -100
			next_track()
		else
			last_l3 = clock
		end
	end
end

local function wrap()
	if not wrapped_frame and type(FrameUpdate_Wrapper) == "function" then
		wrapped_frame = true
		local org = FrameUpdate_Wrapper
		FrameUpdate_Wrapper = function(...)
			local r = org(...)
			pcall(tick, ...)                              -- FrameUpdate_Wrapper(delta): GuiBank.lua uses it as seconds
			return r
		end
	end
	if not wrapped_msg and type(MessageUpdate_Wrapper) == "function" then
		wrapped_msg = true
		local org = MessageUpdate_Wrapper
		MessageUpdate_Wrapper = function(msg, ...)
			pcall(on_message, msg)
			return org(msg, ...)
		end
	end
end

function M.GoScreen(screen, context)
	wrap()
	-- a screen in a context of its own (SpWrecked: HUD.lua opens it with UIEnums.Context.SpWrecked) sits over the HUD,
	-- which stays: nothing to do. Seen as leaving the HUD, the banner never came back after a wreck (player, 2026-11-20)
	local ctx = type(UIEnums) == "table" and UIEnums.Context
	if context ~= nil and type(ctx) == "table" and context ~= ctx.Main then return end
	local s = string.lower(tostring(screen))
	local ingame = string.sub(s, 1, 7) == "ingame\\"     -- HUD, pause, wrecked...: all part of the race
	local start = s == "ingame\\introrace.lua" or s == "ingame\\hud.lua"
	-- Options, Help, garage, popups (quit?): reached from the pause menu too, the race is not over
	local shared = string.sub(s, 1, 7) == "shared\\" or string.sub(s, 1, 7) == "popups\\"
	if start and not in_race then
		banner_hide()
		banner = nil
		in_race, hud_ready = true, false
		race_start()                                      -- at the intro if possible: before RaceStartScript runs
	elseif shared and in_race then
		if not suspended then suspend() end
	elseif not ingame and in_race then
		in_race, hud_ready = false, false
		race_end()
	end
	if ingame and in_race and suspended then resume() end   -- back to the pause menu or the HUD
	if s == "ingame\\hud.lua" and in_race and not hud_ready then
		banner_drop()                                     -- built under the race HUD only: under the intro's view it
		hud_ready = true                                  -- sat top-left, off-screen (2026-11-13)
	elseif ingame and in_race and hud_ready and s ~= "ingame\\hud.lua" then
		banner_drop()                                     -- pause / options: back in the race the HUD is rebuilt and
		hud_ready = false                                 -- our old gadgets were dead (banner gone for good, 2026-11-13)
	elseif not ingame then
		local t = options()                               -- menus: never leave a value of ours in the options
		if t and t.music_type ~= nil and t.music_type >= 2 then set_music(1) end
	end
end

M.PushScreen = M.GoScreen

function M.init()
	return true
end

return M
