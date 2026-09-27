# Debugging Quick Deal Indicator

A step-by-step guide for when something goes wrong: the game crashes, the badge doesn't
show, the numbers look wrong, or an update breaks the mod. It assumes you have never
made or debugged a mod before, so nothing is skipped. Go through the sections in order.

---

## 0. Vocabulary and places you'll need

| Name used below | What it is | Where it is |
|---|---|---|
| **GAME** | The game's install folder | `C:\Program Files (x86)\Steam\steamapps\common\Total War WARHAMMER III` |
| **DATA** | Where mod packs go | `GAME\data` |
| **APPDATA** | The game's settings, logs, crash reports and saves | `%APPDATA%\The Creative Assembly\Warhammer3` |
| **SAVES** | Your save games | `APPDATA\save_games` |
| **REPO** | This project on your disk | `E:\Projects\wh3-quick-trade-indicator` |
| **pack** | A `.pack` file: an archive the game loads. The mod is `quick_deal_indicator.pack` | in DATA (local build) or downloaded by Steam (Workshop) |
| **launcher** | The window that opens when you press Play in Steam; its mod manager enables/disables packs | — |

How to open a folder from the table: press `Win + R`, paste the path (`%APPDATA%` works
as-is), press Enter.

How to open a terminal: press `Win + X` → **Terminal** (or **Windows PowerShell**). Then
go to the project with:

```powershell
cd E:\Projects\wh3-quick-trade-indicator
```

---

## 1. First: is it really the mod?

Crashes happen in the vanilla game too, especially during end turn. Always check this
first — it takes five minutes and saves hours.

1. **Keep a copy of the save that has the problem.** Open SAVES, sort by date, copy the
   most recent `.save` file somewhere safe (e.g. your Desktop). Autosaves get overwritten.
2. **Write down exactly what you did** before the problem: "loaded the save, moved an
   army, pressed End Turn, crashed during AI turns". The more precise, the better.
3. **Reproduce with the mod:** launch the game with the mod enabled, load the copied
   save, do the same thing. Does it crash / fail again? Try 2–3 times.
4. **Reproduce without the mod:** in the launcher, untick **quick_deal_indicator** (and
   every other mod), load the same save, do the same thing, 2–3 times.

Read the result:

| With mod | Without mod | Meaning |
|---|---|---|
| problem | problem | Not this mod. It's the game or another mod. You can stop here. |
| problem | fine | Probably this mod → continue with section 2. |
| sometimes | sometimes | Random game issue; retry more times before blaming the mod. |

If you use other mods: enable them back **one at a time** with this mod to find the one
that conflicts.

> The mod is save-game compatible: you can disable it and re-enable it on the same
> campaign without breaking anything. It only reads data and draws on your HUD.

---

## 2. Collect the evidence

Do this right after the problem happens, **before relaunching the game** (some files are
overwritten at the next launch).

### 2.1 Did the script load? — `GAME\lua_mod_log.txt`

Open it with Notepad. Look for the mod's lines:

- ✅ `Mod [script\campaign\mod\quick_deal_indicator.lua] loaded successfully` → the script
  loaded fine.
- ❌ An error next to `quick_deal_indicator.lua` (e.g. `unexpected symbol near`) → the
  script has a syntax error. Note the line number it mentions.
- ❌ No `quick_deal_indicator` line at all → the pack isn't loaded: check it's in DATA
  and ticked in the launcher (section 5).
- The line `quick_deal_indicator() not found, continuing` is **normal**, not an error.

### 2.2 The mod's own log — `GAME\quick_deal_indicator_debug.txt`

The mod only writes this log if the file already exists. To turn it on:

1. Open GAME in the File Explorer.
2. Right-click in an empty area → **New** → **Text Document**.
3. Name it exactly `quick_deal_indicator_debug.txt` (if Windows hides extensions, make
   sure it isn't `quick_deal_indicator_debug.txt.txt`: in Explorer, **View → Show → File
   name extensions**).
4. Launch the game and reproduce the problem.

What you'll see:

```
[QDI] refresh (campaign loaded): 1 deal(s) with 1 faction(s)
[QDI]   wh3_main_cth_eastern_river_lords diplomatic_option_trade_agreement 5.2
```

- One `refresh (...)` block per campaign load, turn start and diplomacy screen close.
- `[QDI] ERROR during refresh: ...` → the script hit an error; the message says where.
- `[QDI] diplomacy button not found, HUD not updated` → the HUD changed (game patch or
  another UI mod).
- The **last line** before a crash tells you what the mod was doing (or that it was
  doing nothing: if the last refresh is minutes before the crash, the mod was idle).

Delete the file when you're done to turn logging off.

### 2.3 Crash files

After a crash (desktop, error window, or the game just closes):

