"""Small window with brightness sliders above the tray (left click on the sun)."""
import ctypes
import logging
import queue
import threading
import time
import tkinter as tk
from ctypes import wintypes as W
from tkinter import ttk

from .i18n import _

log = logging.getLogger("yarilo")

_LIGHT = {"bg": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "line": "#e1e0d9", "accent": "#2a78d6"}
_DARK = {"bg": "#1f1f1e", "ink": "#f0efec", "ink2": "#c3c2b7", "line": "#383835", "accent": "#3987e5"}


def _windows_dark() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "SystemUsesLightTheme")[0] == 0
    except OSError:
        return False


def _work_area_at_cursor():
    class MI(ctypes.Structure):
        _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT), ("dwFlags", W.DWORD)]
    u = ctypes.windll.user32
    pt = W.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    u.MonitorFromPoint.restype = W.HMONITOR
    u.MonitorFromPoint.argtypes = [W.POINT, W.DWORD]
    mon = u.MonitorFromPoint(pt, 2)   # MONITOR_DEFAULTTONEAREST
    mi = MI()
    mi.cbSize = ctypes.sizeof(mi)
    u.GetMonitorInfoW(mon, ctypes.byref(mi))
    r = mi.rcWork
    return pt.x, pt.y, r.left, r.top, r.right, r.bottom


class _Writer(threading.Thread):
    """Writes slider values off the window thread; while dragging only the latest one counts."""

    def __init__(self, app):
        super().__init__(name="slider-writer", daemon=True)
        self.app = app
        self.cv = threading.Condition()
        self.preview = None      # (value, number or None)
        self.commit = None

    def put_preview(self, v, number):
        with self.cv:
            self.preview = (v, number)
            self.cv.notify()

    def put_commit(self, v, number):
        with self.cv:
            self.commit, self.preview = (v, number), None
            self.cv.notify()

    def run(self):
        while True:
            with self.cv:
                while self.preview is None and self.commit is None:
                    self.cv.wait()
                p, c = self.preview, self.commit
                self.preview = self.commit = None
            try:
                if c is not None:
                    self.app.slider_commit(*c)
                elif p is not None:
                    self.app.slider_preview(*p)
                    time.sleep(0.15)          # at most ~5 writes a second while dragging
            except Exception:
                log.exception("slider")


