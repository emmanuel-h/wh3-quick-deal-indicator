-- Quick Deal Indicator
-- Shows on the HUD diplomacy button how many factions have a Quick Deal the AI
-- would accept (deal chance >= 0). The badge's tooltip lists the deals; clicking
-- it opens diplomacy with the Quick Deal view enabled.
--
-- Never call SetTooltipText on the vanilla diplomacy button: its tooltip is driven
-- by a ContextTooltipSetter callback, and doing so crashed the game (see README).
-- The tooltip lives on our own badge component instead.
--
-- Read-only: the mod only queries the model and changes the local player's HUD.
--
-- Each scan asks the AI to evaluate every deal type with every faction met, which is
-- slow enough to be felt. Scans run only on campaign load, at the start of the local
-- player's turn and when diplomacy closes, and are spread over UI ticks (one faction
-- per tick) so they never freeze a frame.

local VERSION = "1.2.0"
local LOG_PREFIX = "[QDI] "
local DIPLOMACY_PANEL = "diplomacy_dropdown"
local MIN_SCORE = 0
local BADGE_NAME = "quick_deal_indicator_badge"
local BADGE_LAYOUT = "ui/quick_deal_indicator/badge.twui.xml"
-- The badge's parent. Not the diplomacy button itself: its StatePropagatorCallback
-- forces its state onto its children, so the badge couldn't show its own hover state.
-- Not button_group_management either: its RadialList layout would place the badge like
-- another button. faction_buttons_docker has no layout engine.
local BADGE_PARENT = "faction_buttons_docker"
-- Badge size and offset from the diplomacy button's bottom-right corner, as the vanilla
-- missions badge (label_missions_count: 42x41, dock_offset 23,13, anchor 1,1).
local BADGE_W, BADGE_H = 42, 41
local BADGE_OFFSET_X, BADGE_OFFSET_Y = 23, 13
-- Child of the badge showing the number (see badge.twui.xml: it is drawn above the
-- hover glow, which the engine shows while the mouse is over the badge).
local BADGE_COUNT = "qdi_badge_count"
local QUICK_DEAL_BUTTON_PATH = { DIPLOMACY_PANEL, "faction_panel", "faction_panel_bottom", "buttons_bl", "button_quick_deal" }
local DEAL_TYPE_LIST_PATH = { DIPLOMACY_PANEL, "faction_panel", "list_quick_deal_buttons" }
-- The badge click flow waits for conditions (panel opened, button present), checked
-- on a UI timer. The interval is only how often it looks; the timeout only stops the
-- check if the diplomacy screen never shows up (e.g. the button is disabled).
local FLOW_POLL_MS = 50
local FLOW_TIMEOUT_MS = 10000
-- Smallest real timer: fires on the game's next UI tick. Never use 0: vanilla
-- real_callback runs a 0 ms callback immediately, inside the caller.
local NEXT_UPDATE_MS = 1

-- Delay of the refresh after diplomacy closes. Earlier versions also refreshed after
-- army moves, battles, diplomatic events and any panel closing: clicking almost anything
-- opens or closes a panel, and the scans made the game stutter (reported by players).
local REFRESH_DELAY_MS = 250
-- Factions evaluated per UI tick during a scan (each is one AI evaluation per deal type).
local SCAN_FACTIONS_PER_TICK = 1

-- All tooltip text comes from vanilla strings, so it follows the game language.
local LOC_QUICK_DEAL = "uied_component_texts_localised_string_dy_province_owned_Text_3f0076"
local LOC_OPTION_PREFIX = "diplomacy_quick_deal_offers_localised_quick_deal_title_"
local LOC_FACTION_PREFIX = "factions_screen_name_"

