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
-- Two rules learnt the hard way: never create at load time a table a hook fills (AMAX's lua5.1.dll and the game's
-- own Lua are two Lua copies: crash), and keep a gadget's z when moving it.
local M = {
	info = {
		name = "MusicCtl",
		description = "Race music: next track key (L3 x2, ç / à) and a now-playing banner",
		version = 0.3,
	},
}

local TRACKS = {}                         -- filled by make_music.write_titles: { {title hash, seconds, info hashes...}, ... }

local NEXT_MSG = "LeftThumb"              -- UIEnums.Message of L3 (R3 = RightThumb; the d-pad is used by the game)
local NEXT_KEY1, NEXT_KEY2 = "CMN_9", "CMN_0"
local SFX_NEXT = "MotorMashCount"         -- its ingameui.baf wave is our next-track sound (make_music.music_key_sounds)
local COOLDOWN = 2.0                      -- s between two skips
local DOUBLE_PRESS = 0.5                  -- s: L3 twice within this = next
local SWITCH_FRAMES = 45                  -- frames between music_type 0 and p + 2 (> the graph's 0.5 s gate delay)
local SKIP_START = 1.5                    -- s from a skip to the new track's start (switch 0.75 + RaceStartDelay 0.5)
local FIRST_START = 4.0                   -- s from the race HUD to the first track (estimate: countdown)

-- banner (player's design and placement, 2026-11-13; HUD units, parent HUD.ViewportId3d)
local POS_X, POS_Y = -4.5, 8.0
local TEXT_DX, TEXT_DY = 1.0, -0.5
local TEXT_SCALE = 1.25
local INFO_SCALE, INFO_LINES, LINE_DY = 0.85, 2, 1.6   -- info lines under the title (artist, album)
-- animated overlay (player, 2026-11-13): the game's own scrolling clouds of the rank-up popup (mp_rank_up_clouds,
-- texture text_clouds, a 10 s looping u scroll that starts by itself), laid on the backing
local CLOUDS, CLOUDS_ALPHA, CLOUDS_W, CLOUDS_H = true, 0.5, 1.0, 1.0   -- size factors vs the backing
local WIDTH_K, WIDTH_PAD, WIDTH_MIN = 1.0, 2.5, 6.0
local HOLD, SLIDE, SLIDE_DIST = 3.5, 0.6, 14.0
local FLICKER = { 0.0, 0.0, 0.05, 0.7, 0.10, 0.05, 0.18, 0.9, 0.22, 0.1, 0.35, 0.6, 0.40, 0.0, 0.48, 1.0, 0.53, 0.3, 0.60, 1.0 }

local in_race = false
local on_value = nil                      -- the player's Music option at race start (0 = off)
local clock = 0                           -- s, frames / 60 (the race runs at 60 fps): animations
local pending = nil                       -- { frames, music_type } (created in hooks)
local last_action, last_l3, last_key = -100, -100, ""
local pos, track_start, shown = 0, nil, false   -- shuffle position playing, its start (now()), its banner shown
local banner = nil
local hud_ready = false                   -- the race HUD screen is up (gadgets made under the intro sit elsewhere)
local n_log = 0
local wrapped_frame, wrapped_msg = false, false

local function now()                      -- real seconds when os.time exists (frame drops), else the frame clock
	if os and os.time then return os.time() end
	return clock
end

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
	-- one gradient piece only: the body (Pos_BackingMiddle) kept its own offset once resized (player, 2026-11-13)
	local mid = UIButtons.FindChildByName(b.bg, "Pos_BackingMiddle")
	b.mid = mid                                           -- hidden again after every SetActive(bg, true): it reactivates it
	if mid then UIButtons.SetActive(mid, false) end
	UIButtons.SetParent(b.bg, parent, UIEnums.Justify.BottomLeft)
	b.txt = clone_label(parent, TEXT_SCALE)
	for i = 1, INFO_LINES do b.info[i] = clone_label(parent, INFO_SCALE) end
	local _, h = UIButtons.GetSize(b.bg)
	local _, _, z = UIButtons.GetPosition(b.bg)
	b.h, b.z, b.lines = h, z or 0.0, 0
	if CLOUDS then
		local ok, c = pcall(UIButtons.CloneXtGadgetByName, "hud_objects", "mp_rank_up_clouds")
		if ok and c then
			UIButtons.SetParent(c, parent, UIEnums.Justify.BottomLeft)
			local cw, ch = UIButtons.GetSize(c)
			log("clouds " .. tostring(c) .. " size " .. tostring(cw) .. " x " .. tostring(ch))
			b.clouds = c
		else
			log("clouds: no clone (" .. tostring(c) .. ")")
		end
	end
	return b
end

local function banner_place(dx, alpha)
	UIButtons.ChangePosition(banner.bg, POS_X + dx, POS_Y, banner.z)
	UIButtons.ChangePosition(banner.txt, POS_X + dx + TEXT_DX, POS_Y + TEXT_DY, banner.z)
	UIButtons.ChangeAlpha(banner.txt, alpha)
	for i = 1, banner.lines do                            -- info lines under the title (y goes up)
		UIButtons.ChangePosition(banner.info[i], POS_X + dx + TEXT_DX, POS_Y + TEXT_DY - LINE_DY * i, banner.z)
		UIButtons.ChangeAlpha(banner.info[i], alpha)
	end
	UIButtons.ChangeAlpha(banner.bg, alpha)
	if banner.clouds then
		UIButtons.ChangePosition(banner.clouds, POS_X + dx, POS_Y, banner.z)
		UIButtons.ChangeAlpha(banner.clouds, alpha * CLOUDS_ALPHA)
		pcall(UIButtons.SetAlphaIntensity, banner.clouds, alpha * CLOUDS_ALPHA, alpha * CLOUDS_ALPHA)
	end
	pcall(UIButtons.SetAlphaIntensity, banner.bg, alpha, alpha)   -- the backing draws its intensity as alpha
end

local function banner_hide()
	if banner and banner.t0 then
		pcall(UIButtons.SetActive, banner.bg, false)
		if banner.clouds then pcall(UIButtons.SetActive, banner.clouds, false) end
		pcall(UIButtons.SetActive, banner.txt, false)
		for i = 1, INFO_LINES do pcall(UIButtons.SetActive, banner.info[i], false) end
		banner.t0 = nil
	end
end

local function banner_show(p)
	local track = TRACKS[p + 1]
	if not track or not hud_ready then return end
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
		w = math.max(WIDTH_MIN, w * WIDTH_K + WIDTH_PAD)
		UIButtons.ChangeSize(banner.bg, w, banner.h + LINE_DY * banner.lines)
		if banner.clouds then UIButtons.ChangeSize(banner.clouds, w * CLOUDS_W, (banner.h + LINE_DY * banner.lines) * CLOUDS_H) end
		banner.t0 = clock
		banner_place(0, 0.0)
		UIButtons.SetActive(banner.bg, true)
		if banner.mid then UIButtons.SetActive(banner.mid, false) end   -- the parent's SetActive turned the body on
		if banner.clouds then UIButtons.SetActive(banner.clouds, true) end
		UIButtons.SetActive(banner.txt, true)
	end)
	if not ok then log("banner failed: " .. tostring(err)) end
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
	return on_value ~= nil and on_value ~= 0 and #TRACKS > 0
