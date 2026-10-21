# SC-Atom — 스타시티즌 음성 명령 · Star Citizen voice commands

「**아톰**」 하고 부르면 켜지고, 그 뒤로는 명령어만 말하면 게임 키를 대신 누릅니다. 대답은 함선 AI 처럼 짧은 영어 음성입니다.
Say **"Atom"** to turn it on, then just say the command — Atom presses the key and answers in a short ship-AI voice.

명령어 목록 · 설명서 (폰·패드로 보며 익히기):
https://sc.uglywolf.org/atom

Command reference & guide (English):
https://sc.uglywolf.org/atom-en

## 받기 · Download

[Releases](../../releases/latest) 에서 `SC-Atom-<판>.zip` 을 받아 풉니다. 설치·파이썬 필요 없음(윈도우 10/11 64비트).
Download `SC-Atom-<version>.zip` from Releases and unzip. Nothing to install (Windows 10/11 64-bit).

한글채팅(SC-KoChat)을 쓰면 아톰 칸의 「다운로드」로 받고 「실행」·「정지」로 켜고 끕니다.

| 파일 / File | 하는 일 / What it does |
|---|---|
| `run_atom.bat` | 아톰 켜기 · run Atom |
| `mic.bat` | 마이크 고르기 · pick microphone |
| `keys.bat` | 처음 한 번, 게임을 끄고: 기본 키 없는 명령에 빈 왼쪽 Alt+글자 넣기 · once, game closed: add spare Left Alt keys |
| `train.bat` | 목소리 등록(한국어 권장) · voice training (Korean) |
| `selftest.bat` | 조종석에서 모드 키 시험 · cockpit key test |

처음 켤 때 윈도우 표시 언어가 한국어면 한국어, 아니면 영어로 시작합니다(`atom_config.json` 의 `"language"` 로 바꿈).
Atom starts in English unless Windows is in Korean; change it with `"language"` in `atom_config.json`.

## 라이선스 · License

GPL-3.0 (`LICENSE`). 소스는 zip 안 `source\` 폴더에 있습니다 · Source code is in the `source\` folder of the zip.
함께 쓰는 부품(whisper.cpp, Vosk, NumPy, PortAudio 등)과 대답 목소리(Kokoro-82M)의 라이선스는 zip 안 `THIRD-PARTY-NOTICES.txt`.

비공식 팬 도구입니다. Star Citizen 은 Cloud Imperium Games 의 상표입니다. · Unofficial fan tool.

개발 uglywolf · 공동 개발 Claude (Anthropic AI) — 기획·게임 시험·조정은 uglywolf, 코드는 함께 작성.
Developed by uglywolf, co-developed with Claude (Anthropic AI) — design, in-game testing and tuning by uglywolf; code written together.

© 2026 uglywolf
