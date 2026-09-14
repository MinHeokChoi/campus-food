#!/usr/bin/env python3
"""등록된 장소를 전부 긁어 정적 JSON 을 낸다. 표준 라이브러리만 쓴다.

    python3 run.py              # 전부
    python3 run.py hongik       # 한 곳만

한 장소가 터져도 나머지는 계속한다. 실패한 장소의 파일은 **건드리지 않는다** —
오래된 데이터가 빈 데이터보다 낫다. 시계가 "9/12 갱신" 으로 티를 낸다.

JSON 계약은 garmin/SPEC-학식.md 의 "JSON 계약" 절이 기준이다.
표시 순서까지 여기서 정한다. 워치는 정렬하지 않는다.
"""
import datetime as dt
import importlib
import json
import os
import sys

from adapters import REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
KST = dt.timezone(dt.timedelta(hours=9))

# 이미 설치된 시계가 보고 있는 경로. 장소별 파일(menu/<id>.json)은 1단계에서 붙인다.
# 이 두 파일을 옮기면 설치된 앱이 메뉴를 못 받는다.
LEGACY_VENUE = "hongik"
LEGACY_OUT = os.path.join(HERE, "menu.json")
LEGACY_OUT_MIN = os.path.join(HERE, "menu.min.json")

MAX_DAYS = 4


def calendar_for(venue):
    return importlib.import_module("calendars." + venue["calendar"])


def build(mod, now):
    """어댑터를 돌려 문서 하나를 만든다. 실패하면 예외가 그대로 올라간다."""
    today = now.date()
    days = mod.fetch(today)
    cal = calendar_for(mod.VENUE)
    return {
        "updated": now.replace(microsecond=0).isoformat(),
        "days": [{"date": d.date, "meals": [m.as_json() for m in d.meals]}
                 for d in days[:MAX_DAYS]],
        "holidays": cal.upcoming(today),
    }


def minify(doc):
    return {
        "u": doc["updated"],
        "h": doc["holidays"],
        "d": [{"t": d["date"],
               "m": [{"s": m["slot"], "p": m["place"], "e": m["end"], "i": m["items"]}
                     for m in d["meals"]]} for d in doc["days"]],
    }


def write(path, data, indent):
    with open(path, "w", encoding="utf-8") as f:
        if indent is None:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def main(argv):
    wanted = argv[1:] or sorted(REGISTRY)
    unknown = [v for v in wanted if v not in REGISTRY]
    if unknown:
        print("모르는 장소: " + ", ".join(unknown), file=sys.stderr)
        return 2

    now = dt.datetime.now(KST)
    failed = []
    for vid in wanted:
        mod = REGISTRY[vid]
        try:
            doc = build(mod, now)
        except Exception as e:  # noqa: BLE001  한 곳이 터져도 나머지는 계속한다
            print(f"{vid}: {e}", file=sys.stderr)
            failed.append(vid)
            continue

        if vid == LEGACY_VENUE:
            write(LEGACY_OUT, doc, indent=1)
            write(LEGACY_OUT_MIN, minify(doc), indent=None)
        print(f"{vid}: {len(doc['days'])} day(s) {[d['date'] for d in doc['days']]}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
