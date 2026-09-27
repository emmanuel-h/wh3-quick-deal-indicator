# Quick Deal Indicator

A Total War: WARHAMMER III campaign mod that shows, on the HUD **Diplomacy** button
(bottom right, above End Turn), how many factions currently have a **Quick Deal**
the AI would accept — i.e. a *Deal chance* **≥ 0** in the diplomacy screen's
Known Factions list. Hovering the button lists each faction, deal type and chance.

## Status

🚧 Work in progress. The detection method has been validated in-game (see
[How it works](#how-it-works)); the HUD badge and tooltip are being implemented.

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

## Repository layout

```
mod/                          # Files packed into quick_deal_indicator.pack
└── script/campaign/mod/
    └── quick_deal_indicator.lua
```

## License

[MIT](LICENSE)
