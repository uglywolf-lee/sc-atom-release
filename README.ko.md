# SC-Atom — 스타시티즌 음성 명령

[English](README.md) · **한국어**

「**아톰**」 하고 부르면 켜지고, 그 뒤로는 명령어만 말하면 게임 키를 대신 누릅니다. 대답은 함선 AI 처럼 짧은 영어 음성입니다.

명령어 목록 · 설명서 (폰·패드로 보며 익히기):
https://sc.uglywolf.org/atom

## 받기

[Releases](../../releases/latest) 에서 `SC-Atom-<판>.zip` 을 받아 풉니다. 설치·파이썬 필요 없음(윈도우 10/11 64비트).

한글채팅(SC-KoChat)을 쓰면 아톰 칸의 「다운로드」로 받고 「실행」·「정지」로 켜고 끕니다.

| 파일 | 하는 일 |
|---|---|
| `run_atom.bat` | 아톰 켜기 |
| `mic.bat` | 마이크 고르기 — 말하면서 막대가 움직이는 줄을 누르기 |
| `keys.bat` | 처음 한 번, 게임을 끄고: 기본 키 없는 명령에 빈 왼쪽 Alt+글자 넣기(백업 생김, `keys.bat undo` 로 되돌림) |
| `update.bat` | 새 판이 있나 보고, 올릴지 물은 뒤 올림(설정·목소리 등록은 그대로). 켤 때도 새 판이면 묻습니다 |
| `train.bat` | 목소리 등록(한국어 권장, 10분 안팎) |
| `selftest.bat` | 조종석에서 모드 키를 말 없이 시험 |

처음 켤 때 윈도우 표시 언어가 한국어면 한국어, 아니면 영어로 시작합니다(`atom_config.json` 의 `"language"` 로 바꿈).

게임을 어느 드라이브·폴더에 깔았든 알아서 찾습니다. 그래도 `keys.bat` 이 못 찾으면 그 창에 게임 폴더를 끌어다 놓거나,
`atom_config.json` 의 `"actionmaps"` 에 게임 폴더를 적습니다(예: `"D:/Games/Roberts Space Industries/StarCitizen"`).

## 라이선스

GPL-3.0 (`LICENSE`). 소스는 이 저장소의 [`source/`](source/) 와 zip 안 `source\` 폴더에 있습니다(명령표·목소리·모델 같은 데이터는 zip 에).
함께 쓰는 부품(whisper.cpp, Vosk, NumPy, PortAudio 등)과 대답 목소리(Kokoro-82M)의 라이선스는 zip 안 `THIRD-PARTY-NOTICES.txt`.

비공식 팬 도구입니다. Star Citizen 은 Cloud Imperium Games 의 상표입니다.

개발 uglywolf · 공동 개발 Claude (Anthropic AI) — 기획·게임 시험·조정은 uglywolf, 코드는 함께 작성.

© 2026 uglywolf
