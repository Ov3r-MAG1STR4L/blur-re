-- MusicCtl: skip to the next race track with a key (projet I, test copy only).
--
-- No engine message skips a track (UIEnums.GameFlowMessage only has Start/StopIngameAudio = ALL game sound). But
-- audio/dat/music_controller.dat reacts to its MusicType input: MusicTypeGate -> MusicTypeResetScript stops the
-- current track and, 0.5 s later, runs RaceStartScript, which draws a NEW track if MusicType == 0, else stays silent.
-- MusicType follows the audio option "Music" (music_type of Amax.Options(), applied by Amax.UpdateAudioOptions, as
-- Screens\Shared\Options_Audio.lua does): next = music off, then on again 45 frames later.
-- A pause key was tried (2026-10-26) and dropped: music back on always draws a new track (no resume at the same
-- place), so pause / resume felt like next.
-- Input: every UI message goes through the global MessageUpdate_Wrapper(msg, pad, ...) (GuiBank.lua); keyboard keys
-- through UIButtons.GetKeyInput() (the key rebinding screen's function, it also answers in a race).
-- Every new message / key / screen is kept in the global MUSICCTL_ALL ("MCALL#n#...#ALLEND"), read from memory with
-- read_luamarks.py (print_api output is visible nowhere).
local M = {
	info = {
		name = "MusicCtl",
		description = "Next race track with a key (L3, or ç / à on an AZERTY keyboard)",
		version = 0.2,
	},
}

-- Names read in memory in a race (2026-10-26): UIEnums.Message "LeftThumb" = L3 ("RightThumb" = R3; the d-pad is
-- used by the game); UIButtons.GetKeyInput() "" when no key, "CMN_9" = ç, "CMN_0" = à.
local NEXT_MSG = "LeftThumb"
local NEXT_KEY1, NEXT_KEY2 = "CMN_9", "CMN_0"
-- UIEnums.SoundEffect event whose ingameui.baf wave make_reverse.music_key_sounds replaced with our sound
local SFX_NEXT = "BossRaceLose"
local COOLDOWN = 2.0          -- s between two skips (anti-spam)
local SWITCH_FRAMES = 45      -- frames between "off" and "on" (> the graph's 0.5 s RaceStartDelay)

local in_race = false
local on_value, off_value = nil, nil
local last_action = -100
local clock = 0
local pending_on = -1         -- frames before switching the music back on
local last_key = ""
local DOUBLE_PRESS = 0.5      -- s: L3 twice within this = next
local last_l3 = -100
local seen = false            -- messages / keys already logged (made in a hook, not at load time: see quickstart)
local n_log = 0
local wrapped_frame, wrapped_msg = false, false

local function log(text)
	n_log = n_log + 1
	MUSICCTL_ALL = "MCALL#" .. n_log .. "#" .. (MUSICCTL_BODY or "") .. "\n" .. text .. "#ALLEND"
	MUSICCTL_BODY = (MUSICCTL_BODY or "") .. "\n" .. text
	pcall(print_api, " [musicctl] " .. text)
end

-- the options as the Options screen gets them (UIGlobals.OptionsTable is nil in a race: read in memory 2026-10-26)
local function options()
	local ok, t = pcall(Amax.Options)
	if ok and type(t) == "table" then
		return t
	end
	return nil
end

local function set_music(v)
	local t = options()
	if not t then
		log("no options table")
		return false
	end
	t.music_type = v
	local ok, err = pcall(Amax.UpdateAudioOptions, t)
	if not ok then
		log("UpdateAudioOptions failed: " .. tostring(err))
	end
	return ok
end

local function next_track()
	if clock - last_action < COOLDOWN or on_value == nil then
		return
	end
	last_action = clock
	set_music(off_value)
	pending_on = SWITCH_FRAMES
	pcall(function() UISystem.PlaySound(UIEnums.SoundEffect[SFX_NEXT]) end)
	log("next")
end

local function note(kind, v)
	if not seen then
		seen = {}
	end
	local k = kind .. tostring(v)
	if not seen[k] then
		seen[k] = true
		log(kind .. " " .. tostring(v) .. (in_race and " (race)" or ""))
	end
end

local function tick()
	clock = clock + 1 / 60       -- frames, not dt (its unit is unknown); the race runs at 60 fps (fps plugin)
	if not in_race then
		return
	end
	if pending_on > 0 then
		pending_on = pending_on - 1
		if pending_on == 0 then
			pending_on = -1
			set_music(on_value)
		end
	end
	if UIButtons and UIButtons.GetKeyInput then
		local ok, key = pcall(UIButtons.GetKeyInput)
		key = ok and tostring(key or "") or ""
		if key ~= last_key then            -- on a new key only (the value stays while the key is held)
			last_key = key
			if key ~= "" then
				note("key", key)
			end
			if key == NEXT_KEY1 or key == NEXT_KEY2 then
				next_track()
			end
		end
	end
end

local function on_message(msg)
	if not in_race then
		return
	end
	local name = tostring(msg)
	for k, v in pairs(UIEnums.Message) do
		if v == msg then
			name = k
		end
	end
	note("msg", name)
	if name == NEXT_MSG then          -- timed, to see if a hold repeats it (unnamed messages come every frame)
		log(string.format("t %.2f %s", clock, name))
	end
	if name == NEXT_MSG then
		-- double press (2026-10-26, against a single accidental press); a hold needs a release message, not known yet
		if clock - last_l3 <= DOUBLE_PRESS then
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
	note("screen", s)
	local race = s == "ingame\\hud.lua" or s == "ingame\\paused.lua"
	if race and not in_race then
		local t = options()
		on_value = t and t.music_type or nil
		if on_value ~= nil then
			off_value = (on_value == 0) and 1 or 0
		end
		log("race, music_type " .. tostring(on_value))
	elseif not race and in_race and pending_on > 0 then   -- left mid-skip: leave the player's option as it was
		pending_on = -1
		set_music(on_value)
	end
	in_race = race
end

M.PushScreen = M.GoScreen

function M.init()
	return true
end

return M
