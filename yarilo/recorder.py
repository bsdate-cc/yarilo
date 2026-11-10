"""Light log for later charts: every reading to lux-YYYY-MM-DD.csv, changes to events.csv."""
from datetime import datetime
from pathlib import Path

_SAMPLE_HEADER = "time,lux,monitors,mode"
_EVENT_HEADER = "time,kind,lux,before,after"


def _num(x):
    return "" if x is None else str(round(x, 2))


def _vals(v):
    return "" if not v else "/".join(map(str, v))


class Recorder:
    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def _append(self, name: str, header: str, row: str) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / name
        new = not path.exists()
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            if new:
                f.write(header + "\n")
            f.write(row + "\n")

    def sample(self, when: datetime, lux, monitors, mode: str) -> None:
        row = f"{when:%Y-%m-%dT%H:%M:%S},{_num(lux)},{_vals(monitors)},{mode}"
        self._append(f"lux-{when:%Y-%m-%d}.csv", _SAMPLE_HEADER, row)

    def event(self, when: datetime, kind: str, lux, before, after) -> None:
        row = f"{when:%Y-%m-%dT%H:%M:%S},{kind},{_num(lux)},{_vals(before)},{_vals(after)}"
        self._append("events.csv", _EVENT_HEADER, row)
