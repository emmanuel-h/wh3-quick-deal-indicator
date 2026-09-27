-- Quick Deal Indicator
-- Shows on the HUD diplomacy button how many factions have a Quick Deal the AI
-- would accept (deal chance >= 0). The badge's tooltip lists the deals; clicking
-- it opens diplomacy with the Quick Deal view enabled.
--
-- Never call SetTooltipText on the vanilla diplomacy button: its tooltip is driven
-- by a ContextTooltipSetter callback, and doing so crashed the game (see README).
-- The tooltip lives on our own badge component instead.
--
-- Read-only: the mod only queries the model and changes the local player's HUD,
-- so it is safe in multiplayer.

local LOG_PREFIX = "[QDI] "
local DIPLOMACY_PANEL = "diplomacy_dropdown"
local MIN_SCORE = 0
local BADGE_NAME = "quick_deal_indicator_badge"
local BADGE_LAYOUT = "ui/quick_deal_indicator/badge.twui.xml"
local QUICK_DEAL_BUTTON_PATH = { DIPLOMACY_PANEL, "faction_panel", "faction_panel_bottom", "buttons_bl", "button_quick_deal" }
local DEAL_TYPE_LIST_PATH = { DIPLOMACY_PANEL, "faction_panel", "list_quick_deal_buttons" }
-- Delay between the steps of the badge click flow, so each simulated click has fully
-- returned and the panel it opens is built before the next step looks for it.
local CLICK_STEP_DELAY_MS = 300