end

local function next_track()
	if clock - last_action < COOLDOWN or not music_on() then return end
	last_action = clock
	pos = (pos + 1) % #TRACKS
	set_music(0)                                         -- crosses the gate: the graph stops the track...
	pending = { SWITCH_FRAMES, pos + 2 }                 -- ...and starts position pos once the value is back
	track_start, shown = now() + SKIP_START, true
	pcall(function() UISystem.PlaySound(UIEnums.SoundEffect[SFX_NEXT]) end)
	banner_show(pos)
	log("next: position " .. pos)
end

local function race_start()
	local t = options()
	on_value = t and t.music_type or nil
	if on_value ~= nil and on_value >= 2 then on_value = 1 end   -- a value of ours left by a crash
	track_start, shown = nil, false
	if not music_on() then log("race, music off or no track list") return end
	math.randomseed(now())
	pos = math.random(0, #TRACKS - 1)
	set_music(pos + 2)                                   -- 1 -> p + 2 does not cross the gate: read by RaceStartScript
	track_start = now() + FIRST_START
	log("race, start position " .. pos .. " of " .. #TRACKS)
end

local function race_end()
	pending = nil
	banner_hide()
	if on_value ~= nil then set_music(on_value) end      -- p + 2 -> 1: no gate crossing, the music goes on
	track_start = nil
	log("race over")
end

local function tick()
	clock = clock + 1 / 60
	if not in_race then return end
	if pending then
		pending[1] = pending[1] - 1
		if pending[1] <= 0 then
			local v = pending[2]
			pending = nil
			set_music(v)
		end
	end
	if track_start and music_on() and now() >= track_start then
		if not shown and hud_ready then                   -- the first track has started and the HUD is up
			shown = true
			banner_show(pos)
		end
		local track = TRACKS[pos + 1]
		if now() - track_start >= track[2] then          -- the graph went on to the next position by itself
			track_start = track_start + track[2]
			pos = (pos + 1) % #TRACKS
			banner_show(pos)
			log("track end: position " .. pos)
		end
	end
	banner_tick()
	if UIButtons and UIButtons.GetKeyInput then
		local ok, key = pcall(UIButtons.GetKeyInput)
		key = ok and tostring(key or "") or ""
		if key ~= last_key then                           -- a held key keeps its value: new keys only
			last_key = key
			if key == NEXT_KEY1 or key == NEXT_KEY2 then next_track() end
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
			pcall(tick)
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

function M.GoScreen(screen, _opts)
	wrap()
	local s = string.lower(tostring(screen))
	local ingame = string.sub(s, 1, 7) == "ingame\\"     -- HUD, pause, wrecked...: all part of the race
	local start = s == "ingame\\introrace.lua" or s == "ingame\\hud.lua"
	if start and not in_race then
		banner_hide()
		banner = nil
		in_race, hud_ready = true, false
		race_start()                                      -- at the intro if possible: before RaceStartScript runs
	elseif not ingame and in_race then
		in_race, hud_ready = false, false
		race_end()
	end
	if s == "ingame\\hud.lua" and in_race and not hud_ready then
		banner_hide()
		banner = nil                                      -- built under the race HUD only: under the intro's view it
		hud_ready = true                                  -- sat top-left, off-screen (2026-11-13)
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
