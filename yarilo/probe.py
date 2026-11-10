"""DDC/CI check of every monitor, for a person or an agent:

    python -m yarilo probe                  # what each monitor answers; writes back the same value
    python -m yarilo probe --set 40         # 40 % on every monitor (or --monitor 2)
    python -m yarilo probe --vcp 0x6B       # try another VCP code instead of 0x10
    python -m yarilo probe --json           # the same as JSON
"""
import argparse
import json
import re
import sys
import time

from . import config
from .controller import numbered
from .ddc import Monitors, capabilities, get_vcp, set_vcp, vcp_codes

HINT_NO_DDC = ("no DDC/CI answer: turn DDC/CI on in the monitor's own menu, try another cable or port "
               "(docks, KVMs and some USB-C/HDMI adapters do not pass DDC/CI), or this is a laptop panel")


def _ms(t0):
    return round((time.perf_counter() - t0) * 1000)


def check(m, code: int, set_to=None, caps=True) -> dict:
    out = {"device": m.device, "left": m.left, "top": m.top, "size": f"{m.width}x{m.height}",
           "windows_name": m.description, "vcp_code": f"0x{code:02X}"}
    t0 = time.perf_counter()
    got = get_vcp(m, code)
    out["read_ms"] = _ms(t0)
    if got is None:
        out["answers"] = False
        out["hint"] = HINT_NO_DDC
    else:
        cur, mx = got
        out.update(answers=True, current=cur, maximum=mx)
        value = cur if set_to is None else round(set_to * mx / 100)
        t0 = time.perf_counter()
        ok = set_vcp(m, code, value)
        out["write"] = {"value": value, "ok": ok, "ms": _ms(t0)}
        time.sleep(0.2)
        back = get_vcp(m, code)
        out["write"]["read_back"] = None if back is None else back[0]
    if caps:
        t0 = time.perf_counter()
        s = capabilities(m)
        out["capabilities_ms"] = _ms(t0)
        out["capabilities"] = s
        if s:
            model = re.search(r"model\(([^)]*)\)", s)
            mccs = re.search(r"mccs_ver\(([^)]*)\)", s)
            out["model"] = model.group(1) if model else None
            out["mccs_version"] = mccs.group(1) if mccs else None
            codes = vcp_codes(s)
            out["vcp_codes"] = [f"{c:02X}" for c in codes]
            out["lists_brightness_0x10"] = 0x10 in codes
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m yarilo probe", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", type=int, metavar="PERCENT", help="write this brightness instead of the same one")
    ap.add_argument("--monitor", type=int, metavar="N", help="only monitor N (left to right from 1)")
    ap.add_argument("--vcp", type=lambda s: int(s, 0), metavar="CODE", help="VCP code, default from settings (0x10)")
    ap.add_argument("--no-caps", action="store_true", help="skip the capabilities string (it is slow)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    cfg = config.load()
    code = a.vcp if a.vcp is not None else cfg["vcp_code"]
    results = []
    with Monitors() as mons:
        for n, m in numbered(mons, []):
            if a.monitor and n != a.monitor:
                continue
            r = {"number": n, "skipped_in_settings": n in cfg["skip_monitors"]}
            r.update(check(m, code, a.set, caps=not a.no_caps))
            results.append(r)
    report = {"settings_file": str(config.CONFIG_PATH), "vcp_code": f"0x{code:02X}",
              "monitor_offsets": cfg["monitor_offsets"], "skip_monitors": cfg["skip_monitors"],
              "monitors": results}
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"Yarilo probe - DDC/CI, VCP 0x{code:02X}; settings: {config.CONFIG_PATH}")
    if not results:
        print("No monitors found.")
    for r in results:
        print(f"\nMonitor {r['number']}: {r['device']} at x={r['left']} y={r['top']}, {r['size']}, "
              f"Windows calls it \"{r['windows_name']}\"" + ("  [skip_monitors]" if r["skipped_in_settings"] else ""))
        if not r["answers"]:
            print(f"  {r['hint']}")
        else:
            w = r["write"]
            print(f"  brightness: {r['current']} of {r['maximum']} (read {r['read_ms']} ms)")
            print(f"  write {w['value']}: {'OK' if w['ok'] else 'FAILED'} ({w['ms']} ms), reads back {w['read_back']}")
        if "capabilities" in r:
            if r["capabilities"]:
                print(f"  model {r.get('model')}, MCCS {r.get('mccs_version')}, "
                      f"lists 0x10: {'yes' if r.get('lists_brightness_0x10') else 'NO'} "
                      f"({r['capabilities_ms']} ms)")
                print(f"  VCP codes: {' '.join(r.get('vcp_codes', []))}")
            else:
                print("  no capabilities string (many monitors still take brightness)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
