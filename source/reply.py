# © 2026 uglywolf — GPL-3.0
"""대답 소리 틀기. ⚠️ 대답은 동작을 막지 않는다(2026-10-21 사용자 원칙).

- 틀자마자 돌아온다(기다리지 않는다). 키는 이미 보낸 뒤에 부른다.
- 새 대답이 오면 하던 대답은 끊고 바꾼다 — 줄 세우지 않는다.
- 소리 파일이 없거나 틀다 실패해도 조용히 넘어간다(명령은 이미 됐으니까).
- 정신없이 말할 때(「채프 채프 플레어 플레어」) 하나하나 대답하면 망한다 → 대답을 아낀다.
  키는 말할 때마다 다 보내고, 대답만 Replier 가 거른다.
- 자기가 낸 대답을 명령으로 알아들으면 안 된다(「Flares」→ 대답 「Deploying flares」에 flares 가 들어 있다).
  ① 버튼을 누를 때만 듣는다(늘 듣기 없음) ② 버튼을 누르면 하던 대답을 끊는다 — listen_start()
  ③ 그래도 알아들은 말이 방금 낸 대답과 같으면 버린다 — is_echo()
"""
import os
import subprocess
import sys

from atom_home import HERE
VOICES = os.path.join(HERE, "voices")


def wav_seconds(path):
    try:
        import wave
        with wave.open(path) as w:
            return w.getnframes() / w.getframerate()
    except (OSError, EOFError, Exception):
        return 0.0


def path_for(voice, kind, name):
    """kind 는 「cmd」(동작 이름) 또는 「sys」(상황 id)."""
    return os.path.join(VOICES, voice, kind, f"{name}.wav")


if sys.platform == "win32":
    import winsound

    def play(path):
        if not os.path.exists(path):
            return
        try:
            # SND_ASYNC: 바로 돌아오고, 새로 틀면 하던 소리는 저절로 멈춘다
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except RuntimeError:
            pass

    def stop():
        winsound.PlaySound(None, 0)
else:
    _proc = None

    def play(path):
        global _proc
        stop()
        if os.path.exists(path):
            _proc = subprocess.Popen(["afplay", path])

    def stop():
        global _proc
        if _proc and _proc.poll() is None:
            _proc.kill()
        _proc = None


class Replier:
    """대답을 아끼는 문지기.

    - 같은 명령이 SAME_GAP 초 안에 다시 오면 대답하지 않는다.
    - 다른 명령이라도 앞 대답 뒤 BUSY_GAP 초 안이면 대답하지 않는다(앞 대답이 아직 나오는 중).
    """
    SAME_GAP = 3.0
    BUSY_GAP = 1.5

    def __init__(self, voice, clock=None):
        import time
        self.voice = voice
        self.clock = clock or time.monotonic
        self.last_name = None
        self.last_heard = -1e9      # 마지막으로 이 명령을 들은 때(대답 여부와 상관없이)
        self.last_spoke = -1e9      # 마지막으로 대답한 때
        self.last_text = ""         # 마지막으로 낸 대답 글(메아리 거르기용)
        self.last_about = None      # 마지막 대답이 가리킨 동작과 그 소리가 끝나는 벽시계 시각(메아리 거르기용)
        self.until = 0.0

    def listen_start(self):
        """명령 버튼을 눌렀을 때: 사람이 말하려는 참이니 대답을 끊는다(마이크에 섞이지 않게)."""
        stop()

    def is_echo(self, heard, window=4.0):
        """알아들은 말이 방금 우리가 낸 대답과 같으면 True — 그 말은 버린다."""
        if self.clock() - self.last_spoke > window:
            return False
        norm = lambda t: " ".join("".join(c for c in t.lower() if c.isalnum() or c == " ").split())
        h, t = norm(heard), norm(self.last_text)
        # 완전히 같을 때만 — 일부 일치까지 버리면 사람이 일부러 「Flares, Flares」 한 것도 버린다
        return bool(h) and h == t

    def say(self, kind, name, text=""):
        """대답을 틀었으면 True, 아껴서 건너뛰었으면 False. text 는 대답 글(메아리 거르기용)."""
        now = self.clock()
        same = name == self.last_name and now - self.last_heard < self.SAME_GAP
        self.last_name, self.last_heard = name, now
        if same or now - self.last_spoke < self.BUSY_GAP:
            return False
        self.last_spoke, self.last_text = now, text
        path = path_for(self.voice, kind, name)
        import time as _t
        self.last_about = name if kind in ("cmd", "ask") else None
        self.until = _t.time() + wav_seconds(path)
        play(path)
        return True

    def echo_of(self, action, began, tail=0.5):
        """방금 우리가 「퀀텀 모드」를 말했는데(되묻기·대답) 그 소리가 나오는 중이나 막 끝났을 때 시작된 말이
        또 퀀텀 모드로 들렸다면 그건 스피커 소리가 마이크로 들어온 것 — 확인 없이 실행되면 안 된다."""
        return action == self.last_about and began <= self.until + tail


if __name__ == "__main__":
    # 시험: python3 reply.py bf_emma cmd v_master_mode_cycle_long
    import time
    play(path_for(*sys.argv[1:4]))
    time.sleep(3)
