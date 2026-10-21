# © 2026 uglywolf — GPL-3.0
"""받아쓴 글 → 명령 목록. 「체프 체프 플레어」「체골 모드」처럼 조금 틀려도 명령표에 맞춘다.

- 명령 앞에 부르는 이름을 붙이지 않는다(2026-10-21 사용자: 「아톰」 부르기 폐기 — 게임 중엔 디스코드 말고는
  말을 안 한다). 「아톰」 한 마디로 켜고(is_wake), 「아톰 오프」로 끈다(is_off).
  대신 **말 전체가 명령어로만** 이루어졌을 때만 명령으로 본다. 모르는 낱말이 하나라도 섞이면
  대화로 보고 버린다(「미사일 몇 개 남았어」).
- 한글은 자모로 풀어서 비교한다(「체골」과 「채굴」은 자모로 보면 가깝다).
- 앞에서부터 가장 긴 명령어로 끊어 읽는다 → 「채프 채프 플레어」는 명령 셋.
- 한 마디에 명령이 MAX_ACTIONS 개를 넘으면 받아쓰기가 같은 말을 지어내 읊은 것 — 통째로 버린다.
"""
import csv
import difflib
import json
import os
import re

from atom_home import HERE
MATCH = 0.72        # 명령어 하나가 맞았다고 볼 비슷함
MATCH_MULTI = 0.65  # 여러 낱말 조각은 조금 너그럽게(「시드 앱」→「실드 앞」)
SHORT = 2           # 이 글자 수 이하 명령어(아군·타겟)는 짧아서 엉뚱한 말과 잘 닮는다
SHORT_MATCH = 0.75  # 그래서 글자 수가 같고 자모 하나까지만 다를 때(체프→채프) — 「운」이 「아군」으로 간 일(2026-10-21)
NEAR = 0.6         # 말 전체가 한 명령과 이만큼 닮았으면 「다시 말해 주세요」로 되묻는다(nearest)
MAX_ACTIONS = 3     # 「채프 채프 플레어」가 사람이 한 번에 하는 최대. 넘으면 지어낸 것(「경로, 지도, 스타맵, 경로…」)
WAKE = {"ko": "아톰", "en": "atom"}
WAKE_MATCH = 0.6    # 이름은 조금 너그럽게(아톤·아통·다톰)
# whisper 가 「아톰」을 실제로 이렇게 받아썼다(2026-10-21 녹음). 목소리 등록에서 그 사람 버릇을 더 배운다.
WAKE_ALIASES = {"ko": {"아톰", "아톤", "아통", "다톰", "바텀", "액턴", "아토", "아좀", "atom"},
                "en": {"atom", "adam", "atem", "attom", "athim", "atm", "addthem"}}   # 영어 합성음 시험에서 「Atom」이 실제로 이렇게 받아써짐(2026-10-21)
# 오피·오브·오플·종료·총려: 게임 중 「아톰 오프」「아톰 종료」가 실제로 이렇게 받아써졌다(2026-10-21 실사용)
OFF_WORDS = {"ko": {"오프", "오푸", "어프", "오피", "오브", "오플", "꺼", "끄기", "종료", "총려", "off"}, "en": {"off", "of"}}
OFF_ALIASES = {"ko": set(), "en": set()}   # 목소리 등록에서 배운 「아톰 오프」 받아쓰기(붙여 쓴 꼴)
FILLERS = {"ko": {"음", "어", "아", "에", "네", "예", "그", "저", "좀", "자", "막"},
           "en": {"uh", "um", "ah", "er", "the", "please", "okay", "ok"}}

_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"


