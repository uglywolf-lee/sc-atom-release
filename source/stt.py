# © 2026 uglywolf — GPL-3.0
"""받아쓰기 + 명령 고르기. 보기(명령)가 70개 남짓이라 글을 지어내 맞추지 않고, 받아쓰기 모델에
「이 소리가 정확히 이 명령이고 거기서 끝났을 확률」을 보기마다 물어 고른다(객관식 판정).
whisper.cpp examples/command 의 「명령 목록 모드」를 넓힌 것 — 그쪽은 첫 토큰만 보지만 여기선
명령 끝까지와 끝 토큰까지 본다. 끝 토큰을 넣으니 「미사일 몇 개 남았어」는 「미사일」에서 끝날 확률이
낮아 걸러진다.

2026-10-21 녹음 13개 비교(맥): 받아쓰기→글자 맞추기 약 6/11, 문법 제한(GBNF, research/grammar_stt.py) 8/11,
이 방식 10/11, 대화는 점수 -4.7 로 명령(-0.9~-3.5)과 갈림.

pywhispercpp 는 이 기능을 열어 두지 않아 그 안에 묶여 온 libwhisper(1.8.5)를 ctypes 로 부른다 —
사용자 PC 에 따로 깔 것은 없다. 구조체 배치는 whisper.h v1.8.5 그대로이고 불러올 때 기본값으로 확인한다.
"""
import ctypes as C
import glob
import os

import numpy as np

# ── 라이브러리 찾기 ──────────────────────────────────────
def _lib_path():
    import sys
    import pywhispercpp
    base = os.path.dirname(os.path.dirname(pywhispercpp.__file__))
    if getattr(sys, "frozen", False):             # exe 로 묶였으면 dll 은 묶음 안(_internal/pywhispercpp.libs)에 있다
        base = sys._MEIPASS
    # 윈도우 바퀴는 이름을 「whisper-<해시>.dll」로 바꿔 둔다(delvewheel). pywhispercpp 를 먼저 불러야
    # 그 옆 ggml dll 들을 찾는 경로가 잡힌다(위 import).
    pats = ["libwhisper.dylib", "libwhisper.so*", "whisper.dll", "whisper-*.dll", "**/whisper.dll",
            "**/whisper-*.dll", "**/libwhisper*.so*"]
    for p in pats:
        hits = glob.glob(os.path.join(base, p), recursive=True)
        if hits:
            return hits[0]
    raise FileNotFoundError(f"libwhisper 를 못 찾음: {base}")


# ── whisper.h v1.8.5 구조체 ───────────────────────────────
class Aheads(C.Structure):
    _fields_ = [("n_heads", C.c_size_t), ("heads", C.c_void_p)]


class ContextParams(C.Structure):
    _fields_ = [("use_gpu", C.c_bool), ("flash_attn", C.c_bool), ("gpu_device", C.c_int),
                ("dtw_token_timestamps", C.c_bool), ("dtw_aheads_preset", C.c_int),
                ("dtw_n_top", C.c_int), ("dtw_aheads", Aheads), ("dtw_mem_size", C.c_size_t)]


class VadParams(C.Structure):
    _fields_ = [("threshold", C.c_float), ("min_speech_duration_ms", C.c_int), ("min_silence_duration_ms", C.c_int),
                ("max_speech_duration_s", C.c_float), ("speech_pad_ms", C.c_int), ("samples_overlap", C.c_float)]


class Greedy(C.Structure):
    _fields_ = [("best_of", C.c_int)]


class Beam(C.Structure):
    _fields_ = [("beam_size", C.c_int), ("patience", C.c_float)]


