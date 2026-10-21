# © 2026 uglywolf — GPL-3.0
"""음성 명령 → 누를 키. 키가 없는 명령엔 보조 키를 채워 넣는다.

- 키는 사람마다 다르다: 게임 기본 키(commands.tsv 「기본 키」) 위에
  그 사람의 actionmaps.xml(바꾼 키만 들어 있음)을 덮어 읽는다.
- actionmaps.xml 의 빈 값(" ")은 기본 키를 지운 것 → 키 없음.
- 보조 키는 사람이 누르지 않고 앱만 누르는 키. 그래서
  · 왼쪽 Alt 조합만 쓴다(왼쪽 Alt 는 혼자 눌러도 게임 동작이 없다.
    왼쪽 Ctrl 은 아래로 이동·엎드리기, 왼쪽 Shift 는 부스트·달리기가 걸린다)
  · 게임 기본 키(default_keys.txt)와 그 사람이 쓰는 키에 하나라도 걸리면 건너뛴다
  · Alt+F4(창 닫기)는 뺀다
- 넣은 키는 keymap_added.json 에 적어 두고, 되돌리기는 그 줄만 지운다.

사용:
  python3 keymap.py show  <actionmaps.xml>     명령마다 누를 키
  python3 keymap.py plan  <actionmaps.xml>     키 없는 명령에 넣을 보조 키(파일 안 바꿈)
  python3 keymap.py apply <actionmaps.xml>     백업 뒤 보조 키를 넣는다(게임을 끄고)
  python3 keymap.py undo  <actionmaps.xml>     앱이 넣은 키만 지운다
"""
import csv
import json
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET

import i18n
from i18n import T

from atom_home import HERE
COMMANDS_TSV = os.path.join(HERE, "commands.tsv")
DEFAULT_KEYS = os.path.join(HERE, "default_keys.txt")
ADDED_JSON = os.path.join(HERE, "keymap_added.json")

# 앞에서부터 쓴다. 전부 게임 기본 단축키(LIVE 4.10.2)에 안 쓰이는 것만 골랐다.
# Alt+F 숫자키는 뺐다 — 게임에서 Alt+F1(퀀텀)·Alt+F11(미사일)을 보내도 거의 안 먹었다(2026-10-21 실사용).
# 걸어 다니며 한 키 시험에서 통과한 수식키 조합은 Alt+글자(Alt+H)다.
SPARE_KEYS = (
    [f"lalt+{c}" for c in "iopuvyz"]
    + [f"lalt+{i}" for i in (5, 6, 7, 8, 9, 0)]
    # 키 이름은 게임 파일에 실제로 나오는 것만(minus·equals 등은 기본 키, insert·home 등은 사용자 키에서 봄)
    + [f"lalt+{k}" for k in ("minus", "equals", "lbracket", "rbracket", "comma", "slash",
                             "insert", "home", "end", "pgup")]
)


def norm(key):
    """「f6+lalt」와 「lalt+f6」을 같은 키로 본다."""
    return "+".join(sorted(p.strip().lower() for p in key.split("+") if p.strip()))


def load_commands(path=COMMANDS_TSV, all_rows=False):
    """명령표. 「분류」가 # 로 시작하는 줄은 꺼 둔 명령(2026-10-21 사용자: 채굴·인양은 처음엔 안 씀) —
    판단 보기·교육·키 채우기에서 모두 빠진다. # 만 지우면 다시 켜진다."""
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    return rows if all_rows else [r for r in rows if not r["분류"].startswith("#")]


def load_default_keys(path=DEFAULT_KEYS):
    with open(path, encoding="utf-8") as f:
        return {norm(l) for l in f if l.strip()}


def read_user(path):
    """actionmaps.xml → ({(묶음, 동작): [키…] 또는 [] (지움)}, 그 사람이 쓰는 키 모음)."""
    binds, used = {}, set()
    for am in ET.parse(path).getroot().iter("actionmap"):
        for a in am.findall("action"):
            keys = None
            for r in a.findall("rebind"):
                inp = r.get("input", "")
                if not inp.startswith("kb"):
                    continue
                keys = keys if keys is not None else []
                k = inp.split("_", 1)[1].strip() if "_" in inp else ""
                if k:
                    keys.append(k)
                    used.add(norm(k))
            if keys is not None:
                binds[(am.get("name"), a.get("name"))] = keys
    return binds, used