-- Game events after which deals are re-checked (during the local player's turn),
-- in addition to turn start and any panel closing.
local REFRESH_EVENTS = {
	"CharacterFinishedMovingEvent",
	"BattleCompleted",
	"GarrisonOccupiedEvent",
	"RegionFactionChangeEvent",
	"PositiveDiplomaticEvent",
	"NegativeDiplomaticEvent",
}
local REFRESH_DELAY_MS = 250

-- All tooltip text comes from vanilla strings, so it follows the game language.
local LOC_QUICK_DEAL = "uied_component_texts_localised_string_dy_province_owned_Text_3f0076"
local LOC_OPTION_PREFIX = "diplomacy_quick_deal_offers_localised_quick_deal_title_"
local LOC_FACTION_PREFIX = "factions_screen_name_"

-- Incremented on each badge click; a step of the click flow only acts if it still
-- belongs to the latest click.
local click_flow_id = 0
-- A refresh is already scheduled.
local refresh_pending = false

-- Every Quick Deal offer (vanilla diplomacy_quick_deal_offers table), in the
-- order of the buttons under the Known Factions list. Options a faction can't
-- use are reported with can_issue == false and skipped.
local OPTIONS = {
	"diplomatic_option_nonaggression_pact",
	"diplomatic_option_trade_agreement",
	"diplomatic_option_soft_access",
	"diplomatic_option_defensive_alliance",
	"diplomatic_option_military_alliance",
	"diplomatic_option_peace",
	"diplomatic_option_vassal",
	"diplomatic_option_client_state",
	"diplomatic_option_confederation",
}

-- Debug switches: empty files in the game folder, checked once when the script loads.
--   quick_deal_indicator_debug.txt  - the mod appends its log to this file.
--   quick_deal_indicator_no_hud.txt - scan and log only, never touch the HUD
--                                     (to rule the badge/tooltip in or out of a problem).
local DEBUG_FILE = "quick_deal_indicator_debug.txt"
local NO_HUD_FILE = "quick_deal_indicator_no_hud.txt"

local function file_exists(name)
	local ok, exists = pcall(function()
		local f = io.open(name, "r")
		if f then
			f:close()
			return true
		end
		return false
	end)
	return ok and exists
end

local debug_enabled = file_exists(DEBUG_FILE)
local hud_enabled = not file_exists(NO_HUD_FILE)

local function log(msg)
	msg = LOG_PREFIX .. tostring(msg)
	out(msg)
	if debug_enabled then
		pcall(function()
			local f = io.open(DEBUG_FILE, "a")
			f:write(string.format("%9.2f %s\n", os.clock(), msg))
			f:close()
		end)
	end
end

local function local_faction()
	return cm:get_faction(cm:get_local_faction_name(true))
end

--- Returns the deals the AI would accept, sorted by faction then best score:
-- { { faction = FACTION_SCRIPT_INTERFACE, option = string, score = number }, ... }
-- and the number of distinct factions in that list.
local function scan()
	local me = local_faction()
	local deals = {}
	local faction_count = 0

	for _, other in model_pairs(me:factions_met()) do
		if not other:is_dead() then
			local found = false
			for _, option in ipairs(OPTIONS) do
				local score, can_issue = cm:cai_evaluate_quick_deal_action(me, other, option)
				if can_issue and score >= MIN_SCORE then
					table.insert(deals, { faction = other, option = option, score = score })
					found = true
				end
			end
			if found then
				faction_count = faction_count + 1
			end
		end
	end

	table.sort(deals, function(a, b)
		if a.faction:name() ~= b.faction:name() then
			return a.faction:name() < b.faction:name()
		end
		return a.score > b.score
	end)

	return deals, faction_count
end

local function diplomacy_button()
	return find_uicomponent(core:get_ui_root(), "faction_buttons_docker", "button_diplomacy")
end

--- "Quick Deal||Faction - Deal type (chance)" lines, in the game's language.
local function build_tooltip(deals)
	local lines = {}
	for _, deal in ipairs(deals) do
		table.insert(lines, string.format("%s - %s (%.1f)",
			common.get_localised_string(LOC_FACTION_PREFIX .. deal.faction:name()),
			common.get_localised_string(LOC_OPTION_PREFIX .. deal.option),
			deal.score))
	end
	return common.get_localised_string(LOC_QUICK_DEAL) .. "||" .. table.concat(lines, "\n")
end

--- Shows the number of factions and the deal list on our badge, or hides it at 0.
local function update_badge(button, deals, faction_count)
	local badge = core:get_or_create_component(BADGE_NAME, BADGE_LAYOUT, button)
	if faction_count > 0 then
		badge:SetStateText(tostring(faction_count))
		badge:SetTooltipText(build_tooltip(deals), true)
		badge:SetVisible(true)
	else
		badge:SetVisible(false)
	end
end

--- Whether a toggle button's state is one of its "selected*" states. Tolerant on purpose:
-- in-game, a state logged as "selected" didn't match the pattern "^selected".
local function is_selected(state)
	return tostring(state):lower():find("selected", 1, true) ~= nil
end

--- First option, in the diplomacy screen's order, with at least one deal; nil if none.
local function first_available_option(deals)
	local available = {}
	for _, deal in ipairs(deals) do
		available[deal.option] = true
	end
	for _, option in ipairs(OPTIONS) do
		if available[option] then
			return option
		end
	end
	return nil
end

--- Selects the deal-type button for `option` under the Known Factions list.
-- The game creates these buttons with the option key as id (seen in-game, e.g.
-- "diplomatic_option_nonaggression_pact"). Only ids and states are read: reading
-- tooltips of game components is avoided (suspected in a crash, see README).
local function select_deal_type(option)
	local list = find_uicomponent(core:get_ui_root(), unpack(DEAL_TYPE_LIST_PATH))
	if not list then
		log("deal type list not found")
		return
	end
	local button = find_uicomponent(list, option)
	if not button then
		log("no deal type button " .. option .. " (" .. list:ChildCount() .. " buttons), keeping the game's selection")
		return
	end
	local state = button:CurrentState()
	if is_selected(state) then
		log(string.format("deal type %s already selected (%q)", option, tostring(state)))
		return
	end
	log(string.format("clicking deal type %s (was %q)", option, tostring(state)))
	button:SimulateLClick()
	log("deal type " .. option .. " selected")
end

--- Presses the diplomacy screen's Quick Deal button unless it is already on.
local function enable_quick_deal_view()
	local button = find_uicomponent(core:get_ui_root(), unpack(QUICK_DEAL_BUTTON_PATH))
	if not button then
		log("quick deal button not found")
		return
	end
	local state = button:CurrentState()
	if is_selected(state) then
		log(string.format("quick deal view already enabled (%q)", tostring(state)))
		return
	end
	log(string.format("clicking quick deal button (was %q)", tostring(state)))
	button:SimulateLClick()
	log("quick deal view enabled")
end

--- Runs `step` after CLICK_STEP_DELAY_MS if no newer badge click happened meanwhile.
local function after_delay(flow_id, name, step)
	cm:real_callback(function()
		if flow_id ~= click_flow_id then
			log(name .. ": superseded by a newer click, skipped")
			return
		end
		log(name)
		local ok, err = pcall(step)
		if not ok then
			log("ERROR in " .. name .. ": " .. tostring(err))
		end
	end, CLICK_STEP_DELAY_MS, "qdi_" .. name:gsub(" ", "_"))
end

--- Badge click: open diplomacy, then the Quick Deal view, then the deal type.
-- Every step runs from a timer, never inside a UI event, and is only scheduled once
-- the previous simulated click has returned: reacting to PanelOpenedCampaign (which
-- fires inside SimulateLClick) ran our next step re-entrantly on a half-built panel,
-- stalled the script and crashed the game.
local function start_click_flow()
	click_flow_id = click_flow_id + 1
	local flow_id = click_flow_id
	local option = first_available_option((scan()))
	log("badge clicked, first deal type: " .. tostring(option))

	cm:real_callback(function()
		if flow_id ~= click_flow_id then
			return
		end
		local ok, err = pcall(function()
			log("clicking diplomacy button")
			diplomacy_button():SimulateLClick()
			log("diplomacy button clicked")
		end)
		if not ok then
			log("ERROR clicking diplomacy button: " .. tostring(err))
			return
		end
		after_delay(flow_id, "quick deal step", function()
			if not find_uicomponent(core:get_ui_root(), DIPLOMACY_PANEL) then
				log("diplomacy panel not open, stopping")
				return
			end
			enable_quick_deal_view()
			if option then
				after_delay(flow_id, "deal type step", function()
					select_deal_type(option)
				end)
			end
		end)
	end, 0, "qdi_open_diplomacy")
end

local function refresh(reason)
	local ok, err = pcall(function()
		local deals, faction_count = scan()
		log(string.format("refresh (%s): %d deal(s) with %d faction(s)", reason, #deals, faction_count))
		for _, deal in ipairs(deals) do
			log(string.format("  %s %s %.1f", deal.faction:name(), deal.option, deal.score))
		end

		if not hud_enabled then
			return
		end
		local button = diplomacy_button()
		if not button then
			log("diplomacy button not found, HUD not updated")
			return
		end
		update_badge(button, deals, faction_count)
		log("badge updated")
	end)
	if not ok then
		log("ERROR during refresh: " .. tostring(err))
	end
end

--- Refreshes shortly after a game event, during the local player's turn only.
-- Events arriving together (e.g. a battle ending and a region changing hands)
-- produce a single scan.
local function schedule_refresh(reason)
	if not cm:is_local_players_turn(true) then
		log("event " .. reason .. ": not the local player's turn, skipped")
		return
	end
	if refresh_pending then
		log("event " .. reason .. ": refresh already scheduled")
		return
	end
	log("event " .. reason .. ": refresh scheduled")
	refresh_pending = true
	cm:real_callback(function()
		refresh_pending = false
		refresh(reason)
	end, REFRESH_DELAY_MS, "qdi_refresh")
end

local function init()
	log("init, HUD " .. (hud_enabled and "enabled" or "disabled (" .. NO_HUD_FILE .. ")"))

	-- Debug mode: a log line every 5 s shows whether the script's timers still run.
	if debug_enabled then
		cm:repeat_real_callback(function()
			log("heartbeat")
		end, 5000, "qdi_heartbeat")
	end

	-- Loading a save mid-turn: show the current state straight away.
	refresh("campaign loaded")

	core:add_listener(
		"qdi_turn_start",
		"ScriptEventHumanFactionTurnStart",
		function(context)
			return context:faction():name() == cm:get_local_faction_name(true)
		end,
		function()
			refresh("turn start")
		end,
		true
	)

	-- Anything that can change a deal's chance: armies moving, battles, settlements
	-- changing hands, diplomatic events, and closing any panel (diplomacy included).
	for _, event in ipairs(REFRESH_EVENTS) do
		core:add_listener(
			"qdi_refresh_" .. event,
			event,
			true,
			function()
				schedule_refresh(event)
			end,
			true
		)
	end

	core:add_listener(
		"qdi_panel_closed",
		"PanelClosedCampaign",
		true,
		function(context)
			schedule_refresh("panel closed: " .. tostring(context.string))
		end,
		true
	)

	-- Clicking the badge opens diplomacy (as the button would), then the Quick Deal
	-- view on the first deal type that has an acceptable deal.
	core:add_listener(
		"qdi_badge_clicked",
		"ComponentLClickUp",
		function(context)
			return hud_enabled and context.string == BADGE_NAME
		end,
		function()
			local ok, err = pcall(start_click_flow)
			if not ok then
				log("ERROR handling badge click: " .. tostring(err))
			end
		end,
		true
	)
end

cm:add_first_tick_callback(init)
