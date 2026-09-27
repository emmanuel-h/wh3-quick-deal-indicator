# Quick Deal Indicator

A Total War: WARHAMMER III campaign mod that shows, on the HUD **Diplomacy** button
(bottom right, above End Turn), how many factions currently have a **Quick Deal**
the AI would accept — i.e. a *Deal chance* **≥ 0** in the diplomacy screen's
Known Factions list. A tooltip on the badge listing each faction, deal type and chance
is planned.

## Status

🚧 Work in progress. Detection is validated in-game. The first build crashed the game
(see [Known crash](#known-crash-vanilla-tooltip)); the tooltip on the vanilla button was
removed and the badge-only build is being tested.

## Installation

1. Subscribe on the Steam Workshop (link once published), or download
   `quick_deal_indicator.pack` from the [Releases](../../releases) page and copy it into
   `<Steam>/steamapps/common/Total War WARHAMMER III/data/`.
2. Enable it in the game launcher's mod manager.

The mod only reads game state and changes your own HUD, so it is save-game compatible
and multiplayer safe.

## How it works

The game exposes the AI's Quick Deal evaluation to scripts:

```lua
local score, can_issue = cm:cai_evaluate_quick_deal_action(my_faction, other_faction, "diplomatic_option_trade_agreement")
```

`score` is exactly the *Deal chance* shown in the diplomacy screen (the screen rounds
it to one decimal); `can_issue` is `false` when that deal type isn't available with
that faction. Vanilla uses the same call for its diplomacy missions
(`script/campaign/_narrative/wh3_narrative_shared_chains.lua`). Because it's a script
query, no UI has to be opened.

The deal types come from the vanilla `diplomacy_quick_deal_offers` table. The six
buttons under the Known Factions list map to:

| Button | Option key |
|---|---|
| 1 | `diplomatic_option_nonaggression_pact` |
| 2 | `diplomatic_option_trade_agreement` |
| 3 | `diplomatic_option_soft_access` (military access) |
| 4 | `diplomatic_option_defensive_alliance` |
| 5 | `diplomatic_option_military_alliance` |
| 6 | `diplomatic_option_peace` |

`diplomatic_option_vassal`, `_client_state` and `_confederation` are also Quick Deal
offers; they only appear for factions that can use them, so the mod checks all nine
and keeps those where `can_issue` is true. A deal counts as available when the raw
score is ≥ 0.

### When it refreshes

- when the campaign is loaded,
- at the start of the local player's turn (`ScriptEventHumanFactionTurnStart`, filtered
  on `cm:get_local_faction_name(true)` so each multiplayer client only handles itself),
- when the diplomacy screen closes (`PanelClosedCampaign` with `diplomacy_dropdown`),
  so deals signed during the turn are taken into account.

### HUD

- **Badge** — `ui/quick_deal_indicator/badge.twui.xml` is a copy of the vanilla missions
  counter (`hud_campaign.twui.xml > label_missions_count`) without its context callbacks.
  It is created under `faction_buttons_docker > button_diplomacy` with
  `core:get_or_create_component`, shows the number of **factions** with at least one
  deal ≥ 0, and is hidden at 0. It is non-interactive so hovering it still hovers the
  button.
- **Tooltip (planned)** — on the badge itself, one line per deal:
  `Faction - Deal type (chance)`, built only from vanilla strings (the "Quick Deal" label
  of the diplomacy screen, `factions_screen_name_*` and
  `diplomacy_quick_deal_offers_localised_quick_deal_title_*`) so it follows the game
  language (English, French, …) without shipping a `.loc` file.

### Known crash: vanilla tooltip

**Never call `SetTooltipText` on the vanilla diplomacy button.** Its tooltip is driven by
a `ContextTooltipSetter` callback (`Loc("diplomacy_button_tooltip")`) that overwrites
script text. The first build set it once at load (and tried on hover) and crashed the
game three times out of three, from ~20 s to a few minutes after loading, e.g. when
clicking an army: access violation reading address 0 at `Warhammer3.exe+0x244e743`, main
thread. With the HUD switched off (`quick_deal_indicator_no_hud.txt`) it didn't crash.
The test mocks now reject this call. Note also that `ComponentMouseOn` never reported
`button_diplomacy` in-game, so hover code on that button never ran.

## Repository layout

```
mod/                          # Files packed into quick_deal_indicator.pack
├── script/campaign/mod/
│   └── quick_deal_indicator.lua
└── ui/quick_deal_indicator/
    └── badge.twui.xml
tests/
├── mocks.lua                 # Fakes of the game's scripting API (cm, core, UI, loc)
└── test_quick_deal_indicator.py
tools/
├── packtool.py               # list / extract / build PFH5 packs
└── probe/                    # Debug mod: logs every Quick Deal score to a file
```

## Development

Requirements: Python 3.14+ (for the built-in zstd module). [RPFM](https://github.com/Frodo45127/rpfm)
is optional — handy for browsing vanilla files, but not needed to build.

`GAME` below is `C:\Program Files (x86)\Steam\steamapps\common\Total War WARHAMMER III`.

### Automated tests

The script is tested outside the game on a real Lua 5.1 runtime (the game's Lua version)
through [lupa](https://pypi.org/project/lupa/):

```bash
pip install -r tests/requirements.txt
python -m unittest discover -s tests -v
```

`tests/mocks.lua` fakes the parts of the game API the mod uses. The fakes are strict:
calling any `cm`, `core` or `common` function that isn't faked fails the test, which
guards against the mod accidentally using an API that changes the game state. The suite
checks that both scripts compile, the ≥ 0 rule, `can_issue` and dead-faction filtering,
the badge (count, hidden at 0, created once), that the vanilla button's tooltip is never
touched, which events trigger a refresh, and error handling. GitHub Actions runs the suite and a pack build on every push
(`.github/workflows/tests.yml`).

What the mocks can't prove — how the badge renders, and engine crashes — is covered by
the in-game checklist below.

### Build and install

```bash
python tools/packtool.py build mod build/quick_deal_indicator.pack
cp build/quick_deal_indicator.pack "$GAME/data/"
```

Then enable **quick_deal_indicator** in the launcher. `build/` and `*.pack` are git-ignored.

### Reading vanilla files

Vanilla layouts and scripts are useful references. Extract them outside the repo:

```bash
python tools/packtool.py list "$GAME/data/ui3.pack" diplomacy
python tools/packtool.py extract "$GAME/data/ui3.pack" "hud_campaign.twui.xml" vanilla/
python tools/packtool.py extract "$GAME/data/data_script.pack" "script\\" vanilla/
```

Useful references: `ui/campaign ui/hud_campaign.twui.xml` (HUD, diplomacy button),
`ui/campaign ui/diplomacy_hud.twui.xml` (diplomacy screen), `script/_lib/` (script API).

### Debug probe

`tools/probe` is a standalone mod that appends, on campaign load and each time the
diplomacy screen opens, every faction's Quick Deal score and `can_issue` flag for all
nine deal types to `$GAME/quick_deal_probe.txt`. Use it to check the scores against the
*Deal chance* column in-game.

```bash
python tools/packtool.py build tools/probe build/quick_deal_probe.pack
cp build/quick_deal_probe.pack "$GAME/data/"
```

### Logs

- `$GAME/lua_mod_log.txt` — written by the game; shows whether the script loaded or
  failed (syntax errors end up here).
- `$GAME/quick_deal_indicator_debug.txt` — create this empty file to turn on the mod's
  debug log. Each refresh appends its reason and every deal found. Delete it to turn
  logging off.
- `$GAME/quick_deal_indicator_no_hud.txt` — create this empty file to make the mod scan
  and log without touching the HUD, to tell HUD problems from scan problems.
- The same messages also go to the standard script log through `out()`, prefixed `[QDI]`.

### Testing checklist

Enable only `quick_deal_indicator` (plus `quick_deal_probe` if you want raw scores) and
create the debug file, then:

1. **Load a campaign** — the badge shows the number of factions that have a deal ≥ 0,
   or nothing if there are none. The debug log has a `refresh (campaign loaded)` block.
2. **Compare with the game** — open diplomacy; for every deal-type button, each faction
   whose *Deal chance* is ≥ 0 must appear in the debug log with the same value, and no
   other.
3. **Stability** — play normally for at least 10 minutes: hover the diplomacy button,
   click armies and settlements, open and close panels. No crash.
4. **Refresh on close** — sign one of the listed deals, close diplomacy: the badge
   updates (`refresh (diplomacy closed)` in the log).
5. **Turn start** — end the turn: a `refresh (turn start)` block appears, and nothing
   flashes on screen.
6. **Zero case** — with no deal ≥ 0, no badge.
7. **Multiplayer** — play a few co-op turns with both players running the mod: no
   desync, and each player sees only their own deals.
8. **No errors** in `lua_mod_log.txt`.

## Something's wrong?

See [DEBUG.md](DEBUG.md): a step-by-step guide to find out whether a crash comes from
the mod, collect logs and crash files, inspect raw scores and report the problem.

## License

[MIT](LICENSE)
