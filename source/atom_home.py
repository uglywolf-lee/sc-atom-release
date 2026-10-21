# © 2026 uglywolf — GPL-3.0
"""아톰 폴더 — 명령표·목소리·모델·설정·기록이 있는 곳.

.py 로 돌 때는 이 파일 옆, exe(PyInstaller)로 묶였을 때는 SC-Atom.exe 옆이다(묶음 안 _internal 이 아니라).
이름을 흔한 「paths」로 하지 말 것 — PyInstaller 가 남의 같은 이름 모듈을 넣는다(한글채팅 2026-08-27).
"""
import os
import sys

FROZEN = bool(getattr(sys, "frozen", False))
HERE = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