def jamo(s):
    out = []
    for ch in s:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out += [_CHO[code // 588], _JUNG[code % 588 // 28], _JONG[code % 28].strip()]
        else:
            out.append(ch)
    return "".join(out)


def tokens(text, lang=None):
    """낱말로 나눈다. lang 을 주면 「음」「어」 같은 군말은 뺀다."""
    toks = [t for t in re.split(r"[^0-9a-z가-힣]+", text.lower()) if t]
    if lang:
        toks = [t for t in toks if t not in FILLERS[lang]]
    return toks


def sim(a, b):
    return difflib.SequenceMatcher(None, jamo(a), jamo(b)).ratio()


def length_ok(chunk, phrase):
    """글자 수가 너무 다르면 안 맞는다(「랜딩」이 「랜딩기어」의 앞만 닮은 것). 짧은 명령어는 같아야."""
    if len(phrase) <= SHORT:
        return len(chunk) == len(phrase)
    return abs(len(chunk) - len(phrase)) <= max(1, round(len(phrase) * 0.25))


def strip_wake(toks, lang):
    """옛 버릇대로 앞에 붙인 「아톰」을 뗀다 — 띄어 쓴 것(「아톰 미사일」)도 붙여 쓴 것(「아톰실다」)도."""
    if len(toks) > 1 and (toks[0] in WAKE_ALIASES[lang] or sim(toks[0], WAKE[lang]) >= 0.8):
        return toks[1:]
    if toks:
        for w in sorted(WAKE_ALIASES[lang], key=len, reverse=True):
            if toks[0].startswith(w) and len(toks[0]) - len(w) >= 2:
                return [toks[0][len(w):]] + toks[1:]
    return toks


def is_wake(text, lang):
    """「아톰」 한 마디뿐인가 — 켜고 끄는 스위치. 이름 뒤에 다른 말이 붙으면 아니다."""
    word = "".join(tokens(text, lang))
    return bool(word) and (word in WAKE_ALIASES[lang] or (len(word) <= len(WAKE[lang]) + 1 and sim(word, WAKE[lang]) >= WAKE_MATCH))


def is_off(text, lang):
    """「아톰 오프」인가 — 끄는 말. 붙여 받아쓴 「아톰오프」도 받는다."""
    word = "".join(tokens(text, lang))
    if not word:
        return False
    if word in OFF_ALIASES[lang]:
        return True
    for off in OFF_WORDS[lang]:
        if word.endswith(off) and len(word) > len(off):
            head = word[:-len(off)]
            if head in WAKE_ALIASES[lang] or sim(head, WAKE[lang]) >= WAKE_MATCH:
                return True
    return False


# 명령의 게임 동작을 바꿨을 때 — 예전에 등록한 목소리(배운 말)는 옛 동작 이름을 들고 있다
RENAMED = {"v_set_quantum_mode": "v_master_mode_cycle_long",   # 퀀텀 모드: Alt+F1 → B 길게(2026-10-21)
           "v_set_scan_mode": "v_toggle_scan_mode"}           # 스캔 모드: 보조 키 → 기본 V(2026-10-21)


def load_profile(lang, path):
    """목소리 등록 결과(voice_profile_<말>.json) → 그 사람 전용 [(낱말 목록, 동작)]. 없으면 []."""
    if not os.path.exists(path):
        return [], None
    with open(path, encoding="utf-8") as f:
        prof = json.load(f)
    WAKE_ALIASES[lang].update(w for w in prof.get("wake", []) if w)
    OFF_ALIASES[lang].update(w for w in prof.get("off", []) if w)
    return [(p["말"], RENAMED.get(p["동작"], p["동작"])) for p in prof.get("phrases", [])], prof


def load_phrases(lang, path=os.path.join(HERE, "commands.tsv")):
    """[(낱말 목록, 동작)] — 한 동작에 여러 말(대표·비슷한 말)."""
    # 한국어로 받아쓰라 해도 「Atom Quantum Mode」처럼 영어로 적을 때가 있어 한국어는 영어 말도 받는다
    cols = ("말", "비슷한 말", "영어 말", "영어 비슷한 말") if lang == "ko" else ("영어 말", "영어 비슷한 말")
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["분류"].startswith("#"):       # 꺼 둔 명령(keymap.load_commands 와 같음)
                continue
            for c in cols:
                for p in r[c].split(","):      # 비슷한 말은 쉼표로 여러 개
                    if p.strip():
                        out.append((tokens(p), r["동작"]))
    return out


def parse(text, phrases, lang):
    """받아쓴 글 → [동작…]. 말 전체가 명령어로 채워지지 않으면 [] (대화로 본다)."""
    # 옛 버릇대로 「아톰 미사일」이라 해도 이름은 떼고 읽는다(「아톰미사일」이 「다음 미사일」로 가던 일)
    toks = strip_wake(tokens(text, lang), lang)
    if not toks:
        return []
    actions, i = [], 0
    longest = max(len(p) for p, _ in phrases)
    while i < len(toks):
        best = None
        for n in range(min(longest, len(toks) - i), 0, -1):
            chunk = "".join(toks[i:i + n])
            for words, act in phrases:
                whole = "".join(words)
                # 여러 낱말 조각은 같은 낱말 수의 명령어에만(「체프 플레어」가 「플레어」를 먹지 않게) —
                # 단 한 낱말 명령어를 띄어 받아쓴 것은 받는다(「랜딩 기어」를 랜딩·기어 두 번으로 읽던 일)
                if n > 1 and len(words) != n and not (len(words) == 1 and len(chunk) == len(whole)):
                    continue
                # 붙여 쓴 한 낱말은 명령어보다 짧으면 안 된다(「모드」가 「건 모드」의 끝만 닮은 것)
                if n == 1 and len(words) > 1 and not 0 <= len(chunk) - len(whole) <= 1:
                    continue
                if not length_ok(chunk, whole):
                    continue
                score = sim(chunk, whole)
                need = SHORT_MATCH if len(whole) <= SHORT else (MATCH_MULTI if n > 1 else MATCH)
                if score >= need and (best is None or score > best[0] or (score == best[0] and n > best[2])):
                    best = (score, act, n)
            if best is not None:
                break       # 긴 조각에서 맞았으면 짧은 조각으로 뒤집지 않는다
        if best is None:
            return []       # 명령어가 아닌 낱말이 섞였다 = 대화
        actions.append(best[1])
        i += best[2]
    if len(actions) > MAX_ACTIONS:
        return []
    return actions


def nearest(text, phrases, lang):
    """맞추지 못한 말이 어느 한 명령과 꽤 닮았나 → (동작, 비슷함) 또는 None. 되묻기에 쓴다.
    말 전체를 명령어 하나와 견준다(대화 속 낱말 하나가 닮은 것은 안 본다)."""
    word = "".join(strip_wake(tokens(text, lang), lang))
    if not word:
        return None
    best = None
    for words, act in phrases:
        whole = "".join(words)
        if len(whole) <= SHORT:     # 짧은 명령은 되묻지 않는다 — 대화의 「아니, 아니」가 아군으로 갈 수 있다
            continue
        if abs(len(word) - len(whole)) > 2:
            continue
        score = sim(word, whole)
        if score >= NEAR and (best is None or score > best[1]):
            best = (act, score)
    return best


# 되물은 뒤의 대답(군말 빼기 전 낱말로 본다 — 「네」「어」는 군말이기도 하다)
# 아·음·엉·웅: 게임 중 「응」이 7번 이렇게 받아써져 되묻기가 다 버려졌다(2026-10-21 실사용). 되물은 뒤 6초 안에만 본다
YES = {"ko": {"응", "어", "아", "음", "엉", "웅", "으응", "네", "넵", "넹", "예", "그래", "그래요", "맞아", "맞아요", "맞습니다",
              "오케이", "실행", "해", "해줘", "ㅇㅇ", "yes", "ok", "okay"},
       "en": {"yes", "yeah", "yep", "yup", "correct", "affirmative", "affirm", "roger", "confirm", "do", "ok", "okay", "sure"}}
NO = {"ko": {"아니", "아니야", "아냐", "아니요", "아뇨", "취소", "됐어", "no"},
      "en": {"no", "nope", "negative", "cancel"}}


def is_yes(text, lang):
    toks = tokens(text)       # 받아쓰기가 「아, 아, 아…」처럼 되풀이해도 낱말 종류가 셋 이하면 본다
    return 0 < len(set(toks)) <= 3 and all(t in YES[lang] for t in toks)


def is_no(text, lang):
    toks = tokens(text)
    return 0 < len(toks) <= 3 and toks[0] in NO[lang]


# ── 객관식 판정에 쓸 보기 ────────────────────────────────
def load_choices(lang, path=os.path.join(HERE, "commands.tsv")):
    """[(명령어 글, 동작)] — 받아쓰기 모델에 「이 소리가 이 글인가」를 물을 보기. 띄어쓰기 그대로."""
    cols = ("말", "비슷한 말", "영어 말", "영어 비슷한 말") if lang == "ko" else ("영어 말", "영어 비슷한 말")
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["분류"].startswith("#"):       # 꺼 둔 명령(keymap.load_commands 와 같음)
                continue
            for c in cols:
                for p in r[c].split(","):
                    if p.strip():
                        out.append((p.strip(), r["동작"]))
    return out


def shortlist(text, choices, lang, k=12):
    """받아쓴 글과 닮은 보기 k 개(모델에 다 물으면 느리다). 앞에 「아톰」을 붙여 말했으면 보기에도 붙인다."""
    raw = tokens(text, lang)
    toks = strip_wake(raw, lang)
    word = "".join(toks)
    ranked = sorted(choices, key=lambda c: -sim(word, c[0].replace(" ", "").lower()))[:k]
    if toks != raw:
        name = WAKE[lang] if lang == "ko" else "Atom"
        ranked = [(f"{name} {c}", a) for c, a in ranked]
    return ranked
