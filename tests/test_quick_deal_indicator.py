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
        self.fire(f'{{ string = "{panel}" }}', "PanelClosedCampaign")

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
        return badge.state_text

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
        self.assertIn("The Jade Court", self.tooltip())
        self.assertNotIn("Burning Wind Nomads", self.tooltip())

    def test_deals_that_cannot_be_issued_are_ignored(self):
        self.set_factions({"jade": {TRADE: (5.0, False)}})
        self.load_mod()
        self.assertIsNone(self.badge_count())

    def test_dead_factions_are_ignored(self):
        self.set_factions({"jade": {"dead": True, TRADE: (5.0, True)}})
        self.load_mod()
        self.assertIsNone(self.badge_count())

    def test_at_war_peace_deal_counts(self):
        self.set_factions({"nomads": {PEACE: (35.73, True)}})
        self.load_mod()
        self.assertEqual(self.badge_count(), "1")
        self.assertIn("Burning Wind Nomads - Peace Treaty (35.7)", self.tooltip())


class BadgeTests(ModTestCase):
    def test_hidden_when_no_deal(self):
        self.set_factions({"jade": {TRADE: (-1.0, True)}})
        self.load_mod()
        self.assertIsNone(self.badge_count())

    def test_created_once_from_the_mod_layout(self):
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.panel_closed("diplomacy_dropdown")
        self.turn_start("player")
        badges = [c for c in self.mock.diplomacy_button.children.values() if c.id == "quick_deal_indicator_badge"]
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0].layout, "ui/quick_deal_indicator/badge.twui.xml")

    def test_layout_is_valid_and_badge_is_first_child_of_root(self):
        # CreateComponent returns the first child of the layout's root.
        tree = ET.parse(ROOT / "mod" / "ui" / "quick_deal_indicator" / "badge.twui.xml")
        root = tree.getroot().find("hierarchy/root")
        self.assertEqual([child.tag for child in root], ["qdi_badge"])
        badge = tree.getroot().find("components/qdi_badge")
        self.assertEqual(badge.get("visible"), "false")
        self.assertEqual(badge.find("states/newstate").get("interactive"), "false")

    def test_missing_hud_is_logged_not_fatal(self):
        self.mock.ui_ready = False
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        self.assertIsNone(self.badge())
        self.assertTrue(any("diplomacy button not found" in line for line in self.logs()))
        self.assertNoErrors()


class TooltipTests(ModTestCase):
    def setUp(self):
        super().setUp()
        self.set_factions({
            "jade": {TRADE: (2.18, True)},
            "custodians": {TRADE: (2.74, True), NAP: (0.46, True)},
        })

    def expected_section(self):
        return ("\n\n[[col:yellow]]Quick Deal[[/col]]"
                "\nThe Jade Custodians - Trade Agreement (2.7)"
                "\nThe Jade Custodians - Non-Aggression Pact (0.5)"
                "\nThe Jade Court - Trade Agreement (2.2)")

    def test_appended_after_vanilla_text(self):
        self.mock.diplomacy_button.tooltip = VANILLA_TOOLTIP
        self.load_mod()
        self.assertEqual(self.tooltip(), VANILLA_TOOLTIP + self.expected_section())

    def test_repeated_hover_does_not_duplicate(self):
        self.mock.diplomacy_button.tooltip = VANILLA_TOOLTIP
        self.load_mod()
        for _ in range(3):
            self.hover()
        self.assertEqual(self.tooltip(), VANILLA_TOOLTIP + self.expected_section())

    def test_reappended_when_game_sets_vanilla_later(self):
        # At first tick the game hasn't set its tooltip yet (seen in-game).
        self.load_mod()
        self.mock.diplomacy_button.tooltip = VANILLA_TOOLTIP
        self.hover()
        self.assertEqual(self.tooltip(), VANILLA_TOOLTIP + self.expected_section())

    def test_hover_on_other_component_is_ignored(self):
        self.load_mod()
        self.mock.diplomacy_button.tooltip = VANILLA_TOOLTIP
        self.hover("button_missions")
        self.assertEqual(self.tooltip(), VANILLA_TOOLTIP)

    def test_section_removed_when_deals_disappear(self):
        self.mock.diplomacy_button.tooltip = VANILLA_TOOLTIP
        self.load_mod()
        self.set_factions({"jade": {TRADE: (-3.0, True)}})
        self.panel_closed("diplomacy_dropdown")
        self.assertEqual(self.tooltip(), VANILLA_TOOLTIP)
        self.assertIsNone(self.badge_count())

    def test_uses_game_language_strings(self):
        self.set_loc({
            LOC_QUICK_DEAL: "Accord rapide",
            "factions_screen_name_jade": "La Cour de Jade",
            "diplomacy_quick_deal_offers_localised_quick_deal_title_" + TRADE: "Accord commercial",
        })
        self.set_factions({"jade": {TRADE: (2.18, True)}})
        self.load_mod()
        self.assertIn("Accord rapide", self.tooltip())
        self.assertIn("La Cour de Jade - Accord commercial (2.2)", self.tooltip())


class RefreshTests(ModTestCase):
    def setUp(self):
        super().setUp()
        self.set_factions({"jade": {TRADE: (-1.0, True)}})
        self.load_mod()
        self.assertIsNone(self.badge_count())
        self.set_factions({"jade": {TRADE: (1.0, True)}})

    def test_local_turn_start_refreshes(self):
        self.turn_start("player")
        self.assertEqual(self.badge_count(), "1")

    def test_other_human_turn_start_is_ignored(self):
        self.turn_start("other_human")
        self.assertIsNone(self.badge_count())

    def test_diplomacy_closed_refreshes(self):
        self.panel_closed("diplomacy_dropdown")
        self.assertEqual(self.badge_count(), "1")

    def test_other_panel_closed_is_ignored(self):
        self.panel_closed("technology_panel")
        self.assertIsNone(self.badge_count())


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

    def test_debug_file_receives_log_when_present(self):
        Path("quick_deal_indicator_debug.txt").write_text("")
        self.set_factions({"jade": {TRADE: (1.0, True)}})
        self.load_mod()
        content = Path("quick_deal_indicator_debug.txt").read_text()
        self.assertIn("[QDI] refresh (campaign loaded): 1 deal(s) with 1 faction(s)", content)


if __name__ == "__main__":
    unittest.main()
