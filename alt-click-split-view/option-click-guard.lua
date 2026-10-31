-- Preserve link gestures in Zen/Arc, including a browser window that is
-- not frontmost. Other background apps keep the no-hide Option-click guard.
local optionClickBrowsers = {
    ["app.zen-browser.zen"] = true,
    ["company.thebrowser.Browser"] = true,
}

local previousOptionClickTap = optClickTap
optClickTap = hs.eventtap.new({hs.eventtap.event.types.leftMouseDown}, function(event)
    local flags = event:getFlags()
    if not flags.alt then return false end

    local pos = event:location()
    local frontWin = hs.window.frontmostWindow()
    if frontWin and hs.geometry(pos):inside(frontWin:frame()) then
        return false
    end

    for _, win in ipairs(hs.window.orderedWindows()) do
        if hs.geometry(pos):inside(win:frame()) then
            local app = win:application()
            if app and optionClickBrowsers[app:bundleID()] then
                win:focus()
                return false
            end
            break
        end
    end

    local newFlags = {}
    for key, value in pairs(flags) do
        if key ~= "alt" then newFlags[key] = value end
    end
    event:setFlags(newFlags)
    return false
end)
optClickTap:start()
if previousOptionClickTap then previousOptionClickTap:stop() end
