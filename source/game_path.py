# © 2026 uglywolf — GPL-3.0
"""스타시티즌 키 설정 파일(actionmaps.xml) 찾기.

게임이 100GB 가 넘어 사람마다 다른 드라이브·폴더에 깐다(D:\\StarCitizen, F:\\Games\\RSI …).
「경로를 알려 주세요」라고 물으면 대개 못 답하므로 묻지 않고 찾는다. 값싼 것부터:
  ① 설정 atom_config.json 의 actionmaps — 파일도, 폴더(…\\LIVE, …\\StarCitizen, 런처 설치 폴더)도 받는다
  ② 지난번에 찾아 둔 자리(아톰 폴더의 game_path.txt) — 게임을 옮겼으면 버리고 다시 찾는다
  ③ RSI 런처 기록 %APPDATA%\\rsilauncher\\logs\\log.log — 런처가 설치·실행 때 게임 폴더를 적는다
     (게임PC 실측 2026-10-22: 「E:\\\\Roberts Space Industries\\\\StarCitizen\\\\LIVE」, 역슬래시 두 겹.
      launcher store.json 은 암호화돼 있어 못 읽는다)
  ④ 흔한 자리 — 모든 드라이브의 \\, \\Games, \\Program Files … 아래 StarCitizen 또는 Roberts Space Industries\\StarCitizen
  ⑤ 드라이브를 얕게 훑기(5단계까지, 네트워크 드라이브 빼고) — 「StarCitizen」 폴더 안에 Data.p4k 가 있는 채널
  ⑥ (keys.bat 처럼 창이 있을 때만) 사람에게 폴더를 끌어다 놓게 묻는다
게임 폴더 = StarCitizen\\<채널>(LIVE·PTU·EPTU·HOTFIX·TECH-PREVIEW), 표시는 Data.p4k. 채널은 LIVE 먼저.
키 파일은 그 밑 user\\client\\0\\Profiles\\default\\actionmaps.xml 인데, 게임 안에서 키를 한 번 바꿔야 생긴다 —
게임은 찾았는데 파일이 없으면 그 자리를 돌려주고, 부르는 쪽이 missing_message 로 알린다.
"""
import os
import re
import sys

from atom_home import HERE
from i18n import T

CHANNELS = ("LIVE", "PTU", "EPTU", "HOTFIX", "TECH-PREVIEW")
TAIL = os.path.join("user", "client", "0", "Profiles", "default", "actionmaps.xml")
REMEMBER = os.path.join(HERE, "game_path.txt")
COMMON = ("", "Games", "Game", "Program Files", "Program Files (x86)", "SC")
SKIP = {"windows", "$recycle.bin", "system volume information", "programdata", "appdata", "recovery",
        "perflogs", "node_modules", "$windows.~ws", "$windows.~bt", "windowsapps"}
DEPTH = 5                     # 훑는 깊이 — 게임PC 실측 C: 폴더 6,937개 1.1초(4단계는 0.1초). 더 파면 큰 드라이브에서 길어진다


def is_channel(p):
    return os.path.isfile(os.path.join(p, "Data.p4k"))


def drives():
    """내장·외장(이동식) 드라이브만. 네트워크 드라이브는 뺀다 — 끊겨 있으면 폴더 하나 여는 데도 한참 멈춘다."""
    if sys.platform != "win32":
        return []
    import ctypes
    k = ctypes.windll.kernel32
    mask = k.GetLogicalDrives()
    return [f"{c}:\\" for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            if i >= 2 and mask >> i & 1 and k.GetDriveTypeW(f"{c}:\\") in (2, 3)]   # 2 이동식, 3 고정


def channels_under(p):
    """폴더 하나(…\\LIVE, …\\StarCitizen, 런처 설치 폴더) → 그 안의 게임 채널 폴더들(LIVE 먼저)."""
    p = os.path.normpath(p.strip().strip('"').strip("'"))
    if is_channel(p):
        return [p]
    for sc in (p, os.path.join(p, "StarCitizen"), os.path.join(p, "Roberts Space Industries", "StarCitizen")):
        found = [os.path.join(sc, ch) for ch in CHANNELS if is_channel(os.path.join(sc, ch))]
        if found:
            return found
    return []


def pick(channels):
    """채널들 → 쓸 키 파일. LIVE 가 있으면 파일이 아직 없어도 LIVE(대부분 LIVE 에서 논다), 없으면 파일 있는 채널."""
    paths = [os.path.join(ch, TAIL) for ch in channels]
    if os.path.basename(channels[0]).upper() == "LIVE":
        return paths[0]
    return next((p for p in paths if os.path.isfile(p)), paths[0])


