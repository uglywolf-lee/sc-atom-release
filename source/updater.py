# © 2026 uglywolf — GPL-3.0
"""아톰 새 판 확인·올리기 — 한글채팅 없이 혼자 쓰는 사람용(2026-10-22 사용자 「단독은 업데이트 어떻게 하지」).

  켤 때: 깃허브 최신 릴리스 태그와 아톰 폴더의 VERSION.txt 를 견줘 새 판이면 알리고, 창이 있으면 「지금 올릴까요?」를 묻는다
  update.bat (SC-Atom.exe update): 지금 판·새 판을 보여 주고 묻는다. --yes 면 묻지 않음, --restart 면 다 올린 뒤 아톰을 다시 켠다

올리기: zip 을 다 받아 검사(testzip) → 임시 폴더에 풂 → 따로 띄운 창(임시 bat)이 SC-Atom.exe 가 다 꺼지길 기다렸다가
robocopy 로 덮어쓴다(지우는 것 없음). exe 는 자기 자신을 못 바꾸므로 이렇게 나눈다.
zip 에 없는 것(설정·기록·목소리 등록·game_path.txt)은 그대로 남는다. 사용자가 고쳤을 수 있는 명령표 같은 데이터는
새 것과 다르면 덮어쓰기 전에 backup-<옛 판>\\ 에 둔다.
VERSION.txt 가 없으면(.py 로 도는 개발용 폴더) 아무것도 안 한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

import i18n
from atom_home import HERE
from i18n import T

API = "https://api.github.com/repos/uglywolf-lee/sc-atom-release/releases/latest"
PAGE = "https://github.com/uglywolf-lee/sc-atom-release/releases/latest"
VERSION_FILE = os.path.join(HERE, "VERSION.txt")
USER_DATA = ["commands.tsv", "lines.tsv", "training_ko.tsv", "training_en.tsv", "default_keys.txt"]   # 사람이 고칠 수 있는 것
YES = ("y", "yes", "예", "네", "응", "ㅇ", "ㅛ")       # ㅛ = 한글 자판에서 y


def vnum(t):
    return [int(x) for x in re.findall(r"\d+", t or "")] or [0]


def installed():
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def latest():
    """→ (판, zip 주소) 또는 None(인터넷 없음·릴리스 없음)."""
    req = urllib.request.Request(API, headers={"User-Agent": "SC-Atom", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        rel = json.load(r)
    for a in rel.get("assets", []):
        if a["name"].lower().endswith(".zip"):
            return rel["tag_name"].lstrip("v"), a["browser_download_url"]
    return None


def newer():
    """새 판이 있으면 (판, zip 주소). 개발용 폴더·인터넷 없음·최신이면 None."""
    have = installed()
    if not have:
        return None
    try:
        got = latest()
    except Exception:
        return None
    return got if got and vnum(got[0]) > vnum(have) else None


def ask(question):
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        return input(question).strip().lower() in YES
    except (EOFError, KeyboardInterrupt):
        return False


def _download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "SC-Atom"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        total, done, shown = int(r.headers.get("Content-Length") or 0), 0, -1
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            pct = done * 100 // total if total else -1
            if pct // 10 != shown:
                shown = pct // 10
                print(T(f"  받는 중 {pct}%", f"  Downloading {pct}%") if total else f"  {done >> 20}MB", flush=True)


def _backup_user_data(new_dir, old_version):
    """사람이 고쳤을 수 있는 데이터가 새 것과 다르면 옮겨 적어 둔다. → 백업한 파일 이름들."""
    saved = []
    dst = os.path.join(HERE, f"backup-{old_version}")
    for name in USER_DATA:
        mine, theirs = os.path.join(HERE, name), os.path.join(new_dir, name)
        if not (os.path.isfile(mine) and os.path.isfile(theirs)):
            continue
        with open(mine, "rb") as a, open(theirs, "rb") as b:
            if a.read() == b.read():
                continue
        os.makedirs(dst, exist_ok=True)
        shutil.copy2(mine, os.path.join(dst, name))
        saved.append(name)
    return saved, dst


def _helper(src, version, work, restart):
    """아톰이 다 꺼지길 기다렸다가 덮어쓰는 bat. 따로 뜬 창에서 돈다."""
    t = lambda ko, en: T(ko, en).replace("%", "%%")
    lines = [
        "@echo off", "chcp 65001 >nul", "title SC-Atom update",
        f"echo {t('아톰이 꺼지기를 기다립니다…', 'Waiting for Atom to close…')}",
        "set n=0",
        ":wait",
        'tasklist /FI "IMAGENAME eq SC-Atom.exe" /NH | find /I "SC-Atom.exe" >nul',
        "if errorlevel 1 goto copy",
        "set /a n+=1",
        "if %n% GEQ 30 goto busy",
        "timeout /t 1 /nobreak >nul",
        "goto wait",
        ":busy",
        f"echo {t('아톰이 아직 켜져 있습니다 — 아톰 창을 모두 닫고 아무 키나 누르세요', 'Atom is still running — close every Atom window, then press any key')}",
        "pause >nul",
        "set n=0",
        "goto wait",
        ":copy",
        f'robocopy "{src}" "{HERE}" /E /R:3 /W:1 /NFL /NDL /NJH /NJS /NP',
        "if errorlevel 8 goto fail",
        f'rmdir /s /q "{work}"',
        f"echo {t(f'다 됐습니다 — 아톰 {version}', f'Done — Atom {version}')}",
    ]
    if restart:
        lines += [f'start "" /D "{HERE}" "{os.path.join(HERE, "run_atom.bat")}"', "timeout /t 3 /nobreak >nul"]
    else:
        lines += ["timeout /t 8"]
    lines += ['(goto) 2>nul & del "%~f0"',
              ":fail",
              f"echo {t('파일을 못 바꿨습니다 — 아톰 창을 닫고 update.bat 을 다시 하세요. 받은 판: ', 'Could not replace the files — close Atom and run update.bat again. Downloaded copy: ')}{src}",
              "pause"]
    bat = os.path.join(tempfile.gettempdir(), f"sc_atom_update_{int(time.time())}.bat")
    with open(bat, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    return bat


def update(got, restart=False):
    """새 판을 받아 풀고, 덮어쓰는 창을 띄운다. 띄웠으면 True — 부르는 쪽은 곧 끝나야 한다(그래야 파일을 바꾼다)."""
    version, url = got
    work = tempfile.mkdtemp(prefix="sc_atom_update_")
    try:
        z = os.path.join(work, f"SC-Atom-{version}.zip")
        _download(url, z)
        with zipfile.ZipFile(z) as zf:
            bad = zf.testzip()
            if bad:
                raise IOError(T(f"받은 파일이 깨졌습니다: {bad}", f"The download is corrupt: {bad}"))
            zf.extractall(os.path.join(work, "new"))
        os.remove(z)
        src = os.path.join(work, "new", "SC-Atom")
        if not os.path.isfile(os.path.join(src, "SC-Atom.exe")):
            raise IOError(T("받은 zip 에 SC-Atom.exe 가 없습니다", "SC-Atom.exe is missing from the download"))
    except Exception as e:
        shutil.rmtree(work, ignore_errors=True)
        print(T(f"업데이트 실패: {e} — 직접 받기: {PAGE}", f"Update failed: {e} — download it yourself: {PAGE}"))
        return False
    saved, dst = _backup_user_data(src, installed() or "old")
    if saved:
        print(T(f"고친 파일 {len(saved)}개를 옮겨 둠 ({', '.join(saved)}): {dst}",
                f"Saved {len(saved)} edited files ({', '.join(saved)}): {dst}"))
    subprocess.Popen(["cmd", "/c", _helper(src, version, work, restart)], creationflags=subprocess.CREATE_NEW_CONSOLE)
    return True


def check_on_start(log):
    """켤 때 한 번(딴 실): 새 판이면 알리고, 창이 있으면 묻는다. 「예」면 받아서 올리고 아톰을 다시 켠다."""
    got = newer()
    if not got:
        return
    have = installed()
    # 주소는 줄 끝에 둔다(터미널에서 눌러도 뒤 글자가 안 딸려 오게)
    log(T(f"새 판 {got[0]} 이 있습니다(지금 {have}) — update.bat 으로 올리거나 직접 받기: {PAGE}",
          f"Atom {got[0]} is available (you have {have}) — run update.bat or download: {PAGE}"))
    if ask(T(f"지금 {got[0]} 으로 올릴까요? 받은 뒤 아톰이 다시 켜집니다 (y/n): ",
             f"Update to {got[0]} now? Atom will restart afterwards (y/n): ")):
        if update(got, restart=True):
            log(T("새 판으로 바꾸려고 아톰을 끕니다", "Closing Atom to install the new version"))
            os._exit(0)


def main(argv):
    """update.bat — 묻고 올린다."""
    try:                                              # 화면 글은 아톰 설정의 말로
        with open(os.path.join(HERE, "atom_config.json"), encoding="utf-8-sig") as f:
            i18n.LANG = json.load(f).get("language", "ko")
    except (OSError, ValueError):
        pass
    have = installed()

    def done(msg):
        print(msg)
        if sys.stdin and sys.stdin.isatty():
            try:
                input(T("엔터를 누르면 닫힙니다", "Press Enter to close"))
            except (EOFError, KeyboardInterrupt):
                pass

    if not have:
        return done(T("VERSION.txt 가 없는 폴더(개발용)라 업데이트하지 않습니다", "No VERSION.txt here (development folder) — not updating"))
    try:
        got = latest()
    except Exception as e:
        return done(T(f"새 판을 확인하지 못했습니다(인터넷?): {e}", f"Could not check for a new version (internet?): {e}"))
    if not got or vnum(got[0]) <= vnum(have):
        return done(T(f"지금 판 {have} 이 최신입니다", f"You have the latest version ({have})"))
    print(T(f"지금 판 {have} → 새 판 {got[0]}", f"Installed {have} → new {got[0]}"))
    if "--yes" not in argv and not ask(T("올릴까요? 켜져 있는 아톰은 꺼집니다 (y/n): ", "Update now? A running Atom will be closed (y/n): ")):
        return done(T("그만뒀습니다", "Cancelled"))
    if update(got, restart="--restart" in argv):
        print(T("새 창에서 파일을 바꿉니다 — 켜져 있는 아톰 창을 닫아 주세요", "Replacing the files in a new window — please close any running Atom window"))
        time.sleep(2)
