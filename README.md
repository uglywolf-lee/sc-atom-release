# SC-Atom — Star Citizen voice commands

**English** · [한국어](README.ko.md)

Say **"Atom"** to turn it on, then just say the command — Atom presses the key for you and answers in a short ship-AI voice.

Command reference & guide (open it on your phone/tablet while you learn):
https://sc.uglywolf.org/atom-en

## Download

Get `SC-Atom-<version>.zip` from [Releases](https://github.com/uglywolf-lee/sc-atom-release/releases/latest) and unzip it. Nothing to install (Windows 10/11 64-bit).

| File | What it does |
|---|---|
| `run_atom.bat` | Start Atom |
| `mic.bat` | Pick your microphone — speak and click the row whose bar moves |
| `keys.bat` | Once, with the game closed: add a spare Left Alt + letter to actions that have no default key (backup made, `keys.bat undo` reverts) |
| `update.bat` | Check for a new version; asks before updating (settings and voice profile are kept). Atom also asks at start when one is out |
| `selftest.bat` | Cockpit key test — presses the mode keys one by one, no talking |
| `train.bat` | Voice training (mainly for Korean) |

Atom starts in English unless Windows is set to Korean; change it with `"language"` in `atom_config.json`.

Atom finds the game wherever you installed it (any drive or folder). If `keys.bat` still can't find it, drag the game folder into its window,
or set `"actionmaps"` in `atom_config.json` to it (e.g. `"D:/Games/Roberts Space Industries/StarCitizen"`).

## If something goes wrong

Open an [issue](https://github.com/uglywolf-lee/sc-atom-release/issues) and attach `atom_log.txt` from the Atom folder (drag the file into the issue box).
It records what Atom heard, which keys it sent, the keybinding file it found, and the full error if it stopped.
If keys are the problem, attach `selftest_log.txt` too (made by `selftest.bat`).
The log shows folder paths (which may include your Windows user name) and your microphone name — feel free to blank them out before posting.

## License

GPL-3.0 (`LICENSE`). Source code is in [`source/`](https://github.com/uglywolf-lee/sc-atom-release/tree/main/source) in this repo and in the `source\` folder of the zip (data files such as `commands.tsv`, voices and models ship in the release zip).
Third-party components (whisper.cpp, Vosk, NumPy, PortAudio …) and the reply voices (Kokoro-82M) are listed in `THIRD-PARTY-NOTICES.txt` inside the zip.

Unofficial fan tool. Star Citizen is a trademark of Cloud Imperium Games.

Developed by uglywolf, co-developed with Claude (Anthropic AI) — design, in-game testing and tuning by uglywolf; code written together.

© 2026 uglywolf
