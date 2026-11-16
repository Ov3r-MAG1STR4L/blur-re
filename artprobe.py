#!/usr/bin/env python3
"""Album-art probe (Blur_test only, 2026-11-16): can an AMAX plugin show a picture square in the race HUD?
Installs the plugin artprobe: in a race, a square (clone of gfx_FanBlobSingleC, the fan-message backing) above the
music banner, opening from its centre and closing on itself like fan_message (scale.x keys), in a 4 s loop. Its
texture is set with UIButtons.ChangeTexture({filename, pos={u,v}, size={u,v}}, 0.0, id) (form used by HUD.luac);
the 8 key (CMN_8) goes to the next texture variant, the 7 key to the next gadget template
(probe 1: gfx_FanBlobSingleC lives in another unit space: 6 x 6 = a dot, top-left). Log in memory: read_luamarks.py APROBE.
usage: artprobe.py [--undo]   (Blur closed)"""
import os, shutil, sys
import make_music as mm

PLUGINS = os.path.join(mm.TEST, "amax", "plugins", "plugins.lua")
PLUGIN_DIR = os.path.join(mm.TEST, "amax", "plugins", "artprobe")
REQUIRE = 'require("artprobe.artprobe"),'
PLUGIN = r'''-- artprobe: album-art probe (Blur_test only). 8 = next texture variant, in a race.
local M = { info = { name = "ArtProbe", description = "Album art probe", version = 0.1 } }
local ART_X, ART_Y, ART_W, ART_H = -3.5, 11.0, 6.0, 6.0     -- HUD units, parent HUD.ViewportId3d, BottomLeft (y goes up)
local CYCLE, OPEN, CLOSE_AT = 4.0, 0.19, 3.6
local VARIANTS = {
	{ "hud_main full", { filename = "hud_main", pos = { u = 0.0, v = 0.0 }, size = { u = 1.0, v = 1.0 } } },
	{ "hud_main fan combo", { filename = "hud_main", pos = { u = 0.3125, v = 0.125 }, size = { u = 0.0625, v = 0.125 } } },
	{ "hud_grad full", { filename = "hud_grad", pos = { u = 0.0, v = 0.0 }, size = { u = 1.0, v = 1.0 } } },
	{ "light_paint_02 full", { filename = "light_paint_02", pos = { u = 0.0, v = 0.0 }, size = { u = 1.0, v = 1.0 } } },
	{ "unknown name", { filename = "blur_music_art", pos = { u = 0.0, v = 0.0 }, size = { u = 1.0, v = 1.0 } } },
}
local TEMPLATES = { "Position_Team_Icon", "Pos_BackingBottom", "Fans_Icon", "gfx_FanBlobSingleC" }   -- 7 = next
local template = 1
local ready, art, variant, t0, clock, last_key, n_log = false, nil, 1, 0, 0, "", 0
local wrapped = false

local function log(text)
	n_log = n_log + 1
	APROBE_BODY = (APROBE_BODY or "") .. "\n" .. text
	APROBE_ALL = "APROBE#" .. n_log .. "#" .. APROBE_BODY .. "#ALLEND"
end

local function apply()
	local v = VARIANTS[variant]
	local ok, err = pcall(UIButtons.ChangeTexture, v[2], 0.0, art.id)
	log("variant " .. variant .. " (" .. v[1] .. "): ChangeTexture " .. tostring(ok) .. " " .. tostring(err))
end

local function build()
	local parent = type(HUD) == "table" and type(HUD.ViewportId3d) == "table" and (HUD.ViewportId3d[1] or HUD.ViewportId3d[0])
	if not parent then return end
	local id = UIButtons.CloneXtGadgetByName("hud_objects", TEMPLATES[template])
	UIButtons.SetParent(id, parent, UIEnums.Justify.BottomLeft)
	local w0, h0 = UIButtons.GetSize(id)
	local _, _, z = UIButtons.GetPosition(id)
	art = { id = id, z = z or 0.0 }
	UIButtons.ChangeSize(id, ART_W, ART_H)
	UIButtons.ChangePosition(id, ART_X, ART_Y, art.z)
	pcall(UIButtons.ChangeColour, id, "!255 255 255 255")
	UIButtons.ChangeAlpha(id, 1.0)
	pcall(UIButtons.SetAlphaIntensity, id, 1.0, 1.0)
	UIButtons.SetActive(id, true)
	local w1, h1 = UIButtons.GetSize(id)
	log("built " .. TEMPLATES[template] .. " " .. tostring(id) .. " size " .. tostring(w0) .. "x" .. tostring(h0) .. " -> " .. tostring(w1) .. "x" .. tostring(h1))
	apply()
	t0 = clock
end

local function tick()
	clock = clock + 1 / 60
	if not ready then return end
	if not art then build() return end
	local t = (clock - t0) % CYCLE                           -- fan_message keys: open from the centre, hold, close on itself
	local sx = 1.0
	if t < OPEN then sx = t / OPEN elseif t > CLOSE_AT then sx = math.max(0, 1 - (t - CLOSE_AT) / OPEN) end
	UIButtons.ChangeScale(art.id, sx, 1.0, 1.0)
	local ok, key = pcall(UIButtons.GetKeyInput)
	key = ok and tostring(key or "") or ""
	if key ~= last_key then
		last_key = key
		if key == "CMN_8" then variant = variant % #VARIANTS + 1 apply() end
		if key == "CMN_7" then
			pcall(UIButtons.SetActive, art.id, false)
			template = template % #TEMPLATES + 1
			art = nil
		end
	end
end

function M.GoScreen(screen, _opts)
	if not wrapped and type(FrameUpdate_Wrapper) == "function" then
		wrapped = true
		local org = FrameUpdate_Wrapper
		FrameUpdate_Wrapper = function(...)
			local r = org(...)
			local ok, err = pcall(tick)
			if not ok then log("tick error " .. tostring(err)) ready = false end
			return r
		end
	end
	local s = string.lower(tostring(screen))
	ready = s == "ingame\\hud.lua"                           -- gadgets are dead after pause / outside the race HUD
	art = nil
end

M.PushScreen = M.GoScreen

function M.init()
	return true
end

return M
'''


def main():
    lua = open(PLUGINS, encoding="utf-8").read()
    if "--undo" in sys.argv:
        open(PLUGINS, "w", encoding="utf-8", newline="\n").write(lua.replace("\n\t" + REQUIRE, ""))
        shutil.rmtree(PLUGIN_DIR, ignore_errors=True)
        print("artprobe removed from Blur_test")
        return
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    open(os.path.join(PLUGIN_DIR, "artprobe.lua"), "w", encoding="utf-8", newline="\n").write(PLUGIN)
    if REQUIRE not in lua:
        k = lua.rstrip().rfind("}")
        os.chmod(PLUGINS, 0o666)
        open(PLUGINS, "w", encoding="utf-8", newline="\n").write(lua[:k].rstrip() + "\n\t" + REQUIRE + "\n}\n")
    print("artprobe installed in", mm.TEST)


if __name__ == "__main__":
    main()