def effective(cmd, binds):
    """이 명령에 지금 누를 키(없으면 None)."""
    mine = binds.get((cmd["묶음"], cmd["동작"]))
    if mine is not None:
        return mine[0] if mine else None
    return cmd["기본 키"] or None


def plan(commands, binds, used, default_keys):
    taken = set(default_keys) | set(used)
    spare = [k for k in SPARE_KEYS if norm(k) not in taken]
    out = []
    for c in commands:
        if effective(c, binds) is None:
            if not spare:
                raise RuntimeError("보조 키가 모자람")
            out.append((c, spare.pop(0)))
    return out


def _find_or_add(parent, tag, name):
    for e in parent.findall(tag):
        if e.get("name") == name:
            return e
    return ET.SubElement(parent, tag, {"name": name})


def apply(path, assignments):
    if not assignments:
        return None
    backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, backup)
    tree = ET.parse(path)
    profile = tree.getroot().find("ActionProfiles")
    added = []
    for c, key in assignments:
        am = _find_or_add(profile, "actionmap", c["묶음"])
        act = _find_or_add(am, "action", c["동작"])
        # 키를 지운 빈 줄(" ")이 있으면 그 자리를 채운다
        for r in act.findall("rebind"):
            if r.get("input", "").startswith("kb") and not r.get("input").split("_", 1)[-1].strip():
                act.remove(r)
        ET.SubElement(act, "rebind", {"input": f"kb1_{key}"})
        added.append({"묶음": c["묶음"], "동작": c["동작"], "키": key, "말": c["말"]})
    ET.indent(tree, space=" ")
    tree.write(path, encoding="utf-8", xml_declaration=False)
    # 앞서 넣은 기록이 있으면 이어 붙인다 — 덮어쓰면 undo 가 이번 것만 지운다(2026-10-21 건 모드 더할 때 발견)
    rec = {"file": path, "backup": backup, "added": []}
    if os.path.exists(ADDED_JSON):
        with open(ADDED_JSON, encoding="utf-8") as f:
            old = json.load(f)
        if os.path.normcase(old.get("file", "")) == os.path.normcase(path):
            rec = old
    rec["added"] += added
    with open(ADDED_JSON, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return backup


def undo(path):
    with open(ADDED_JSON, encoding="utf-8") as f:
        rec = json.load(f)
    tree = ET.parse(path)
    profile = tree.getroot().find("ActionProfiles")
    removed = 0
    for a in rec["added"]:
        for am in profile.findall("actionmap"):
            if am.get("name") != a["묶음"]:
                continue
            for act in am.findall("action"):
                if act.get("name") != a["동작"]:
                    continue
                for r in act.findall("rebind"):
                    # 그 사이 사람이 다른 키로 바꿨으면 손대지 않는다
                    if r.get("input") == f"kb1_{a['키']}":
                        act.remove(r)
                        removed += 1
                if not list(act):
                    am.remove(act)
            if not list(am):
                profile.remove(am)
    ET.indent(tree, space=" ")
    tree.write(path, encoding="utf-8", xml_declaration=False)
    os.remove(ADDED_JSON)
    return removed


def main(argv):
    if len(argv) != 3 or argv[1] not in ("show", "plan", "apply", "undo"):
        sys.exit(__doc__)
    cmd, path = argv[1], argv[2]
    try:                                             # 화면 글은 아톰 설정의 말로
        with open(os.path.join(HERE, "atom_config.json"), encoding="utf-8-sig") as f:
            i18n.LANG = json.load(f).get("language", "ko")
    except (OSError, ValueError):
        pass
    commands = load_commands()
    binds, used = read_user(path)
    if cmd == "show":
        for c in commands:
            print(f"{T(c['말'], c['영어 말'])}\t{effective(c, binds) or T('(없음)', '(none)')}")
    elif cmd == "plan":
        for c, key in plan(commands, binds, used, load_default_keys()):
            print(f"{T(c['말'], c['영어 말'])}\t{c['동작']}\t{key}")
    elif cmd == "apply":
        backup = apply(path, plan(commands, binds, used, load_default_keys()))
        print(T(f"백업: {backup}", f"Backup: {backup}") if backup else T("넣을 것 없음", "Nothing to add"))
    else:
        n = undo(path)
        print(T(f"지운 키 {n}개", f"Removed {n} keys"))


if __name__ == "__main__":
    main(sys.argv)
