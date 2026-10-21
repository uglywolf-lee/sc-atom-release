# © 2026 uglywolf — GPL-3.0
"""목소리 등록(교육): 그 사람 목소리로 명령을 몇 번씩 말하게 하고, 받아쓰기가 그 사람 말을
어떻게 받아쓰는지 배운다(「미사일」→「비사일 모드」, 「아톰」→「아톤」). 모델을 새로 학습하지 않는다 —
받아쓴 글을 그 사람 전용 비슷한 말로 적어 둘 뿐이라 몇 분이면 끝나고 따로 깔 것이 없다.

  python train.py                 교육 내용 전부(이미 한 것은 건너뜀, 중간에 끊어도 이어서)
  python train.py 전투 채굴        그 분류만(켜기·끄기·이어 말하기·명령 아닌 말은 늘 함께)
  python train.py 다시 12 13       그 번호를 지우고 다시 말하기
  python train.py 다시배우기       녹음은 그대로 두고 지금 받아쓰기 설정으로 다시 받아써 배운다
  python train.py 결과             배운 것을 다시 따져 결과만 보인다
  python train.py 만들기           교육 내용(training_<말>.tsv)을 명령표에서 새로 만든다
  (영어 인자도 된다: make · result · relearn · redo 12 13 · combat mining … — 실행은 train.bat)

녹음은 training/<말>/ 에, 배운 것은 voice_profile_<말>.json 에(둘 다 그 사람 PC 에만).
"""
import csv
import hashlib
import json
import os
import sys
import time
import wave

import numpy as np

import atom
import keymap
import matcher
from i18n import T

HERE = atom.HERE
RETRY = 3                       # 아무것도 못 받아쓰면 다시 말하게 하는 횟수

# 교육 내용에 늘 들어가는 것: 켜기·끄기, 한 번에 여러 명령, 명령이 아닌 대화(명령으로 잡히면 안 됨)
FIXED = {
    "ko": {
        "켜기": [("아톰", "WAKE", 5)],
        "끄기": [("아톰 오프", "OFF", 3)],
        "이어 말하기": [
            ("채프 채프 플레어",
             "v_weapon_countermeasure_noise_launch,v_weapon_countermeasure_noise_launch,v_weapon_countermeasure_decoy_launch", 1),
            ("증가 증가", "v_weapon_increase_max_missiles,v_weapon_increase_max_missiles", 1),
            ("타겟 미사일", "v_target_cycle_in_view_reset,v_set_missile_mode", 1),
        ],
        "명령 아닌 말": [("미사일 몇 개 남았어", "NONE", 1), ("퀀텀 언제 끝나", "NONE", 1),
                     ("채굴하러 가자", "NONE", 1), ("타겟 잡았어", "NONE", 1), ("랜딩기어 내려 줘", "NONE", 1),
                     ("지도 좀 봐 봐", "NONE", 1), ("적 뒤에 있어", "NONE", 1), ("오늘 인양 많이 했다", "NONE", 1)],
    },
    "en": {
        "켜기": [("Atom", "WAKE", 5)],
        "끄기": [("Atom off", "OFF", 3)],
        "이어 말하기": [
            ("chaff chaff flares",
             "v_weapon_countermeasure_noise_launch,v_weapon_countermeasure_noise_launch,v_weapon_countermeasure_decoy_launch", 1),
            ("target, missile mode", "v_target_cycle_in_view_reset,v_set_missile_mode", 1),
        ],
        "명령 아닌 말": [("How many missiles do we have left", "NONE", 1), ("Let's go mining", "NONE", 1),
                     ("Target is locked", "NONE", 1), ("Quantum is almost done", "NONE", 1),
                     ("Hostile behind us", "NONE", 1)],
    },
}
ALWAYS = ("켜기", "끄기", "이어 말하기", "명령 아닌 말")
# 분류 이름은 표 안에서 한국어 그대로 쓰고, 화면과 명령줄에서만 영어로 바꾼다(영어권 사용자 — 2026-10-21)
GROUP_EN = {"켜기": "Wake", "끄기": "Off", "이어 말하기": "Chains", "명령 아닌 말": "Not a command",
            "공통": "General", "전투": "Combat", "방어": "Defense", "채굴": "Mining", "인양": "Salvage"}
