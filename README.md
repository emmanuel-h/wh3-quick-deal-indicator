# Quick Deal Indicator

A Total War: WARHAMMER III campaign mod that shows, on the HUD **Diplomacy** button
(bottom right, above End Turn), how many factions currently have a **Quick Deal**
the AI would accept — i.e. a *Deal chance* **≥ 0** in the diplomacy screen's
Known Factions list. Hovering the badge lists each faction, deal type and chance;
clicking it opens diplomacy directly on the Quick Deal view, on the first deal type that
has an acceptable deal. The count is kept up to date as you play.

## Status

🚧 Work in progress. Validated in-game, with no crash over 10-minute sessions: detection,
the badge and its tooltip, clicking it to open diplomacy on the Quick Deal view with the
first available deal type selected, and refreshing when a panel closes. Refresh after army
moves is confirmed too. Under investigation: the badge click flow stalled the script
and crashed the game (see [Known crashes](#known-crashes) §3); a redesigned flow is
awaiting in-game testing. Still to test: turn start,
French, multiplayer. A hover highlight is postponed.

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
- during the local player's turn (`cm:is_local_players_turn(true)`), after anything that
  can change a deal's chance: `CharacterFinishedMovingEvent`, `BattleCompleted`,
  `GarrisonOccupiedEvent`, `RegionFactionChangeEvent`, `PositiveDiplomaticEvent`,
  `NegativeDiplomaticEvent`, and any panel closing (`PanelClosedCampaign`, diplomacy
  included). These refreshes run 250 ms after the event through a real (UI) timer, and
  events arriving together produce a single scan. Events during AI turns are ignored.

### HUD

- **Badge** — `ui/quick_deal_indicator/badge.twui.xml` is a copy of the vanilla missions
  counter (`hud_campaign.twui.xml > label_missions_count`) without its context callbacks.
  It is created under `faction_buttons_docker > button_diplomacy` with
  `core:get_or_create_component`, shows the number of **factions** with at least one
  deal ≥ 0, and is hidden at 0. It has a single state (see
  [Known crashes](#known-crashes)).
- **Tooltip** — set on the badge itself (our component has no context callbacks):
  `Quick Deal||Faction - Deal type (chance)`, one line per deal, sorted by faction then
  score. Built only from vanilla strings (the "Quick Deal" label of the diplomacy screen,
  `factions_screen_name_*` and `diplomacy_quick_deal_offers_localised_quick_deal_title_*`)
  so it follows the game language (English, French, …) without shipping a `.loc` file.
- **Click** — the badge is interactive, so it catches clicks on that corner of the
  button. On `ComponentLClickUp` the mod rescans and notes the first deal type (in the
  screen's button order: non-aggression pact, trade agreement, military access,
  defensive alliance, military alliance, peace, then vassal / tributary / confederation)
  that has a deal ≥ 0. Then:
  1. on the next UI update (a real timer, not inside the badge's UI event), click the
     diplomacy button (`SimulateLClick`);
  2. once that click has returned, a check runs every 50 ms (`repeat_real_callback`)
     and acts only when what it needs exists — no fixed delay, so a slow machine just
     waits longer:
     - when `diplomacy_dropdown` and its `faction_panel > faction_panel_bottom >
       buttons_bl > button_quick_deal` exist: press it, unless already selected;
     - when `faction_panel > list_quick_deal_buttons` contains the button named after
       the option (the game uses the option key as id, e.g.
       `diplomatic_option_nonaggression_pact`): select it, unless already selected.
       Only ids and states are read.
  3. The check stops when done, or after 10 s without the next thing appearing (e.g. the
     diplomacy button is disabled); at the deal-type stage it then logs the button ids
     it found.

  The mod's own simulated clicks run with a `simulating_click` guard: the game fires
  events and runs due timers inside `SimulateLClick`, and the check does nothing while
  the guard is set. A newer badge click replaces a flow in progress. Nothing listens to
  `PanelOpenedCampaign`, so opening diplomacy manually is never affected. See
  [Known crashes](#known-crashes) §3 for why the flow is built this way.

### Known crashes

All crashes had the same signature: access violation reading address 0 at
`Warhammer3.exe+0x244e743`, main thread, typically when clicking an army. Crash reports
are in `%APPDATA%\The Creative Assembly\Warhammer3\crash_report\`.

#### 1. Tooltip set on the vanilla diplomacy button

**Never call `SetTooltipText` on the vanilla diplomacy button.** Its tooltip is driven by
a `ContextTooltipSetter` callback (`Loc("diplomacy_button_tooltip")`) that overwrites
script text. The first build set it once at load (and tried on hover) and crashed the
game three times out of three, from ~20 s to a few minutes after loading, e.g. when
clicking an army: access violation reading address 0 at `Warhammer3.exe+0x244e743`, main
thread. With the HUD switched off (`quick_deal_indicator_no_hud.txt`) it didn't crash, and a
build that kept the badge but dropped that call didn't crash either.
The test mocks now reject this call. Note also that `ComponentMouseOn` never reported
`button_diplomacy` in-game, so hover code on that button never ran.

#### 2. Hover state and tooltip reads on game buttons

A build added three things at once: a second `hover` state on the badge (switched on
`ComponentMouseOn`/`Off`), reading the tooltips of the game-created deal-type buttons
(`GetTooltipText`) to identify them, and the event-driven refresh. In-game:

- `ComponentMouseOn`/`Off` never reached the badge, so hovering did nothing;
- after clicking the badge the game itself switched it to the `hover` state and it stayed
  lit;
- the script stopped right after logging the first deal-type button (no error caught,
  no later refresh), and clicking an army then crashed the game.

The next build removed the `hover` state and all tooltip reads on game components
(buttons are found by id, which the log showed to be the option key), and kept the event
refresh. The mocks reject `GetTooltipText` on game deal-type buttons. That build ran
10 minutes without crashing (badge click, deal-type selection, army clicks and moves),
so the cause was one of the two removed parts; which one isn't established.

#### 3. Badge clicked while another panel was open

With the settlement panel open, clicking the badge logged `badge clicked`, then the
settlement panel closing *during the click handler* (the simulated click on the
diplomacy button closed it synchronously). After that no timer callback ever ran again
(not the Quick Deal step, not the scheduled refresh, not the 2 s expiry), and the game
crashed 35 s later when clicking an army. The two sessions where the click flow worked
had no other panel open. Crash 2 showed the same pattern: the script stalled silently
mid-flow, then the game crashed.

A first fix deferred the diplomacy click to a timer and added step logging, timestamps
(`os.clock()`) and a 5 s `heartbeat` in debug mode. The log then showed the real
mechanism: `SimulateLClick` on the diplomacy button never returned (`diplomacy button
clicked` was never logged). Inside it, the game fired `PanelOpenedCampaign` and ran due
timers, so the Quick Deal step (scheduled from that event) ran re-entrantly on the
half-built panel and never came back. Heartbeats stopped and event listeners died (the
badge stopped reacting to clicks).

Fix: nothing reacts to `PanelOpenedCampaign` any more. After the diplomacy click has
returned, a check waits for each panel/button to exist (no fixed delays, so it doesn't
depend on the machine's speed), and is inert while one of the mod's own clicks is in
progress (see the Click description above). Tests simulate the game running timers
inside the clicks and check nothing runs there.

Also seen in-game: a deal-type button whose state was logged as `selected` didn't match
the Lua pattern `^selected`, so it was clicked again. States are now checked with a
tolerant `is_selected()` (case-insensitive, anywhere in the string) and logged with
`%q` to reveal hidden characters.

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
workshop/
├── description.bbcode        # Steam Workshop description, ready to paste
└── quick_deal_indicator.png  # 256x256 Workshop preview (same name as the pack)
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
the badge (count, hidden at 0, created once), the badge
tooltip (content, order, localised strings), the click flow (Quick Deal pressed once,
never toggled off, request expiry, manual openings untouched, first deal type in screen
order, matching by id, game button tooltips never read, unknown buttons left alone), that
the vanilla button's tooltip is never touched, which events trigger a refresh (only on the local player's
turn, grouped), and error handling. GitHub Actions runs the suite and a pack build on every push
(`.github/workflows/tests.yml`).

What the mocks can't prove — how the badge renders, whether the game delivers the click
event to it, and engine crashes — is covered by the in-game checklist below.

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
   whose *Deal chance* is ≥ 0 must appear in the badge tooltip with the same value, and
   no other.
3. **Badge tooltip** — hover the badge: the tooltip shows the "Quick Deal" title, then
   one line per deal. The badge never stays in a different look.
4. **Badge click** — click the badge: diplomacy opens on the Known Factions list with the
   Deal chance column (Quick Deal enabled), with the first deal type that has a deal ≥ 0
   selected. The log shows `badge clicked, first deal type: ...`,
   `clicking diplomacy button`, `diplomacy button clicked`,
   `quick deal button ready after N ms`, `quick deal button ... clicked`,
   `deal type button ready after N ms`, `deal type ... clicked` (or `already selected`),
   then `click flow finished: done`.
   Repeat with other panels open first (a settlement, an army's units, recruitment,
   technologies), and check the `heartbeat` lines keep coming afterwards. Clicking the diplomacy button outside the badge opens
   diplomacy normally.
5. **Live refresh** — move an army, win a battle, or open and close any panel: the log
   shows `event <name>: refresh scheduled` (or why it was skipped), then a
   `refresh (<name>)` block, and the badge follows.
6. **Stability** — play normally for at least 10 minutes: hover the diplomacy button,
   click armies and settlements, open and close panels. No crash.
7. **Refresh on close** — sign one of the listed deals, close diplomacy: the badge
   updates (`refresh (diplomacy closed)` in the log).
8. **Turn start** — end the turn: a `refresh (turn start)` block appears, and nothing
   flashes on screen.
9. **Zero case** — with no deal ≥ 0, no badge.
10. **French** — set the game language to French: the badge tooltip is in French.
11. **Multiplayer** — play a few co-op turns with both players running the mod: no
   desync, and each player sees only their own deals.
12. **No errors** in `lua_mod_log.txt`.

## Something's wrong?

See [DEBUG.md](DEBUG.md): a step-by-step guide to find out whether a crash comes from
the mod, collect logs and crash files, inspect raw scores and report the problem.

## License

[MIT](LICENSE)
