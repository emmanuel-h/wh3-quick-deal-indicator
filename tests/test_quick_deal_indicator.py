"""Tests for the Quick Deal Indicator script, run on a real Lua 5.1 runtime (lupa).

    python -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import lupa.lua51 as lupa

ROOT = Path(__file__).resolve().parent.parent
MOD_SCRIPT = ROOT / "mod" / "script" / "campaign" / "mod" / "quick_deal_indicator.lua"
PROBE_SCRIPT = ROOT / "tools" / "probe" / "script" / "campaign" / "mod" / "quick_deal_probe.lua"
MOCKS = ROOT / "tests" / "mocks.lua"

TRADE = "diplomatic_option_trade_agreement"
NAP = "diplomatic_option_nonaggression_pact"
PEACE = "diplomatic_option_peace"
LOC_QUICK_DEAL = "uied_component_texts_localised_string_dy_province_owned_Text_3f0076"
VANILLA_TOOLTIP = "Diplomacy [[col:yellow]] <7>[[/col]]||Negotiate with other factions."


def lua_path(path):
    return str(path).replace("\\", "/")


class ModTestCase(unittest.TestCase):
    def setUp(self):
        # Run in an empty folder so the debug-log file check behaves like a player's install.
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)
        self.lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(f'dofile("{lua_path(MOCKS)}")')
        self.mock = self.lua.globals().mock
        self.set_loc({
            LOC_QUICK_DEAL: "Quick Deal",
            "factions_screen_name_jade": "The Jade Court",
            "factions_screen_name_custodians": "The Jade Custodians",
            "factions_screen_name_nomads": "Burning Wind Nomads",
            "diplomacy_quick_deal_offers_localised_quick_deal_title_" + TRADE: "Trade Agreement",
            "diplomacy_quick_deal_offers_localised_quick_deal_title_" + NAP: "Non-Aggression Pact",
            "diplomacy_quick_deal_offers_localised_quick_deal_title_" + PEACE: "Peace Treaty",
        })

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    # -- scenario helpers ---------------------------------------------------

    def set_loc(self, entries):
        for key, value in entries.items():
            self.mock.loc[key] = value

    def set_factions(self, factions):
        """factions: {name: {option: (score, can_issue)}} or {name: {"dead": True, ...}}"""
        met = self.lua.table()
        table = self.lua.table()
        for i, (name, data) in enumerate(factions.items(), start=1):
            met[i] = name
            scores = self.lua.table()
            for option, value in data.items():
                if option != "dead":
                    scores[option] = self.lua.table(value[0], value[1])
            table[name] = self.lua.table_from({"dead": data.get("dead", False), "scores": scores})
        self.mock.factions = table
        self.mock.met = met

    def load_mod(self):
        self.lua.execute(f'dofile("{lua_path(MOD_SCRIPT)}")')
        self.mock.run_first_tick()

    def fire(self, lua_context_expr, event):
        self.lua.execute(f"mock.fire({event!r}, {lua_context_expr})")

    def turn_start(self, faction):
        self.fire(f'{{ faction = function() return {{ name = function() return "{faction}" end }} end }}',
                  "ScriptEventHumanFactionTurnStart")

    def panel_closed(self, panel):
        """Closes a panel and lets the deferred refresh run."""
        self.fire(f'{{ string = "{panel}" }}', "PanelClosedCampaign")
        self.mock.run_real_callbacks()

    def game_event(self, event):
        """Fires a model event (context unused by the mod) and lets timers run."""
        self.fire("{}", event)
        self.mock.run_real_callbacks()

    def click(self, component="quick_deal_indicator_badge"):
        self.fire(f'{{ string = "{component}" }}', "ComponentLClickUp")

    def open_diplomacy_manually(self):
        self.mock.diplomacy_open = True
        self.fire('{ string = "diplomacy_dropdown" }', "PanelOpenedCampaign")

    def hover(self, component="button_diplomacy"):
        self.fire(f'{{ string = "{component}" }}', "ComponentMouseOn")
        self.mock.run_real_callbacks()

    # -- observations -------------------------------------------------------

    def badge(self):
        return self.mock.badge()

    def badge_count(self):
        """Displayed number, or None when the badge is hidden/absent."""
        badge = self.badge()
        if badge is None or not badge.visible:
            return None
        return self.mock.badge_count_text()

    def tooltip(self):
        return self.mock.diplomacy_button.tooltip

    def logs(self):
        return list(self.mock.logs.values())

    def assertNoErrors(self):
        errors = [line for line in self.logs() if "ERROR" in line]
        self.assertEqual(errors, [], "script logged errors")


class CompileTests(unittest.TestCase):
    def test_scripts_compile_under_lua51(self):
        lua = lupa.LuaRuntime()
        for script in (MOD_SCRIPT, PROBE_SCRIPT):
            with self.subTest(script=script.name):
                result = lua.eval(f'{{ loadfile("{lua_path(script)}") }}')
                self.assertIsNotNone(result[1], f"syntax error: {result[2]}")


class ScanTests(ModTestCase):
    def test_counts_factions_with_a_deal_at_or_above_zero(self):
        self.set_factions({
            "jade": {TRADE: (2.18, True), NAP: (-6.2, True)},
            "custodians": {TRADE: (2.74, True), NAP: (0.5, True)},
            "nomads": {PEACE: (-1.0, True)},
        })
        self.load_mod()
        self.assertEqual(self.badge_count(), "2")
        self.assertNoErrors()

    def test_exactly_zero_counts_and_negative_does_not(self):
        self.set_factions({"jade": {TRADE: (0.0, True)}, "nomads": {PEACE: (-0.01, True)}})
        self.load_mod()
        self.assertEqual(self.badge_count(), "1")
        self.assertIn("[QDI]   jade diplomatic_option_trade_agreement 0.0", self.logs())

    def test_deals_that_cannot_be_issued_are_ignored(self):
        self.set_factions({"jade": {TRADE: (5.0, False)}})
        self.load_mod()
        self.assertEqual(self.badge_count(), "0")

    def test_dead_factions_are_ignored(self):
        self.set_factions({"jade": {"dead": True, TRADE: (5.0, True)}})
        self.load_mod()
        self.assertEqual(self.badge_count(), "0")

    def test_at_war_peace_deal_counts(self):
        self.set_factions({"nomads": {PEACE: (35.73, True)}})
        self.load_mod()
        self.assertEqual(self.badge_count(), "1")
        self.assertIn("[QDI]   nomads diplomatic_option_peace 35.7", self.logs())


class BadgeTests(ModTestCase):
    def test_shows_zero_when_no_deal(self):
        self.set_factions({"jade": {TRADE: (-1.0, True)}})
        self.load_mod()
        self.assertEqual(self.badge_count(), "0")

    def test_created_once_from_the_mod_layout(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.panel_closed("diplomacy_dropdown")
        self.turn_start("player")
        badges = [c for c in self.mock.docker.children.values() if c.id == "quick_deal_indicator_badge"]
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0].layout, "ui/quick_deal_indicator/badge.twui.xml")

    def test_badge_is_outside_the_diplomacy_button(self):
        # Inside it, the button's StatePropagatorCallback overrides the badge's own hover.
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.assertEqual(len(self.mock.diplomacy_button.children), 0)
        self.assertIsNotNone(self.badge())

    def test_badge_is_placed_on_the_buttons_bottom_right_corner(self):
        # Like the vanilla missions badge: 42x41, bottom-right at corner + (23, 13).
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        badge = self.badge()
        self.assertEqual((badge.x, badge.y), (1700 + 55 + 23 - 42, 950 + 55 + 13 - 41))

    def test_badge_follows_the_button_when_it_moves(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.mock.diplomacy_button.x, self.mock.diplomacy_button.y = 1600, 900
        self.panel_closed("technology_panel")
        badge = self.badge()
        self.assertEqual((badge.x, badge.y), (1600 + 36, 900 + 27))

    def test_badge_hidden_when_the_button_is_hidden(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.mock.diplomacy_button.visible = False
        self.panel_closed("technology_panel")
        self.assertIsNone(self.badge_count())

    def test_count_is_shown_on_the_count_child(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}, "custodians": {NAP: (2.0, True)}})
        self.load_mod()
        self.assertEqual(self.badge_count(), "2")
        self.assertEqual(list(self.badge().state_texts.values()), [], "no text on the disc itself")
        self.assertNoErrors()

    def test_layout_glow_follows_the_mouse_over_the_badge(self):
        tree = ET.parse(ROOT / "mod" / "ui" / "quick_deal_indicator" / "badge.twui.xml")
        root = tree.getroot()
        hierarchy = root.find("hierarchy/root/qdi_badge")
        # Draw order: glow above the disc, the number above the glow.
        self.assertEqual([c.tag for c in hierarchy], ["qdi_badge_glow", "qdi_badge_count"])
        comps = root.find("components")
        glow = comps.find("qdi_badge_glow")
        callback = glow.find("callbackwithcontextlist/callback_with_context")
        self.assertEqual(callback.get("callback_id"), "ContextVisibilitySetter")
        self.assertEqual(callback.get("context_function_id"),
                         "self.ParentContext.IsMouseOver && self.ParentContext.IsDisabled == false")
        self.assertEqual(glow.get("visible"), "false")
        images = {i.get("this"): i.get("imagepath") for i in glow.find("componentimages")}
        self.assertEqual(list(images.values()), ["ui/quick_deal_indicator/badge_hover.png"])
        self.assertTrue((ROOT / "mod" / "ui" / "quick_deal_indicator" / "badge_hover.png").is_file())
        # Only the disc takes the mouse.
        for child in ("qdi_badge_glow", "qdi_badge_count"):
            for state in comps.find(child).find("states"):
                self.assertNotEqual(state.get("interactive"), "true", child)
        badge_states = comps.find("qdi_badge").find("states")
        self.assertEqual([s.get("interactive") for s in badge_states], ["true"])

    def test_layout_is_valid_and_badge_is_first_child_of_root(self):
        # CreateComponent returns the first child of the layout's root.
        tree = ET.parse(ROOT / "mod" / "ui" / "quick_deal_indicator" / "badge.twui.xml")
        root = tree.getroot().find("hierarchy/root")
        self.assertEqual([child.tag for child in root], ["qdi_badge"])
        badge = tree.getroot().find("components/qdi_badge")
        self.assertEqual(badge.get("visible"), "false")
        # Interactive so it shows its tooltip and receives clicks.
        self.assertEqual(badge.find("states/active").get("interactive"), "true")
        self.assertIsNone(badge.find("callbackwithcontextlist"), "no Button callback any more")

    def test_missing_hud_is_logged_not_fatal(self):
        self.mock.ui_ready = False
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.assertIsNone(self.badge())
        self.assertTrue(any("diplomacy button not found" in line for line in self.logs()))
        self.assertNoErrors()


class BadgeTooltipTests(ModTestCase):
    def setUp(self):
        super().setUp()
        self.set_factions({
            "jade": {TRADE: (2.18, True)},
            "custodians": {TRADE: (2.74, True), NAP: (0.46, True)},
        })

    def test_lists_deals_sorted_by_faction_then_score(self):
        self.load_mod()
        self.assertEqual(self.badge().tooltip,
                         "Quick Deal||"
                         "The Jade Custodians - Trade Agreement (2.7)\n"
                         "The Jade Custodians - Non-Aggression Pact (0.5)\n"
                         "The Jade Court - Trade Agreement (2.2)")

    def test_updated_on_refresh(self):
        self.load_mod()
        self.set_factions({"jade": {TRADE: (3.0, True)}})
        self.panel_closed("diplomacy_dropdown")
        self.assertEqual(self.badge().tooltip, "Quick Deal||The Jade Court - Trade Agreement (3.0)")

    def test_title_only_when_no_deal(self):
        self.set_factions({"jade": {TRADE: (-1.0, True)}})
        self.load_mod()
        self.assertEqual(self.badge().tooltip, "Quick Deal")

    def test_uses_game_language_strings(self):
        self.set_loc({
            LOC_QUICK_DEAL: "Accord rapide",
            "factions_screen_name_jade": "La Cour de Jade",
            "diplomacy_quick_deal_offers_localised_quick_deal_title_" + TRADE: "Accord commercial",
        })
        self.set_factions({"jade": {TRADE: (2.18, True)}})
        self.load_mod()
        self.assertEqual(self.badge().tooltip, "Accord rapide||La Cour de Jade - Accord commercial (2.2)")


class BadgeClickTests(ModTestCase):
    def setUp(self):
        super().setUp()
        self.set_factions({"jade": {TRADE: (2.18, True)}})
        self.load_mod()

    def test_quick_deal_is_clicked_once_without_reading_its_state(self):
        # Diplomacy always opens with Quick Deal off (seen in-game).
        self.click()
        self.mock.run_real_callbacks()
        self.assertEqual(self.mock.quick_deal_button.clicks, 1)
        self.assertNoErrors()

    def test_click_opens_diplomacy_then_quick_deal_view(self):
        self.click()
        # Nothing is clicked inside the UI click handler itself.
        self.assertEqual(self.mock.diplomacy_button.clicks, 0)
        self.mock.run_real_callbacks(1)  # next UI tick
        self.assertEqual(self.mock.diplomacy_button.clicks, 1)
        self.assertEqual(self.mock.quick_deal_button.clicks, 0, "must wait for the panel to build")
        self.mock.run_real_callbacks(300)
        self.assertEqual(self.mock.quick_deal_button.clicks, 1)
        self.assertEqual(self.mock.quick_deal_button.state, "selected")
        self.assertNoErrors()

    def test_no_step_runs_inside_the_diplomacy_click(self):
        # In-game, SimulateLClick fired PanelOpenedCampaign and ran due timers inside
        # the click; a step reacting to that ran on a half-built panel and stalled.
        steps_during_click = []

        def click_diplomacy(*_):
            self.mock.diplomacy_open = True
            self.fire('{ string = "diplomacy_dropdown" }', "PanelOpenedCampaign")
            before = self.mock.quick_deal_button.clicks
            self.mock.run_real_callbacks(300)
            steps_during_click.append(self.mock.quick_deal_button.clicks - before)

        self.mock.diplomacy_button.on_click = click_diplomacy
        self.click()
        self.mock.run_real_callbacks(1)  # next UI tick
        self.assertEqual(steps_during_click, [0])
        self.mock.run_real_callbacks(300)
        self.assertEqual(self.mock.quick_deal_button.clicks, 1)
        self.assertNoErrors()

    def test_manual_diplomacy_opening_is_untouched(self):
        self.open_diplomacy_manually()
        self.mock.run_real_callbacks()
        self.assertEqual(self.mock.quick_deal_button.clicks, 0)

    def test_gives_up_if_diplomacy_does_not_open(self):
        self.mock.diplomacy_button.on_click = None  # button disabled: nothing opens
        self.click()
        self.mock.run_real_callbacks()
        self.assertEqual(self.mock.quick_deal_button.clicks, 0)
        self.assertIn("[QDI] click flow finished: gave up waiting at stage 'quick deal'", self.logs())
        self.assertEqual(self.active_polls(), [])
        self.assertNoErrors()

    def test_waits_as_long_as_the_quick_deal_button_takes(self):
        # A slow machine: the button appears only after many checks.
        self.mock.quick_deal_ready = False
        self.click()
        self.mock.run_real_callbacks(1)  # next UI tick
        for _ in range(40):  # 40 checks of 50 ms: 2 s
            self.run_one_poll()
        self.assertEqual(self.mock.quick_deal_button.clicks, 0)
        self.mock.quick_deal_ready = True
        self.run_one_poll()
        self.assertEqual(self.mock.quick_deal_button.clicks, 1)
        self.assertIn("[QDI] quick deal button ready after 2050 ms", self.logs())

    def test_no_check_runs_inside_the_mods_own_clicks(self):
        # If the game runs the poll inside the Quick Deal click, a nested check must not
        # click the toggle again (that would switch Quick Deal back off).
        original = self.mock.quick_deal_button.on_click

        def click_quick_deal(button):
            self.run_one_poll()  # the game runs timers during the click, before the state changes
            original(button)

        self.mock.quick_deal_button.on_click = click_quick_deal
        self.click()
        self.mock.run_real_callbacks()
        self.assertEqual(self.mock.quick_deal_button.clicks, 1)
        self.assertEqual(self.mock.quick_deal_button.state, "selected")
        self.assertNoErrors()

    def test_poll_stops_once_done(self):
        self.click()
        self.mock.run_real_callbacks()
        self.assertEqual(self.active_polls(), [])

    def active_polls(self):
        """Pending click-flow checks (single-shot 50 ms timers)."""
        return [cb for cb in self.mock.real_callbacks.values() if cb.ms == 50]

    def run_one_poll(self):
        """Fires the pending click-flow check once (it re-arms itself if needed)."""
        pending = self.active_polls()
        self.mock.real_callbacks = self.lua.table_from(
            [cb for cb in self.mock.real_callbacks.values() if cb.ms != 50])
        for cb in pending:
            cb.f()

    def test_newer_click_supersedes_the_pending_flow(self):
        self.click()
        self.mock.run_real_callbacks(1)  # next UI tick
        self.click()
        self.mock.run_real_callbacks()
        self.assertEqual(self.mock.quick_deal_button.clicks, 1)
        self.assertIn("[QDI] click flow finished: superseded by a newer click", self.logs())

    def test_missing_quick_deal_button_gives_up_cleanly(self):
        self.mock.quick_deal_ready = False  # never built
        self.click()
        self.mock.run_real_callbacks()
        self.assertIn("[QDI] click flow finished: gave up waiting at stage 'quick deal'", self.logs())
        self.assertNoErrors()

    def test_click_at_zero_opens_quick_deal_with_default_deal_type(self):
        self.set_factions({"jade": {TRADE: (-1.0, True)}})
        self.panel_closed("technology_panel")
        self.assertEqual(self.badge_count(), "0")
        self.click()
        self.mock.run_real_callbacks()
        self.assertEqual(self.mock.quick_deal_button.clicks, 1)
        self.assertIn("[QDI] click flow finished: no deal type to select", self.logs())
        self.assertNoErrors()

    def test_other_component_clicks_are_ignored(self):
        self.click("button_missions")
        self.mock.run_real_callbacks()
        self.assertEqual(self.mock.diplomacy_button.clicks, 0)


class VanillaTooltipTests(ModTestCase):
    def test_vanilla_button_tooltip_is_never_touched(self):
        # The mock raises if SetTooltipText is called on the button; errors are logged.
        self.mock.diplomacy_button.tooltip = VANILLA_TOOLTIP
        self.set_factions({"jade": {TRADE: (2.18, True)}})
        self.load_mod()
        self.hover()
        self.turn_start("player")
        self.panel_closed("diplomacy_dropdown")
        self.assertEqual(self.tooltip(), VANILLA_TOOLTIP)
        self.assertNoErrors()


class RefreshTests(ModTestCase):
    def setUp(self):
        super().setUp()
        self.set_factions({"jade": {TRADE: (-1.0, True)}})
        self.load_mod()
        self.assertEqual(self.badge_count(), "0")
        self.set_factions({"jade": {TRADE: (1.0, True)}})

    def test_local_turn_start_refreshes(self):
        self.turn_start("player")
        self.assertEqual(self.badge_count(), "1")

    def test_other_human_turn_start_is_ignored(self):
        self.turn_start("other_human")
        self.assertEqual(self.badge_count(), "0")

    def test_diplomacy_closed_refreshes(self):
        self.panel_closed("diplomacy_dropdown")
        self.assertEqual(self.badge_count(), "1")

    def test_any_panel_closed_refreshes(self):
        self.panel_closed("technology_panel")
        self.assertEqual(self.badge_count(), "1")

    def test_game_events_refresh(self):
        for event in ("CharacterFinishedMovingEvent", "BattleCompleted", "GarrisonOccupiedEvent",
                      "RegionFactionChangeEvent", "PositiveDiplomaticEvent", "NegativeDiplomaticEvent"):
            with self.subTest(event=event):
                self.set_factions({"jade": {TRADE: (-1.0, True)}})
                self.game_event(event)
                self.assertEqual(self.badge_count(), "0")
                self.set_factions({"jade": {TRADE: (1.0, True)}})
                self.game_event(event)
                self.assertEqual(self.badge_count(), "1")

    def test_no_refresh_outside_local_players_turn(self):
        self.mock.my_turn = False
        self.game_event("BattleCompleted")
        self.panel_closed("diplomacy_dropdown")
        self.assertEqual(self.badge_count(), "0")

    def test_events_close_together_give_a_single_scan(self):
        before = self.refresh_count()
        self.fire("{}", "BattleCompleted")
        self.fire("{}", "RegionFactionChangeEvent")
        self.fire('{ string = "diplomacy_dropdown" }', "PanelClosedCampaign")
        self.mock.run_real_callbacks()
        self.assertEqual(self.refresh_count() - before, 1)

    def test_events_are_logged_with_their_outcome(self):
        self.fire("{}", "BattleCompleted")
        self.fire("{}", "RegionFactionChangeEvent")
        self.mock.run_real_callbacks()
        self.mock.my_turn = False
        self.fire("{}", "CharacterFinishedMovingEvent")
        logs = self.logs()
        self.assertIn("[QDI] event BattleCompleted: refresh scheduled", logs)
        self.assertIn("[QDI] event RegionFactionChangeEvent: refresh already scheduled", logs)
        self.assertIn("[QDI] refresh (BattleCompleted): 1 deal(s) with 1 faction(s)", logs)
        self.assertIn("[QDI] event CharacterFinishedMovingEvent: not the local player's turn, skipped", logs)

    def refresh_count(self):
        return sum(1 for line in self.logs() if line.startswith("[QDI] refresh ("))


class DealTypeSelectionTests(ModTestCase):
    """Clicking the badge selects the first deal type, in screen order, with a deal >= 0."""

    def add_buttons_by_id(self):
        return {option: self.mock.add_deal_type_button(option, "")
                for option in (NAP, TRADE, "diplomatic_option_soft_access", PEACE)}

    def click_and_settle(self):
        self.click()
        self.mock.run_real_callbacks(300)  # diplomacy, quick deal, deal type steps

    def test_selects_first_type_in_screen_order(self):
        self.set_factions({"jade": {PEACE: (5.0, True), TRADE: (1.0, True)}})
        self.load_mod()
        buttons = self.add_buttons_by_id()
        self.click_and_settle()
        self.assertEqual(buttons[TRADE].state, "selected")
        self.assertEqual(buttons[PEACE].clicks, 0)
        self.assertEqual(buttons[NAP].clicks, 0)
        self.assertNoErrors()

    def test_non_aggression_pact_comes_first(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}, "custodians": {NAP: (0.2, True)}})
        self.load_mod()
        buttons = self.add_buttons_by_id()
        self.click_and_settle()
        self.assertEqual(buttons[NAP].state, "selected")

    def test_waits_for_the_list_to_be_built(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        buttons = self.add_buttons_by_id()
        self.click()
        self.mock.run_real_callbacks(1)  # next UI tick
        self.assertEqual(buttons[TRADE].clicks, 0)
        self.mock.run_real_callbacks(300)
        self.assertEqual(buttons[TRADE].clicks, 1)

    def test_unknown_buttons_are_left_alone(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        other = self.mock.add_deal_type_button("mystery", "Something")
        self.click()
        self.mock.run_real_callbacks()
        self.assertEqual(other.clicks, 0)
        self.assertIn("[QDI] click flow finished: gave up waiting at stage 'deal type'", self.logs())
        self.assertNoErrors()

    def test_selected_type_is_clicked_anyway(self):
        # Radio buttons: clicking the selected one keeps it selected (seen in-game), so
        # the mod doesn't read the state (text reads are suspected in the crashes).
        self.set_factions({"jade": {NAP: (1.0, True)}})
        self.load_mod()
        buttons = self.add_buttons_by_id()
        buttons[NAP].state = "selected"
        self.click_and_settle()
        self.assertEqual(buttons[NAP].clicks, 1)
        self.assertEqual(buttons[NAP].state, "selected")
        self.assertNoErrors()

    def test_no_text_is_read_from_game_components(self):
        # The mock raises on GetTooltipText; any call would be logged as an error.
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.add_buttons_by_id()
        self.click_and_settle()
        self.assertNoErrors()


class RobustnessTests(ModTestCase):
    def test_errors_in_scan_are_caught_and_logged(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.lua.execute("cm.cai_evaluate_quick_deal_action = function() error('boom') end")
        self.load_mod()
        self.assertTrue(any("ERROR during refresh" in line and "boom" in line for line in self.logs()))

    def test_no_debug_file_is_created_by_default(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.assertFalse(Path("quick_deal_indicator_debug.txt").exists())

    def test_no_hud_switch_scans_but_leaves_hud_untouched(self):
        Path("quick_deal_indicator_debug.txt").write_text("")
        Path("quick_deal_indicator_no_hud.txt").write_text("")
        self.mock.diplomacy_button.tooltip = VANILLA_TOOLTIP
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.hover()
        self.turn_start("player")
        self.panel_closed("diplomacy_dropdown")
        self.assertEqual(len(self.mock.docker.children), 0)
        self.assertEqual(self.tooltip(), VANILLA_TOOLTIP)
        content = Path("quick_deal_indicator_debug.txt").read_text()
        self.assertIn("HUD disabled", content)
        self.assertEqual(content.count("1 deal(s) with 1 faction(s)"), 3)

    def test_debug_file_receives_log_when_present(self):
        Path("quick_deal_indicator_debug.txt").write_text("")
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        content = Path("quick_deal_indicator_debug.txt").read_text()
        self.assertIn("[QDI] refresh (campaign loaded): 1 deal(s) with 1 faction(s)", content)
        heartbeats = [cb.name for cb in (self.mock.repeat_callbacks or {}).values()]
        self.assertEqual(heartbeats, ["qdi_heartbeat"])


if __name__ == "__main__":
    unittest.main()
