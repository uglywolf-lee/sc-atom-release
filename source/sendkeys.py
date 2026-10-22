# © 2026 uglywolf — GPL-3.0
"""스타시티즌 키 이름(「lalt+f1」「mouse4」「mwheel_down」)을 실제 입력으로 보낸다(윈도우).

- 키보드는 스캔코드로 보낸다. 게임은 키를 물리 자리로 읽으니 가상 키보다 안전하고,
  한국어 배열이어도 자리는 같다.
- 수식키는 차례대로: 수식키 누름 → 키 누름 → 키 뗌 → 수식키 뗌.
- 누르는 시간은 게임 파일(defaultProfile.xml 의 ActivationModes)에 적힌 값을 따른다.
  tap 은 0.25초 안에 떼야 하고, delayed_press 는 0.25초 넘게 눌러야 걸린다.
"""
import sys
import time

# (스캔코드, 확장키 여부)
SCANCODES = {
    "escape": (0x01, False), "1": (0x02, False), "2": (0x03, False), "3": (0x04, False),
    "4": (0x05, False), "5": (0x06, False), "6": (0x07, False), "7": (0x08, False),
    "8": (0x09, False), "9": (0x0A, False), "0": (0x0B, False), "minus": (0x0C, False),
    "equals": (0x0D, False), "backspace": (0x0E, False), "tab": (0x0F, False),
    "q": (0x10, False), "w": (0x11, False), "e": (0x12, False), "r": (0x13, False),
    "t": (0x14, False), "y": (0x15, False), "u": (0x16, False), "i": (0x17, False),
    "o": (0x18, False), "p": (0x19, False), "lbracket": (0x1A, False), "rbracket": (0x1B, False),
    "enter": (0x1C, False), "lctrl": (0x1D, False), "a": (0x1E, False), "s": (0x1F, False),
    "d": (0x20, False), "f": (0x21, False), "g": (0x22, False), "h": (0x23, False),
    "j": (0x24, False), "k": (0x25, False), "l": (0x26, False), "semicolon": (0x27, False),
    "apostrophe": (0x28, False), "grave": (0x29, False), "lshift": (0x2A, False),
    "backslash": (0x2B, False), "z": (0x2C, False), "x": (0x2D, False), "c": (0x2E, False),
    "v": (0x2F, False), "b": (0x30, False), "n": (0x31, False), "m": (0x32, False),
    "comma": (0x33, False), "period": (0x34, False), "slash": (0x35, False),
    "rshift": (0x36, False), "np_multiply": (0x37, False), "lalt": (0x38, False),
    "space": (0x39, False), "capslock": (0x3A, False),
    "f1": (0x3B, False), "f2": (0x3C, False), "f3": (0x3D, False), "f4": (0x3E, False),
    "f5": (0x3F, False), "f6": (0x40, False), "f7": (0x41, False), "f8": (0x42, False),
    "f9": (0x43, False), "f10": (0x44, False), "numlock": (0x45, False),
    "scrolllock": (0x46, False), "np_7": (0x47, False), "np_8": (0x48, False),
    "np_9": (0x49, False), "np_subtract": (0x4A, False), "np_4": (0x4B, False),
    "np_5": (0x4C, False), "np_6": (0x4D, False), "np_add": (0x4E, False),
    "np_1": (0x4F, False), "np_2": (0x50, False), "np_3": (0x51, False),
    "np_0": (0x52, False), "np_period": (0x53, False), "f11": (0x57, False), "f12": (0x58, False),
    "np_enter": (0x1C, True), "rctrl": (0x1D, True), "np_divide": (0x35, True),
    "print": (0x37, True), "ralt": (0x38, True), "pause": (0x45, False),
    "home": (0x47, True), "up": (0x48, True), "pgup": (0x49, True), "left": (0x4B, True),
    "right": (0x4D, True), "end": (0x4F, True), "down": (0x50, True), "pgdn": (0x51, True),
    "insert": (0x52, True), "delete": (0x53, True),
}
MODIFIERS = ("lalt", "ralt", "lctrl", "rctrl", "lshift", "rshift")
# (누를 때, 뗄 때) 마우스 플래그
MOUSE_BUTTONS = {
    "mouse1": (0x0002, 0x0004, 0), "mouse2": (0x0008, 0x0010, 0), "mouse3": (0x0020, 0x0040, 0),
    "mouse4": (0x0080, 0x0100, 1), "mouse5": (0x0080, 0x0100, 2),
}
WHEEL = {"mwheel_up": 120, "mwheel_down": -120}

TAP = 0.1           # tap 은 0.25초(빠른 것은 0.15초) 안에 떼야 한다. 게임이 한 장(30fps 면 0.033초)에
                    # 못 읽고 지나가지 않게 몇 장 걸치게 누른다(2026-10-21 퀀텀 모드 4번에 1번만 먹음 — 0.06초였음)
MARGIN = 0.15       # 길게 누르는 동작은 게임 기준값보다 이만큼 더
DELAYED = {"delayed_press": 0.25, "delayed_press_quicker": 0.15, "delayed_press_medium": 0.5,
           "delayed_press_long": 1.5, "delayed_hold": 0.25, "delayed_hold_long": 1.5,
           "delayed_hold_no_retrigger": 0.15}
BETWEEN = 0.1       # 수식키를 누른 뒤 키까지 — 게임이 Alt 를 먼저 읽어야 Alt+F1 이 F1(모비글라스)로 안 간다


