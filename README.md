# Quick Deal Indicator

A Total War: WARHAMMER III campaign mod that shows, on the HUD **Diplomacy** button
(bottom right, above End Turn), how many factions currently have a **Quick Deal**
the AI would accept — i.e. a *Deal chance* **≥ 0** in the diplomacy screen's
Known Factions list. Hovering the badge lights it up and lists each faction, deal type
and chance;
clicking it opens diplomacy directly on the Quick Deal view, on the first deal type that
has an acceptable deal. The count is kept up to date as you play.

## Status

🚧 Work in progress. Validated in-game with no crash: detection, the badge and its
tooltip, refresh after army moves and panels closing, and clicking the badge to open
diplomacy on the Quick Deal view with the first available deal type selected.
Implemented, awaiting in-game testing: the badge lighting up on hover. Still to test:
turn start, French, multiplayer. Several builds crashed the game along the way; see
[Known crashes](#known-crashes).

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
  deal ≥ 0, and is hidden at 0.
- **Hover** — the badge's states use vanilla button names: `active`, `down_off` and
  `inactive` (normal) and `hover` and `down` (the vanilla badge image brightened,
  `ui/quick_deal_indicator/badge_hover.png`, with white text), and its layout has the
  vanilla `Button` callback, as in `templates/round_extra_small_button.twui.xml`. With
  both, the engine switches the states by itself on mouse over and click; no script is
  involved (the game sends no `ComponentMouseOn`/`Off` for the badge). Without the
  `Button` callback the badge only lit up when hovering the diplomacy button, whose
  `StatePropagatorCallback` copies its state to its children. The count is set on every state
  (`SetStateText` only changes the current one), then the badge is put back to
  `active`.
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
  1. on the next UI tick (a 1 ms real timer, so not inside the badge's UI event), click
     the diplomacy button (`SimulateLClick`);
  2. once that click has returned, a check runs every 50 ms (single-shot real timers,
     each armed only after the previous check has returned) and acts only when what it
     needs exists — no fixed delay, so a slow machine just waits longer:
     - when `diplomacy_dropdown` and its `faction_panel > faction_panel_bottom >
       buttons_bl > button_quick_deal` exist: click it (diplomacy always opens with
       Quick Deal off, seen in-game, so its state isn't read);
     - when `faction_panel > list_quick_deal_buttons` contains the button named after
       the option (the game uses the option key as id, e.g.
       `diplomatic_option_nonaggression_pact`): click it. These behave like radio
       buttons — clicking the selected one keeps it selected (seen in-game) — so again
       no state is read.
  3. The check stops when done, or after 10 s without the next thing appearing (e.g. the
     diplomacy button is disabled).

  The mod only *finds* game components (by name) and *clicks* them: it never reads text
  from them (`CurrentState`, `GetTooltipText`, `Id`), see
  [Known crashes](#known-crashes) §3. The mocks make any such read fail the tests.

  Because each check is armed only after the previous one has returned, no check is
  pending while one of the mod's own clicks runs — the game fires events and runs due
  timers inside `SimulateLClick`, so this matters. A newer badge click replaces a flow
  in progress. Nothing listens to
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
depend on the machine's speed), and no check can be pending during one of the mod's own
clicks (see the Click description above). Tests simulate the game running timers inside
the clicks and check nothing runs there.

Two facts from vanilla `script/_lib/lib_timer_manager.lua` explained earlier confusing
results:

- `real_callback(f, 0)` doesn't defer anything: an interval `<= 0` calls `f()`
  immediately, inside the caller. So the earlier "deferred to the next UI update" steps
  written with 0 ms actually ran synchronously (inside the badge's click event, or
  nested inside the diplomacy click). The mod now uses 1 ms for "next tick", and the
  mocks reproduce the vanilla behaviour.
- `remove_real_callback` unregisters with a numeric id while registration used a
  string, and clears `real_timer[id]` instead of `real_timers[id]`: cancelling doesn't
  reliably work. The mod never uses it (chained single shots stop by themselves); the
  mocks make any use fail.

With those fixed, the next in-game runs stalled right after reading the Quick Deal
button's state: once before the log line after `CurrentState()`, once after it
(`quick deal button state: "active"`) but before the next log line, with only plain Lua
in between (checking the string). The game then crashed at `Warhammer3.exe+0x244e83b`,
next to the usual address. A script dying in plain Lua right after using a string
returned by a game component, plus earlier signs (a state printed as `selected` that
didn't match `^selected`; crash 2 while reading `GetTooltipText` strings), point to
strings returned by game components being unsafe to use. The mod now reads no text
from game components at all (see the Click description above). With that change the
whole flow ran without a stall or crash, heartbeats continued, so this is the best
explanation so far. (`Id()` seems fine: vanilla `get_or_create_component` reads the ids
of the diplomacy button's children on every refresh, in every session.)

The badge's hover look was reintroduced afterwards using vanilla state names (see HUD
above): the stuck `hover` state in §2 came from the engine switching the badge to
`hover` on click and then trying to return to `active`, which didn't exist (the normal
state was named `NewState`).

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
    ├── badge.twui.xml
    └── badge_hover.png       # brighter badge for the hover/down states
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
the badge (count on every state, hidden at 0, created once, layout states), the badge
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
3. **Badge tooltip and hover** — hover the badge: it lights up, and the tooltip shows
   the "Quick Deal" title, then one line per deal. Moving away restores it; after
   clicking it and closing diplomacy it must not stay lit.
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
