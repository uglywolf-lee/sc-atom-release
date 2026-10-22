# © 2026 uglywolf — GPL-3.0
"""SC-Atom.exe 입구 — exe 하나로 아톰과 딸린 도구를 다 돌린다(2026-10-21, 한글채팅과 별개로 나눠 주는 판).

  SC-Atom.exe                 아톰(듣기·키·대답)            ← run_atom.bat
  SC-Atom.exe mic             마이크 고르기 창                ← mic.bat
  SC-Atom.exe train [...]     목소리 등록(인자는 train.py)    ← train.bat
  SC-Atom.exe selftest [foot] 조종석 키 시험                  ← selftest.bat
  SC-Atom.exe update [--yes]  새 판 확인·올리기(묻고 나서)       ← update.bat
  SC-Atom.exe keys [apply|undo|show|plan]  기본 키 없는 명령에 빈 왼쪽 Alt+글자 넣기(게임을 끄고) ← keys.bat
키 설정 파일(actionmaps.xml)은 game_path.py 가 찾는다(런처 기록 → 흔한 자리 → 드라이브 훑기 → 물어보기).
설정(atom_config.json)의 actionmaps 에 키 파일이나 게임 폴더를 적어 정할 수도 있다.
"""
import sys


def main(argv):
    for s in (sys.stdout, sys.stderr):          # 출력을 파일로 돌리면 cp949 라 「—」에서 죽는다(2026-10-22 update 시험) — 못 쓰는 글자는 ? 로
        try:
            s.reconfigure(errors="replace")
        except Exception:
            pass
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
    elif cmd == "update":
        import updater
        updater.main(argv[1:])
    elif cmd == "keys":
        import atom
        import keymap
        import game_path
        path = atom.load_config()["actionmaps"] or game_path.ask()   # 못 찾았으면 이 창에서 폴더를 받는다
        if game_path.missing_message(path):
            atom.log(game_path.missing_message(path))
            return
        atom.log(atom.T(f"키 설정 파일: {path}", f"Keybinding file: {path}"))
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