-- Badge click flow in progress (nil when idle):
-- { stage = "quick deal" | "deal type", option = string|nil, waited_ms = number }
local flow = nil
-- A refresh is already scheduled.
local refresh_pending = false
-- Scan in progress (nil when idle):
-- { reason = string, names = { faction name, ... }, next = index, deals = {...}, faction_count = number }
local scan_job = nil
-- Deals found by the last finished scan (used by the badge click, which doesn't rescan).
local last_deals = {}

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

--- Names of the factions met by the local player, to scan one per tick. Names, not
-- interfaces: each is looked up again when its turn comes.
local function met_faction_names()
	local names = {}
	for _, other in model_pairs(local_faction():factions_met()) do
		table.insert(names, other:name())
	end
	return names
end

--- Adds to `deals` every deal the AI would accept from the faction `name`:
-- { faction = string, option = string, score = number }. Returns true if there is one.
local function scan_faction(name, deals)
	local other = cm:get_faction(name)
	if not other or other:is_dead() then
		return false
	end
	local me = local_faction()
	local found = false
	for _, option in ipairs(OPTIONS) do
		local score, can_issue = cm:cai_evaluate_quick_deal_action(me, other, option)
		if can_issue and score >= MIN_SCORE then
			table.insert(deals, { faction = name, option = option, score = score })
			found = true
		end
	end
	return found
end

--- Sorts deals by faction, then best score.
local function sort_deals(deals)
	table.sort(deals, function(a, b)
		if a.faction ~= b.faction then
			return a.faction < b.faction
		end
		return a.score > b.score
	end)
end

local function diplomacy_button()
	return find_uicomponent(core:get_ui_root(), "faction_buttons_docker", "button_diplomacy")
end

--- "Quick Deal||Faction - Deal type (chance)" lines, in the game's language.
local function build_tooltip(deals)
	local lines = {}
	for _, deal in ipairs(deals) do
		table.insert(lines, string.format("%s - %s (%.1f)",
			common.get_localised_string(LOC_FACTION_PREFIX .. deal.faction),
			common.get_localised_string(LOC_OPTION_PREFIX .. deal.option),
			deal.score))
	end
	local title = common.get_localised_string(LOC_QUICK_DEAL)
	if #lines == 0 then
		return title
	end
	return title .. "||" .. table.concat(lines, "\n")
end

--- Places the badge over the diplomacy button's bottom-right corner. The button's place
-- depends on the faction's other HUD buttons (radial layout), so this runs on every
-- refresh. Only numbers are read from the button.
local function place_badge(badge, button)
	local x, y = button:Position()
	local w, h = button:Dimensions()
	badge:MoveTo(x + w + BADGE_OFFSET_X - BADGE_W, y + h + BADGE_OFFSET_Y - BADGE_H)
end

--- Shows the number of factions (0 included) and the deal list on our badge; hides it
-- only when the diplomacy button itself is hidden.
local function update_badge(button, deals, faction_count)
	local parent = find_uicomponent(core:get_ui_root(), BADGE_PARENT)
	if not parent then
		log(BADGE_PARENT .. " not found, HUD not updated")
		return
	end
	local badge = core:get_or_create_component(BADGE_NAME, BADGE_LAYOUT, parent)
	if button:Visible() then
		place_badge(badge, button)
		find_uicomponent(badge, BADGE_COUNT):SetStateText(tostring(faction_count))
		badge:SetTooltipText(build_tooltip(deals), true)
		badge:SetVisible(true)
	else
		badge:SetVisible(false)
	end
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

--- Clicks a game component, logging before and after (a click that never returns
-- shows up as a missing "clicked" line).
local function simulate_click(uic, what)
	log("clicking " .. what)
	uic:SimulateLClick()
	log(what .. " clicked")
end

--- Selects the deal-type button for `option` under the Known Factions list.
-- The game creates these buttons with the option key as id (seen in-game, e.g.
-- "diplomatic_option_nonaggression_pact"). They behave like radio buttons: clicking the
-- selected one keeps it selected (seen in-game), so the mod just clicks it. No text is
-- read from game components (state and tooltip strings are suspected in the crashes,
-- see README).
local function select_deal_type(option)
	local list = find_uicomponent(core:get_ui_root(), unpack(DEAL_TYPE_LIST_PATH))
	local button = list and find_uicomponent(list, option)
	if not button then
		log("no deal type button " .. option .. ", keeping the game's selection")
		return
	end
	simulate_click(button, "deal type " .. option)
end

local function stop_flow(reason)
	log("click flow finished: " .. reason)
	flow = nil
end

--- One check of the click flow: acts only once what the current stage needs exists.
-- Returns true when the flow should keep checking.
local function poll_flow()
	flow.waited_ms = flow.waited_ms + FLOW_POLL_MS
	if flow.waited_ms > FLOW_TIMEOUT_MS then
		stop_flow("gave up waiting at stage '" .. flow.stage .. "'")
		return false
	end

	local root = core:get_ui_root()
	if flow.stage == "quick deal" then
		if not find_uicomponent(root, DIPLOMACY_PANEL) then
			return true
		end
		local button = find_uicomponent(root, unpack(QUICK_DEAL_BUTTON_PATH))
		if not button then
			return true
		end
		log(string.format("quick deal button ready after %d ms", flow.waited_ms))
		-- Diplomacy always opens with Quick Deal off (seen in-game), so the toggle is
		-- clicked without reading its state (no text is read from game components).
		simulate_click(button, "quick deal button")
		if not flow.option then
			stop_flow("no deal type to select")
			return false
		end
		flow.stage = "deal type"
		flow.waited_ms = 0
		return true
	end

	-- flow.stage == "deal type"
	local list = find_uicomponent(root, unpack(DEAL_TYPE_LIST_PATH))
	if not list or not find_uicomponent(list, flow.option) then
		return true
	end
	log(string.format("deal type button ready after %d ms", flow.waited_ms))
	select_deal_type(flow.option)
	stop_flow("done")
	return false
end

--- Schedules the next check of `this_flow` with a single-shot timer. The next check is
-- only armed once the current one has returned, so no check can run nested inside one
-- of the mod's own clicks (the game runs due timers inside SimulateLClick). Chained
-- single shots also stop by themselves; vanilla remove_real_callback is avoided (it
-- unregisters with the wrong key type and doesn't clear its table entry).
local function schedule_poll(this_flow)
	cm:real_callback(function()
		if flow ~= this_flow then
			return  -- finished or replaced by a newer click
		end
		local ok, keep_going = pcall(poll_flow)
		if not ok then
			log("ERROR in click flow: " .. tostring(keep_going))
			stop_flow("error")
		elseif keep_going then
			schedule_poll(this_flow)
		end
	end, FLOW_POLL_MS)
end

--- Badge click: open diplomacy, then the Quick Deal view, then the deal type.
-- The deal type comes from the last scan (the one the badge shows): rescanning here
-- would freeze the game on every click.
-- The diplomacy click runs on the next UI tick (never inside the badge's UI event);
-- the checks start once that click has returned and wait for each panel/button to
-- exist, whatever the machine's speed.
local function start_click_flow()
	local option = first_available_option(last_deals)
	log("badge clicked, first deal type: " .. tostring(option))
	if flow then
		stop_flow("superseded by a newer click")
	end
	flow = { stage = "quick deal", option = option, waited_ms = 0 }
	local this_flow = flow

	cm:real_callback(function()
		if flow ~= this_flow then
			return
		end
		local ok, err = pcall(simulate_click, diplomacy_button(), "diplomacy button")
		if not ok then
			log("ERROR clicking diplomacy button: " .. tostring(err))
			stop_flow("error")
			return
		end
		schedule_poll(this_flow)
	end, NEXT_UPDATE_MS)
end

--- Last step of a scan: logs the deals and shows them on the badge.
local function finish_scan(job)
	sort_deals(job.deals)
	last_deals = job.deals
	log(string.format("refresh (%s): %d deal(s) with %d faction(s)", job.reason, #job.deals, job.faction_count))
	for _, deal in ipairs(job.deals) do
		log(string.format("  %s %s %.1f", deal.faction, deal.option, deal.score))
	end

	if not hud_enabled then
		return
	end
	local button = diplomacy_button()
	if not button then
		log("diplomacy button not found, HUD not updated")
		return
	end
	update_badge(button, job.deals, job.faction_count)
	log("badge updated")
end

--- One tick of a scan: evaluates the next faction(s). Returns true when there is more.
local function scan_step(job)
	for _ = 1, SCAN_FACTIONS_PER_TICK do
		local name = job.names[job.next]
		if not name then
			finish_scan(job)
			return false
		end
		job.next = job.next + 1
		if scan_faction(name, job.deals) then
			job.faction_count = job.faction_count + 1
		end
	end
	return true
end

--- Runs `job` one step per UI tick with chained single-shot timers (as the click flow).
local function schedule_scan_step(job)
	cm:real_callback(function()
		if scan_job ~= job then
			return  -- replaced by a newer scan
		end
		local ok, more = pcall(scan_step, job)
		if not ok then
			log("ERROR during refresh: " .. tostring(more))
			scan_job = nil
		elseif more then
			schedule_scan_step(job)
		else
			scan_job = nil
		end
	end, NEXT_UPDATE_MS)
end

--- Starts a scan; one already running is dropped and started over, so the badge
-- always ends up showing the state after the latest event.
local function refresh(reason)
	local ok, err = pcall(function()
		if scan_job then
			log("scan (" .. scan_job.reason .. ") restarted for " .. reason)
		end
		scan_job = { reason = reason, names = met_faction_names(), next = 1, deals = {}, faction_count = 0 }
		schedule_scan_step(scan_job)
	end)
	if not ok then
		scan_job = nil
		log("ERROR during refresh: " .. tostring(err))
	end
end

--- Refreshes shortly after an event, during the local player's turn only. Events
-- arriving together produce a single scan.
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
	log("init v" .. VERSION .. ", HUD " .. (hud_enabled and "enabled" or "disabled (" .. NO_HUD_FILE .. ")"))

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

	-- Signing deals in diplomacy changes them.
	core:add_listener(
		"qdi_diplomacy_closed",
		"PanelClosedCampaign",
		function(context)
			return context.string == DIPLOMACY_PANEL
		end,
		function()
			schedule_refresh("diplomacy closed")
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
