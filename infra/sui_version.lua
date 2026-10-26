-- Semantic version ordering, including numbered personal pre-releases.
local M = {}
local function parse(v)
    local a, b, c, tail = tostring(v or ""):match("^v?(%d+)%.(%d+)%.(%d+)(.*)$")
    if not a then return nil end
    local pre = tail:match("^%-([^+]+)")
    local ids = {}
    if pre then for id in pre:gmatch("[^.]+") do ids[#ids + 1] = id end end
    return { tonumber(a), tonumber(b), tonumber(c), pre = pre, ids = ids }
end
function M.greater(a, b)
    local x, y = parse(a), parse(b)
    if not x or not y then return false end
    for i = 1, 3 do
        if x[i] ~= y[i] then return x[i] > y[i] end
    end
    if not x.pre then return y.pre ~= nil end
    if not y.pre then return false end
    for i = 1, math.max(#x.ids, #y.ids) do
        local l, r = x.ids[i], y.ids[i]
        if not l then return false end
        if not r then return true end
        if l ~= r then
            local ln, rn = tonumber(l), tonumber(r)
            if ln and rn then return ln > rn end
            if ln then return false end
            if rn then return true end
            return l > r
        end
    end
    return false
end
return M
