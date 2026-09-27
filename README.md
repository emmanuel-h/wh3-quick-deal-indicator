# WH3 Quick Trade Indicator

A Total War: WARHAMMER III campaign mod that tells you, at a glance, which factions
currently have a **Quick Deal** available with a score **greater than or equal to 0**
(i.e. a deal the AI would accept without you losing out).

No more opening the diplomacy screen and clicking "Quick Deal" on every faction one by one.

## Status

🚧 Work in progress — the scanning logic is scaffolded but the UI component paths used
to read the Quick Deal result still need to be verified in-game (see
[Development](#development)).

## Features (planned)

- Scan all factions you are in contact with when the diplomacy screen opens.
- Highlight factions whose best Quick Deal has a score ≥ 0.
- Optional notification at the start of your turn listing those factions.

## Installation

1. Download `wh3_quick_trade_indicator.pack` from the
   [Releases](../../releases) page (or subscribe on the Steam Workshop once published).
2. Copy it into `<Steam>/steamapps/common/Total War WARHAMMER III/data/`.
3. Enable it in the game launcher's mod manager.

Save-game compatible: the mod only reads state and adds UI, it can be enabled or
disabled mid-campaign.

## Repository layout

```
mod/                          # Contents of the .pack, mirrored as loose files
└── script/campaign/mod/
    └── quick_trade_indicator.lua
```

## Development

Tools:

- [RPFM](https://github.com/Frodo45127/rpfm) — to build the `.pack` from the `mod/` folder.
- The in-game UI inspector / [Mod Configuration Tool](https://steamcommunity.com/sharedfiles/filedetails/?id=2927955021)
  console to find UI component names and test Lua live.

Build:

1. In RPFM, create a new pack of type **Mod** named `wh3_quick_trade_indicator.pack`.
2. Add the `mod/` folder contents at the pack root (so the script ends up at
   `script/campaign/mod/quick_trade_indicator.lua`).
3. Save the pack into the game's `data/` folder and enable it in the launcher.

Logging: the script writes to the standard script log (`script_log_*.txt`) with the
`[QTI]` prefix. Enable script logging to see it.

## License

TBD
