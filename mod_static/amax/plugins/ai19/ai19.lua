-- AI19: "Max AI" beyond 18 in custom races (19 AI = 20 cars = the engine limit; MAX_AI below).
-- The game's menu script (Blur.exe, BZUI archive, Screens\Multiplayer\Shared\MpCustomRaceAdvanced.lua) builds the
-- list with: for i = 2, 18 do UIButtons.AddItem(GUI.ai_padding_id, i, "GAME_NUM_" .. i, true) end
-- This plugin wraps UIButtons.AddItem and adds 19..MAX_AI right after 18. Needs max_ai_per_console >= MAX_AI.
local M = {
	info = {
		name = "AI19",
		description = "Max AI up to 19 in custom races",
		version = 0.1,
	},
}

-- MAX_AI: 19 = 20 cars, the engine's known limit. Raised for an experiment (does the game clamp, crash, or accept?)
local MAX_AI = 49

local ORG_AddItem = nil

function M.PushScreen(_screen)
	if ORG_AddItem or not (UIButtons and UIButtons.AddItem) then
		return
	end
	ORG_AddItem = UIButtons.AddItem
	UIButtons.AddItem = function(id, value, text, ...)
		local r = ORG_AddItem(id, value, text, ...)
		if value == 18 and GUI and GUI.ai_padding_id ~= nil and id == GUI.ai_padding_id then
			for i = 19, MAX_AI do
				ORG_AddItem(id, i, "GAME_NUM_" .. i, ...)
			end
		end
		return r
	end
end

function M.init()
	return true
end

return M