class FullParams(C.Structure):
    _fields_ = [
        ("strategy", C.c_int), ("n_threads", C.c_int), ("n_max_text_ctx", C.c_int),
        ("offset_ms", C.c_int), ("duration_ms", C.c_int),
        ("translate", C.c_bool), ("no_context", C.c_bool), ("no_timestamps", C.c_bool),
        ("single_segment", C.c_bool), ("print_special", C.c_bool), ("print_progress", C.c_bool),
        ("print_realtime", C.c_bool), ("print_timestamps", C.c_bool),
        ("token_timestamps", C.c_bool), ("thold_pt", C.c_float), ("thold_ptsum", C.c_float),
        ("max_len", C.c_int), ("split_on_word", C.c_bool), ("max_tokens", C.c_int),
        ("debug_mode", C.c_bool), ("audio_ctx", C.c_int), ("tdrz_enable", C.c_bool),
        ("suppress_regex", C.c_char_p), ("initial_prompt", C.c_char_p), ("carry_initial_prompt", C.c_bool),
        ("prompt_tokens", C.c_void_p), ("prompt_n_tokens", C.c_int),
        ("language", C.c_char_p), ("detect_language", C.c_bool),
        ("suppress_blank", C.c_bool), ("suppress_nst", C.c_bool),
        ("temperature", C.c_float), ("max_initial_ts", C.c_float), ("length_penalty", C.c_float),
        ("temperature_inc", C.c_float), ("entropy_thold", C.c_float), ("logprob_thold", C.c_float),
        ("no_speech_thold", C.c_float),
        ("greedy", Greedy), ("beam_search", Beam),
        ("new_segment_callback", C.c_void_p), ("new_segment_callback_user_data", C.c_void_p),
        ("progress_callback", C.c_void_p), ("progress_callback_user_data", C.c_void_p),
        ("encoder_begin_callback", C.c_void_p), ("encoder_begin_callback_user_data", C.c_void_p),
        ("abort_callback", C.c_void_p), ("abort_callback_user_data", C.c_void_p),
        ("logits_filter_callback", C.c_void_p), ("logits_filter_callback_user_data", C.c_void_p),
        ("grammar_rules", C.c_void_p), ("n_grammar_rules", C.c_size_t), ("i_start_rule", C.c_size_t),
        ("grammar_penalty", C.c_float),
        ("vad", C.c_bool), ("vad_model_path", C.c_char_p), ("vad_params", VadParams),
    ]



