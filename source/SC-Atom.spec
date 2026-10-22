# -*- mode: python ; coding: utf-8 -*-
# SC-Atom.exe 묶기 (게임PC, 아톰 venv 에서): venv\Scripts\python.exe -m PyInstaller --noconfirm SC-Atom.spec
# 명령표·목소리·모델·bat 은 묶음 안이 아니라 exe 옆에 둔다(사용자가 고치고, 아톰이 atom_home.HERE 로 찾는다) — tools/make_release.py
import glob
import os

from PyInstaller.utils.hooks import collect_all

datas, binaries, hidden = [], [], []
for pkg in ("vosk", "sounddevice", "_sounddevice_data", "pywhispercpp", "cffi"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h

# pywhispercpp 바퀴는 libwhisper·ggml dll 을 site-packages 맨 위에 「whisper-<해시>.dll」로 둔다.
# stt.py 는 그 libwhisper 를 ctypes 로 직접 부르므로 묶음 맨 위(_internal)에 같이 넣는다.
import pywhispercpp
site = os.path.dirname(os.path.dirname(pywhispercpp.__file__))
for pat in ("whisper-*.dll", "ggml*.dll", "_pywhispercpp*.pyd"):
    binaries += [(f, ".") for f in glob.glob(os.path.join(site, pat))]

hidden += ["atom", "atom_home", "game_path", "i18n", "keymap", "matcher", "mic_pick", "reply", "selftest", "sendkeys",
           "stt", "train", "updater", "vosk_stt", "winsound", "tkinter"]

a = Analysis(
    ["sc_atom.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["torch", "kokoro", "matplotlib", "pandas", "scipy", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SC-Atom", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SC-Atom", upx=False)
