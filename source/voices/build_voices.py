# © 2026 uglywolf — GPL-3.0
"""목소리 묶음 만들기: commands.tsv 「대답」 + lines.tsv 를 Kokoro 로 읽히고 AI 효과를 입힌다.

사용(맥, Kokoro 환경): ~/projects/kokoro-tts/venv/bin/python voices/build_voices.py [--missing] [목소리…]
  --missing: 없는 줄만 만든다(명령을 더했을 때)
결과: voices/<목소리>/cmd/<동작>.wav, voices/<목소리>/ask/<동작>.wav(되묻기), voices/<목소리>/sys/<id>.wav
목소리·대사 저작: Kokoro-82M(Apache-2.0) 영국 영어 목소리.
"""
import csv
import os
import subprocess
import sys

import numpy as np
import soundfile as sf
from kokoro import KPipeline

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VOICES = ["bf_lily", "bf_emma", "bm_george", "bm_lewis"]   # 2026-10-21 사용자가 고른 넷
# 「AI」 효과(2026-10-21 사용자 확정): 은은한 겹소리 + 짧은 울림
EFFECT = ("highpass=f=120,lowpass=f=9500,chorus=0.7:0.9:20|32:0.3|0.25:0.5|0.6:2|2.3,"
          "aecho=0.8:0.7:45:0.18,volume=1.2")
RATE = 24000


def lines():
    with open(os.path.join(ROOT, "commands.tsv"), encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            yield "cmd", r["동작"], r["대답"]
    sys.path.insert(0, ROOT)
    from atom import ask_text                # 되묻는 말(「Did you mean quantum mode?」)
    with open(os.path.join(ROOT, "commands.tsv"), encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            yield "ask", r["동작"], ask_text(r)
    with open(os.path.join(ROOT, "lines.tsv"), encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            yield "sys", r["id"], r["대답"]


def main(voices, missing=False):
    pipe = KPipeline(lang_code="b")          # b = 영국 영어
    for v in voices:
        n = 0
        for kind, name, text in lines():
            out = os.path.join(HERE, v, kind, f"{name}.wav")
            if missing and os.path.exists(out):
                continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            audio = np.concatenate([a.numpy() for _, _, a in pipe(text, voice=v, speed=1.0)])
            raw = out + ".raw.wav"
            sf.write(raw, audio, RATE)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", EFFECT, out], check=True)
            os.remove(raw)
            n += 1
        print(f"{v}: {n}줄", flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--missing"]
    main(args or VOICES, missing="--missing" in sys.argv)