ARG_EN = {"make": "만들기", "result": "결과", "relearn": "다시배우기", "redo": "다시", "all": "전부",
          **{v.lower(): k for k, v in GROUP_EN.items()}}


def group_name(g):
    return T(g, GROUP_EN.get(g, g))
REPEAT = 2                      # 명령 하나를 몇 번 말하나


def training_path(lang):
    return os.path.join(HERE, f"training_{lang}.tsv")


def rec_dir(lang):
    return os.path.join(HERE, "training", lang)


def records_path(lang):
    return os.path.join(rec_dir(lang), "records.tsv")


# ── 교육 내용 ───────────────────────────────────────────
def make_training(lang):
    rows = []
    for group in ("켜기", "끄기"):
        for text, want, times in FIXED[lang][group]:
            rows.append((group, text, want, times))
    col = "말" if lang == "ko" else "영어 말"
    for c in keymap.load_commands():
        rows.append((c["분류"], c[col], c["동작"], REPEAT))
    for group in ("이어 말하기", "명령 아닌 말"):
        for text, want, times in FIXED[lang][group]:
            rows.append((group, text, want, times))
    with open(training_path(lang), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["번호", "분류", "말할 문장", "정답", "횟수"])
        for i, r in enumerate(rows, 1):
            w.writerow([i, *r])
    return len(rows)


def load_training(lang):
    if not os.path.exists(training_path(lang)):
        make_training(lang)
    with open(training_path(lang), encoding="utf-8") as f:
        return [dict(r, 번호=int(r["번호"]), 횟수=int(r["횟수"])) for r in csv.DictReader(f, delimiter="\t")]


def wav_name(row, k):
    """녹음 이름은 문장으로 정한다 — 명령을 더해 번호가 밀려도 이미 한 녹음이 그대로 맞는다."""
    return f"{hashlib.sha1(row['말할 문장'].encode('utf-8')).hexdigest()[:10]}_{k}.wav"


def load_records(lang, rows=None):
    if not os.path.exists(records_path(lang)):
        return []
    with open(records_path(lang), encoding="utf-8") as f:
        recs = [dict(r, 번호=int(r["번호"])) for r in csv.DictReader(f, delimiter="\t")]
    if rows:                                       # 번호는 지금 교육 내용 기준으로 다시 매긴다
        now = {wav_name(r, 1)[:10]: r["번호"] for r in rows}
        for r in recs:
            r["번호"] = now.get(r["파일"][:10], r["번호"])
    return recs


def save_records(lang, recs):
    os.makedirs(rec_dir(lang), exist_ok=True)
    with open(records_path(lang), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["파일", "번호", "정답", "받아쓴 글"], delimiter="\t")
        w.writeheader()
        for r in recs:
            w.writerow({k: r[k] for k in ("파일", "번호", "정답", "받아쓴 글")})


def save_wav(path, pcm):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(atom.RATE)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())


