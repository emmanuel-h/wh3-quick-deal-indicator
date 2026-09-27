-- Quick Deal Indicator: research probe (read-only, logs only).
-- Writes quick_deal_probe.txt in the game folder.

local OPTIONS = {
	"diplomatic_option_trade_agreement",
	"diplomatic_option_nonaggression_pact",
	"diplomatic_option_soft_access",
	"diplomatic_option_defensive_alliance",
	"diplomatic_option_military_alliance",
	"diplomatic_option_peace",
	"diplomatic_option_vassal",
	"diplomatic_option_client_state",
	"diplomatic_option_confederation",
}

local function log(msg)
	out("[QDI-PROBE] " .. msg)
	pcall(function()
		local f = io.open("quick_deal_probe.txt", "a")
		f:write(msg .. "\n")
		f:close()
	end)
end

local function probe(tag)
	local ok, err = pcall(function()
		local local_faction = cm:get_faction(cm:get_local_faction_name(true))
		log(string.format("=== %s | turn %d | local=%s | mp=%s", tag, cm:model():turn_number(), local_faction:name(), tostring(cm:is_multiplayer())))

		local button = find_uicomponent(core:get_ui_root(), "faction_buttons_docker", "button_diplomacy")
		log("button_diplomacy found=" .. tostring(button ~= false and button ~= nil) .. " tooltip=" .. tostring(button and button:GetTooltipText()))

		for _, other in model_pairs(local_faction:factions_met()) do
			if not other:is_dead() then
				local parts = {}
				for _, option in ipairs(OPTIONS) do
					local score, can_issue = cm:cai_evaluate_quick_deal_action(local_faction, other, option)
					table.insert(parts, string.format("%s=%s/%s", option:gsub("diplomatic_option_", ""), tostring(score), tostring(can_issue)))
				end
				log(string.format("%s (%s) war=%s | %s", other:name(), common.get_localised_string("factions_screen_name_" .. other:name()), tostring(local_faction:at_war_with(other)), table.concat(parts, " ")))
			end
		end
	end)
	if not ok then
		log("ERROR: " .. tostring(err))
	end
end

cm:add_first_tick_callback(function()
	probe("first_tick")

	core:add_listener(
		"qdi_probe_diplomacy_opened",
		"PanelOpenedCampaign",
		function(context) return context.string == "diplomacy_dropdown" end,
		function() probe("diplomacy_opened") end,
		true
	)
end)
