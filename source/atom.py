# © 2026 uglywolf — GPL-3.0
"""SC-Atom: 「아톰, 퀀텀 모드」라고 말하면 스타시티즌 키를 대신 누르고 짧게 대답한다.

  듣기(마이크, 늘 듣고 말소리만 끊어 냄) → 받아쓰기(whisper.cpp small, CPU)
  → 알아듣기(matcher: 부르는 이름 필수) → 키 보내기(keymap·sendkeys, 따로 도는 줄)
  → 대답(reply.Replier, 키를 보낸 뒤 · 아껴서)

설정은 옆의 atom_config.json(없으면 기본값으로 만든다). 실행: python atom.py
"""
import json
import os
import queue
import sys
import threading
import time

import numpy as np
import sounddevice as sd

import game_path
import i18n
import keymap
import matcher
from i18n import T
import reply
import sendkeys

from atom_home import HERE
CONFIG = os.path.join(HERE, "atom_config.json")
LOG = os.path.join(HERE, "atom_log.txt")
DEFAULTS = {
    "language": "ko",                       # ko 또는 en — 명령을 말하는 말(설정 파일이 없으면 윈도우 표시 언어로 정함)
    "voice": "bf_emma",                     # 대답 목소리(voices/ 아래 폴더 이름)
    "model": os.path.join("models", "ggml-tiny.bin"),  # 보기가 적으면 tiny 가 small 만큼 맞고 5배 빠르다(실제 녹음 97개: 92 대 90)
    "threads": 2,                           # 인식기 코어(게임에 나머지를 남긴다)
    "audio_ctx": 512,                       # 짧은 명령만큼만 처리(아이맥 프로 0.6초)
    "mic": "",                              # 마이크 이름 일부(비우면 기본 마이크)
    "actionmaps": "",                       # 비우면 알아서 찾는다(game_path.py) — 키 파일이나 게임 폴더를 적어도 된다
    "game_window": "Star Citizen",          # 이 이름의 창이 앞에 있을 때만 키를 보낸다
    # 영어는 Vosk(말 목록)가 whisper 보다 낫다(합성음 시험 명령 98% 대 92%, 끄기 6/6 대 2~3/6 — vosk_stt.py 머리말).
    # 모델 폴더가 없거나 vosk 가 안 깔렸으면 whisper 로 듣는다
    "vosk_model": os.path.join("models", "vosk-model-small-en-us-0.15"),
}
REFERENCE = "https://sc.uglywolf.org/atom"   # 명령어 레퍼런스(폰·패드로 보며 익히는 페이지). 설명서는 끝에 -guide
RATE = 16000
BLOCK = 0.05                                # 50ms 씩 읽는다
END_SILENCE = 0.6                           # 이만큼 조용하면 한 마디 끝(「채프, 플레어」 사이 쉼에 안 끊기게)
ASK_WAIT = 6.0                              # 되물은 뒤 이 안에 다시 말하면 그 대답으로 본다
MAX_COMMAND = 3.0                           # 이보다 긴 말은 대화로 보고 버린다(「채프 채프 플레어」 2초 남짓)
MAX_UTTER = 5.0                             # 한 마디 최대 길이


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def system_language():
    """처음 켤 때의 말: 윈도우 표시 언어가 한국어면 ko, 아니면 en — 영어권 사용자가 설정을 안 고쳐도 되게(2026-10-21, 레딧 공개 준비)."""
    if sys.platform == "win32":
        try:
            import ctypes
            return "ko" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x12 else "en"   # 0x12 = LANG_KOREAN
        except Exception:
            pass
    import locale
    return "ko" if (locale.getlocale()[0] or "").lower().startswith("ko") else "en"


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8-sig") as f:   # 메모장이 앞에 BOM 을 붙여도 읽는다(2026-10-21 시험에서 멈춤)
            cfg.update(json.load(f))
    else:
        cfg["language"] = system_language()
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    i18n.LANG = cfg["language"]               # 화면·로그 글도 그 말로
    cfg["actionmaps"], _ = game_path.find(cfg["actionmaps"])   # 설치 자리가 사람마다 다르다
    return cfg


