-- Global launcher for the Little Zen Sine mod.
-- Load with: littleZen = require("little-zen")
local M = {}
local bundleID = "app.zen-browser.zen"
local menuTitle = "New Little Zen"
local pending

function M.open()
    if pending then
        pending:stop()
        pending = nil
    end
    local app = hs.application.get(bundleID)
    if not app then
        hs.application.launchOrFocusByBundleID(bundleID)
    else
        app:activate()
    end

    local attempts = 0
    local openedMainWindow = false
    pending = hs.timer.doEvery(0.1, function()
        attempts = attempts + 1
        local target = hs.application.get(bundleID)
        if target and target:selectMenuItem(menuTitle) then
            pending:stop()
            pending = nil
        elseif attempts >= 100 then
            pending:stop()
            pending = nil
            hs.alert.show("Little Zen is unavailable. Enable its Sine mod in Zen.")
        elseif target and not openedMainWindow and #target:allWindows() == 0 then
            -- Zen can still be running with only its macOS hidden window.
            -- Bootstrap a regular window so Sine can install its menu command.
            openedMainWindow = target:selectMenuItem({"File", "New Window"}) or false
        end
    end)
end

function M.stop()
    if pending then pending:stop(); pending = nil end
    if M.hotkey then M.hotkey:delete(); M.hotkey = nil end
end

M.hotkey = hs.hotkey.bind({"cmd", "alt"}, "n", M.open)
return M
