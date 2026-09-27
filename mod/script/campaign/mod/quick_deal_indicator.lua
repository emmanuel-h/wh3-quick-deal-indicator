-- Quick Deal Indicator
-- Shows on the HUD diplomacy button how many factions have a Quick Deal the AI
-- would accept (deal chance >= 0).
--
-- Never call SetTooltipText on the vanilla diplomacy button: its tooltip is driven
-- by a ContextTooltipSetter callback, and doing so crashed the game (see DEBUG.md).
--
-- Read-only: the mod only queries the model and changes the local player's HUD,
-- so it is safe in multiplayer.

local LOG_PREFIX = "[QDI] "
local DIPLOMACY_PANEL = "diplomacy_dropdown"
local MIN_SCORE = 0
local BADGE_NAME = "quick_deal_indicator_badge"
local BADGE_LAYOUT = "ui/quick_deal_indicator/badge.twui.xml"

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
			f:write(msg .. "\n")
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

--- Shows the number of factions on the diplomacy button, or hides the badge at 0.
local function update_badge(button, faction_count)
	local badge = core:get_or_create_component(BADGE_NAME, BADGE_LAYOUT, button)
	if faction_count > 0 then
		badge:SetStateText(tostring(faction_count))
		badge:SetVisible(true)
	else
		badge:SetVisible(false)
	end
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
		update_badge(button, faction_count)
		log("badge updated")
	end)
	if not ok then
		log("ERROR during refresh: " .. tostring(err))
	end
end

local function init()
	log("init, HUD " .. (hud_enabled and "enabled" or "disabled (" .. NO_HUD_FILE .. ")"))

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

	core:add_listener(
		"qdi_diplomacy_closed",
		"PanelClosedCampaign",
		function(context)
			return context.string == DIPLOMACY_PANEL
		end,
		function()
			refresh("diplomacy closed")
		end,
		true
	)
end

cm:add_first_tick_callback(init)
