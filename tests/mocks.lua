-- Minimal fakes of the WH3 campaign scripting API used by the mod.
-- Tests configure `mock` then load the mod script and fire events.
--
-- Accessing any cm/core/common function that isn't faked raises an error, so the
-- tests catch calls the mod makes that we haven't vetted (e.g. anything that would
-- modify the game model).

mock = {
	logs = {},
	listeners = {},
	first_tick = {},
	real_callbacks = {},
	local_faction = "player",
	multiplayer = false,
	factions = {},   -- name -> { dead = bool, scores = { option = { score, can_issue } } }
	met = {},        -- ordered list of faction names met by the local faction
	loc = {},        -- key -> localised string
	ui_ready = true, -- false: find_uicomponent finds nothing
}

local function strict(name, t)
	return setmetatable(t, {
		__index = function(_, key)
			error("mock: " .. name .. "." .. tostring(key) .. " is not faked", 2)
		end,
	})
end

function out(msg)
	table.insert(mock.logs, msg)
end

-- Model ----------------------------------------------------------------------

local function faction_interface(name)
	return strict("faction", {
		name = function() return name end,
		is_dead = function() return mock.factions[name].dead == true end,
		factions_met = function()
			local list = {}
			for _, other in ipairs(mock.met) do
				table.insert(list, faction_interface(other))
			end
			return list
		end,
	})
end

function model_pairs(list)
	return ipairs(list)
end

-- UI ------------------------------------------------------------------------

local function new_component(id)
	local c = { id = id, children = {}, visible = true, state_text = "", tooltip = "", layout = nil }
	c.Id = function() return c.id end
	c.ChildCount = function() return #c.children end
	c.Find = function(_, i) return c.children[i + 1] end
	c.CreateComponent = function(_, name, path)
		local child = new_component(name)
		child.layout = path
		-- Layouts start hidden (badge.twui.xml has visible="false").
		child.visible = false
		table.insert(c.children, child)
		return child
	end
	c.SetStateText = function(_, text) c.state_text = text end
	c.SetVisible = function(_, v) c.visible = v end
	c.Visible = function() return c.visible end
	c.GetTooltipText = function() return c.tooltip end
	c.SetTooltipText = function(_, text, all_states)
		assert(all_states == true, "SetTooltipText should apply to all states")
		c.tooltip = text
	end
	return c
end

mock.ui_root = new_component("root")
mock.diplomacy_button = new_component("button_diplomacy")
-- The vanilla button's tooltip is driven by a ContextTooltipSetter callback;
-- setting it from script crashed the game in testing.
mock.diplomacy_button.SetTooltipText = function()
	error("SetTooltipText on button_diplomacy is forbidden (crashes the game)", 2)
end

function UIComponent(c)
	return c
end

function find_uicomponent(parent, ...)
	local path = { ... }
	if mock.ui_ready and parent == mock.ui_root
		and path[1] == "faction_buttons_docker" and path[2] == "button_diplomacy" and #path == 2 then
		return mock.diplomacy_button
	end
	return false
end

-- Game interfaces -------------------------------------------------------------

cm = strict("cm", {
	add_first_tick_callback = function(_, f) table.insert(mock.first_tick, f) end,
	get_local_faction_name = function(_, force)
		assert(force == true, "get_local_faction_name must be forced (multiplayer)")
		return mock.local_faction
	end,
	get_faction = function(_, name) return faction_interface(name) end,
	is_multiplayer = function() return mock.multiplayer end,
	cai_evaluate_quick_deal_action = function(_, me, other, option)
		assert(me:name() == mock.local_faction, "evaluated for a non-local faction")
		local entry = mock.factions[other:name()].scores[option]
		if not entry then
			return 0, false
		end
		return entry[1], entry[2]
	end,
	real_callback = function(_, f, ms, name)
		table.insert(mock.real_callbacks, { f = f, ms = ms, name = name })
	end,
})

core = strict("core", {
	get_ui_root = function() return mock.ui_root end,
	add_listener = function(_, name, event, condition, callback, persistent)
		table.insert(mock.listeners, { name = name, event = event, condition = condition, callback = callback })
	end,
	-- Same logic as vanilla lib_core.lua.
	get_or_create_component = function(_, name, path, parent)
		parent = parent or mock.ui_root
		for i = 0, parent:ChildCount() - 1 do
			local child = UIComponent(parent:Find(i))
			if child:Id() == name then
				return child, false
			end
		end
		return UIComponent(parent:CreateComponent(name, path)), true
	end,
})

common = strict("common", {
	get_localised_string = function(key)
		return mock.loc[key] or ("<" .. key .. ">")
	end,
})

-- Helpers for tests -------------------------------------------------------------

function mock.run_first_tick()
	for _, f in ipairs(mock.first_tick) do f() end
end

-- Fires an event; `context` is a table of fields/methods.
function mock.fire(event, context)
	for _, l in ipairs(mock.listeners) do
		if l.event == event and l.condition(context) then
			l.callback(context)
		end
	end
end

function mock.run_real_callbacks()
	local pending = mock.real_callbacks
	mock.real_callbacks = {}
	for _, cb in ipairs(pending) do cb.f() end
end

function mock.badge()
	for _, child in ipairs(mock.diplomacy_button.children) do
		if child.id == "quick_deal_indicator_badge" then
			return child
		end
	end
	return nil
end