class Popup:
    def __init__(self, app):
        self.app = app
        self.q: queue.Queue = queue.Queue()
        self.writer = _Writer(app)
        self.writer.start()
        self.win = None
        self._vars = []          # keeps the Tk variables alive on the window thread
        threading.Thread(target=self._run, name="popup", daemon=True).start()

    # called from any thread
    def show(self):
        self.q.put("show")

    def close(self):
        self.q.put("quit")

    # window thread
    def _run(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.after(100, self._poll)
        self.root.mainloop()

    def _poll(self):
        try:
            while True:
                cmd = self.q.get_nowait()
                if cmd == "show":
                    self._open()
                elif cmd == "quit":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _close_win(self, *_args):
        if self.win is not None:
            self.win.destroy()
            self.win = None
            self._vars = []

    def _slider(self, parent, c, label, value, number, lo, hi):
        """One labelled slider; number None = all monitors together. Returns a refresh function."""
        row = tk.Frame(parent, bg=c["bg"])
        row.pack(fill="x", pady=(4, 0))
        head = tk.Frame(row, bg=c["bg"])
        head.pack(fill="x")
        tk.Label(head, text=label, bg=c["bg"], fg=c["ink2"], font=("Segoe UI", 9)).pack(side="left")
        shown = tk.Label(head, bg=c["bg"], fg=c["ink"], font=("Segoe UI", 10))
        shown.pack(side="right")
        if value is None:
            tk.Label(row, text=_("не отвечает по DDC/CI"), bg=c["bg"], fg=c["ink2"],
                     font=("Segoe UI", 9), anchor="w").pack(fill="x")
            return lambda _get=None: None
        var = tk.DoubleVar(value=value)
        self._vars.append(var)
        dragging = {"on": False}

        def current():
            v = int(round(var.get()))
            shown.config(text=str(v))
            return v

        def on_move(_e):
            v = current()
            if dragging["on"]:
                self.writer.put_preview(v, number)

        def on_press(_e):
            dragging["on"] = True
            self.app.slider_begin()

        def on_release(_e):
            dragging["on"] = False
            self.writer.put_commit(current(), number)

        def on_key(e):
            step = 1 if e.keysym in ("Right", "Up") else -1
            var.set(max(lo, min(hi, int(round(var.get())) + step)))
            self.app.slider_begin()
            self.writer.put_commit(current(), number)
            return "break"

        scale = ttk.Scale(row, from_=lo, to=hi, orient="horizontal", length=300, variable=var,
                          command=on_move, style="Yarilo.Horizontal.TScale")
        scale.pack(fill="x")
        scale.bind("<ButtonPress-1>", on_press)
        scale.bind("<ButtonRelease-1>", on_release)
        for k in ("<Left>", "<Right>", "<Up>", "<Down>"):
            scale.bind(k, on_key)   # on the scale itself: "break" stops its own step as well
        current()

        def refresh(get_value):
            v = get_value()
            if not dragging["on"] and v is not None and v != int(round(var.get())) and not self.writer.preview:
                var.set(v)
                current()
        scale.focus_set()
        return refresh

    def _open(self):
        self._close_win()
        app = self.app
        c = _DARK if _windows_dark() else _LIGHT
        lo, hi = app.cfg["min"], app.cfg["max"]
        states = app.monitor_states()
        w = self.win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=c["line"])
        style = ttk.Style(w)
        style.theme_use("clam")
        style.configure("Yarilo.Horizontal.TScale", background=c["accent"], troughcolor=c["line"],
                        bordercolor=c["line"], lightcolor=c["accent"], darkcolor=c["accent"])
        style.layout("Yarilo.Horizontal.TScale", [("Horizontal.Scale.trough", {"sticky": "nswe", "children": [
            ("Horizontal.Scale.slider", {"side": "left", "sticky": ""})]})])   # no dotted focus ring
        body = tk.Frame(w, bg=c["bg"], padx=16, pady=12)
        body.pack(padx=1, pady=1)
        tk.Label(body, text=_("Яркость"), bg=c["bg"], fg=c["ink"],
                 font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        status = tk.Label(body, bg=c["bg"], fg=c["ink2"], font=("Segoe UI", 9), anchor="w", justify="left",
                          wraplength=300)
        status.pack(fill="x", pady=(2, 4))

        refreshers = []
        answering = [(n, v) for n, v in states if v is not None]
        if app.cfg["linked"] or len(states) < 2:
            base = app.ctl.applied if app.ctl.applied is not None else (answering[0][1] if answering else None)
            label = _("Все мониторы") if len(states) > 1 else _("Монитор {n}", n=states[0][0]) if states else ""
            r = self._slider(body, c, label, base, None, lo, hi)
            refreshers.append(lambda: r(lambda: app.ctl.applied))
        else:
            for n, v in states:
                r = self._slider(body, c, _("Монитор {n}", n=n), v, n, lo, hi)

                def value_of(n=n):
                    if app.expected and n in app.numbers:
                        return app.expected[app.numbers.index(n)]
                    return None
                refreshers.append(lambda r=r, value_of=value_of: r(value_of))

        def check(text, value, command):
            var = tk.BooleanVar(value=value)
            self._vars.append(var)
            tk.Checkbutton(body, text=text, variable=var, command=lambda: command(var), bg=c["bg"], fg=c["ink"],
                           activebackground=c["bg"], activeforeground=c["ink"], selectcolor=c["bg"],
                           font=("Segoe UI", 10), anchor="w").pack(fill="x")
            return var

        if len(states) > 1:
            def on_linked(var):
                app.set_linked(var.get())
                w.after(10, self._open)       # rebuild with one or several sliders
            check(_("Вместе"), app.cfg["linked"], on_linked)
        auto = None
        if app.has_sensor:
            def on_auto(var):
                app.toggle_auto()
                var.set(app.auto_on())
            auto = check(_("Автояркость"), app.auto_on(), on_auto)
            tk.Label(body, text=_("Ползунок выключает автояркость; вернуть — галочкой"),
                     bg=c["bg"], fg=c["ink2"], font=("Segoe UI", 8), anchor="w").pack(fill="x")

        def tick():
            if self.win is not w:
                return
            status.config(text=app.status_line())
            for r in refreshers:
                r()
            if auto is not None:
                auto.set(app.auto_on())
            w.after(700, tick)
        tick()

        w.update_idletasks()
        cx, cy, left, top, right, bottom = _work_area_at_cursor()
        ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
        x = max(left + 8, min(cx - ww // 2, right - ww - 8))
        y = bottom - wh - 8 if cy > (top + bottom) / 2 else top + 8
        w.geometry(f"+{x}+{y}")
        w.bind("<Escape>", self._close_win)
        w.bind("<FocusOut>", lambda e: w.after(150, self._close_if_unfocused, w))
        w.focus_force()

    def _close_if_unfocused(self, w):
        try:
            focused = w.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if self.win is w and focused is None:
            self._close_win()
