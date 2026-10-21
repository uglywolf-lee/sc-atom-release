# © 2026 uglywolf — GPL-3.0
"""마이크 고르기 창. 입력 장치마다 소리 막대가 움직인다 — 말할 때 움직이는 줄을 누르면 atom_config.json 에 적는다.

친구 PC 는 윈도우 기본 마이크가 엉뚱할 수 있다(게임PC 도 기본은 무음 PENTA, 실제는 Revelator — 2026-10-21).
이름을 고르게 하면 모르니 소리로 고르게 한다. 실행: mic.bat (한글채팅 「마이크 고르기」 단추도 이것을 띄운다)
"""
import queue
import tkinter as tk

import numpy as np
import sounddevice as sd

import atom

BG, CARD, FG, DIM, ACCENT, GOOD = "#0a1520", "#13202d", "#e8f4ff", "#7a8fa0", "#00d4ff", "#3ddc84"
FLOOR, TOP = -80.0, -20.0                  # 막대 왼쪽 끝·오른쪽 끝(dB)


def devices():
    """[(번호, 이름)] — 기본 입력 장치와 같은 오디오 방식(MME 등)만. 윈도우는 한 마이크가 방식마다 여러 번 나온다."""
    try:
        api = sd.query_devices(kind="input")["hostapi"]
    except Exception:
        api = None
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and (api is None or d["hostapi"] == api):
            out.append((i, d["name"]))
    return out


class Meter:
    """장치 하나를 열어 두고 최근 소리 크기(dB)를 들고 있는다."""

    def __init__(self, index):
        self.q = queue.Queue()
        self.db = None
        self.stream = None
        try:
            rate = int(sd.query_devices(index)["default_samplerate"])
            self.stream = sd.InputStream(device=index, channels=1, samplerate=rate, dtype="float32",
                                         callback=lambda data, *_: self.q.put(float(np.sqrt(np.mean(data ** 2)))))
            self.stream.start()
        except Exception:
            self.stream = None                 # 못 여는 장치(다른 프로그램이 독점 등) — 「열 수 없음」으로 보인다

    def read(self):
        level = None
        while not self.q.empty():
            level = self.q.get_nowait()
        if level is not None:
            self.db = 20 * np.log10(level + 1e-9)
        return self.db

    def close(self):
        if self.stream:
            try:
                self.stream.close()
            except Exception:
                pass


def main():
    cfg = atom.load_config()
    root = tk.Tk()
    root.title("SC-Atom 마이크 고르기 / Pick microphone")
    root.configure(bg=BG)
    root.resizable(False, False)
    tk.Label(root, text="말해 보세요 — 막대가 움직이는 줄을 누르세요\nSpeak, then click the row whose bar moves",
             bg=BG, fg=FG, font=("맑은 고딕", 11), justify="left").pack(anchor="w", padx=16, pady=(14, 8))
    rows = []
    status = tk.Label(root, text="", bg=BG, fg=GOOD, font=("맑은 고딕", 10))

    def pick(name):
        cfg["mic"] = name
        with open(atom.CONFIG, "w", encoding="utf-8") as f:
            import json
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        for r in rows:
            r["mark"].config(text="●" if r["name"] == name else "")
        status.config(text=f"저장됨 / Saved: {name}  — 아톰을 다시 켜면 적용됩니다 (restart Atom)")

    for index, name in devices():
        f = tk.Frame(root, bg=CARD, cursor="hand2")
        f.pack(fill="x", padx=16, pady=3)
        mark = tk.Label(f, text="●" if cfg["mic"] and cfg["mic"].lower() in name.lower() else "", width=2,
                        bg=CARD, fg=ACCENT, font=("맑은 고딕", 10))
        mark.pack(side="left")
        label = tk.Label(f, text=name, width=42, anchor="w", bg=CARD, fg=FG, font=("맑은 고딕", 10))
        label.pack(side="left", padx=(0, 8), pady=6)
        bar = tk.Canvas(f, width=200, height=14, bg="#06101a", highlightthickness=0)
        bar.pack(side="left", padx=(0, 10))
        db = tk.Label(f, text="", width=10, anchor="e", bg=CARD, fg=DIM, font=("Consolas", 9))
        db.pack(side="left", padx=(0, 8))
        r = {"name": name, "mark": mark, "bar": bar, "db": db, "meter": Meter(index)}
        rows.append(r)
        for w in (f, mark, label, bar, db):
            w.bind("<Button-1>", lambda _e, n=name: pick(n))
    if not rows:
        tk.Label(root, text="입력 장치가 없습니다 / No input device", bg=BG, fg="#ff6b6b").pack(padx=16, pady=8)
    status.pack(anchor="w", padx=16, pady=(8, 4))
    tk.Button(root, text="닫기 / Close", command=root.destroy, bg="#1a2b3a", fg=FG, relief="flat",
              padx=14, pady=4).pack(anchor="e", padx=16, pady=(0, 14))

    def tick():
        for r in rows:
            v = r["meter"].read()
            r["bar"].delete("all")
            if r["meter"].stream is None:
                r["db"].config(text="열 수 없음")
                continue
            if v is None:
                continue
            frac = min(1.0, max(0.0, (v - FLOOR) / (TOP - FLOOR)))
            r["bar"].create_rectangle(0, 0, int(200 * frac), 14, fill=GOOD if v > -50 else ACCENT, width=0)
            r["db"].config(text=f"{v:.0f} dB")
        root.after(80, tick)

    tick()
    try:
        root.mainloop()
    finally:
        for r in rows:
            r["meter"].close()


if __name__ == "__main__":
    main()
