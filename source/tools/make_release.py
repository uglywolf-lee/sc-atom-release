# © 2026 uglywolf — GPL-3.0
"""나눠 줄 SC-Atom 폴더·zip 만들기(게임PC, SC-Atom.spec 으로 묶은 뒤).

  python tools/make_release.py <묶은 dist\\SC-Atom> <모델 폴더> <내놓을 곳> <판 번호>

- exe 옆에: 명령표·대사·교육 내용·기본 키 표·README·LICENSE·고지문, voices\\(wav 만), models\\(tiny·Vosk 영어), bat 다섯
- source\\: 실행에 쓰는 .py 와 묶기 설정만(GPL-3.0 — 받은 사람이 소스를 받을 수 있게). research·녹음·설계 기록은 안 넣는다(2026-10-21 사용자 「2번」)
- atom_config.json 은 넣지 않는다 — 처음 켤 때 기본값으로 만든다(마이크는 mic.bat 으로 고름)
"""
import glob
import os
import shutil
import sys
import zipfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = ["commands.tsv", "lines.tsv", "training_ko.tsv", "training_en.tsv", "default_keys.txt", "README.md", "LICENSE"]
CODE = ["sc_atom.py", "atom.py", "atom_home.py", "game_path.py", "i18n.py", "keymap.py", "matcher.py", "mic_pick.py", "reply.py",
        "selftest.py", "sendkeys.py", "stt.py", "train.py", "updater.py", "vosk_stt.py", "SC-Atom.spec",
        "voices/build_voices.py", "voices/check_voices.py", "tools/make_release.py"]
MODELS = ["ggml-tiny.bin", "vosk-model-small-en-us-0.15"]
BATS = {
    "run_atom.bat": ("SC-Atom", "SC-Atom.exe"),
    "mic.bat": None,                                   # 창만 띄우고 끝(아래에서 따로 씀)
    "train.bat": ("SC-Atom voice training", "SC-Atom.exe train %*"),
    "selftest.bat": ("SC-Atom key test", "SC-Atom.exe selftest %*"),
    "keys.bat": ("SC-Atom keys", "SC-Atom.exe keys %*"),
    "update.bat": None,                                # pause 없이(아래) — 올리는 동안 이 bat 자신도 새 것으로 바뀐다
}
NOTICES = """SC-Atom — 함께 묶인 부품과 라이선스 / Third-party components and licenses

SC-Atom 자체: GPL-3.0 (LICENSE), 소스는 source\\ 폴더 · © 2026 uglywolf

- Python 3.12 — PSF License — https://www.python.org/
- PyInstaller bootloader — GPL-2.0 with bootloader exception — https://pyinstaller.org/
- whisper.cpp / ggml (via pywhispercpp) — MIT — https://github.com/ggml-org/whisper.cpp
- pywhispercpp — MIT — https://github.com/absadiki/pywhispercpp
- Whisper tiny model (ggml-tiny.bin, OpenAI Whisper weights) — MIT — https://github.com/openai/whisper
- Vosk API — Apache-2.0 — https://github.com/alphacep/vosk-api
- Vosk model vosk-model-small-en-us-0.15 — Apache-2.0 — https://alphacephei.com/vosk/models
- NumPy — BSD-3-Clause — https://numpy.org/
- python-sounddevice — MIT — https://github.com/spatialaudio/python-sounddevice
- PortAudio — MIT — http://www.portaudio.com/
- cffi — MIT — https://cffi.readthedocs.io/
- 대답 목소리 voices\\ — Kokoro-82M (Apache-2.0) 로 만든 소리 — https://huggingface.co/hexgrad/Kokoro-82M

Star Citizen 은 Cloud Imperium Games 의 상표입니다. 이 프로그램은 비공식 팬 도구입니다.
"""


def bat(title, line):
    return f"@echo off\r\nchcp 65001 >nul\r\ntitle {title}\r\ncd /d \"%~dp0\"\r\n{line}\r\npause\r\n"


def main(dist, models, out_root, version):
    out = os.path.join(out_root, "SC-Atom")
    if os.path.exists(out):
        raise SystemExit(f"이미 있음: {out}")
    shutil.copytree(dist, out)
    for f in DATA:
        shutil.copy2(os.path.join(SRC, f), out)
    with open(os.path.join(out, "THIRD-PARTY-NOTICES.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(NOTICES)
    with open(os.path.join(out, "VERSION.txt"), "w", encoding="utf-8") as f:
        f.write(version + "\n")
    for d in glob.glob(os.path.join(SRC, "voices", "*", "")):          # voices\<목소리>\cmd|ask|sys\*.wav
        name = os.path.basename(os.path.dirname(d))
        for kind in ("cmd", "ask", "sys"):
            src = os.path.join(d, kind)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(out, "voices", name, kind))
    os.makedirs(os.path.join(out, "models"))
    for m in MODELS:
        p = os.path.join(models, m)
        (shutil.copytree if os.path.isdir(p) else shutil.copy2)(p, os.path.join(out, "models", m))
    for name, spec in BATS.items():
        if spec:
            text = bat(*spec)
        elif name == "update.bat":                     # 묻기·닫기는 SC-Atom.exe update 가 한다
            text = "@echo off\r\nchcp 65001 >nul\r\ntitle SC-Atom update\r\ncd /d \"%~dp0\"\r\nSC-Atom.exe update %*\r\n"
        else:
            text = "@echo off\r\ncd /d \"%~dp0\"\r\nstart \"\" SC-Atom.exe mic\r\n"
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)
    for c in CODE:
        dst = os.path.join(out, "source", c)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(SRC, c), dst)
    z = os.path.join(out_root, f"SC-Atom-{version}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(out):
            for f in files:
                p = os.path.join(root, f)
                zf.write(p, os.path.relpath(p, out_root))
    n = sum(len(f) for _, _, f in os.walk(out))
    print(f"폴더 {out} ({n}개 파일) · zip {z} ({os.path.getsize(z) / 1e6:.1f}MB)")


if __name__ == "__main__":
    main(*sys.argv[1:5])
