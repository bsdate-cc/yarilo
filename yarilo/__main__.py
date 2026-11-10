"""python -m yarilo          - the tray
python -m yarilo probe    - check the monitors over DDC/CI (see yarilo/probe.py)
python -m yarilo chart    - build and open the light chart (with a sensor)
"""
import sys


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "probe":
        from .probe import main as probe
        return probe(args[1:])
    if args and args[0] == "chart":
        from .report import build_and_open
        print(build_and_open())
        return 0
    from .app import main as tray
    tray()
    return 0


sys.exit(main())