class STT:
    AUTO_PAD = 32               # audio_ctx="auto" 일 때 말 길이에 더하는 여유(1 = 20ms)

    def __init__(self, model_path, language="ko", n_threads=2, audio_ctx=512, use_gpu=False):
        self.lib = C.CDLL(_lib_path())
        L = self.lib
        L.whisper_context_default_params_by_ref.restype = C.POINTER(ContextParams)
        L.whisper_init_from_file_with_params.restype = C.c_void_p
        L.whisper_init_from_file_with_params.argtypes = [C.c_char_p, ContextParams]
        L.whisper_full_default_params_by_ref.restype = C.POINTER(FullParams)
        L.whisper_full_default_params_by_ref.argtypes = [C.c_int]
        L.whisper_full.restype = C.c_int
        L.whisper_full.argtypes = [C.c_void_p, FullParams, C.POINTER(C.c_float), C.c_int]
        L.whisper_full_n_segments.argtypes = [C.c_void_p]
        L.whisper_full_get_segment_text.restype = C.c_char_p
        L.whisper_full_get_segment_text.argtypes = [C.c_void_p, C.c_int]
        L.whisper_token_eot.argtypes = [C.c_void_p]
        L.whisper_free.argtypes = [C.c_void_p]
        L.whisper_decode.argtypes = [C.c_void_p, C.POINTER(C.c_int32), C.c_int, C.c_int, C.c_int]
        L.whisper_get_logits.restype = C.POINTER(C.c_float)
        L.whisper_get_logits.argtypes = [C.c_void_p]
        L.whisper_tokenize.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(C.c_int32), C.c_int]
        L.whisper_n_vocab.argtypes = [C.c_void_p]
        L.whisper_lang_id.argtypes = [C.c_char_p]
        for f in ("whisper_token_sot", "whisper_token_transcribe", "whisper_token_not"):
            getattr(L, f).argtypes = [C.c_void_p]
        L.whisper_token_lang.argtypes = [C.c_void_p, C.c_int]

        cp = L.whisper_context_default_params_by_ref().contents
        cp.use_gpu = use_gpu        # 인텔 맥 AMD 그래픽카드에선 Metal 이 계산을 깬다 — 기본은 CPU
        self.ctx = L.whisper_init_from_file_with_params(model_path.encode(), cp)
        if not self.ctx:
            raise RuntimeError(f"모델을 못 불러옴: {model_path}")
        self.eot = L.whisper_token_eot(self.ctx)
        self.n_vocab = L.whisper_n_vocab(self.ctx)
        self.params = L.whisper_full_default_params_by_ref(0).contents     # 0 = greedy
        self.check_layout(self.params)
        self.lang = language.encode()
        p = self.params
        # audio_ctx: 소리를 몇 칸(1칸 = 20ms)까지 분석하나. "auto" 면 말 길이만큼만 — 명령은 2~3초라
        # 늘 10초(512)를 분석하던 것보다 몇 배 빠르다
        self.ctx_mode = audio_ctx
        p.n_threads, p.audio_ctx, p.language = n_threads, (0 if audio_ctx == "auto" else int(audio_ctx)), self.lang
        p.no_context, p.single_segment, p.no_timestamps = True, True, True
        p.print_progress = p.print_realtime = p.print_timestamps = False
        p.max_tokens, p.temperature, p.temperature_inc = 24, 0.0, 0.0     # 다시 뽑기(온도 올리기) 없음
        self.prefix = [L.whisper_token_sot(self.ctx), L.whisper_token_lang(self.ctx, L.whisper_lang_id(self.lang)),
                       L.whisper_token_transcribe(self.ctx), L.whisper_token_not(self.ctx)]
        self._tok = {}

    @staticmethod
    def check_layout(p):
        """기본값을 읽어 구조체 배치가 라이브러리와 맞는지 본다(어긋나면 엉뚱한 칸에 쓰게 된다)."""
        want = {"strategy": 0, "n_max_text_ctx": 16384, "greedy.best_of": 5, "beam_search.beam_size": -1,
                "grammar_penalty": 100.0, "no_speech_thold": 0.6, "entropy_thold": 2.4, "logprob_thold": -1.0}
        got = {"strategy": p.strategy, "n_max_text_ctx": p.n_max_text_ctx, "greedy.best_of": p.greedy.best_of,
               "beam_search.beam_size": p.beam_search.beam_size, "grammar_penalty": round(p.grammar_penalty, 3),
               "no_speech_thold": round(p.no_speech_thold, 3), "entropy_thold": round(p.entropy_thold, 3),
               "logprob_thold": round(p.logprob_thold, 3)}
        bad = {k: (got[k], v) for k, v in want.items() if got[k] != v}
        if bad:
            raise RuntimeError(f"whisper 구조체 배치가 다름(라이브러리 판이 1.8.5 가 아님?): {bad}")

    def __call__(self, pcm):
        """받아쓰기(문법 없이). 이 소리의 분석(인코더 결과)이 모델 안에 남아 score() 가 쓴다."""
        x = np.ascontiguousarray(pcm, dtype=np.float32)
        if self.ctx_mode == "auto":
            self.params.audio_ctx = min(1500, int(len(x) / 16000 * 50) + self.AUTO_PAD)
        if self.lib.whisper_full(self.ctx, self.params, x.ctypes.data_as(C.POINTER(C.c_float)), len(x)) != 0:
            return ""
        n = self.lib.whisper_full_n_segments(self.ctx)
        return "".join(self.lib.whisper_full_get_segment_text(self.ctx, s).decode("utf-8", "replace")
                       for s in range(n)).strip()

    def tokenize(self, text):
        if text not in self._tok:
            buf = (C.c_int32 * 64)()
            n = self.lib.whisper_tokenize(self.ctx, (" " + text).encode(), buf, 64)
            self._tok[text] = list(buf[:max(n, 0)]) + [self.eot]
        return self._tok[text]

    def _logprobs(self, row=0):
        """마지막 디코드의 row 번째 토큰 뒤 로그 확률. whisper.cpp 는 여러 토큰을 한 번에 넣으면 마지막 줄에만 담는다."""
        n = self.n_vocab
        x = np.ctypeslib.as_array(self.lib.whisper_get_logits(self.ctx), shape=((row + 1) * n,))[row * n:].astype(np.float64)
        x -= x.max()
        return x - np.log(np.exp(x).sum())

    def score(self, candidates):
        """바로 앞 __call__ 의 소리에 대고 → [(후보, 토큰당 평균 로그 확률)] 높은 차례.
        후보들이 앞 토큰을 같이 쓰면 그만큼은 다시 계산하지 않는다."""
        L, ctx, th, n0 = self.lib, self.ctx, self.params.n_threads, len(self.prefix)
        arr = (C.c_int32 * n0)(*self.prefix)
        if L.whisper_decode(ctx, arr, n0, 0, th) != 0:
            return []
        seqs = sorted((self.tokenize(c), c) for c in set(candidates))
        one = (C.c_int32 * 1)()
        path, lps = [], [self._logprobs(n0 - 1)]  # lps[k] = path[:k] 뒤에 올 토큰의 로그 확률
        out = []
        for toks, cand in seqs:
            m = 0
            while m < min(len(path), len(toks)) and path[m] == toks[m]:
                m += 1
            path, lps = path[:m], lps[:m + 1]
            total = 0.0
            for j, tok in enumerate(toks):
                total += lps[j][tok]
                if j >= m and j + 1 < len(toks):
                    one[0] = tok
                    if L.whisper_decode(ctx, one, 1, n0 + j, th) != 0:
                        break
                    path.append(tok)
                    lps.append(self._logprobs())
            out.append((cand, total / len(toks)))
        out.sort(key=lambda x: -x[1])
        return out

    def close(self):
        if self.ctx:
            self.lib.whisper_free(self.ctx)
            self.ctx = None
