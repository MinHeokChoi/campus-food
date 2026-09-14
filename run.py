#!/usr/bin/env python3
"""등록된 장소를 전부 긁어 정적 JSON 을 낸다. 표준 라이브러리만 쓴다.

    python3 run.py              # 전부
    python3 run.py hongik snu   # 몇 곳만

한 장소가 터져도 나머지는 계속한다. 실패한 장소의 파일은 **건드리지 않는다** —
오래된 데이터가 빈 데이터보다 낫다. 시계가 "9/12 갱신" 으로 티를 낸다.

사이트 개편은 예외가 아니라 **빈 배열**로 온다. 그래서 받아 온 결과가 말이 되는지
check() 로 본 다음에야 파일을 쓴다.

내는 것:
  venues.json          장소 목록 (워치의 선택 화면이 읽는다)
  menu/<id>.json       장소별 메뉴
  status.json          장소별 성공/실패. 연속 실패가 쌓이면 워크플로가 이슈를 연다
  menu.json            홍익대 전용 옛 경로. v1.x 가 설치된 시계가 이걸 본다 — 옮기면 안 된다
  menu.min.json        같은 내용, 키를 줄인 것
"""
import datetime as dt
import importlib
import json
import os
import sys

from adapters import REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
KST = dt.timezone(dt.timedelta(hours=9))

MENU_DIR = os.path.join(HERE, "menu")
VENUES_OUT = os.path.join(HERE, "venues.json")
STATUS_OUT = os.path.join(HERE, "status.json")

# v1.x 가 설치된 시계가 상수로 들고 있는 경로. 홍익대만 여기로도 낸다.
LEGACY_VENUE = "hongik"
LEGACY_OUT = os.path.join(HERE, "menu.json")
LEGACY_OUT_MIN = os.path.join(HERE, "menu.min.json")

MAX_DAYS = 4
MAX_ITEM_LEN = 40          # 이보다 길면 메뉴가 아니라 안내문이 섞여 들어온 것이다
FAIL_STREAK_ALERT = 3      # 연속 이 횟수만큼 실패하면 이슈를 연다


def calendar_for(venue):
    return importlib.import_module("calendars." + venue["calendar"])


class BadData(Exception):
    """받아 오긴 했는데 말이 안 된다. 어댑터 실패와 같이 취급한다."""


def check(venue, days, today):
    """사이트가 개편되면 대개 예외가 아니라 빈 값·이상한 값으로 온다. 여기서 잡는다."""
    if not days:
        raise BadData("날이 하나도 없다")
    declared = {p["id"] for p in venue["places"]}
    seen = set()
    for d in days:
        if d.date in seen:
            raise BadData("같은 날짜가 두 번: " + d.date)
        seen.add(d.date)
        if d.date < today.isoformat():
            raise BadData("지난 날짜: " + d.date)
        if not d.meals:
            raise BadData(d.date + " 에 끼니가 없다")
        for m in d.meals:
            if not m.slot or not m.place:
                raise BadData(d.date + " 끼니 이름이 비었다")
            if m.place_id not in declared:
                raise BadData("선언 안 된 식당: " + str(m.place_id))
            if not m.items:
                raise BadData(d.date + " " + m.slot + " 에 메뉴가 없다")
            for i in m.items:
                if not i or len(i) > MAX_ITEM_LEN:
                    raise BadData("메뉴 항목이 이상하다: " + repr(i[:50]))
            if m.end is not None and (len(m.end) != 5 or m.end[2] != ":"):
                raise BadData("마감시각 형식: " + repr(m.end))
    if sorted(seen) != [d.date for d in days]:
        raise BadData("날짜가 오름차순이 아니다")


def build(mod, now):
    """어댑터를 돌려 문서 하나를 만든다. 실패하면 예외가 그대로 올라간다."""
    today = now.date()
    venue = mod.VENUE
    days = mod.fetch(today)[:MAX_DAYS]
    check(venue, days, today)
    cal = calendar_for(venue)
    return {
        "venue": venue["id"],
        "updated": now.replace(microsecond=0).isoformat(),
        "days": [{"date": d.date,
                  "meals": [{"slot": m.slot, "place": m.place, "placeId": m.place_id,
                             "end": m.end, "items": list(m.items)} for m in d.meals]}
                 for d in days],
        "holidays": cal.upcoming(today),
    }


def legacy(doc):
    """v1.x 시계가 아는 모양. placeId 와 venue 가 없던 때의 것이다."""
    return {
        "updated": doc["updated"],
        "days": [{"date": d["date"],
                  "meals": [{"slot": m["slot"], "place": m["place"],
                             "end": m["end"], "items": m["items"]} for m in d["meals"]]}
                 for d in doc["days"]],
        "holidays": doc["holidays"],
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if indent is None:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def load_status():
    try:
        with open(STATUS_OUT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"venues": {}}


def write_venues():
    """워치의 선택 화면이 읽는 목록. 정렬은 여기서 정한다 — 워치는 받은 순서대로 그린다.

    나라 > 지역 > 이름 순. 한글 음절은 유니코드 코드포인트 순이 곧 가나다 순이다.
    """
    venues = []
    for mod in REGISTRY.values():
        v = mod.VENUE
        venues.append({"id": v["id"], "name": v["name"], "region": v["region"],
                       "country": v["country"], "tz": v["tz"],
                       "places": [dict(p) for p in v["places"]]})
    venues.sort(key=lambda v: (v["country"], v["region"], v["name"]))
    write(VENUES_OUT, {"venues": venues}, indent=1)


def main(argv):
    wanted = argv[1:] or sorted(REGISTRY)
    unknown = [v for v in wanted if v not in REGISTRY]
    if unknown:
        print("모르는 장소: " + ", ".join(unknown), file=sys.stderr)
        return 2

    now = dt.datetime.now(KST)
    stamp = now.replace(microsecond=0).isoformat()
    status = load_status()
    failed = []

    for vid in wanted:
        mod = REGISTRY[vid]
        prev = status["venues"].get(vid, {})
        try:
            doc = build(mod, now)
        except Exception as e:  # noqa: BLE001  한 곳이 터져도 나머지는 계속한다
            streak = prev.get("failStreak", 0) + 1
            status["venues"][vid] = {
                "ok": False,
                "error": "%s: %s" % (type(e).__name__, e),
                "failStreak": streak,
                "lastSuccess": prev.get("lastSuccess"),
                "checkedAt": stamp,
            }
            print("%s: %s (연속 %d회)" % (vid, e, streak), file=sys.stderr)
            failed.append(vid)
            continue

        write(os.path.join(MENU_DIR, vid + ".json"), doc, indent=1)
        if vid == LEGACY_VENUE:
            write(LEGACY_OUT, legacy(doc), indent=1)
            write(LEGACY_OUT_MIN, minify(legacy(doc)), indent=None)
        status["venues"][vid] = {
            "ok": True, "error": None, "failStreak": 0,
            "lastSuccess": stamp, "checkedAt": stamp,
            "days": [d["date"] for d in doc["days"]],
        }
        print("%s: %d day(s) %s" % (vid, len(doc["days"]), [d["date"] for d in doc["days"]]))

    write_venues()
    status["updated"] = stamp
    write(STATUS_OUT, status, indent=1)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
