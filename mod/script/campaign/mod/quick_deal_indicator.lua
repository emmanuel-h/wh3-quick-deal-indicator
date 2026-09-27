-- Quick Trade Indicator
-- Shows which factions have a Quick Deal available with a score >= 0.
--
-- Scripts in script/campaign/mod/ are loaded automatically by the campaign
-- script environment; cm:add_first_tick_callback runs once the game is ready.

local LOG_PREFIX = "[QTI] "

local function log(msg)
	out(LOG_PREFIX .. tostring(msg))
end

-- UI component paths. These MUST be verified in-game with the UI inspector,
-- they are placeholders for where the diplomacy panel exposes its data.
local UI = {
	diplomacy_panel = "diplomacy_dropdown",
	quick_deal_button = "button_quick_deal",   -- TODO: verify
	deal_score_text = "deal_score",            -- TODO: verify
}

local MIN_SCORE = 0

-- Faction key -> score of the best Quick Deal found during the last scan.
local quick_deal_scores = {}

local function reset_scores()
	quick_deal_scores = {}
end

--- Reads the score shown after a Quick Deal has been proposed.
-- @return number|nil
local function read_current_deal_score()
	local panel = find_uicomponent(core:get_ui_root(), UI.diplomacy_panel)
	if not panel then
		return nil
	end

	local score_uic = find_uicomponent(panel, UI.deal_score_text)
	if not score_uic then
		return nil
	end

	return tonumber(score_uic:GetStateText():match("-?%d+"))
end

--- Returns the list of faction keys that currently have a Quick Deal with score >= MIN_SCORE.
local function get_available_quick_deals()
	local result = {}
	for faction_key, score in pairs(quick_deal_scores) do
		if score >= MIN_SCORE then
			table.insert(result, faction_key)
		end
	end
	table.sort(result)
	return result
end

local function on_diplomacy_opened()
	reset_scores()
	log("Diplomacy panel opened, scanning factions")
	-- TODO: iterate the faction list, select each faction, press the Quick Deal
	-- button, read the score with read_current_deal_score(), store it in
	-- quick_deal_scores, then decorate the faction rows whose score >= MIN_SCORE.
end

local function init()
	log("Initialising")

	core:add_listener(
		"qti_diplomacy_opened",
		"PanelOpenedCampaign",
		function(context)
			return context.string == UI.diplomacy_panel
		end,
		on_diplomacy_opened,
		true
	)

	core:add_listener(
		"qti_diplomacy_closed",
		"PanelClosedCampaign",
		function(context)
			return context.string == UI.diplomacy_panel
		end,
		function()
			local available = get_available_quick_deals()
			log("Factions with a Quick Deal >= " .. MIN_SCORE .. ": " .. table.concat(available, ", "))
		end,
		true
	)
end

cm:add_first_tick_callback(init)
