# © 2026 uglywolf — GPL-3.0
"""목소리 묶음 검사: 로컬 whisper 로 받아써서 대사 낱말이 다 들렸는지 본다. 틀린 줄만 보고.

사용(맥, whisper 있는 환경): ~/projects/tts-test/venv/bin/python voices/check_voices.py
결과: voices/check_report.tsv (목소리·종류·이름·대사·들린 말) + 화면엔 목소리별 통과 수
"""
import csv
import difflib
import glob
import os
import re

import whisper

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def texts():
    t = {}
    with open(os.path.join(ROOT, "commands.tsv"), encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            t[("cmd", r["동작"])] = r["대답"]
    with open(os.path.join(ROOT, "lines.tsv"), encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            t[("sys", r["id"])] = r["대답"]
    return t


NUM = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five"}


def words(s):
    s = re.sub(r"[^a-z0-9' ]", " ", s.lower().replace("’", "'"))
    return [NUM.get(x, x).rstrip("s") for x in s.split()]   # 숫자 표기·복수형 차이는 같게 본다


def heard_ok(want, got):
    """대사 낱말이 모두 들렸나 — 철자가 조금 다른 것(gimbals/jimbals)은 맞게 친다."""
    return all(any(difflib.SequenceMatcher(None, x, y).ratio() >= 0.75 for y in got) for x in want)


def main():
    t = texts()
    w = whisper.load_model("small")
    bad = []
    for vdir in sorted(d for d in glob.glob(os.path.join(HERE, "*")) if os.path.isdir(d)):
        v = os.path.basename(vdir)
        ok = total = 0
        for (kind, name), text in t.items():
            path = os.path.join(vdir, kind, f"{name}.wav")
            if not os.path.exists(path):
                continue
            total += 1
            heard = w.transcribe(path, language="en", fp16=False)["text"].strip()
            got = words(heard)
            if heard_ok(words(text), got):
                ok += 1
            else:
                bad.append((v, kind, name, text, heard))
        print(f"{v}: {ok}/{total}", flush=True)
    with open(os.path.join(HERE, "check_report.tsv"), "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, delimiter="\t", lineterminator="\n")
        wr.writerow(["목소리", "종류", "이름", "대사", "들린 말"])
        wr.writerows(bad)
    print(f"틀린 줄 {len(bad)}개 → voices/check_report.tsv")


if __name__ == "__main__":
    main()
