local source = assert(...)
local cases = {}
local function run(name, frontContains, targetBundle, flags, wantAlt, wantFocus)
    local callback, focused
    local target = {
        frame = function() return {inside=true} end,
        application = function() return {bundleID=function() return targetBundle end} end,
        focus = function() focused=true end,
    }
    local mock = {
        eventtap = {
            event = {types={leftMouseDown=1}},
            new = function(_, fn)
                callback=fn
                return {start=function() end,stop=function() end}
            end,
        },
        geometry = function() return {inside=function(_,r) return r.inside end} end,
        window = {
            frontmostWindow = function() return {frame=function() return {inside=frontContains} end} end,
            orderedWindows = function() return {target} end,
        },
    }
    local env=setmetatable({hs=mock,optClickTap=false},{__index=_G})
    assert(load(source,"option-click-guard","t",env))()
    local event = {
        getFlags=function() return flags end,
        location=function() return {x=0,y=0} end,
        setFlags=function(_,value) flags=value end,
    }
    assert(callback(event)==false,name.." swallowed the click")
    assert(not not flags.alt==wantAlt,name.." incorrect modifier")
    assert(not not focused==wantFocus,name.." incorrect focus")
    cases[#cases+1]=name
end
run("foreground",true,"unrelated.app",{alt=true},true,false)
run("background Zen",false,"app.zen-browser.zen",{alt=true},true,true)
run("background Arc",false,"company.thebrowser.Browser",{alt=true},true,true)
run("other background app",false,"unrelated.app",{alt=true,cmd=true},false,false)
run("normal click",false,"app.zen-browser.zen",{},false,false)
return cases
