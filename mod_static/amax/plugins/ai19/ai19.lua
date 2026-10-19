-- AI19: "Max AI" up to 19 in custom races (1 player + 19 AI = 20 cars, the engine limit).
-- The game's menu script (Blur.exe, BZUI archive, Screens\Multiplayer\Shared\MpCustomRaceAdvanced.lua) builds the
-- list with: for i = 2, 18 do UIButtons.AddItem(GUI.ai_padding_id, i, "GAME_NUM_" .. i, true) end
-- This plugin wraps UIButtons.AddItem and adds 19 right after 18. Needs multiplayer.bin max_ai_per_console >= 19.
local M = {
	info = {
		name = "AI19",
		description = "Max AI up to 19 in custom races",
		version = 0.1,
	},
}

local ORG_AddItem = nil

function M.PushScreen(_screen)
	if ORG_AddItem or not (UIButtons and UIButtons.AddItem) then
		return
	end
	ORG_AddItem = UIButtons.AddItem
	UIButtons.AddItem = function(id, value, text, ...)
		local r = ORG_AddItem(id, value, text, ...)
		if value == 18 and GUI and GUI.ai_padding_id ~= nil and id == GUI.ai_padding_id then
			ORG_AddItem(id, 19, "GAME_NUM_19", ...)
		end
		return r
	end
end

function M.init()
	return true
end

return M
