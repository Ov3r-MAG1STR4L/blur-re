-- Railgun: a "Railgun On / Off" row in the custom race Power-up Options (test copy only, with railgun.dll).
-- The game's screen (Blur.exe BZUI, Screens\Multiplayer\Shared\MpCustomRacePowerups.lua) builds its right column
-- with CustomRace_SetupToggle(GUI.table_id, option, text, icon, "perk_icons") for Random (3), Shunt (10) and
-- Shield (9); the 4th place is free. We add our row (option 12) right after the Shield's AddTableRow, keep the
-- choice in UIGlobals.CustomRaceSettings.powerups.railgun, and hand it to railgun.dll when the race is set up
-- (Amax.SetupRace) through package.loadlib (two exported functions, no argument).
local M = {
	info = {
		name = "Railgun",
		description = "Railgun On / Off in the custom race power-up options",
		version = 0.1,
	},
}

local RAIL = 12
local DLL = ".\\amax\\dlls\\railgun.dll"
local wrapped = false
local rail_id = nil

local function settings()
	local s = UIGlobals and UIGlobals.CustomRaceSettings
	if s and s.powerups and s.powerups.railgun == nil then
		s.powerups.railgun = true
	end
	return s
end

local VANILLA = { "bolt", "shock", "mine", "nitro", "barge", "shield", "shunt", "repair" }

local function tell_dll(mode)
	if not (package and package.loadlib) then
		print_api("railgun: no package.loadlib, the switch cannot reach railgun.dll")
		return
	end
	local f, err = package.loadlib(DLL, "railgun_" .. mode)
	if f then f() else print_api("railgun: " .. tostring(err)) end
end

local function add_row(table_id)
	local s = settings()
	local text = (UIText and (UIText.CMN_SUPER_SHIELD or UIText.MP_POWERUP_BOLT))
	rail_id = CustomRace_SetupToggle(table_id, RAIL, text, "perk_bolt", "perk_icons")
	GUI.options.railgun = RAIL
	GUI.powerups[RAIL] = rail_id
	UIButtons.SetSelection(rail_id, BoolToNumber(s == nil or s.powerups.railgun))
	CustomRace_SetupPowerupIcon(rail_id, "Shield_Glow")
end

local function wrap()
	if wrapped or not (UIButtons and UIButtons.AddTableRow and Amax and Amax.SetupRace) then
		return
	end
	wrapped = true
	local org_row = UIButtons.AddTableRow
	local busy = false
	UIButtons.AddTableRow = function(table_id, node, option, ...)
		local r = org_row(table_id, node, option, ...)
		if not busy and GUI and GUI.options and GUI.powerups and GUI.options.shield == option
			and GUI.table_id == table_id and GUI.powerups[RAIL] == nil and CustomRace_SetupToggle then
			busy = true
			pcall(add_row, table_id)
			busy = false
		end
		return r
	end
	local org_setup = Amax.SetupRace
	Amax.SetupRace = function(s, ...)
		if rail_id and GUI and GUI.powerups and GUI.powerups[RAIL] == rail_id and s and s.powerups then
			local ok, v = pcall(UIButtons.GetSelection, rail_id)
			if ok then s.powerups.railgun = NumberToBool(v) end
		end
		local on = not (s and s.powerups and s.powerups.railgun == false)
		local any = false
		for _, k in ipairs(VANILLA) do
			if s and s.powerups and s.powerups[k] then any = true end
		end
		if on and not any and s and s.powerups then
			-- railgun only: the game turns every power-up off when the 8 of its own are off (CustomRace.cpp:
			-- mPickupsEnabled), so the Bolt goes on behind the scenes, every position draws (random power-ups), and
			-- the dll refuses every type but the railgun. The menu keeps the user's choice.
			local bolt, random = s.powerups.bolt, s.random_powerups
			s.powerups.bolt, s.random_powerups = true, 1
			tell_dll("only")
			local r = { org_setup(s, ...) }
			s.powerups.bolt, s.random_powerups = bolt, random
			return unpack(r)
		end
		tell_dll(on and "on" or "off")
		return org_setup(s, ...)
	end
end

function M.PushScreen(_screen) wrap() end
function M.GoScreen(_screen, _opts) wrap() end

function M.init()
	return true
end

return M
