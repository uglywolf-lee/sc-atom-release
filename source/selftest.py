# © 2026 uglywolf — GPL-3.0
"""게임 안 시험: 명령을 차례로 보내고, 무엇을 언제 보냈는지 적는다.

게임PC 에서 「selftest.bat」을 두 번 눌러 실행 → 10초 안에 게임 창으로 → 배에 앉아 화면만 본다(모드 키 8번).
걸어 다니며 하는 옛 시험은 「selftest.bat foot」.
키는 실제 앱과 같은 길(commands.tsv + 그 사람의 actionmaps.xml)로 정한다.
"""
import os
import sys
import time

import json

import i18n
import keymap
import sendkeys
from i18n import T

ACTIONMAPS = ""        # 비우면 아톰처럼 찾는다(game_path.find — 친구 PC 는 설치 위치가 다르다)
LOG = os.path.join(keymap.HERE, "selftest_log.txt")

# 걸어 다니는 상태(정거장·도시)에서 화면으로 바로 보이는 것만 — 배를 부를 필요 없이.
# 같은 키를 두 번 보내 켜졌다 꺼지는지 본다. (묶음, 동작, 기본 키, 방식, 보이는 것)
FOOT_TESTS = [
    # 걸을 때 F4 는 1인칭 → 외부 카메라 1 → 외부 카메라 2 → 1인칭 (2026-10-21 게임에서 확인)
    ("player", "thirdperson", "f4", "tap", "외부 카메라 1"),
    ("player", "thirdperson", "f4", "tap", "외부 카메라 2"),
    ("player", "thirdperson", "f4", "tap", "1인칭으로"),
    ("player", "toggle_flashlight", "t", "press", "손전등 켜짐"),
    ("player", "toggle_flashlight", "t", "press", "손전등 꺼짐"),
    ("player", "toggleAttachHelmet", "lalt+h", "tap", "헬멧 씀/벗음 — 수식키 조합"),
    ("player", "toggleAttachHelmet", "lalt+h", "tap", "헬멧 원래대로"),
    ("player", "mobiglas", "f1", "press", "모비글래스 열림"),
    ("player", "mobiglas", "f1", "press", "모비글래스 닫힘"),
    ("player", "v_starmap", "f2", "press", "지도 열림"),
    ("player", "v_starmap", "f2", "press", "지도 닫힘"),
]
# 조종석 시험(2026-10-21): 모드 키만. 말 없이 키만 보내고, 무엇을 눌렀는지 대답 소리로 알린다.
# 배 시동 켠 채 조종석에 앉아 SCM·건 모드에서 시작한다. 격납고 안이어도 된다. (명령표의 「말」, 보이는 것)
SHIP_TESTS = [                     # (명령표의 「말」 — 찾는 열쇠, 보이는 것 한국어, 영어)
    ("미사일", "미사일 모드로", "missile mode"),
    ("건 모드", "건 모드로 돌아옴", "back to guns mode"),
    ("스캔 모드", "스캔 모드 켜짐", "scan mode on"),
    ("스캔 모드", "스캔 모드 꺼짐", "scan mode off"),
    ("나브 모드", "NAV 로", "to NAV"),
    ("전투 모드", "SCM 으로", "to SCM"),
    ("퀀텀 모드", "NAV 로(B 길게)", "to NAV (hold B)"),
    ("퀀텀 모드", "SCM 으로(B 길게)", "to SCM (hold B)"),
]
GAP = 4.0
SHIP_GAP = 6.0


def main(which="ship", path=ACTIONMAPS):
    try:                                              # 화면 글은 아톰 설정의 말로(영어권 사용자 — 2026-10-21)
        with open(os.path.join(keymap.HERE, "atom_config.json"), encoding="utf-8-sig") as f:
            i18n.LANG = json.load(f).get("language", "ko")
    except (OSError, ValueError):
        pass
    if not path:
        import atom
        path = atom.load_config()["actionmaps"]
    import game_path
    if game_path.missing_message(path):              # 키 파일이 없으면 게임 기본 키로 시험한다(아톰도 그렇게 보낸다)
        print(game_path.missing_message(path))
        binds = {}
    else:
        binds, _ = keymap.read_user(path)
    with open(LOG, "w", encoding="utf-8") as log:
        def say(msg):
            line = f"{time.strftime('%H:%M:%S')} {msg}"
            print(line)
            log.write(line + "\n")
            log.flush()

        for s in range(10, 0, -1):
            print(T(f"{s}초 뒤 시작 — 게임 창을 누르세요", f"Starting in {s}s — click the game window"), end="\r")
            time.sleep(1)
        print()
        if sendkeys.blocked_by_admin():               # 시험 키도 막힌다 — 먼저 알린다
            say("게임이 관리자 권한으로 돌고 있어 윈도우가 아톰의 키를 막습니다 — run_atom.bat 을 우클릭해 「관리자 권한으로 실행」하거나, RSI 런처를 관리자 권한 없이 켜세요 / Star Citizen is running as administrator, so Windows blocks Atom's keys — right-click run_atom.bat and choose 'Run as administrator', or start the RSI Launcher without admin rights")
        if which == "foot":
            for i, (amap, action, default, mode, look) in enumerate(FOOT_TESTS, 1):
                c = {"묶음": amap, "동작": action, "기본 키": default}
                key = keymap.effective(c, binds)
                if key is None:
                    say(f"{i:2}. {look}: " + T("키 없음 — 건너뜀", "no key — skipped"))
                else:
                    say(f"{i:2}. {look} ← {key} ({mode})")
                    sendkeys.send(key, mode)
                time.sleep(GAP)
        else:
            import reply
            cmds = {c["말"]: c for c in keymap.load_commands()}
            for i, (word, look_ko, look_en) in enumerate(SHIP_TESTS, 1):
                look = T(look_ko, look_en)
                c = cmds[word]
                key = keymap.effective(c, binds)
                if key is None:
                    say(f"{i:2}. {word} → {look}: " + T("키 없음 — 건너뜀", "no key — skipped"))
                else:
                    say(f"{i:2}. {T(word, c['영어 말'])} → {look} ← {key} ({c['방식']})")
                    sendkeys.send(key, c["방식"], c["길게"])
                    reply.play(reply.path_for("bf_emma", "cmd", c["동작"]))   # 키 먼저, 소리는 뒤에(앱과 같은 차례)
                time.sleep(SHIP_GAP)
        say(T("끝", "done"))


if __name__ == "__main__":
    main(*sys.argv[1:3])
