# © 2026 uglywolf — GPL-3.0
"""SC-Atom.exe 입구 — exe 하나로 아톰과 딸린 도구를 다 돌린다(2026-10-21, 한글채팅과 별개로 나눠 주는 판).

  SC-Atom.exe                 아톰(듣기·키·대답)            ← run_atom.bat
  SC-Atom.exe mic             마이크 고르기 창                ← mic.bat
  SC-Atom.exe train [...]     목소리 등록(인자는 train.py)    ← train.bat
  SC-Atom.exe selftest [foot] 조종석 키 시험                  ← selftest.bat
  SC-Atom.exe keys [apply|undo|show|plan]  기본 키 없는 명령에 빈 왼쪽 Alt+글자 넣기(게임을 끄고) ← keys.bat
키 설정 파일(actionmaps.xml)은 아톰처럼 드라이브를 돌며 찾는다. 설정(atom_config.json)의 actionmaps 로 정할 수도 있다.
"""
import sys


def main(argv):
    cmd = argv[0].lower() if argv else ""
    if cmd == "mic":
        import mic_pick
        mic_pick.main()
    elif cmd == "train":
        import train
        train.main(argv[1:])
    elif cmd == "selftest":
        import selftest
        selftest.main(*(argv[1:2] or ["ship"]))
    elif cmd == "keys":
        import atom
        import keymap
        path = atom.load_config()["actionmaps"]
        if not path:
            atom.log(atom.T("스타시티즌 키 설정 파일(actionmaps.xml)을 못 찾았습니다 — 게임을 한 번 켜서 키 설정을 저장하세요",
                            "Star Citizen keybinding file (actionmaps.xml) not found — open the game and save your keybindings once"))
            return
        keymap.main(["keymap", (argv[1] if len(argv) > 1 else "apply"), path])
    else:
        import atom
        try:
            atom.main()
        except KeyboardInterrupt:
            pass
        except Exception:                      # 오류는 atom_log.txt 에 남긴다(창이 닫혀도 볼 수 있게)
            import traceback
            atom.log(atom.T("오류로 멈춤:\n", "Stopped by an error:\n") + traceback.format_exc())
            raise


if __name__ == "__main__":
    main(sys.argv[1:])