# ── 게임 창이 앞에 있나 ─────────────────────────────────
if sys.platform == "win32":
    import ctypes

    def game_in_front(title):
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return title.lower() in buf.value.lower()
else:
    def game_in_front(title):
        return True                          # 맥 시험: 늘 앞에 있다고 본다


# ── 채팅창이 열려 있나(한글채팅이 알려 준다) ──────────────
# 열린 채팅창에 키를 보내면 글자로 들어간다(2026-10-21 사용자). 게임에 물을 길은 없고, 한글채팅(SC-KoChat)이
# 엔터·Esc·조종 키·한글 모드로 짐작한 것을 이름 붙은 신호로 내보낸다. 한글채팅이 안 떠 있으면 막지 않는다.
CHAT_EVENT = "SC-KoChat-chat-open"
if sys.platform == "win32":
    def chat_open():
        k32 = ctypes.windll.kernel32
        k32.OpenEventW.restype = ctypes.c_void_p
        h = k32.OpenEventW(0x00100000, False, CHAT_EVENT)      # SYNCHRONIZE
        if not h:
            return False
        try:
            return k32.WaitForSingleObject(ctypes.c_void_p(h), 0) == 0
        finally:
            k32.CloseHandle(ctypes.c_void_p(h))
else:
    def chat_open():
        return False


# ── 키 보내기: 따로 도는 줄 하나에서 차례로 ────────────────
class KeySender(threading.Thread):
    def __init__(self, cfg):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.q = queue.Queue()
        self.commands = {c["동작"]: c for c in keymap.load_commands()}
        self.binds, self.mtime = {}, None
        self.reload()

    def reload(self):
        """키 설정 파일이 바뀌었으면 다시 읽는다(게임은 키를 바꾸면 바로 적는다)."""
        path = self.cfg["actionmaps"]
        try:
            m = os.path.getmtime(path)
        except OSError:
            if self.mtime is not False:
                log(T("게임 기본 키로 보냅니다 — ", "Using game default keys — ") + game_path.missing_message(path))
            self.binds, self.mtime = {}, False
            return
        if m != self.mtime:
            self.binds, _ = keymap.read_user(path)
            self.mtime = m
            log(T(f"키 설정 읽음 ({len(self.binds)}개 바뀐 키): {path}", f"Keybindings loaded ({len(self.binds)} changed keys): {path}"))

    def key_for(self, action):
        self.reload()
        return keymap.effective(self.commands[action], self.binds)

    def run(self):
        while True:
            key, c = self.q.get()
            try:
                sendkeys.send(key, c["방식"], c["길게"])
            except Exception as e:          # 한 키가 실패해도 다음 명령은 받는다
                log(T(f"키 보내기 실패 {key}: {e}", f"Failed to send key {key}: {e}"))


def profile_path(lang):
    return os.path.join(HERE, f"voice_profile_{lang}.json")


def stt_prompt(lang):
    """받아쓰기에 미리 알려 주는 말 — 없음. 명령어 목록을 주면 그 목록을 지어내 읊는다
    (2026-10-21 게임 안 「경로, 지도, 스타맵, 경로…」). 명령어는 목소리 등록으로 그 사람 버릇을 배운다."""
    return ""


# ── 받아쓰기 + 명령 고르기 ─────────────────────────────────
ACCEPT = -2.5                               # 보기 점수(토큰당 로그 확률)가 이 위면 바로 실행
ASK = -4.0                                  # 이 위면 「Did you mean …?」 되묻기, 아래면 대화로 보고 무시
MARGIN = 0.15                               # 1·2등이 다른 명령인데 이만큼도 차이가 안 나면 되묻는다
# 게임 소리가 깔리면 점수가 전체로 내려간다 — 2026-10-21 실사용에서 되묻기 21번 중 대부분이 1등 정답이었고 대답은 못 받았다.
# 그래서 2등과 멀찍이 떨어진 1등은 점수가 낮아도 바로 실행한다(교육 녹음 194개: 바로 실행 149→167, 되묻기 27→8, 틀림 1·대화 1)
ACCEPT_FAR = -4.0
MARGIN_FAR = 0.9
# 기준은 사용자 교육 녹음(tiny, 켜진 명령 47개)으로 정함(2026-10-21): -2.5 이상 바로 실행 143/172·틀림 0·대화 0,
# 틀린 1등은 모두 -4.04 아래. 맞은 172개 중 86개는 받아쓰기가 틀렸는데도 소리로 정답을 골랐다.