def load_wav(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


# ── 배우기 ─────────────────────────────────────────────
BASE_WAKE = {lang: set(v) for lang, v in matcher.WAKE_ALIASES.items()}
BASE_OFF = {lang: set(v) for lang, v in matcher.OFF_ALIASES.items()}


def set_switch(lang, wake=(), off=()):
    matcher.WAKE_ALIASES[lang] = BASE_WAKE[lang] | set(wake)
    matcher.OFF_ALIASES[lang] = BASE_OFF[lang] | set(off)


def learn(recs, lang, base):
    """녹음 받아쓰기 → (켜기 버릇, 끄기 버릇, 그 사람 비슷한 말 [(낱말, 동작)], 겹쳐서 뺀 말)."""
    wake, off, learned = set(), set(), {}            # learned: 붙여 쓴 말 → (낱말, {동작})
    for r in recs:
        want, toks = r["정답"], matcher.tokens(r["받아쓴 글"], lang)
        if not toks:
            continue
        if want == "WAKE":
            if len(toks) <= 2:
                wake.add("".join(toks))
        elif want == "OFF":
            off.add("".join(toks))
        elif want != "NONE" and "," not in want:      # 이어 말하기는 배우지 않고 따져 보기만
            toks = matcher.strip_wake(toks, lang)
            learned.setdefault("".join(toks), (toks, set()))[1].add(want)
    phrases, dropped = [], []
    for key, (words, acts) in learned.items():
        if key in wake or key in off:                  # 켜기·끄기와 똑같이 받아써진 명령은 쓰지 않는다
            dropped.append((" ".join(words), sorted(acts) + ["켜기/끄기"]))
        elif len(acts) == 1:
            phrases.append((words, next(iter(acts))))
        else:
            dropped.append((" ".join(words), sorted(acts)))
    set_switch(lang, wake, off)
    return sorted(wake), sorted(off), phrases, dropped


def expected(want):
    if want == "NONE":
        return []
    return want.split(",")


def judge(text, lang, phrases):
    """atom.py 와 같은 차례: 끄기 → 켜기 → 명령."""
    if matcher.is_off(text, lang):
        return ["OFF"]
    if matcher.is_wake(text, lang):
        return ["WAKE"]
    return matcher.parse(text, phrases, lang)


def check(recs, lang, base):
    """하나씩 빼고 나머지로 배운 뒤 그 하나를 맞혀 본다 = 게임에서 새로 말할 때 맞을 가능성."""
    out = []
    for i, r in enumerate(recs):
        want = [r["정답"]] if r["정답"] in ("WAKE", "OFF") else expected(r["정답"])
        _, _, mine, _ = learn(recs[:i] + recs[i + 1:], lang, base)
        got = judge(r["받아쓴 글"], lang, mine + base)
        set_switch(lang)
        plain = judge(r["받아쓴 글"], lang, base)
        out.append((r, got, got == want, plain == want))
    return out


def report(lang, cfg, quiet=False):
    recs = load_records(lang, load_training(lang))
    if not recs:
        print(T("녹음이 없습니다 — 먼저 교육을 하세요.", "No recordings — run the training first."))
        return []
    base = matcher.load_phrases(lang)
    checked = check(recs, lang, base)
    wake, off, phrases, dropped = learn(recs, lang, base)
    prof = {"lang": lang, "made": time.strftime("%Y-%m-%d %H:%M"), "prompt": atom.stt_prompt(lang),
            "model": cfg["model"], "wake": wake, "off": off,
            "phrases": [{"말": w, "동작": a} for w, a in phrases],
            "dropped": [{"말": w, "동작": a} for w, a in dropped]}
    with open(atom.profile_path(lang), "w", encoding="utf-8") as f:
        json.dump(prof, f, ensure_ascii=False, indent=1)

    names = {c["동작"]: c["말" if lang == "ko" else "영어 말"] for c in keymap.load_commands()}
    names.update({"WAKE": T("켜기(아톰)", "Wake (Atom)"), "OFF": T("끄기(아톰 오프)", "Off (Atom off)"), "NONE": T("무시", "ignore")})
    sw = [x for x in checked if x[0]["정답"] in ("WAKE", "OFF")]
    lines = [T(f"목소리 등록 결과 ({prof['made']}, 녹음 {len(recs)}개)", f"Voice training result ({prof['made']}, {len(recs)} recordings)"), ""]
    cmd = [x for x in checked if x[0]["정답"] not in ("NONE", "WAKE", "OFF")]
    neg = [x for x in checked if x[0]["정답"] == "NONE"]
    lines.append(T(f"명령 맞춤: {sum(x[2] for x in cmd)}/{len(cmd)}   (등록 없이 기본 규칙만: {sum(x[3] for x in cmd)}/{len(cmd)})",
                   f"Commands recognized: {sum(x[2] for x in cmd)}/{len(cmd)}   (without training: {sum(x[3] for x in cmd)}/{len(cmd)})"))
    lines.append(T(f"켜기·끄기 맞춤: {sum(x[2] for x in sw)}/{len(sw)}", f"Wake/off recognized: {sum(x[2] for x in sw)}/{len(sw)}"))
    lines.append(T(f"명령 아닌 말 무시: {sum(x[2] for x in neg)}/{len(neg)}", f"Non-commands ignored: {sum(x[2] for x in neg)}/{len(neg)}"))
    bad = [x for x in sw + cmd if not x[2]]
    if bad:
        lines += ["", T("못 맞춘 것 (번호 — 해야 할 말 → 받아쓴 글 → 알아들은 것):", "Missed (number — what to say -> transcribed -> understood):")]
        for r, got, _, _ in bad:
            lines.append(f"  {r['번호']:>3} {', '.join(names.get(a, a) for a in ([r['정답']] if r['정답'] in names else expected(r['정답'])))}"
                         f" → 「{r['받아쓴 글']}」 → {', '.join(names.get(a, a) for a in got) or T('없음', 'nothing')}")
    wrong_neg = [x for x in neg if not x[2]]
    if wrong_neg:
        lines += ["", T("⚠ 명령이 아닌 말이 명령으로 잡힘(그 말은 게임 중 디스코드에서 조심):", "⚠ Non-command speech taken as a command (careful saying it on Discord while playing):")]
        for r, got, _, _ in wrong_neg:
            lines.append(f"  {r['번호']:>3} 「{r['받아쓴 글']}」 → {', '.join(names.get(a, a) for a in got)}")
    if dropped:
        lines += ["", T("⚠ 두 명령이 똑같이 받아써져서 뺀 말(둘 중 하나를 다른 말로 부르는 게 좋습니다):", "⚠ Dropped: two commands transcribed the same (better to say one of them differently):")]
        for w, acts in dropped:
            lines.append(f"  「{w}」 → {' / '.join(names.get(a, a) for a in acts)}")
    if bad:
        lines += ["", T("못 맞춘 번호는 다시 말해 볼 수 있습니다. 두세 번 해도 안 되면 그 명령은 손으로 누르는 게 낫습니다.", "You can redo the missed numbers. If one still fails after two or three tries, press that key by hand.")]
    text = "\n".join(lines)
    with open(os.path.join(rec_dir(lang), "report.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    if not quiet:
        print(text)
    return sorted({r["번호"] for r, *_ in bad})


# ── 녹음 ───────────────────────────────────────────────
def record(lang, cfg, rows, recs):
    done = {r["파일"] for r in recs}
    todo = []
    for row in rows:
        for k in range(1, row["횟수"] + 1):
            name = wav_name(row, k)
            if name not in done:
                todo.append((row, k, name))
    if not todo:
        print(T("이미 다 했습니다. 결과만 다시 따집니다.", "Already done. Re-checking the result only."))
        return
    total = sum(r["횟수"] for r in rows)
    print(T(f"\n목소리 등록 — {len(todo)}번 말하면 됩니다(전체 {total}). 중간에 창을 닫아도 다음에 이어서 합니다.",
            f"\nVoice training — {len(todo)} lines to say (of {total}). You can close the window and continue later."))
    print(T("게임할 때처럼 평소 목소리로 말하세요. 화면의 문장을 한 번만 말하고, 다음 문장이 뜨면 또 말하면 됩니다.",
            "Speak in your normal in-game voice. Say each line once, then the next one appears."))
    print(T("명령 앞에 「아톰」을 붙이지 마세요 — 「아톰」은 켤 때, 「아톰 오프」는 끌 때만 씁니다.\n",
            "Do not put \"Atom\" before commands — \"Atom\" only turns it on, \"Atom off\" turns it off.\n"))
    stt = atom.make_stt(cfg)
    print(T("마이크 소음 재는 중 — 1초만 조용히 해 주세요…", "Measuring room noise — please stay quiet for a second…"))
    gen = atom.utterances(cfg, with_time=True)
    os.makedirs(rec_dir(lang), exist_ok=True)
    for n, (row, k, name) in enumerate(todo, 1):
        group = row["분류"]
        tip = T("  (디스코드에서 대화하듯 — 명령으로 잡히면 안 되는 말)", "  (say it like chatting on Discord — must NOT become a command)") if group == "명령 아닌 말" else ""
        print(f"[{n}/{len(todo)}] {group_name(group)}{tip}")
        print(f"      ▶  {row['말할 문장']}")
        shown = time.time()
        for _ in range(RETRY):
            pcm, start = next(gen)
            while start < shown - 0.2:             # 문장이 뜨기 전에 시작한 소리(앞 문장 꼬리)는 버린다
                pcm, start = next(gen)
            text = stt(pcm)
            if text:
                break
            print(T("      … 못 들었어요. 다시 한 번 말해 주세요", "      … didn't catch that. Please say it again"))
            shown = time.time()
        save_wav(os.path.join(rec_dir(lang), name), pcm)
        recs.append({"파일": name, "번호": row["번호"], "정답": row["정답"], "받아쓴 글": text})
        save_records(lang, recs)                   # 하나 할 때마다 적는다(끊겨도 이어서)
        print(T(f"      받아씀: 「{text}」\n", f"      heard: \"{text}\"\n"))


def relearn(lang, cfg):
    recs = load_records(lang)
    stt = atom.make_stt(cfg)
    for r in recs:
        r["받아쓴 글"] = stt(load_wav(os.path.join(rec_dir(lang), r["파일"])))
    save_records(lang, recs)


def main(argv):
    cfg = atom.load_config()
    lang = cfg["language"]
    argv = [ARG_EN.get(a.lower(), a) for a in argv]   # 영어로 준 인자(relearn, combat …)도 받는다
    if argv[:1] == ["만들기"]:
        print(T(f"교육 내용 {make_training(lang)}줄 → {training_path(lang)}", f"Training list: {make_training(lang)} lines -> {training_path(lang)}"))
        return
    rows = load_training(lang)
    recs = load_records(lang, rows)
    if argv[:1] == ["결과"]:
        report(lang, cfg)
        return
    if argv[:1] == ["다시배우기"]:
        relearn(lang, cfg)
        report(lang, cfg)
        return
    if argv[:1] == ["다시"]:
        nums = {int(x) for x in argv[1:]}
        for r in [r for r in recs if r["번호"] in nums]:
            try:
                os.remove(os.path.join(rec_dir(lang), r["파일"]))
            except OSError:
                pass
        recs = [r for r in recs if r["번호"] not in nums]
        save_records(lang, recs)
        rows = [r for r in rows if r["번호"] in nums]
    elif argv:
        groups = set(argv)
        unknown = groups - {r["분류"] for r in rows}
        if unknown:
            print(T(f"모르는 분류: {', '.join(unknown)} — 있는 분류: {', '.join(dict.fromkeys(r['분류'] for r in rows))}",
                    f"Unknown group: {', '.join(unknown)} — groups: {', '.join(dict.fromkeys(GROUP_EN.get(r['분류'], r['분류']).lower() for r in rows))}"))
            return
        rows = [r for r in rows if r["분류"] in groups or r["분류"] in ALWAYS]
    try:
        record(lang, cfg, rows, recs)
    except KeyboardInterrupt:
        print(T("\n멈춤 — 여기까지 한 것은 저장했습니다.", "\nStopped — everything so far is saved."))
        report(lang, cfg)
        return
    bad = report(lang, cfg)
    # 두 번 눌러 연 사람도 이어서 고칠 수 있게: 다시 말할 번호를 묻는다
    while bad and sys.stdin.isatty():
        ans = input(T(f"\n다시 말할 번호(띄어서 여러 개, 「전부」는 {' '.join(map(str, bad))}, 그냥 Enter 는 끝): ",
                      f"\nNumbers to redo (space-separated, \"all\" = {' '.join(map(str, bad))}, Enter to finish): ")).strip()
        if not ans:
            break
        nums = bad if ans.lower() in ("전부", "all") else [int(x) for x in ans.split() if x.isdigit()]
        main(["다시", *map(str, nums)])
        return


if __name__ == "__main__":
    main(sys.argv[1:])