def hold_seconds(mode, hold=""):
    """명령의 방식(commands.tsv 「방식」「길게」)으로 누르고 있을 시간."""
    if hold:
        return float(hold) + MARGIN
    if mode in DELAYED:
        return DELAYED[mode] + MARGIN
    return TAP


def parse(key):
    """「f6+lalt」→ (["lalt"], "f6"). 수식키를 앞으로 모은다."""
    parts = [p.strip().lower() for p in key.split("+") if p.strip()]
    mods = [p for p in parts if p in MODIFIERS]
    main = [p for p in parts if p not in MODIFIERS]
    if not main and len(mods) == 1:     # 「lshift」(부스트)처럼 수식키 하나만 누르는 키
        main, mods = mods, []
    if len(main) != 1:
        raise ValueError(f"키 하나여야 함: {key}")
    k = main[0]
    if k not in SCANCODES and k not in MOUSE_BUTTONS and k not in WHEEL:
        raise ValueError(f"모르는 키 이름: {k}")
    return mods, k


def plan(key, mode="", hold=""):
    """보낼 순서를 (할 일, 이름, 기다림) 목록으로 — 맥에서도 시험할 수 있게 실제 입력과 나눈다."""
    mods, k = parse(key)
    steps = [("down", m, BETWEEN) for m in mods]
    if k in WHEEL:
        steps.append(("wheel", k, BETWEEN))
    else:
        repeat = 2 if mode.startswith("double_tap") else 1
        for i in range(repeat):
            steps.append(("down", k, hold_seconds(mode, hold)))
            steps.append(("up", k, 0.08 if i < repeat - 1 else BETWEEN))
    steps += [("up", m, BETWEEN) for m in reversed(mods)]
    return steps


def send(key, mode="", hold=""):
    run(plan(key, mode, hold))


def run(steps):
    for what, name, wait in steps:
        _emit(what, name)
        time.sleep(wait)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    _SendInput = ctypes.windll.user32.SendInput
    KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x1, 0x2, 0x8
    MOUSEEVENTF_WHEEL = 0x0800
    # 한글채팅(SC-KoChat)이 「자기가 넣은 입력」으로 보고 건너뛰는 표식 'QIME'. 이게 없으면 채팅에 한글로 치는 중
    # 아톰이 누른 V·B 가 한글채팅 후킹에 걸려 글자로 바뀔 수 있다(2026-10-21 같이 켜기 붙이며)
    KOCHAT_MARK = 0x51494D45

    def _send_one(inp):
        if _SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
            raise OSError("SendInput 실패")

    def _emit(what, name):
        if name in WHEEL:
            _send_one(INPUT(0, _U(mi=MOUSEINPUT(0, 0, WHEEL[name] & 0xFFFFFFFF, MOUSEEVENTF_WHEEL, 0, 0))))
        elif name in MOUSE_BUTTONS:
            down, up, xbtn = MOUSE_BUTTONS[name]
            _send_one(INPUT(0, _U(mi=MOUSEINPUT(0, 0, xbtn, down if what == "down" else up, 0, 0))))
        else:
            sc, ext = SCANCODES[name]
            flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if ext else 0) | (KEYEVENTF_KEYUP if what == "up" else 0)
            _send_one(INPUT(1, _U(ki=KEYBDINPUT(0, sc, flags, 0, KOCHAT_MARK))))
    # ── 관리자 권한 차이 ─────────────────────────────────
    # 게임(또는 게임을 띄운 RSI 런처)이 관리자 권한이고 아톰이 아니면 윈도우(UIPI)가 SendInput 을 소리 없이 막는다 —
    # 반환값도 성공이라 기록엔 보낸 것으로 찍힌다(이슈 #1, 2026-10-23: 「아톰은 정상인데 인겜에서 함이 반응을 못 한다」).
    def foreground_pid():
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(ctypes.windll.user32.GetForegroundWindow(), ctypes.byref(pid))
        return pid.value

    def elevated(pid=None):
        """그 프로세스(없으면 아톰 자신)가 관리자 권한으로 도나. 알 수 없으면 None."""
        k32, adv = ctypes.WinDLL("kernel32"), ctypes.WinDLL("advapi32")   # 따로 불러 argtypes 가 남의 호출에 안 번지게
        k32.OpenProcess.restype = k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        proc = k32.GetCurrentProcess() if pid is None else k32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not proc:
            return None
        tok = wintypes.HANDLE()
        try:
            if not adv.OpenProcessToken(proc, 0x0008, ctypes.byref(tok)):                     # TOKEN_QUERY
                return None
            val, got = wintypes.DWORD(), wintypes.DWORD()
            ok = adv.GetTokenInformation(tok, 20, ctypes.byref(val), 4, ctypes.byref(got))     # TokenElevation
            return bool(val.value) if ok else None
        finally:
            if tok:
                k32.CloseHandle(tok)
            if pid is not None:
                k32.CloseHandle(proc)

    def blocked_by_admin():
        """앞에 있는 창(게임)이 관리자 권한이고 아톰은 아니면 True."""
        return elevated(foreground_pid()) is True and elevated() is False
else:
    def _emit(what, name):
        print(f"  {what:5} {name}")

    def foreground_pid():
        return 0

    def blocked_by_admin():
        return False


if __name__ == "__main__":
    # 시험: python3 sendkeys.py lalt+f1 [방식] [길게]
    send(*sys.argv[1:4])