def make_stt(cfg):
    """언어에 맞는 듣기. 영어는 Vosk(있으면), 한국어는 whisper."""
    if cfg["language"] == "en":
        model = cfg["vosk_model"] if os.path.isabs(cfg["vosk_model"]) else os.path.join(HERE, cfg["vosk_model"])
        if os.path.isdir(model):
            try:
                import vosk_stt
                return vosk_stt.VoskTranscriber(cfg, log)
            except ImportError:
                log("vosk not installed — using whisper")
        else:
            log(f"Vosk model not found ({model}) — using whisper")
    return Transcriber(cfg)


class Transcriber:
    def __init__(self, cfg):
        import stt
        model = cfg["model"] if os.path.isabs(cfg["model"]) else os.path.join(HERE, cfg["model"])
        t = time.time()
        ctx = cfg["audio_ctx"] if cfg["audio_ctx"] == "auto" else int(cfg["audio_ctx"])
        self.stt = stt.STT(model, cfg["language"], int(cfg["threads"]), ctx)
        log(T(f"받아쓰기 모델 준비 {time.time() - t:.1f}초", f"Speech model ready in {time.time() - t:.1f}s"))

    def __call__(self, pcm):
        return self.stt(pcm)

    def rejects(self, text):
        return False                            # whisper 는 choose 의 점수로 거른다

    def choose(self, text, choices, lang):
        """→ (동작, 점수, 보기 글, 2등과의 차이) 또는 None. 바로 앞 __call__ 의 소리로 판정한다."""
        short = matcher.shortlist(text, choices, lang)
        if not short:
            return None
        act_of = dict(short)
        ranked = self.stt.score([c for c, _ in short])
        if not ranked:
            return None
        best, score = ranked[0]
        gap = next((score - v for c, v in ranked[1:] if act_of[c] != act_of[best]), 9.0)
        return act_of[best], score, best, gap


# ── 듣기: 말소리만 끊어 낸다 ──────────────────────────────
SILENT_DB = -90                             # 방 소음이 이보다 낮으면 마이크가 죽은 것(게임PC 기본 마이크 PENTA -97dB, 살아 있는 마이크 -77~-61dB)


