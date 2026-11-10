"""Tray app: a brightness slider for external monitors over DDC/CI, and - with a light
sensor - auto brightness."""
import ctypes
import logging
import os
import socket
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

import pystray

from . import __version__, autostart, config, i18n, icons, report
from .controller import Controller, Settings, base_from, monitor_values, numbered, offsets_for, ramp
from .ddc import Monitors, get_brightness, set_brightness
from .hotkeys import Hotkeys
from .i18n import _
from .recorder import Recorder
from .sensor import SensorClient
from .sun import day_weight, sun_elevation

log = logging.getLogger("yarilo")


def settings_from(cfg: dict) -> Settings:
    return Settings(
        window_s=cfg["window_s"], stale_s=cfg["stale_s"], threshold=cfg["threshold"],
        step=cfg["step"], hold_s=cfg["hold_s"], fast_jump=cfg["fast_jump"],
        fast_hold_s=cfg["fast_hold_s"], min_b=cfg["min"], max_b=cfg["max"],
        manual_pause_s=cfg["manual_pause_min"] * 60,
    )


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class App:
    def __init__(self, cfg_path=config.CONFIG_PATH):
        self.cfg_path = cfg_path
        self.cfg = config.load(cfg_path)
        self._cfg_mtime = self._mtime()
        self.ctl = Controller(settings_from(self.cfg), self.cfg["points_day"], self.cfg["points_night"])
        self.sensor = self._make_sensor()
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.expected: list[int] | None = None   # what we believe the monitors show, in order
        self.numbers: list[int] = []             # their numbers, left to right
        self.last_ok: datetime | None = None     # last answer from the sensor
        self.sensor_down = False
        self.ddc_error = False
        self.rec = Recorder(config.DATA_DIR / "lux")
        self._drag_before = None
        self.popup = None
        self.hotkeys = None
        self.icon = pystray.Icon("yarilo", icons.image("on"), _("Ярило"), self._menu())

    # --- settings file ---
    def _make_sensor(self):
        urls = self.cfg["sensor_urls"]
        return SensorClient(urls, field=self.cfg["sensor_json_field"]) if urls else None

    @property
    def has_sensor(self) -> bool:
        return self.sensor is not None

    def _mtime(self):
        try:
            return os.path.getmtime(self.cfg_path)
        except OSError:
            return None

    def _save(self):
        config.save(self.cfg_path, self.cfg)
        self._cfg_mtime = self._mtime()

    def _reload_if_changed(self):
        m = self._mtime()
        if m == self._cfg_mtime:
            return
        self._cfg_mtime = m
        cfg = config.load(self.cfg_path)
        with self.lock:
            old_keys = self.cfg["hotkeys"]
            self.cfg = cfg
            i18n.set_language(cfg["language"])
            self.ctl.s = settings_from(cfg)
            self.ctl.day_points = [(float(l), int(b)) for l, b in cfg["points_day"]]
            self.ctl.night_points = [(float(l), int(b)) for l, b in cfg["points_night"]]
            self.sensor = self._make_sensor()
            if cfg["hotkeys"] != old_keys:
                self._start_hotkeys()
        log.info("settings reloaded")

    # --- monitors ---
    def _visible(self, mons):
        return numbered(mons, self.cfg["skip_monitors"])

    def _offsets(self, numbers=None):
        return offsets_for(numbers if numbers is not None else self.numbers, self.cfg["monitor_offsets"])

    def _read(self, mons):
        code = self.cfg["vcp_code"]
        return [get_brightness(m, code) for m in mons]

    def _write(self, mons, values) -> bool:
        code = self.cfg["vcp_code"]
        return all([set_brightness(m, v, code) for m, v in zip(mons, values)])

    def monitor_states(self) -> list[tuple[int, int | None]]:
        """(number, brightness or None if it does not answer) for the slider window."""
        with self.lock:
            with Monitors() as all_mons:
                vis = self._visible(all_mons)
                return [(n, v) for (n, _m), v in zip(vis, self._read([m for _n, m in vis]))]

    def sync(self, quiet: bool = False):
        """Take what the monitors show now as the current brightness."""
        with Monitors() as all_mons:
            vis = self._visible(all_mons)
            vals = self._read([m for _n, m in vis])
        if vals and all(v is not None for v in vals):
            self.numbers = [n for n, _m in vis]
            self.expected = vals
            self.ctl.applied = base_from(vals, self._offsets())
            log.info("monitors now: %s", vals)
        elif not quiet:
            log.warning("could not read the monitors: %s", vals)

    def resync_if_unknown(self):
        """After a failed write: read back what the monitors really show."""
        if self.expected is None:
            self.sync(quiet=True)

    def _apply_values(self, values_for, t: float, kind: str, check_buttons: bool, smooth: bool) -> bool:
        """values_for(numbers, current) -> new values; writes them, maybe step by step."""
        with Monitors() as all_mons:
            vis = self._visible(all_mons)
            if not vis:
                return False
            numbers, mons = [n for n, _m in vis], [m for _n, m in vis]
            current = self._read(mons)
            same_set = self.expected is not None and numbers == self.numbers
            if (check_buttons and same_set
                    and any(c is not None and c != e for c, e in zip(current, self.expected))):
                # someone used the monitor buttons: do not fight
                log.info("changed with the monitor buttons: %s -> %s; pause %d min",
                         self.expected, current, self.cfg["manual_pause_min"])
                self._event("joystick", t, self.expected, current)
                self.expected = current
                if all(c is not None for c in current):
                    self.ctl.applied = base_from(current, self._offsets(numbers))
                self.ctl.pause_for_manual(t)
                return False
            values = values_for(numbers, current)
            start = current if all(c is not None for c in current) else None
            steps = ramp(start, values) if (smooth and start) else [values]
            ok = True
            for i, step in enumerate(steps):
                if not self._write(mons, step):
                    ok = False
                    break
                if i < len(steps) - 1:
                    time.sleep(self.cfg["smooth_step_s"])
        before = self.expected if same_set else None
        if ok:
            if kind != "preview":   # dragging writes many times; the release is logged
                lux = self.ctl.smoothed_lux(t)
                log.info("%s: %s -> %s at %s lx", kind, before, values, "?" if lux is None else f"{lux:.1f}")
                self._event(kind, t, before, values)
            self.numbers, self.expected = numbers, values
            self.ctl.applied = base_from(values, self._offsets(numbers))
            self.ddc_error = False
        else:
            # a sleeping monitor may have refused while another took the value:
            # what is on the monitors is unknown now, so it must not count as buttons
            self.expected = None
            if not self.ddc_error:
                log.warning("the monitors did not take %s", values)
            self.ddc_error = True
        return ok

    def _together(self, base: int):
        """A function for _apply_values: the common brightness `base`, with each offset."""
        return lambda numbers, current: monitor_values(base, self._offsets(numbers), count=len(numbers))

    def apply(self, base: int, t: float, by_hand: bool = False) -> bool:
        return self._apply_values(self._together(base), t, "hand" if by_hand else "auto",
                                  check_buttons=not by_hand, smooth=self.cfg["smooth"] and not by_hand)

    # --- by hand: slider, brighter/darker, hotkeys ---
    def _auto_off_by_hand(self, t):
        if self.has_sensor and not self.ctl.user_paused:
            self.ctl.user_paused = True
            log.info("auto brightness off: brightness by hand")
            self._event("off", t, None, None)

    def slider_begin(self):
        with self.lock:
            if self._drag_before is None:
                self._drag_before = list(self.expected) if self.expected else None
            self._auto_off_by_hand(time.monotonic())

    def _one(self, number: int, value: int):
        """A function for _apply_values: this monitor gets `value`, the others keep theirs."""
        def values_for(numbers, current):
            return [value if n == number else (c if c is not None else value) for n, c in zip(numbers, current)]
        return values_for

    def slider_preview(self, value: int, number: int | None = None):
        """While dragging: straight to the monitors. number None - all together."""
        with self.lock:
            fn = self._together(int(value)) if number is None else self._one(number, int(value))
            self._apply_values(fn, time.monotonic(), "preview", False, False)

    def slider_commit(self, value: int, number: int | None = None):
        with self.lock:
            t = time.monotonic()
            before = self._drag_before or self.expected
            self._drag_before = None
            self._auto_off_by_hand(t)
            self.slider_preview(value, number)
            self.ctl.set_by_hand(t, self.ctl.applied if self.ctl.applied is not None else int(value))
            self._event("hand", t, before, self.expected)
        self.refresh()

    def nudge(self, delta: int):
        """Brighter/darker: every monitor by `delta`, each from where it is."""
        with self.lock:
            t = time.monotonic()
            self._auto_off_by_hand(t)
            lo, hi = self.cfg["min"], self.cfg["max"]

            def values_for(numbers, current):
                return [_clamp((c if c is not None else 50) + delta, lo, hi) for c in current]
            self._apply_values(values_for, t, "hand", check_buttons=False, smooth=False)
            if self.ctl.applied is not None:
                self.ctl.set_by_hand(t, self.ctl.applied)
        self.refresh()

    def brighter(self):
        self.nudge(+self.cfg["step"])

    def darker(self):
        self.nudge(-self.cfg["step"])

    def set_linked(self, linked: bool):
        self.cfg["linked"] = bool(linked)
        self._save()

    def _start_hotkeys(self):
        if self.hotkeys is not None:
            self.hotkeys.stop()
            self.hotkeys = None
        specs = {k: v for k, v in self.cfg["hotkeys"].items() if v}
        if specs:
            actions = {"brighter": self.brighter, "darker": self.darker}
            self.hotkeys = Hotkeys(specs, lambda name: actions.get(name, lambda: None)())
            self.hotkeys.start()

    # --- the log ---
    def _event(self, kind, t, before, after):
        if not (self.has_sensor and self.cfg["record_light"]):
            return
        try:
            self.rec.event(datetime.now(), kind, self.ctl.smoothed_lux(t), before, after)
        except OSError:
            log.exception("could not write an event")

    def _mode(self) -> str:
        if self.ctl.user_paused:
            return "off"
        return "hold" if self.ctl.paused_until is not None else "auto"

    # --- loop ---
    def loop(self):
        try:
            with self.lock:
                self.sync()
        except Exception:
            log.exception("first read of the monitors")
        self.refresh()
        while not self.stop.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("error in the loop")
            self.stop.wait(self.cfg["poll_s"])

    def _tick(self):
        self._reload_if_changed()
        if not self.has_sensor:
            return
        lux = self.sensor.read()
        t = time.monotonic()
        with self.lock:
            self._update_sun()
            self.resync_if_unknown()
            if lux is not None:
                self.ctl.add_sample(t, lux)
                self.last_ok = datetime.now()
                if self.sensor_down:
                    log.info("the sensor answers again")
                self.sensor_down = False
            elif not self.sensor_down and self.ctl.smoothed_lux(t) is None:
                self.sensor_down = True
                log.warning("the sensor does not answer: %s", self.sensor.last_error)
            new = self.ctl.decide(t)
            if new is not None:
                self.apply(new, t)
            if self.cfg["record_light"]:
                try:
                    self.rec.sample(datetime.now(), lux, self.expected, self._mode())
                except OSError:
                    log.exception("could not write a reading")
        self.refresh()

    def _update_sun(self):
        loc = self.cfg["location"]
        if not loc:
            self.ctl.day_weight = 1.0
            return
        try:
            elev = sun_elevation(datetime.now().astimezone(), loc["lat"], loc["lon"])
        except Exception:
            log.exception("sun")
            return
        self.ctl.day_weight = day_weight(elev, self.cfg["night_below_deg"], self.cfg["day_above_deg"])

    def _phase(self) -> str | None:
        if not self.cfg["location"]:
            return None
        w = self.ctl.day_weight
        return _("день") if w >= 0.99 else _("ночь") if w <= 0.01 else _("сумерки")

    # --- what the user sees ---
    def _pause_end(self) -> str | None:
        if self.ctl.paused_until is None:
            return None
        left = self.ctl.paused_until - time.monotonic()
        return (datetime.now() + timedelta(seconds=max(0, left))).strftime("%H:%M")

    def status_line(self) -> str:
        if self.expected:
            bright = _("яркость") + " " + " / ".join(map(str, self.expected))
        else:
            bright = _("мониторы не отвечают")
        if not self.has_sensor:
            return bright
        lux = self.ctl.smoothed_lux(time.monotonic())
        if lux is None:
            light = _("датчик не отвечает")
            if self.last_ok:
                light += " " + _("с {time}", time=f"{self.last_ok:%H:%M}")
        else:
            light = _("{lux} лк", lux=f"{lux:.0f}")
            if self._phase():
                light += ", " + self._phase()
        text = f"{light} → {bright}"
        if self.ctl.user_paused:
            text += " · " + _("автояркость выключена")
        elif self._pause_end():
            text += " · " + _("пауза до {time}: меняли кнопками монитора", time=self._pause_end())
        if self.hotkeys is not None and self.hotkeys.failed:
            text += " · " + _("горячая клавиша не работает: {names}", names=", ".join(self.hotkeys.failed))
        return text

    def auto_on(self) -> bool:
        return self.has_sensor and not self.ctl.user_paused and self.ctl.paused_until is None

    def refresh(self):
        self.ctl.is_paused(time.monotonic())   # lets an expired pause end
        state = "on" if (self.auto_on() or not self.has_sensor) else "paused"
        self.icon.icon = icons.image(state, self.has_sensor and self.sensor_down)
        self.icon.title = (_("Ярило") + ": " + self.status_line())[:127]
        self.icon.update_menu()

    # --- menu ---
    def _menu(self):
        item = pystray.MenuItem
        sensor = lambda i: self.has_sensor  # noqa: E731
        return pystray.Menu(
            item(lambda i: self.status_line(), None, enabled=False),
            item(lambda i: _("Яркость…"), self.open_popup, default=True),
            item(lambda i: _("Ярче") + f" +{self.cfg['step']}", self.brighter),
            item(lambda i: _("Темнее") + f" −{self.cfg['step']}", self.darker),
            pystray.Menu.SEPARATOR,
            item(lambda i: _("Автояркость"), self.toggle_auto, checked=lambda i: self.auto_on(), visible=sensor),
            item(lambda i: _("График света"), self.open_report, visible=sensor),
            item(lambda i: _("Открыть страницу датчика"), self.open_sensor_page, visible=sensor),
            item(lambda i: _("Запускать при входе в Windows"), self.toggle_autostart,
                 checked=lambda i: autostart.is_enabled()),
            item(lambda i: _("Открыть настройки"), self.open_config),
            pystray.Menu.SEPARATOR,
            item(lambda i: _("Выход"), self.quit),
        )

    def toggle_auto(self):
        with self.lock:
            t = time.monotonic()
            if self.auto_on():
                self.ctl.user_paused = True
                log.info("auto brightness off")
                self._event("off", t, None, None)
            else:
                self.ctl.user_paused = False
                self.ctl.paused_until = None
                self.sync()                  # hand-made brightness is the new start
                log.info("auto brightness on")
                self._event("on", t, None, None)
        self.refresh()

    def toggle_autostart(self):
        if autostart.is_enabled():
            autostart.disable()
        else:
            autostart.enable()
        self.refresh()

    def open_popup(self):
        if self.popup is not None:
            self.popup.show()

    def open_report(self):
        def work():
            try:
                report.build_and_open(cfg=self.cfg)
            except Exception:
                log.exception("light chart")
        threading.Thread(target=work, name="report", daemon=True).start()

    def open_sensor_page(self):
        page = self.sensor.page() if self.sensor else None
        if not page:
            return
        u = urllib.parse.urlsplit(page)
        try:   # browsers often do not know a router's local names
            page = f"{u.scheme}://{socket.gethostbyname(u.hostname)}{':' + str(u.port) if u.port else ''}/"
        except OSError:
            pass
        webbrowser.open(page)

    def open_config(self):
        if not os.path.exists(self.cfg_path):
            self._save()
        subprocess.Popen(["notepad.exe", str(self.cfg_path)])

    def quit(self):
        log.info("quit")
        self.stop.set()
        if self.hotkeys is not None:
            self.hotkeys.stop()
        if self.popup is not None:
            self.popup.close()
        self.icon.stop()

    def run(self):
        def setup(icon):
            icon.visible = True
            from .popup import Popup
            self.popup = Popup(self)
            self._start_hotkeys()
            threading.Thread(target=self.loop, name="yarilo", daemon=True).start()

        self.icon.run(setup=setup)


def _setup_logging():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    h = RotatingFileHandler(config.DATA_DIR / "yarilo.log", maxBytes=512_000,
                            backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)


def main():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel32.CreateMutexW(None, False, "Local\\yarilo-tray")
    already = ctypes.get_last_error() == 183   # ERROR_ALREADY_EXISTS, read before any other call
    i18n.set_language(config.load()["language"])
    if already:
        ctypes.windll.user32.MessageBoxW(None, _("Ярило уже запущено — значок с солнцем в трее."), _("Ярило"), 0x40)
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # crisp slider window on any scaling
    except (AttributeError, OSError):
        pass
    _setup_logging()
    log.info("start %s", __version__)
    App().run()
    del mutex