def from_launcher_log():
    """RSI 런처 기록에 적힌 StarCitizen 폴더들, 최근 것부터."""
    appdata = os.environ.get("APPDATA", "")
    found = []
    for rel in (("logs", "log.log"), ("log", "log.log"), ("log.log",)):     # 런처 판마다 자리가 달랐다
        try:
            with open(os.path.join(appdata, "rsilauncher", *rel), encoding="utf-8", errors="ignore") as f:
                txt = f.read()
        except OSError:
            continue
        # 「:」를 못 넘게 해서 한 줄의 다른 드라이브 경로와 이어 붙지 않게, 「StarCitizen_Launcher.exe」 는 빼고
        for m in re.finditer(r'[A-Za-z]:[\\/][^"\r\n:*?<>|]*?StarCitizen(?![\w.-])', txt):
            found.append(re.sub(r"[\\/]+", lambda _: "\\", m.group(0)))
    out = []
    for p in reversed(found):
        if p.lower() not in (o.lower() for o in out):
            out.append(p)
    return out


def scan():
    """드라이브를 얕게 훑어 「StarCitizen」 폴더를 찾는다. 찾은 채널들 또는 []."""
    for d in drives():
        for root, dirs, _ in os.walk(d):
            depth = 0 if root == d else root[len(d):].count(os.sep) + 1
            for name in dirs:
                if name.lower() == "starcitizen":
                    ch = channels_under(os.path.join(root, name))
                    if ch:
                        return ch
            if depth >= DEPTH:
                dirs[:] = []
            else:
                dirs[:] = [n for n in dirs if not n.startswith((".", "$")) and n.lower() not in SKIP]
    return []


def remember(channel):
    try:
        with open(REMEMBER, "w", encoding="utf-8") as f:
            f.write(channel + "\n")
    except OSError:
        pass


def remembered():
    try:
        with open(REMEMBER, encoding="utf-8") as f:
            p = f.read().strip()
    except OSError:
        return []
    return channels_under(p) if p else []


def find(setting=""):
    """→ (actionmaps.xml 경로, 찾은 곳). 게임을 못 찾으면 ("", "")."""
    if setting:
        if setting.lower().endswith(".xml"):
            # 파일이 아직 없어도 그 채널 폴더가 맞으면 쓴다(키를 바꾸면 생긴다)
            ch = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(setting))))))
            if os.path.isfile(setting) or is_channel(ch):
                return setting, "setting"
        else:
            ch = channels_under(setting)
            if ch:
                return pick(ch), "setting"
    ch = remembered()
    if ch:
        return pick(ch), "remembered"
    for how, cands in (("launcher", from_launcher_log), ("common", lambda: [os.path.join(d, m) for d in drives() for m in COMMON])):
        for p in cands():
            ch = channels_under(p)
            if ch:
                remember(ch[0])
                return pick(ch), how
    ch = scan()
    if ch:
        remember(ch[0])
        return pick(ch), "scan"
    return "", ""


def ask():
    """마지막 수단 — 창이 있을 때만(keys.bat). 폴더를 끌어다 놓게 하고 기억해 둔다. → 키 파일 경로 또는 ""."""
    if not sys.stdin or not sys.stdin.isatty():
        return ""
    print(T("\n스타시티즌 게임 폴더를 못 찾았습니다.",
            "\nCouldn't find the Star Citizen game folder."))
    print(T("게임이 깔린 폴더(StarCitizen 또는 그 안의 LIVE)를 이 창에 끌어다 놓거나 붙여 넣고 엔터를 누르세요.",
            "Drag the folder where the game is installed (StarCitizen, or LIVE inside it) into this window, or paste it, then press Enter."))
    print(r"  예/e.g.  D:\Games\Roberts Space Industries\StarCitizen")
    for _ in range(3):
        try:
            p = input(T("  폴더: ", "  Folder: "))
        except (EOFError, KeyboardInterrupt):
            return ""
        if not p.strip():
            return ""
        ch = channels_under(p)
        if ch:
            remember(ch[0])
            print(T(f"  찾았습니다: {ch[0]}\n", f"  Found: {ch[0]}\n"))
            return pick(ch)
        print(T("  거기엔 게임(Data.p4k)이 없습니다. 다시 넣어 주세요.",
                "  No game (Data.p4k) there. Please try again."))
    return ""


def missing_message(path):
    """키 파일을 쓸 수 없을 때 사람에게 보일 글. 쓸 수 있으면 ""."""
    if not path:
        return T('스타시티즌 게임 폴더를 못 찾았습니다 — atom_config.json 의 "actionmaps" 에 게임 폴더를 적어 주세요 '
                 '(예: "D:/Games/Roberts Space Industries/StarCitizen")',
                 'Couldn\'t find the Star Citizen game folder — put it in "actionmaps" in atom_config.json '
                 '(e.g. "D:/Games/Roberts Space Industries/StarCitizen")')
    if not os.path.isfile(path):
        return T(f"게임은 찾았지만 키 설정 파일이 아직 없습니다 — 게임 옵션 → 키 설정에서 아무 키나 하나 바꿨다가 되돌리고 게임을 끈 뒤 다시 하세요: {path}",
                 f"Found the game, but the keybinding file doesn't exist yet — in the game's Options → Keybindings change any key "
                 f"(you can change it back), quit the game, then try again: {path}")
    return ""