def utterances(cfg, with_time=False, on_ready=None):
    """한 마디씩 float32 배열을 내놓는다. 처음 1초로 방 소음을 잰다.
    with_time 이면 (배열, 말 시작 시각) — 목소리 등록이 문장을 띄우기 전 소리를 가려낸다.
    on_ready(방 소음 dB) — 마이크가 죽었으면 알려 줄 곳."""
    device = None
    if cfg["mic"]:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0 and cfg["mic"].lower() in d["name"].lower():
                device = i
                break
        if device is None:
            log(T(f"설정의 마이크 「{cfg['mic']}」 를 못 찾아 기본 마이크로 듣습니다 — mic.bat 으로 다시 고르세요",
                  f"Microphone \"{cfg['mic']}\" not found, using the default one — pick again with mic.bat"))
    blocks = queue.Queue()
    n = int(RATE * BLOCK)
    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=n, device=device,
                        callback=lambda data, *_: blocks.put(data[:, 0].copy())):
        t0 = time.time()
        floor = np.median([np.sqrt(np.mean(blocks.get() ** 2)) for _ in range(int(1 / BLOCK))])
        count = int(1 / BLOCK)                # 지금까지 읽은 블록 수 → 그 소리가 난 시각
        level = max(floor * 4, 0.004)
        floor_db = 20 * np.log10(floor + 1e-9)
        log(T(f"마이크 준비 (방 소음 {floor_db:.0f}dB, 말소리 기준 {20 * np.log10(level):.0f}dB)",
               f"Microphone ready (room noise {floor_db:.0f}dB, speech threshold {20 * np.log10(level):.0f}dB)"))
        if floor_db < SILENT_DB:
            log(T("마이크에서 소리가 안 들어옵니다 — 다른 마이크일 수 있습니다. mic.bat 으로 고르세요",
                   "No sound from the microphone — it may be the wrong one. Pick it with mic.bat"))
        if on_ready:
            on_ready(floor_db)
        buf, quiet, talking = [], 0, False
        pre = []                              # 말 시작 직전 0.2초도 붙인다(첫 소리 잘림 막기)
        while True:
            b = blocks.get()
            count += 1
            loud = np.sqrt(np.mean(b ** 2)) > level
            if not talking:
                pre = (pre + [b])[-4:]
                if loud:
                    talking, buf, quiet = True, list(pre), 0
                    began = t0 + (count - len(pre)) * BLOCK
                continue
            buf.append(b)
            quiet = 0 if loud else quiet + 1
            if quiet * BLOCK >= END_SILENCE or len(buf) * BLOCK >= MAX_UTTER:
                talking = False
                pcm = np.concatenate(buf)
                if len(pcm) > RATE * 0.3:     # 0.3초보다 짧은 건 잡음
                    peak = float(np.abs(pcm).max()) or 1.0
                    pcm = pcm * (0.9 / peak)  # 작은 목소리는 키운다
                    yield (pcm, began) if with_time else pcm


def ask_text(c):
    """되묻는 말 — voices/build_voices.py 도 이것으로 소리를 만든다."""
    return f"Did you mean {c['영어 말'].lower()}?"


def set_title(state):
    """창 제목에 지금 상태 — 작업표시줄에서도 무엇이 도는지 보이게(2026-10-21 사용자: 「수상하게 아무것도 안 뜨면 안 된다」)."""
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(f"SC-Atom — {state}")
        except Exception:
            pass


def already_running():
    """아톰이 이미 떠 있나 — 둘이 뜨면 명령 하나에 키가 두 번 나간다(한글채팅 단추로 켜고 손으로 또 켤 때)."""
    if sys.platform != "win32":
        return False
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    already_running.handle = k32.CreateMutexW(None, False, "SC-Atom-single")   # 프로그램이 끝날 때까지 쥐고 있는다
    return k32.GetLastError() == 183          # ERROR_ALREADY_EXISTS