- `APPDATA\crash_report\` — one pair per crash, named by date and time:
  - `D<date>_T<time>.stack.txt` — the list of modules on the crashing call stack. If it
    only shows `Warhammer3`, `ntdll`, `KERNEL32`, the crash is inside the game engine
    itself (the mod's Lua runs inside the engine too, so this alone doesn't clear the
    mod — use section 1).
  - `D<date>_T<time>.mdmp` — the full crash dump (large file, for developers).
- `%LOCALAPPDATA%\CrashDumps\Warhammer3.exe.<number>.dmp` — Windows' copy of the dump.
- `APPDATA\logs\no_clean_exit` — just a marker that the game didn't close normally.
- `APPDATA\logs\mp_log.txt` — engine log. The last lines tell you what the game was
  doing (e.g. `REPORT_START_OF_TURN_END` = end turn was being processed). Times in this
  file are UTC, not your local time (on this PC they are currently 2 hours behind the
  clock).

Compare times: note the crash file's time and the times of the last lines in the mod's
log and in `mp_log.txt`.

### 2.4 Screenshots

`Win + Shift + S` takes a screenshot. Take one of the HUD (bottom right) and of anything
that looks wrong.

---

## 3. Inspect the raw numbers (probe mod)

If the badge count or the tooltip values look wrong, compare them with what the game
computes, using the probe mod in `tools/probe`. It writes every faction's score for every
deal type to `GAME\quick_deal_probe.txt`.

Requirements: Python 3.14 or newer. Check in a terminal:

```powershell
python --version
```

If it's missing or older: download it from https://www.python.org/downloads/, run the
installer and **tick "Add python.exe to PATH"** on the first screen. Close and reopen the
terminal afterwards.

Then, in the terminal, from REPO:

```powershell
python tools/packtool.py build tools/probe build/quick_deal_probe.pack
Copy-Item build/quick_deal_probe.pack "C:\Program Files (x86)\Steam\steamapps\common\Total War WARHAMMER III\data\"
```

1. In the launcher, tick **quick_deal_probe**, play.
2. Open diplomacy, click each of the six deal-type buttons under the Known Factions list
   and take a screenshot of each.
3. Quit, open `GAME\quick_deal_probe.txt`. Each line is
   `faction (name) war=... | deal=score/can_issue ...`. The *Deal chance* on screen is the
   score rounded to one decimal.

**Remove the probe afterwards:** quit the game (Windows can't delete a pack the game has
open), untick it in the launcher and delete `DATA\quick_deal_probe.pack`.

---

## 4. Run the automated tests

The tests run the mod's script on a real Lua 5.1 (the game's Lua version) with fake game
functions. They catch logic mistakes without launching the game.

One-time setup, in a terminal:

```powershell
cd E:\Projects\wh3-quick-trade-indicator
python -m pip install --user -r tests/requirements.txt
```

Run them:

```powershell
python -m unittest discover -s tests -v
```

Every line should end with `ok`, and the last line should be `OK`. A `FAIL` or `ERROR`
names the test and shows what differed. They also run automatically on GitHub after
every push: https://github.com/emmanuel-h/wh3-quick-deal-indicator/actions

The tests **can't** check how things look in-game or engine crashes — only section 1
can.

---

## 5. Rebuild and reinstall the mod

After changing anything in `mod/`:

```powershell
cd E:\Projects\wh3-quick-trade-indicator
python -m unittest discover -s tests
python tools/packtool.py build mod build/quick_deal_indicator.pack
Copy-Item build/quick_deal_indicator.pack "C:\Program Files (x86)\Steam\steamapps\common\Total War WARHAMMER III\data\"
```

- The game must be closed, otherwise the copy fails ("file in use").
- Make sure the launcher shows **quick_deal_indicator** ticked.
- **Workshop and local copy at the same time:** if you are subscribed on the Workshop
  *and* have a local pack in DATA, the launcher can list two entries. Keep only one
  ticked — to test a local build, untick the Workshop one.

To uninstall completely: untick it in the launcher and delete
`DATA\quick_deal_indicator.pack` (or unsubscribe on the Workshop).

---

## 6. Common problems

| Symptom | Likely cause | What to do |
|---|---|---|
| No badge at all | No deal ≥ 0 right now (normal), or the mod isn't loaded | Check the debug log: `0 deal(s)` is normal. Otherwise section 2.1 |
| Badge number doesn't match the diplomacy screen | The screen changed since the last refresh (the mod refreshes on load, turn start and when diplomacy closes) | Open and close diplomacy, compare again. Still wrong → section 3 |
| `diplomacy button not found` in the log | Game patch or another HUD mod changed the HUD | Try without other UI mods; report it |
| `ERROR during refresh` in the log | Game patch changed a function the mod uses | Report it with the log |
| Crash | See section 1 first | Then report with section 2's files |
| After a game patch, the mod stops working | CA changed the UI or the script API | Report it; check the Workshop page for an update |

---

## 7. Reporting the problem

Open an issue at https://github.com/emmanuel-h/wh3-quick-deal-indicator/issues (or bring
the files to whoever maintains the mod) with:

1. What you did, step by step, and what happened (section 1, step 2).
2. The result of the with/without-mod test (section 1).
3. The game version (bottom of the launcher) and the list of other mods enabled.
4. `lua_mod_log.txt` and `quick_deal_indicator_debug.txt`.
5. For a crash: the `.stack.txt`, and the time of the crash. Keep the `.mdmp`; it's
   big, attach it only if asked.
6. Screenshots.
7. The copied save file, if the problem happens every time on it.
