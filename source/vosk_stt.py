# © 2026 uglywolf — GPL-3.0
"""영어 듣기: Vosk 작은 영어 모델 + 말 목록(문법). 언어가 en 일 때 whisper 대신 쓴다(2026-10-21).

같은 영어 합성음(목소리 6 × 깨끗·잡음 섞음 414개)에서 whisper tiny 는 명령 92%·켜기 3/6·끄기 2~3/6·대화 실행 4~6,
Vosk 는 명령 98%·켜기 5/6·끄기 6/6·대화 실행 0~2 였다. 한국어는 Vosk 작은 모델이 약해서 whisper 그대로.

- 들을 말은 명령표의 영어 말 + 켜기·끄기 + 응·아니. 목록 밖의 말은 「[unk]」로 나오고, 그게 섞인 마디는 대화로 보고 버린다.
- atom.Transcriber 와 같은 모양: stt(소리) → 글, stt.choose(글, …) → (동작, 점수, 보기 글, 차이), stt.rejects(글) → 버릴지.
  점수는 Vosk 낱말 확신도로 만든다 — 확신이 높으면 바로 실행, 중간이면 되묻기, 낮으면 무시(atom 의 ACCEPT·ASK 선에 맞춰).
모델: vosk-model-small-en-us-0.15 (Apache-2.0, 압축 40MB) — models/ 아래.
"""
import json
import os

import numpy as np

import matcher

RUN = 0.7          # 한 명령: 낱말 확신이 모두 이 위면 바로 실행(합성음 시험: 0.5~0.9 사이 거의 같음)
ASK = 0.5          # 이 위면 되묻기
MULTI = 0.9        # 여러 명령을 한 번에(「chaff chaff flares」)는 더 깐깐하게 — 대화 「where is the star map」이 「weapons star map」으로 잡힘


def norm(text):
    return " ".join("".join(ch for ch in text.lower() if ch.isalnum() or ch in " '").split())


def parse_exact(text, phrases):
    """Vosk 는 목록의 말을 글자 그대로 내놓는다 → 닮음(matcher.parse) 대신 똑같은 말로만 나눈다.
    닮음으로 나누면 「target missile mode」의 「target missile」이 「fire missile」을 닮아 먼저 잡히고 「mode」가 남아 버려졌다.
    말 전체를 빈틈없이 덮는 나눔 가운데 조각이 가장 적은 것을 고른다. 못 덮으면 []."""
    toks = matcher.tokens(text)
    table = {}
    for words, act in phrases:
        table.setdefault(tuple(words), act)
    longest = max((len(k) for k in table), default=1)
    best = {0: []}                                  # 앞에서 i 낱말까지 덮는 가장 짧은 동작 목록
    for i in range(len(toks)):
        if i not in best:
            continue
        for n in range(1, min(longest, len(toks) - i) + 1):
            act = table.get(tuple(toks[i:i + n]))
            if act and (i + n not in best or len(best[i]) + 1 < len(best[i + n])):
                best[i + n] = best[i] + [act]
    return best.get(len(toks), [])


class VoskTranscriber:
    def __init__(self, cfg, log=print):
        from vosk import KaldiRecognizer, Model, SetLogLevel
        SetLogLevel(-1)
        from atom_home import HERE
        path = cfg["vosk_model"] if os.path.isabs(cfg["vosk_model"]) else os.path.join(HERE, cfg["vosk_model"])
        self.model = Model(path)
        self.Kaldi = KaldiRecognizer
        self.phrases = matcher.load_phrases("en")
        phrases = {"atom", "atom off"} | matcher.YES["en"] | matcher.NO["en"]
        for words, _ in self.phrases:
            phrases.add(" ".join(words))
        self.grammar = json.dumps(sorted(norm(p) for p in phrases if p) + ["[unk]"])
        self.conf = 0.0
        log(f"Vosk ready ({len(phrases)} phrases)")

    def _recognizer(self):
        """사전에 없는 낱말(mobiglas 등)이 든 말은 Vosk 가 빼면서 마디마다 경고를 찍는다 — 아톰 창이 덮이니 그동안만 stderr 를 막는다."""
        err = os.dup(2)
        null = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null, 2)
            return self.Kaldi(self.model, 16000, self.grammar)
        finally:
            os.dup2(err, 2)
            os.close(null)
            os.close(err)

    def __call__(self, pcm):
        rec = self._recognizer()
        rec.SetWords(True)
        rec.AcceptWaveform((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
        res = json.loads(rec.FinalResult())
        words = res.get("result", [])
        self.conf = min((w["conf"] for w in words), default=0.0)
        return res.get("text", "")

    def rejects(self, text):
        """목록 밖의 말이 섞였거나(대화), 여러 명령인데 확신이 모자라면 버린다."""
        if "[unk]" in text:
            return True
        return len(self.parse(text)) >= 2 and self.conf < MULTI

    def parse(self, text, *_):
        return parse_exact(text, self.phrases)

    def choose(self, text, choices, lang):
        """목록 말 하나와 똑같이 나왔으면 그 명령. 점수는 확신도로 atom 의 선(바로 실행 -2.5, 되묻기 -4.0)에 맞춘다."""
        acts = self.parse(text)
        if len(acts) != 1:
            return None
        score = -1.0 if self.conf >= RUN else (-3.0 if self.conf >= ASK else -9.0)
        return acts[0], score, text, 9.0