def main():
    if already_running():
        log(T("아톰이 이미 켜져 있어 이 창은 닫습니다", "Atom is already running — closing this window"))
        time.sleep(3)
        return
    cfg = load_config()
    lang = cfg["language"]
    phrases = matcher.load_phrases(lang)
    choices = matcher.load_choices(lang)
    mine, prof = matcher.load_profile(lang, profile_path(lang))
    if prof is None:
        if lang == "ko":                      # 영어(Vosk)는 말 목록으로 들어서 등록 없이도 잘 알아듣는다
            log(T("목소리 등록 안 됨 — train.bat 을 먼저 하면 훨씬 잘 알아듣습니다", "No voice profile — run train.bat first for much better recognition"))
    else:
        if prof.get("prompt") != stt_prompt(lang) or os.path.basename(prof.get("model", "")) != os.path.basename(cfg["model"]):
            log(T("목소리 등록이 지금 받아쓰기 설정과 다릅니다 — 「train.bat relearn」을 하세요", "Voice profile does not match the current speech model — run \"train.bat relearn\""))
        live = {c["동작"] for c in keymap.load_commands()}
        mine = [(w, a) for w, a in mine if a in live]   # 꺼 두거나 지운 명령(채굴·인양·빔)으로 가는 배운 말은 뺀다
        phrases = mine + phrases          # 그 사람 말을 먼저 본다(같은 점수면 앞의 것)
        log(T(f"목소리 등록 읽음: 배운 말 {len(mine)}개", f"Voice profile loaded: {len(mine)} learned phrases"))
    sender = KeySender(cfg)
    sender.start()
    replier = reply.Replier(cfg["voice"])
    texts = {c["동작"]: c["대답"] for c in keymap.load_commands()}
    asks = {c["동작"]: ask_text(c) for c in keymap.load_commands()}
    stt = make_stt(cfg)
    # 처음엔 대기. 「아톰」으로 켜고 그 뒤로는 명령어만 말한다. 「아톰 오프」로 끈다.
    # 켜진 채 「아톰」을 또 부르면 꺼지지 않고 켜짐 대답만 다시(2026-10-21 사용자)
    active = False
    set_title(T("대기 중 (「아톰」 하면 켜짐)", "standing by (say \"Atom\")"))
    asked = None                            # 되물은 명령과 그 시각 — (동작, 시각)
    replier.say("sys", "ready", "Atom standing by.")
    # 주소는 줄 끝에 둔다(터미널에서 눌러도 뒤 글자가 안 딸려 오게)
    log(T("명령어 목록·설명서 (폰·패드로 보세요): " + REFERENCE, "Command list & guide (open on your phone): " + REFERENCE + "-en"))
    log(T(f"대기 중 — 「{matcher.WAKE[lang]}」 하면 켜지고 「{matcher.WAKE[lang]} 오프」 하면 꺼집니다",
           "Standing by — say \"Atom\" to turn on, \"Atom off\" to turn off"))
    def mic_check(db):
        if db < SILENT_DB:
            replier.say("sys", "mic_silent", "Microphone is silent.")
    for pcm, began in utterances(cfg, with_time=True, on_ready=mic_check):
        if len(pcm) / RATE > MAX_COMMAND:   # 명령은 짧다. 긴 말은 대화 — 받아쓰지도 않는다
            continue
        t = time.time()
        text = stt(pcm)
        took = time.time() - t
        if not text:
            continue
        if replier.is_echo(text):           # 우리 대답이 마이크로 다시 들어온 것
            continue
        if stt.rejects(text):               # Vosk: 목록 밖의 말이 섞인 마디 = 대화
            log(T(f"(무시) {text}  [{took:.2f}초]", f"(ignored) {text}  [{took:.2f}s]"))
            continue
        if matcher.is_off(text, lang):
            if active:
                log(T(f"꺼짐 「{text}」  [{took:.2f}초]", f"Off \"{text}\"  [{took:.2f}s]"))
            active = False
            set_title(T("대기 중 (「아톰」 하면 켜짐)", "standing by (say \"Atom\")"))
            replier.last_spoke = -1e9
            replier.say("sys", "offline", "Voice control offline.")
            continue
        if matcher.is_wake(text, lang):
            if not active:
                log(T(f"켜짐 「{text}」  [{took:.2f}초]", f"On \"{text}\"  [{took:.2f}s]"))
            active = True
            set_title(T("켜짐 — 듣는 중", "ON — listening"))
            replier.last_spoke = -1e9       # 켜짐 대답은 아끼지 않는다(지금 켜져 있는지 확인하는 말)
            replier.say("sys", "online", "Voice control online.")
            continue
        if not active:
            log(T(f"(대기 중이라 무시) {text}  [{took:.2f}초]", f"(standing by, ignored) {text}  [{took:.2f}s]"))
            continue
        # 되물은 참이면: 「응」은 실행, 「아니」는 취소, 그 밖의 말은 아래에서 새 명령으로 읽는다
        confirmed = False                   # 「응」으로 확인한 것은 메아리 검사에서 뺀다
        if asked and time.time() - asked[1] < ASK_WAIT:
            if matcher.is_yes(text, lang):
                actions, confirmed = [asked[0]], True
                log(T(f"(되물어 확인) 「{text}」 → {asked[0]}", f"(confirmed) \"{text}\" -> {asked[0]}"))
                asked = None
            elif matcher.is_no(text, lang):
                log(T(f"(되물음 취소) 「{text}」", f"(cancelled) \"{text}\""))
                asked = None
                continue
            else:
                actions = None
        else:
            asked, actions = None, None
        if actions is None:
            # Vosk(영어)는 글자 그대로 나누고, whisper 는 닮음으로 나눈다
            actions = stt.parse(text, phrases, lang) if hasattr(stt, "parse") else matcher.parse(text, phrases, lang)
            if len(actions) <= 1:
                # 한 명령은 받아쓰기 모델에 보기마다 확률을 물어 고른다(글자 맞추기는 「차게」→타겟을 못 함)
                pick = stt.choose(text, choices, lang)
                actions = []
                if pick:
                    act, score, said, gap = pick
                    # 느슨한 선은 한국어 실사용 로그로 맞춘 것 — 영어(whisper)에서는 대화·「chaff→jump」를 실행시켜 안 쓴다
                    far = lang == "ko" and score >= ACCEPT_FAR and gap >= MARGIN_FAR and not said.lower().startswith(matcher.WAKE[lang])
                    if (score >= ACCEPT and gap >= MARGIN) or far:   # 「아톰 ○○」 꼴은 켜고 끄는 말이 샌 것일 때가 많아 느슨한 선에서 뺀다
                        actions = [act]
                    elif score >= ASK and (act != (asked or (None,))[0]):
                        asked = (act, time.time())
                        log(T(f"(되물음) 「{text}」 — 「{said}」 인가요? {score:.2f}/{gap:.2f}  [{time.time() - t:.2f}초]",
                               f"(asking) \"{text}\" — \"{said}\"? {score:.2f}/{gap:.2f}  [{time.time() - t:.2f}s]"))
                        replier.last_spoke = -1e9
                        replier.say("ask", act, asks.get(act, ""))
                        continue
                    elif score >= ASK:              # 되묻는 중에 같은 명령으로 또 들림 = 그것
                        actions = [act]
                        log(T(f"(다시 말해 확인) 「{text}」 → {act} {score:.2f}", f"(confirmed by repeat) \"{text}\" -> {act} {score:.2f}"))
                    if not actions:
                        log(T(f"(무시) {text} — 「{said}」 {score:.2f}  [{time.time() - t:.2f}초]", f"(ignored) {text} — \"{said}\" {score:.2f}  [{time.time() - t:.2f}s]"))
                        continue
                else:
                    log(T(f"(무시) {text}  [{time.time() - t:.2f}초]", f"(ignored) {text}  [{time.time() - t:.2f}s]"))
                    continue
        if len(actions) == 1 and not confirmed and replier.echo_of(actions[0], began):
            log(T(f"(우리 대답 소리라 무시) {text} → {actions[0]}", f"(our own reply, ignored) {text} -> {actions[0]}"))
            continue
        asked = None
        if chat_open():
            log(T(f"채팅창이 열려 있어 안 보냄: {text}", f"Chat window open — not sent: {text}"))
            replier.say("sys", "chat_open", "Chat window is open.")
            continue
        if not game_in_front(cfg["game_window"]):
            log(T(f"게임 창이 앞에 없음 — 안 보냄: {text}", f"Star Citizen not in front — not sent: {text}"))
            replier.say("sys", "not_focused", "Star Citizen is not in focus.")
            continue
        for a in actions:                   # ① 키 먼저(차례로) ② 대답은 그 뒤에, 아껴서
            key = sender.key_for(a)
            if key is None:
                log(T(f"키 없음: {a}", f"No key bound: {a}"))
                replier.say("sys", "no_key", "That command has no key bound.")
                continue
            sender.q.put((key, sender.commands[a]))
        log(T(f"「{text}」 → {', '.join(actions)}  [{time.time() - t:.2f}초]", f"\"{text}\" -> {', '.join(actions)}  [{time.time() - t:.2f}s]"))
        replier.say("cmd", actions[-1], texts.get(actions[-1], ""))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback
        log(T("오류로 멈춤:\n", "Stopped by an error:\n") + traceback.format_exc())
        raise
